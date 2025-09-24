"""
Flask Backend - Agente Qualificador de Leads via WhatsApp
Sistema completo de qualificação automática com IA
"""
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import logging
import structlog
from cachetools import TTLCache
from pydantic import BaseModel, ValidationError

# Imports dos serviços
from backend.models.database_models import (
    DatabaseConnection, Lead, Session, Message, Qualificacao, SystemLog,
    LeadRepository, SessionRepository, MessageRepository, QualificacaoRepository, SystemLogRepository
)
from backend.services.scoring_service import ScoringService
from backend.services.whatsapp_service import WhatsAppService
from backend.services.qualification_service import QualificationService
from backend.services.lead_detector import LeadDetectorService
from backend.services.google_sheets_service import GoogleSheetsService
# NOVO: Importar o serviço do agente LangChain (COMENTADO TEMPORARIAMENTE)
# from backend.services.langchain_agent_service import LangchainAgentService
import time

# 🔧 HOTFIX: Cache TTL robusto para deduplicação de mensagens WAHA
DEDUP_CACHE = TTLCache(maxsize=10000, ttl=60)  # 10k mensagens, TTL 60s

class ParsedWahaPayload(BaseModel):
    """Define um contrato de dados limpo para informações extraídas do webhook do WAHA."""
    telefone: str
    nome: str
    mensagem: str
    message_id: str
    is_from_me: bool

def _parse_waha_payload(data: dict) -> ParsedWahaPayload:
    """
    Recebe o payload bruto do WAHA, extrai, limpa e valida os dados essenciais.
    Esta função é o "portão de entrada" de dados, garantindo que o resto do sistema
    receba apenas informações limpas e estruturadas.
    """
    payload = data.get('payload', data)
    
    if not payload or not isinstance(payload, dict):
        raise ValueError("Payload do webhook está vazio ou em formato inválido.")

    # 1. Extrair e validar 'from' (telefone)
    telefone_raw = payload.get('from')
    if not telefone_raw:
        raise ValueError("Campo 'from' (telefone) ausente no payload.")
    
    telefone = ''.join(filter(str.isdigit, str(telefone_raw).split('@')[0]))
    if not telefone:
        raise ValueError(f"Não foi possível extrair um número de telefone válido de '{telefone_raw}'.")

    # 2. Extrair e validar 'body' (mensagem)
    mensagem = payload.get('body')
    if mensagem is None: # Permite mensagens vazias, mas o campo deve existir
        raise ValueError("Campo 'body' (mensagem) ausente no payload.")

    # 3. Extrair 'id' da mensagem para deduplicação
    message_id = payload.get('id', f"{telefone}_{int(time.time())}")

    # 4. Verificar se a mensagem é do próprio agente
    is_from_me = payload.get('fromMe', False)

    # 5. Extrair 'nome' com múltiplas estratégias de fallback
    nome_bruto = None
    if payload.get('_data') and isinstance(payload['_data'], dict):
        for field in ['notifyName', 'pushname', 'verifiedName', 'name']:
            if payload['_data'].get(field):
                nome_bruto = payload['_data'][field]
                break
    
    if not nome_bruto and payload.get('contact') and isinstance(payload['contact'], dict):
        for field in ['name', 'pushname', 'notifyName']:
            if payload['contact'].get(field):
                nome_bruto = payload['contact'][field]
                break

    if not nome_bruto:
        nome_bruto = payload.get('pushName') # Campo comum no root do payload

    # 6. Limpar e definir fallback para o nome
    if nome_bruto and str(nome_bruto).strip():
        nome_final = str(nome_bruto).strip().split()[0].capitalize()
    else:
        # Fallback CRÍTICO: se não houver nome, usa um placeholder que a IA possa entender.
        nome_final = "Amigo(a)"

    return ParsedWahaPayload(
        telefone=telefone,
        nome=nome_final,
        mensagem=mensagem,
        message_id=message_id,
        is_from_me=is_from_me
    )

def cleanup_message_cache():
    """Cache TTL automático - função mantida por compatibilidade"""
    # Cache TTL gerencia automaticamente a expiração
    pass

def is_duplicate_message(message_id, telefone):
    """🔧 HOTFIX: Verifica deduplicação robusta com cache TTL"""
    # Criar chave única para telefone + message_id
    cache_key = f"{telefone}:{message_id}"
    
    # Verificar se já foi processada
    if cache_key in DEDUP_CACHE:
        return True
    
    # Marcar como processada (TTL automático)
    DEDUP_CACHE[cache_key] = True
    return False

# As funções extrair_nome_lead e limpar_telefone_waha foram consolidadas em _parse_waha_payload
# e podem ser removidas em uma limpeza futura para manter o código mais limpo.
def extrair_nome_lead(payload):
    """[DEPRECATED] Extrai nome real do lead do payload WhatsApp WAHA com estrutura real"""
    nome_real = None
    
    # Log detalhado do payload para debug
    logger.info("Tentando extrair nome do payload", 
               payload_keys=list(payload.keys()) if payload else [],
               payload_sample={k: str(v)[:100] for k, v in payload.items() if k in ['_data', 'contact', 'vCards']} if payload else {})
    
    # Estratégia 1: Buscar em _data (dados estendidos do WAHA)
    if payload.get('_data'):
        data_obj = payload['_data']
        if isinstance(data_obj, dict):
            # Campos possíveis em _data
            nome_fields = ['notifyName', 'pushname', 'verifiedName', 'name']
            for field in nome_fields:
                if data_obj.get(field) and str(data_obj[field]).strip():
                    nome_real = str(data_obj[field]).strip()
                    logger.info("Nome encontrado em _data", field=field, nome=nome_real)
                    break
    
    # Estratégia 2: Buscar em vCards (cartões de contato)
    if not nome_real and payload.get('vCards'):
        vcards = payload['vCards']
        if isinstance(vcards, list) and len(vcards) > 0:
            vcard = vcards[0]
            if isinstance(vcard, dict) and vcard.get('displayName'):
                nome_real = str(vcard['displayName']).strip()
                logger.info("Nome encontrado em vCard", nome=nome_real)
    
    # Estratégia 3: Buscar em contact (estrutura de contato)
    if not nome_real and payload.get('contact'):
        contact = payload['contact']
        if isinstance(contact, dict):
            nome_fields = ['name', 'pushname', 'notifyName', 'verifiedName']
            for field in nome_fields:
                if contact.get(field) and str(contact[field]).strip():
                    nome_real = str(contact[field]).strip()
                    logger.info("Nome encontrado em contact", field=field, nome=nome_real)
                    break
    
    # Estratégia 4: Campos diretos (fallback)
    if not nome_real:
        nome_fields = ['notifyName', 'pushName', 'fromName', 'name']
        for field in nome_fields:
            if payload.get(field) and str(payload[field]).strip():
                nome_real = str(payload[field]).strip()
                logger.info("Nome encontrado diretamente", field=field, nome=nome_real)
                break
    
    if nome_real:
        # Usar apenas primeiro nome para personalização
        primeiro_nome = nome_real.split()[0] if nome_real else nome_real
        # Capitalizar primeira letra
        nome_final = primeiro_nome.capitalize() if primeiro_nome else None
        
        logger.info("Nome processado com sucesso", 
                   nome_completo=nome_real,
                   primeiro_nome=nome_final)
        return nome_final
    
    # Log detalhado se nenhum nome foi encontrado
    logger.warning("Nenhum nome encontrado no payload", 
                  payload_keys=list(payload.keys()) if payload else [],
                  _data_keys=list(payload.get('_data', {}).keys()) if payload.get('_data') else [],
                  contact_keys=list(payload.get('contact', {}).keys()) if payload.get('contact') else [],
                  vcards_count=len(payload.get('vCards', [])) if payload.get('vCards') else 0)
    
    return None

def limpar_telefone_waha(telefone_raw):
    """Limpa telefone do formato WAHA (ex: 555124150039@c.us) para apenas números"""
    if not telefone_raw:
        logger.error("Telefone raw vazio", telefone_raw=repr(telefone_raw))
        return None
    
    try:
        # Remove @c.us e outros sufixos WhatsApp
        telefone_limpo = str(telefone_raw).split('@')[0]
        
        # Remove caracteres não numéricos
        telefone_numerico = ''.join(filter(str.isdigit, telefone_limpo))
        
        if not telefone_numerico:
            logger.error("Telefone sem números após limpeza", 
                        telefone_raw=telefone_raw,
                        telefone_limpo=telefone_limpo)
            return None
            
        logger.info("Telefone limpo com sucesso", 
                   telefone_raw=telefone_raw,
                   telefone_limpo=telefone_numerico)
        
        return telefone_numerico
    except Exception as e:
        logger.error("Erro ao limpar telefone", 
                    telefone_raw=repr(telefone_raw),
                    error=str(e))
        return None

# Configuração de logging estruturado
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Carregar variáveis de ambiente
load_dotenv()

# Inicializar Flask
app = Flask(__name__)
CORS(app)

# Configurações
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# Inicializar serviços
try:
    db = DatabaseConnection()
    lead_repo = LeadRepository(db)
    session_repo = SessionRepository(db)
    message_repo = MessageRepository(db)
    qualificacao_repo = QualificacaoRepository(db)
    log_repo = SystemLogRepository(db)
    
    scoring_service = ScoringService()
    whatsapp_service = WhatsAppService()
    qualification_service = QualificationService(
        session_repo, message_repo, qualificacao_repo, scoring_service, whatsapp_service
    )
    google_sheets_service = GoogleSheetsService()
    lead_detector = LeadDetectorService(lead_repo, whatsapp_service, qualification_service)
    # NOVO: Inicializar o serviço LangChain (COMENTADO TEMPORARIAMENTE)
    # langchain_agent_service = LangchainAgentService()
    
    logger.info("Serviços inicializados com sucesso")
except Exception as e:
    logger.error("Erro ao inicializar serviços", error=str(e))
    raise


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de health check"""
    try:
        # Testar conexão com banco
        db.get_client().table('leads').select('id').limit(1).execute()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': 'connected',
                'whatsapp': 'configured',
                'scoring': 'ready',
                'qualification': 'ready'
            }
        }), 200
    except Exception as e:
        logger.error("Health check falhou", error=str(e))
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/webhook', methods=['GET', 'POST'])
def webhook_whatsapp():
    """Webhook para receber mensagens do WAHA, agora com lógica de parsing e validação centralizada."""
    if request.method == 'GET':
        logger.info("Teste de webhook GET recebido com sucesso.")
        return jsonify({'status': 'webhook_online'}), 200

    try:
        data = request.get_json()
        if not data:
            logger.warning("Webhook recebeu requisição sem corpo JSON.")
            return jsonify({'status': 'empty_request'}), 200

        logger.info("=== WEBHOOK RECEBIDO ===", raw_data=data)
        
        event_type = data.get('event')
        if event_type == 'session.status':
            return handle_session_status(data.get('payload', data))
        
        valid_events = ['message', 'message.any']
        if event_type not in valid_events:
            logger.info("Evento ignorado (não é uma mensagem)", event_type=event_type)
            return jsonify({'status': 'ignored_event'}), 200

        # Ponto de entrada ÚNICO para parsing e validação
        parsed_data = _parse_waha_payload(data)

        if parsed_data.is_from_me:
            logger.info("Mensagem própria ignorada", message_id=parsed_data.message_id)
            return jsonify({'status': 'own_message_ignored'}), 200
        
        if is_duplicate_message(parsed_data.message_id, parsed_data.telefone):
            logger.info("Mensagem duplicada ignorada", message_id=parsed_data.message_id)
            return jsonify({'status': 'duplicate_message_ignored'}), 200

        # A partir daqui, trabalhamos apenas com dados limpos e garantidos
        telefone = parsed_data.telefone
        nome_contato = parsed_data.nome
        mensagem = parsed_data.mensagem

        # Buscar ou criar lead
        lead_data = lead_repo.get_lead_by_phone(telefone)
        is_new_lead = not lead_data

        if is_new_lead:
            logger.info("Criando novo lead", telefone=telefone, nome_contato=nome_contato)
            novo_lead = Lead(nome=nome_contato, telefone=telefone, canal='whatsapp', status='novo')
            lead_data = lead_repo.create_lead(novo_lead)
            if not lead_data:
                logger.error("Falha ao criar novo lead", telefone=telefone)
                return jsonify({'status': 'error_creating_lead'}), 200

        logger.info("Iniciando processamento da mensagem", lead_id=lead_data['id'], is_new_lead=is_new_lead)

        # NOVO: Lógica de Roteamento - Usar LangChain para novos leads (COMENTADO TEMPORARIAMENTE)
        # if is_new_lead:
        #     logger.info("Roteando novo lead para o LangchainAgentService", lead_id=lead_data['id'])
        #     # O ID da sessão pode ser o próprio ID do lead para simplicidade inicial
        #     session_id = lead_data['id']
        #     resposta_langchain = langchain_agent_service.processar_mensagem(
        #         session_id=session_id,
        #         nome_lead=nome_contato,
        #         mensagem=mensagem
        #     )
        #     # Enviar a resposta via WhatsApp
        #     whatsapp_service.enviar_mensagem(telefone, resposta_langchain)
            
        #     # Registrar a mensagem enviada
        #     message_repo.create_message(Message(
        #         lead_id=lead_data['id'],
        #         session_id=session_id, # Usar o mesmo ID
        #         conteudo=resposta_langchain,
        #         tipo='enviada',
        #         metadata={'source': 'langchain_poc'}
        #     ))

        #     resultado = {'success': True, 'resposta': resposta_langchain, 'source': 'langchain'}
        # else:
        #     # Lógica antiga para leads existentes
        resultado = qualification_service.processar_mensagem_recebida(
            lead_data['id'], mensagem
        )
        
        if resultado.get('success', False):
            logger.info("Mensagem processada com sucesso", lead_id=lead_data['id'], resultado=resultado)
        else:
            logger.error("Erro ao processar mensagem", lead_id=lead_data['id'], error=resultado.get('error'))
        
        return jsonify({'status': 'processed', 'result': resultado}), 200

    except (ValidationError, ValueError) as e:
        logger.warning("Erro de validação do payload do webhook", error=str(e), request_data=request.data[:500].decode('utf-8', errors='ignore'))
        return jsonify({'status': 'validation_error', 'details': str(e)}), 200
        
    except Exception as e:
        logger.exception("Erro crítico no webhook", error=str(e))
        return jsonify({'status': 'internal_error_handled'}), 200


@app.route('/leads', methods=['GET'])
def listar_leads():
    """Lista todos os leads"""
    try:
        # Buscar leads com paginação
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        status = request.args.get('status')
        
        # Query base
        query = db.get_client().table('leads').select('*')
        
        # Filtrar por status se especificado
        if status:
            query = query.eq('status', status)
        
        # Aplicar paginação e ordenação
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        
        return jsonify({
            'leads': result.data,
            'page': page,
            'limit': limit,
            'total': len(result.data)
        }), 200
        
    except Exception as e:
        logger.error("Erro ao listar leads", error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/leads/<lead_id>', methods=['GET'])
def obter_lead(lead_id):
    """Obtém detalhes de um lead específico"""
    try:
        # Buscar lead
        lead_result = db.get_client().table('leads').select('*').eq('id', lead_id).execute()
        
        if not lead_result.data:
            return jsonify({'error': 'Lead não encontrado'}), 404
        
        lead = lead_result.data[0]
        
        # Buscar sessões do lead
        sessions_result = db.get_client().table('sessions').select('*').eq('lead_id', lead_id).execute()
        
        # Buscar qualificação se existir
        qual_result = db.get_client().table('qualificacoes').select('*').eq('lead_id', lead_id).execute()
        
        # Buscar mensagens recentes
        messages_result = db.get_client().table('messages').select('*').eq('lead_id', lead_id).order('created_at', desc=True).limit(20).execute()
        
        return jsonify({
            'lead': lead,
            'sessions': sessions_result.data,
            'qualification': qual_result.data[0] if qual_result.data else None,
            'recent_messages': messages_result.data
        }), 200
        
    except Exception as e:
        logger.error("Erro ao obter lead", lead_id=lead_id, error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/leads/<lead_id>/requalify', methods=['POST'])
def requalificar_lead(lead_id):
    """Reinicia o processo de qualificação de um lead"""
    try:
        # Verificar se lead existe
        lead_result = db.get_client().table('leads').select('*').eq('id', lead_id).execute()
        
        if not lead_result.data:
            return jsonify({'error': 'Lead não encontrado'}), 404
        
        # Desativar sessões existentes
        db.get_client().table('sessions').update({'ativa': False}).eq('lead_id', lead_id).execute()
        
        # Resetar status do lead
        db.get_client().table('leads').update({
            'status': 'novo',
            'score': 0,
            'processado': False
        }).eq('id', lead_id).execute()
        
        # Iniciar nova qualificação
        resultado = qualification_service.iniciar_qualificacao(lead_id)
        
        logger.info("Lead requalificado", lead_id=lead_id, resultado=resultado)
        
        return jsonify({'status': 'requalification_started', 'result': resultado}), 200
        
    except Exception as e:
        logger.error("Erro ao requalificar lead", lead_id=lead_id, error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def estatisticas():
    """Retorna estatísticas do sistema"""
    try:
        # Estatísticas de leads
        total_leads = db.get_client().table('leads').select('id', count='exact').execute().count
        
        leads_qualificados = db.get_client().table('leads').select('id', count='exact').eq('status', 'qualificado').execute().count
        
        leads_nao_qualificados = db.get_client().table('leads').select('id', count='exact').eq('status', 'nao_qualificado').execute().count
        
        leads_em_qualificacao = db.get_client().table('leads').select('id', count='exact').eq('status', 'em_qualificacao').execute().count
        
        # Estatísticas por canal
        canais_result = db.get_client().rpc('get_leads_by_canal').execute()
        
        # Score médio
        score_result = db.get_client().rpc('get_average_score').execute()
        
        # Logs de erro recentes
        error_logs = log_repo.get_error_logs(10)
        
        return jsonify({
            'leads': {
                'total': total_leads,
                'qualificados': leads_qualificados,
                'nao_qualificados': leads_nao_qualificados,
                'em_qualificacao': leads_em_qualificacao,
                'taxa_qualificacao': round((leads_qualificados / total_leads * 100), 2) if total_leads > 0 else 0
            },
            'canais': canais_result.data if canais_result.data else [],
            'score_medio': score_result.data[0] if score_result.data else 0,
            'erros_recentes': len(error_logs),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error("Erro ao obter estatísticas", error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/test-scoring', methods=['POST'])
def testar_scoring():
    """Endpoint para testar o algoritmo de scoring"""
    try:
        data = request.get_json()
        
        required_fields = ['patrimonio', 'objetivo', 'urgencia', 'interesse']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Campos obrigatórios: patrimonio, objetivo, urgencia, interesse'}), 400
        
        # Calcular score
        resultado = scoring_service.calcular_score_completo(
            data['patrimonio'],
            data['objetivo'],
            data['urgencia'],
            data['interesse']
        )
        
        return jsonify({
            'score_result': {
                'patrimonio_pontos': resultado.patrimonio_pontos,
                'objetivo_pontos': resultado.objetivo_pontos,
                'urgencia_pontos': resultado.urgencia_pontos,
                'interesse_pontos': resultado.interesse_pontos,
                'score_total': resultado.score_total,
                'resultado': resultado.resultado,
                'observacoes': resultado.observacoes
            }
        }), 200
        
    except Exception as e:
        logger.error("Erro ao testar scoring", error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/process-new-leads', methods=['POST'])
def processar_novos_leads():
    """Endpoint para processar novos leads da planilha"""
    try:
        # Detectar e processar novos leads
        resultado = lead_detector.detectar_e_processar_novos_leads()
        
        logger.info("Processamento de novos leads concluído", resultado=resultado)
        
        return jsonify({
            'status': 'completed',
            'novos_leads': resultado.get('novos_leads', 0),
            'processados': resultado.get('processados', 0),
            'erros': resultado.get('erros', 0),
            'detalhes': resultado.get('detalhes', [])
        }), 200
        
    except Exception as e:
        logger.error("Erro ao processar novos leads", error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/test-whatsapp', methods=['POST'])
def testar_whatsapp():
    """Testa conexão com WAHA"""
    try:
        # Testar conexão com WAHA
        response = whatsapp_service.test_connection()
        
        return jsonify({
            'status': 'success',
            'waha_connection': response,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error("Erro ao testar WhatsApp", error=str(e))
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/logs', methods=['GET'])
def obter_logs():
    """Obtém logs do sistema"""
    try:
        limit = request.args.get('limit', 100, type=int)
        nivel = request.args.get('nivel', 'INFO')
        
        if nivel == 'ERROR':
            logs = log_repo.get_error_logs(limit)
        else:
            logs = log_repo.get_recent_logs(limit)
        
        return jsonify({
            'logs': logs,
            'total': len(logs),
            'nivel': nivel
        }), 200
        
    except Exception as e:
        logger.error("Erro ao obter logs", error=str(e))
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error("Erro interno do servidor", error=str(error))
    return jsonify({'error': 'Erro interno do servidor'        }), 500

# ========== ENDPOINTS GOOGLE SHEETS ==========

@app.route('/google-sheets/test', methods=['GET'])
def test_google_sheets():
    """Testa conexão com Google Sheets"""
    try:
        resultado = google_sheets_service.testar_conexao()
        return jsonify(resultado), 200 if resultado['success'] else 500
    except Exception as e:
        logger.error("Erro ao testar Google Sheets", error=str(e))
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/google-sheets/detectar-leads', methods=['POST'])
def detectar_leads_sheets():
    """Detecta e processa novos leads da planilha"""
    try:
        resultado = google_sheets_service.detectar_novos_leads()
        
        if resultado['success']:
            logger.info("Detecção de leads concluída", 
                       novos=resultado['novos_leads'],
                       processados=resultado['processados'],
                       erros=resultado['erros'])
        
        return jsonify(resultado), 200 if resultado['success'] else 500
        
    except Exception as e:
        logger.error("Erro ao detectar leads", error=str(e))
        return jsonify({
            'success': False,
            'error': str(e),
            'novos_leads': 0,
            'processados': 0,
            'erros': 1
        }), 500

@app.route('/google-sheets/enviar-crm', methods=['POST'])
def enviar_resultado_crm():
    """Envia resultado de qualificação para CRM"""
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        
        if not lead_id:
            return jsonify({
                'success': False,
                'error': 'lead_id é obrigatório'
            }), 400
        
        # Buscar dados do lead
        lead_data = lead_repo.get_lead_by_id(lead_id)
        if not lead_data:
            return jsonify({
                'success': False,
                'error': 'Lead não encontrado'
            }), 404
        
        # Buscar dados da qualificação
        qualificacao = qualificacao_repo.get_qualificacao_by_lead(lead_id)
        
        # Preparar dados para CRM
        crm_data = {
            'nome': lead_data['nome'],
            'telefone': lead_data['telefone'],
            'email': lead_data.get('email', ''),
            'canal': lead_data['canal'],
            'status': lead_data['status'],
            'score': lead_data['score'],
            'patrimonio_faixa': qualificacao.get('patrimonio_faixa', '') if qualificacao else '',
            'objetivo': qualificacao.get('objetivo', '') if qualificacao else '',
            'prazo': qualificacao.get('prazo', '') if qualificacao else '',
            'resumo_conversa': google_sheets_service.gerar_resumo_conversa(lead_id),
            'proximo_passo': google_sheets_service.definir_proximo_passo(
                lead_data['status'], lead_data['score']
            )
        }
        
        resultado = google_sheets_service.enviar_resultado_crm(crm_data)
        return jsonify(resultado), 200 if resultado['success'] else 500
        
    except Exception as e:
        logger.error("Erro ao enviar resultado para CRM", error=str(e))
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@app.route('/numeros-autorizados', methods=['GET'])
def listar_numeros_autorizados():
    """Lista números autorizados a receber mensagens"""
    try:
        numeros = whatsapp_service.phone_validator.get_numeros_autorizados()
        
        return jsonify({
            'numeros_autorizados': numeros,
            'total': len(numeros),
            'info': 'Apenas estes números podem receber mensagens do sistema',
            'protecao_ativa': True
        }), 200
        
    except Exception as e:
        logger.error("Erro ao listar números autorizados", error=str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/adicionar-numero-autorizado', methods=['POST'])
def adicionar_numero_autorizado():
    """Adiciona número à lista de autorizados"""
    try:
        data = request.get_json()
        telefone = data.get('telefone')
        motivo = data.get('motivo', 'Adicionado via API')
        
        if not telefone:
            return jsonify({'error': 'Telefone é obrigatório'}), 400
        
        whatsapp_service.phone_validator.adicionar_numero_autorizado(telefone, motivo)
        
        return jsonify({
            'success': True,
            'telefone': telefone,
            'motivo': motivo,
            'message': 'Número adicionado com sucesso'
        }), 200
        
    except Exception as e:
        logger.error("Erro ao adicionar número autorizado", error=str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/mensagens-simuladas', methods=['GET'])
def listar_mensagens_simuladas():
    """Lista mensagens que foram simuladas (não enviadas via WAHA)"""
    try:
        # Buscar mensagens recentes
        limit = request.args.get('limit', 10, type=int)
        
        # Buscar leads recentes para mostrar as conversas
        leads = lead_repo.get_recent_leads(limit)
        
        mensagens_simuladas = []
        
        for lead in leads:
            # Buscar mensagens da sessão mais recente
            sessoes = session_repo.get_sessions_by_lead_id(lead['id'])
            if sessoes:
                sessao_recente = sessoes[0]
                mensagens = message_repo.get_session_messages(sessao_recente['id'])
                
                for msg in mensagens:
                    if msg.get('tipo') == 'enviada':
                        mensagens_simuladas.append({
                            'nome_lead': lead.get('nome', 'N/A'),
                            'telefone': lead.get('telefone', 'N/A'),
                            'mensagem': msg.get('conteudo', ''),
                            'timestamp': msg.get('created_at', ''),
                            'simulada': True  # Todas as mensagens estão sendo simuladas
                        })
        
        return jsonify({
            'mensagens': mensagens_simuladas,
            'total': len(mensagens_simuladas),
            'info': 'Mensagens que seriam enviadas via WhatsApp (simuladas devido a problema com WAHA)',
            'solucao': 'Configure WAHA corretamente para envio real'
        }), 200
        
    except Exception as e:
        logger.error("Erro ao listar mensagens simuladas", error=str(e))
        return jsonify({'error': str(e)}), 500


# Handlers não utilizados removidos para WAHA Core otimizado
# Mantidos apenas: handle_session_status() e handle_message_edited()


def handle_session_status(payload):
    """Processa mudanças de status da sessão WhatsApp"""
    try:
        status = payload.get('status')
        session_name = payload.get('name')
        
        logger.info("Status da sessão alterado", 
                   session_name=session_name, 
                   status=status)
        
        # Aqui você pode implementar lógica para:
        # - Monitorar saúde da conexão WhatsApp
        # - Alertar sobre desconexões
        # - Reconectar automaticamente se necessário
        
        if status in ['DISCONNECTED', 'FAILED']:
            logger.warning("Sessão WhatsApp com problema", 
                          session_name=session_name, 
                          status=status)
            # TODO: Implementar alertas ou reconexão
        
        return jsonify({'status': 'session_status_processed', 'session_status': status}), 200
        
    except Exception as e:
        logger.error("Erro ao processar status da sessão", error=str(e))
        return jsonify({'status': 'error', 'error': str(e)}), 500


def handle_message_edited(payload):
    """Processa mensagens editadas (WAHA 2025.6+)"""
    try:
        message_id = payload.get('id')
        new_body = payload.get('body', '')
        from_number = payload.get('from', '')
        
        logger.info("Mensagem editada detectada", 
                   message_id=message_id,
                   from_number=from_number,
                   new_content=new_body[:50] + "..." if len(new_body) > 50 else new_body)
        
        # TODO: Implementar lógica para mensagens editadas se necessário
        # Por exemplo: atualizar histórico, re-processar com IA, etc.
        
        return jsonify({'status': 'message_edited_processed'}), 200
        
    except Exception as e:
        logger.error("Erro ao processar mensagem editada", error=str(e))
        return jsonify({'status': 'error', 'error': str(e)}), 500






if __name__ == '__main__':
    # Configurar logging para produção
    if not app.config['DEBUG']:
        logging.basicConfig(level=logging.INFO)
    
    # Log de inicialização
    logger.info("Iniciando Agente Qualificador de Leads", 
                host=os.getenv('FLASK_HOST', '0.0.0.0'),
                port=int(os.getenv('FLASK_PORT', 5000)),
                debug=app.config['DEBUG'])
    
    # Iniciar servidor
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=app.config['DEBUG']
    )



