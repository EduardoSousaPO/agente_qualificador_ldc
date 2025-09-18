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
import time

# Cache para deduplicação de mensagens (em memória)
message_cache = {}
CACHE_EXPIRY_SECONDS = 300  # 5 minutos

def cleanup_message_cache():
    """Remove mensagens expiradas do cache"""
    current_time = time.time()
    expired_keys = [key for key, timestamp in message_cache.items() 
                   if current_time - timestamp > CACHE_EXPIRY_SECONDS]
    for key in expired_keys:
        del message_cache[key]

def is_duplicate_message(message_id, telefone):
    """Verifica se a mensagem já foi processada"""
    cleanup_message_cache()
    cache_key = f"{telefone}:{message_id}"
    
    if cache_key in message_cache:
        return True
    
    # Marcar mensagem como processada
    message_cache[cache_key] = time.time()
    return False

def extrair_nome_lead(payload):
    """Extrai nome real do lead do payload WhatsApp com priorização inteligente"""
    nome_real = None
    
    # Prioridade: fromName > contact.name > pushName
    if payload.get('fromName'):
        nome_real = payload['fromName'].strip()
    elif payload.get('contact', {}).get('name'):
        nome_real = payload['contact']['name'].strip()
    elif payload.get('pushName'):
        nome_real = payload['pushName'].strip()
    
    if nome_real:
        # Usar apenas primeiro nome para personalização
        primeiro_nome = nome_real.split()[0] if nome_real else nome_real
        # Capitalizar primeira letra
        return primeiro_nome.capitalize() if primeiro_nome else None
    
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


@app.route('/webhook', methods=['POST'])
def webhook_whatsapp():
    """Webhook para receber mensagens do WAHA"""
    try:
        data = request.get_json()
        logger.info("=== WEBHOOK RECEBIDO ===", 
                   data=data, 
                   headers=dict(request.headers),
                   method=request.method,
                   url=request.url)
        
        # Extrair dados da estrutura WAHA
        payload = data.get('payload', {})
        event_type = data.get('event', '')
        
        # Log detalhado para debug de eventos
        logger.info("Evento recebido para análise", event_type=event_type, payload_keys=list(payload.keys()) if payload else [])
        
        # Aceitar eventos específicos (message.any removido para evitar duplicação)
        valid_events = ['message', 'message.ack', 'message.waiting', 'message.revoked', 'session.status']
        if event_type not in valid_events:
            logger.info("Evento ignorado", event_type=event_type, valid_events=valid_events)
            return jsonify({'status': 'ignored', 'event_type': event_type}), 200
        
        # Processar eventos especiais (não processam mensagens)
        if event_type == 'message.ack':
            return handle_message_ack(payload)
        elif event_type == 'message.waiting':
            return handle_message_waiting(payload)
        elif event_type == 'message.revoked':
            return handle_message_revoked(payload)
        elif event_type == 'session.status':
            return handle_session_status(payload)
        
        # Só processar como mensagem se for evento 'message'
        if event_type != 'message':
            logger.info("Evento não é mensagem, ignorando processamento", event_type=event_type)
            return jsonify({'status': 'not_message_event'}), 200
        
        # Continuar com processamento normal para evento 'message'
        
        # Validar estrutura da mensagem WAHA
        logger.info("Validando payload", 
                   payload_exists=bool(payload), 
                   payload_keys=list(payload.keys()) if payload else [],
                   from_exists='from' in payload if payload else False,
                   body_exists='body' in payload if payload else False)
        
        if not payload:
            logger.warning("Payload vazio", data=data)
            return jsonify({'status': 'empty_payload'}), 400
            
        if 'from' not in payload:
            logger.warning("Campo 'from' ausente no payload", payload_keys=list(payload.keys()))
            return jsonify({'status': 'missing_from_field'}), 400
            
        if 'body' not in payload:
            logger.warning("Campo 'body' ausente no payload", payload_keys=list(payload.keys()))
            return jsonify({'status': 'missing_body_field'}), 400
        
        # Ignorar mensagens próprias
        if payload.get('fromMe', False):
            logger.info("Mensagem própria ignorada")
            return jsonify({'status': 'own_message'}), 200
        
        telefone = payload['from']
        mensagem = payload['body']
        
        # Verificar deduplicação de mensagens
        message_id = payload.get('id', f"{telefone}_{int(time.time())}")
        if is_duplicate_message(message_id, telefone):
            logger.info("Mensagem duplicada ignorada", 
                       telefone=telefone, 
                       message_id=message_id,
                       mensagem=mensagem[:50])
            return jsonify({'status': 'duplicate_message'}), 200
        
        # Extrair nome do contato com função melhorada
        nome_contato = extrair_nome_lead(payload)
        
        # Buscar ou criar lead
        logger.info("Buscando lead por telefone", 
                   telefone=telefone, 
                   telefone_type=type(telefone).__name__,
                   telefone_length=len(telefone) if telefone else 0)
        
        lead_data = lead_repo.get_lead_by_phone(telefone)
        
        # Log do resultado da busca
        logger.info("Resultado busca lead por telefone", 
                   telefone=telefone,
                   lead_encontrado=bool(lead_data),
                   lead_id=lead_data.get('id') if lead_data else None,
                   lead_telefone=lead_data.get('telefone') if lead_data else None,
                   lead_nome=lead_data.get('nome') if lead_data else None)
        
        if not lead_data:
            # Lead não encontrado - criar automaticamente
            logger.info("Criando novo lead automaticamente", telefone=telefone, nome_contato=nome_contato)
            
            # Usar nome real do contato ou fallback mais humano
            if nome_contato:
                nome_lead = nome_contato
                logger.info("Usando nome real do contato", nome_original=nome_contato, nome_usado=nome_lead)
            else:
                # Fallback mais humano - evitar "Lead 1234"
                nome_lead = "Amigo"  # Muito mais humano e acolhedor
                logger.info("Usando fallback humano", nome_usado=nome_lead)
            
            # Criar novo lead
            novo_lead = Lead(
                nome=nome_lead,
                telefone=telefone,
                canal='whatsapp',  # Canal correto para mensagens via WhatsApp
                status='novo'
            )
            
            lead_data = lead_repo.create_lead(novo_lead)
            
            if not lead_data:
                logger.error("Falha ao criar novo lead automaticamente", telefone=telefone)
                return jsonify({'status': 'failed_to_create_lead'}), 500
            
            logger.info("Novo lead criado com sucesso", 
                       lead_id=lead_data.get('id'), 
                       nome=nome_lead, 
                       telefone=telefone,
                       nome_original=nome_contato)
        
        # Log antes do processamento
        logger.info("Iniciando processamento IA", 
                   lead_id=lead_data['id'],
                   lead_telefone_atual=lead_data.get('telefone'),
                   mensagem_length=len(mensagem) if mensagem else 0)
        
        # Processar mensagem recebida
        resultado = qualification_service.processar_mensagem_recebida(
            lead_data['id'], mensagem
        )
        
        if resultado['success']:
            logger.info("Mensagem processada com sucesso", 
                       lead_id=lead_data['id'], 
                       resultado=resultado)
        else:
            logger.error("Erro ao processar mensagem", 
                        lead_id=lead_data['id'], 
                        error=resultado.get('error'))
        
        return jsonify({'status': 'processed', 'result': resultado}), 200
        
    except Exception as e:
        logger.error("Erro no webhook", error=str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500


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


def handle_message_ack(payload):
    """Processa confirmações de entrega de mensagens"""
    try:
        ack_type = payload.get('ack')  # sent, delivered, read
        message_id = payload.get('id')
        chat_id = payload.get('chatId', '')
        
        logger.info("Confirmação de entrega recebida", 
                   message_id=message_id, 
                   ack_type=ack_type, 
                   chat_id=chat_id)
        
        # Aqui você pode implementar lógica para:
        # - Atualizar status da mensagem no banco
        # - Detectar falhas de entrega
        # - Implementar reenvio automático se necessário
        
        if ack_type in ['failed', 'error']:
            logger.warning("Falha na entrega da mensagem", 
                          message_id=message_id, 
                          ack_type=ack_type)
            # TODO: Implementar lógica de reenvio
        
        return jsonify({'status': 'ack_processed', 'ack_type': ack_type}), 200
        
    except Exception as e:
        logger.error("Erro ao processar confirmação de entrega", error=str(e))
        return jsonify({'status': 'error', 'error': str(e)}), 500


def handle_message_waiting(payload):
    """Processa mensagens na fila de envio"""
    try:
        message_id = payload.get('id')
        chat_id = payload.get('chatId', '')
        
        logger.info("Mensagem na fila de envio", 
                   message_id=message_id, 
                   chat_id=chat_id)
        
        # Aqui você pode implementar lógica para:
        # - Controlar velocidade de envio
        # - Evitar spam por envios múltiplos
        # - Monitorar fila de mensagens
        
        return jsonify({'status': 'waiting_processed'}), 200
        
    except Exception as e:
        logger.error("Erro ao processar mensagem na fila", error=str(e))
        return jsonify({'status': 'error', 'error': str(e)}), 500


def handle_message_revoked(payload):
    """Processa mensagens revogadas/deletadas"""
    try:
        message_id = payload.get('id')
        chat_id = payload.get('chatId', '')
        
        logger.info("Mensagem revogada", 
                   message_id=message_id, 
                   chat_id=chat_id)
        
        # Aqui você pode implementar lógica para:
        # - Registrar mensagens deletadas
        # - Atualizar histórico de conversa
        # - Notificar sobre mensagens importantes deletadas
        
        return jsonify({'status': 'revoked_processed'}), 200
        
    except Exception as e:
        logger.error("Erro ao processar mensagem revogada", error=str(e))
        return jsonify({'status': 'error', 'error': str(e)}), 500


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



