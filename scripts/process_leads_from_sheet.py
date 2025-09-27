import json
import os
from datetime import datetime, timezone
from typing import Dict, List

import structlog
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from backend.models.database_models import (
    DatabaseConnection,
    LeadRepository,
    SessionRepository,
    MessageRepository,
    Session,
    Message,
)
from backend.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger(__name__)


def _load_sheets_credentials() -> Credentials:
    # Primeiro tenta carregar do JSON inline
    raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if raw:
        try:
            info = json.loads(raw)
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            return Credentials.from_service_account_info(info, scopes=scopes)
        except Exception:
            pass
    
    # Se não funcionar, tenta carregar do arquivo
    json_file = "google_credentials.json"
    if os.path.exists(json_file):
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        return Credentials.from_service_account_file(json_file, scopes=scopes)
    
    raise RuntimeError("Credenciais do Google não encontradas. Configure GOOGLE_SHEETS_CREDENTIALS_JSON ou google_credentials.json")


def _parse_range_config(range_config: str) -> (str, int):
    if "!" in range_config:
        sheet_name, cell_range = range_config.split("!", 1)
    else:
        sheet_name, cell_range = range_config, "A1"
    start_cell = cell_range.split(":")[0]
    row_digits = "".join(ch for ch in start_cell if ch.isdigit())
    start_row = int(row_digits) if row_digits else 1
    return sheet_name, start_row


def _expand_row(row: List[str], size: int) -> List[str]:
    if len(row) < size:
        row = row + [""] * (size - len(row))
    return row


def _update_row(sheet_api, spreadsheet_id: str, sheet_name: str, header: List[str], original_row: List[str], row_number: int, updates: Dict[str, str]):
    row_values = _expand_row(list(original_row), len(header))
    for key, value in updates.items():
        if key in header:
            idx = header.index(key)
            row_values[idx] = value
    end_col = chr(65 + len(header) - 1)
    range_name = f"{sheet_name}!A{row_number}:{end_col}{row_number}"
    sheet_api.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body={'values': [row_values]}
    ).execute()


def _first_name(nome: str) -> str:
    if not nome:
        return ""
    return str(nome).strip().split()[0].capitalize()


def process_leads_from_sheet():
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID não configurado")

    range_config = os.getenv("GOOGLE_SHEETS_LEADS_RANGE", "Leads!A1:H")

    creds = _load_sheets_credentials()
    service = build("sheets", "v4", credentials=creds)
    sheet_api = service.spreadsheets()

    response = sheet_api.values().get(spreadsheetId=spreadsheet_id, range=range_config).execute()
    values = response.get("values", [])

    if not values or len(values) == 1:
        logger.info("Nenhum lead novo encontrado na planilha", range=range_config)
        return

    header = values[0]
    sheet_name, start_row = _parse_range_config(range_config)

    db_conn = DatabaseConnection()
    lead_repo = LeadRepository(db_conn)
    session_repo = SessionRepository(db_conn)
    message_repo = MessageRepository(db_conn)
    whatsapp = WhatsAppService()

    processed = 0
    skipped = 0

    for offset, row in enumerate(values[1:], start=1):
        row_number = start_row + offset
        row_map: Dict[str, str] = {header[idx]: row[idx] if idx < len(row) else "" for idx in range(len(header))}

        status = (row_map.get("status") or "").strip().lower()
        if status not in ("", "novo", "new"):
            skipped += 1
            continue

        telefone = (row_map.get("telefone") or row_map.get("phone") or "").strip()
        if not telefone:
            _update_row(sheet_api, spreadsheet_id, sheet_name, header, row, row_number, {
                "status": "erro",
                "observacao": "telefone ausente"
            })
            continue

        canal = (row_map.get("canal") or "whatsapp").strip().lower()
        nome = row_map.get("nome") or row_map.get("name") or ""
        contexto = row_map.get("contexto") or row_map.get("notes") or ""
        lead_id = row_map.get("lead_id") or row_map.get("id") or ""

        whatsapp_limpo = whatsapp.normalizar_telefone(telefone)

        lead_data = None
        if lead_id:
            resultado = db_conn.get_client().table('leads').select('*').eq('id', lead_id).execute()
            if resultado.data:
                lead_data = resultado.data[0]
        if not lead_data:
            lead_data = lead_repo.get_lead_by_phone(whatsapp_limpo)
            if lead_data:
                lead_id = lead_data['id']

        if not lead_data:
            _update_row(sheet_api, spreadsheet_id, sheet_name, header, row, row_number, {
                "status": "erro",
                "observacao": "lead não encontrado"
            })
            continue

        sessao_ativa = session_repo.get_active_session(lead_id)
        if sessao_ativa:
            _update_row(sheet_api, spreadsheet_id, sheet_name, header, row, row_number, {
                "status": "ativo",
                "observacao": f"Sessão {sessao_ativa['id']} já ativa"
            })
            continue

        mensagem = whatsapp.montar_mensagem_inicial_personalizada(
            canal=canal,
            nome=_first_name(nome or lead_data.get('nome', '')),
            contexto_extra=contexto
        )

        envio = whatsapp.enviar_mensagem(whatsapp_limpo, mensagem)
        if not envio.get('success'):
            _update_row(sheet_api, spreadsheet_id, sheet_name, header, row, row_number, {
                "status": "erro_envio",
                "observacao": envio.get('error', 'falha ao enviar mensagem')
            })
            continue

        contexto_sessao = lead_data.get('contexto') or {}
        if isinstance(contexto_sessao, str):
            try:
                contexto_sessao = json.loads(contexto_sessao)
            except Exception:
                contexto_sessao = {}
        contexto_sessao.update({
            'canal_origem': canal,
            'descricao_origem': contexto,
            'primeiro_contato_em': datetime.now(timezone.utc).isoformat()
        })

        nova_sessao = Session(
            lead_id=lead_id,
            estado='saudacao',
            contexto=contexto_sessao,
            ativa=True
        )
        sessao_data = session_repo.create_session(nova_sessao)
        session_id = sessao_data['id'] if sessao_data else None

        if session_id:
            metadata = {
                'source': 'sheet_initial',
                'message_id': envio.get('message_id'),
                'canal': canal
            }
            message_repo.create_message(Message(
                session_id=session_id,
                lead_id=lead_id,
                conteudo=mensagem,
                tipo='enviada',
                metadata=metadata
            ))
            session_repo.update_session(session_id, {
                'contexto': contexto_sessao,
                'estado': 'saudacao'
            })

        _update_row(sheet_api, spreadsheet_id, sheet_name, header, row, row_number, {
            'status': 'contatado',
            'mensagem_inicial': mensagem,
            'observacao': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        })

        processed += 1

    logger.info(
        "Processamento concluído",
        processed=processed,
        skipped=skipped,
        range=range_config
    )


if __name__ == '__main__':
    process_leads_from_sheet()
