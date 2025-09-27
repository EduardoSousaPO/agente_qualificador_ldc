"""Flask backend exposing webhook endpoints for the qualification bot."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict

from cachetools import TTLCache
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
import structlog
from pydantic import BaseModel, ValidationError

from backend.models.database_models import (
    DatabaseConnection,
    Lead,
    LeadRepository,
    SessionRepository,
    MessageRepository,
    QualificacaoRepository,
    SystemLogRepository,
    ReuniaoRepository,
)
from backend.services.google_sheets_service import GoogleSheetsService
from backend.services.leads_watcher import LeadsWatcher
from backend.services.messaging_service import MessagingService
from backend.services.metrics_service import metrics_service
from backend.services.qualification_service import QualificationService
from backend.services.whatsapp_service import WhatsAppService

load_dotenv()
logger = structlog.get_logger()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

INCOMING_DEDUP = TTLCache(maxsize=10000, ttl=120)


class ParsedWahaPayload(BaseModel):
    telefone: str
    nome: str
    mensagem: str
    message_id: str
    is_from_me: bool = False


def _parse_waha_payload(data: Dict[str, Any]) -> ParsedWahaPayload:
    payload = data.get('payload', data)
    if not payload or not isinstance(payload, dict):
        raise ValidationError('payload ausente', ParsedWahaPayload)

    telefone_raw = payload.get('from')
    if not telefone_raw:
        raise ValidationError('campo from ausente', ParsedWahaPayload)
    telefone = ''.join(filter(str.isdigit, str(telefone_raw)))
    if not telefone:
        raise ValidationError('telefone inválido', ParsedWahaPayload)

    mensagem = payload.get('body', '')
    message_id = payload.get('id', f"{telefone}_{int(datetime.utcnow().timestamp())}")
    is_from_me = payload.get('fromMe', False)

    nome = 'tudo bem'
    if payload.get('_data') and isinstance(payload['_data'], dict):
        for field in ('notifyName', 'pushname', 'verifiedName', 'name'):
            value = payload['_data'].get(field)
            if value:
                nome = str(value).strip().split()[0]
                break
    if not nome and payload.get('contact'):
        contact = payload['contact']
        if isinstance(contact, dict):
            for field in ('name', 'pushname', 'notifyName'):
                value = contact.get(field)
                if value:
                    nome = str(value).strip().split()[0]
                    break
    nome = nome or 'tudo bem'

    return ParsedWahaPayload(
        telefone=telefone,
        nome=nome,
        mensagem=str(mensagem or ''),
        message_id=str(message_id),
        is_from_me=bool(is_from_me),
    )


def _is_duplicate_incoming(telefone: str, message_id: str) -> bool:
    cache_key = f"{telefone}:{message_id}"
    if cache_key in INCOMING_DEDUP:
        return True
    INCOMING_DEDUP[cache_key] = True
    return False


# Initialise dependencies ----------------------------------------------------
try:
    database = DatabaseConnection()
    lead_repo = LeadRepository(database)
    session_repo = SessionRepository(database)
    message_repo = MessageRepository(database)
    qualificacao_repo = QualificacaoRepository(database)
    reuniao_repo = ReuniaoRepository(database)
    system_log_repo = SystemLogRepository(database)  # pylint: disable=unused-variable

    whatsapp_service = WhatsAppService()
    messaging_service = MessagingService(whatsapp_service, message_repo)
    qualification_service = QualificationService(
        lead_repo=lead_repo,
        session_repo=session_repo,
        message_repo=message_repo,
        qualificacao_repo=qualificacao_repo,
        reuniao_repo=reuniao_repo,
        messaging_service=messaging_service,
        whatsapp_service=whatsapp_service,
    )
    sheets_service = GoogleSheetsService()
    leads_watcher = LeadsWatcher(
        sheets_service=sheets_service,
        lead_repo=lead_repo,
        qualification_service=qualification_service,
        poll_interval_seconds=int(os.getenv('LEADS_WATCHER_INTERVAL', '60')),
    )
    leads_watcher.start()
    logger.info("Application services initialised")
except Exception as exc:  # pylint: disable=broad-except
    logger.exception("Failed to initialise services", error=str(exc))
    raise


# Health check endpoint movido para o final com métricas


@app.route('/webhook', methods=['GET', 'POST'])
def webhook_whatsapp():
    if request.method == 'GET':
        return jsonify({'status': 'webhook_online'}), 200

    try:
        payload = request.get_json(silent=True) or {}
        parsed = _parse_waha_payload(payload)
    except ValidationError as exc:
        logger.error("Invalid webhook payload", error=str(exc))
        return jsonify({'status': 'invalid_payload'}), 200

    if parsed.is_from_me:
        return jsonify({'status': 'ignored_self_message'}), 200

    if _is_duplicate_incoming(parsed.telefone, parsed.message_id):
        return jsonify({'status': 'duplicate_ignored'}), 200

    try:
        telefone_normalizado = whatsapp_service.normalizar_telefone(parsed.telefone)
    except Exception:  # pylint: disable=broad-except
        telefone_normalizado = parsed.telefone

    lead = lead_repo.get_lead_by_phone(telefone_normalizado)
    if not lead:
        novo_lead = Lead(nome=parsed.nome, telefone=telefone_normalizado, canal='whatsapp')
        lead = lead_repo.create_lead(novo_lead)
        if not lead:
            logger.error("Could not create lead for incoming message", telefone=telefone_normalizado)
            return jsonify({'status': 'lead_creation_failed'}), 200

    result = qualification_service.processar_mensagem_recebida(
        lead_id=lead['id'],
        telefone=telefone_normalizado,
        mensagem=parsed.mensagem,
        nome=parsed.nome,
    )

    return jsonify({'status': 'processed', 'resultado': result}), 200


@app.route('/leads/run-watcher', methods=['POST'])
def run_watcher_once():
    try:
        leads_watcher.process_once()
        return jsonify({'status': 'ok'}), 200
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Watcher execution failed", error=str(exc))
        return jsonify({'status': 'error', 'error': str(exc)}), 500


@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Endpoint para obter métricas do sistema"""
    try:
        summary = metrics_service.get_metrics_summary()
        return jsonify(summary), 200
    except Exception as exc:
        logger.exception("Erro ao obter métricas", error=str(exc))
        return jsonify({'status': 'error', 'error': str(exc)}), 500


@app.route('/metrics/detailed', methods=['GET'])
def get_detailed_metrics():
    """Endpoint para obter métricas detalhadas com histórico"""
    try:
        detailed = metrics_service.get_detailed_metrics()
        return jsonify(detailed), 200
    except Exception as exc:
        logger.exception("Erro ao obter métricas detalhadas", error=str(exc))
        return jsonify({'status': 'error', 'error': str(exc)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de health check com métricas básicas"""
    try:
        summary = metrics_service.get_metrics_summary()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'total_messages': summary['totals']['messages'].get('total_sent', 0),
                'message_success_rate': summary['rates']['message_success_rate'],
                'total_qualifications': summary['totals']['qualifications'].get('total_qualifications', 0),
                'qualification_rate': summary['rates']['qualification_rate']
            }
        }), 200
    except Exception as exc:
        logger.exception("Erro no health check", error=str(exc))
        return jsonify({'status': 'unhealthy', 'error': str(exc)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')))
