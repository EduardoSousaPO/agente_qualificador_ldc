"""
Serviço de Qualificação de Leads
Gerencia o fluxo completo de qualificação via WhatsApp
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import structlog

from backend.models.database_models import Session, Message, Qualificacao, SystemLog
from backend.services.scoring_service import ScoringService
from backend.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger()


class QualificationService:
    """Serviço para gerenciar o processo de qualificação"""
    
    def __init__(self, session_repo, message_repo, qualificacao_repo, scoring_service, whatsapp_service):
        self.session_repo = session_repo
        self.message_repo = message_repo
        self.qualificacao_repo = qualificacao_repo
        self.scoring_service = scoring_service
        self.whatsapp_service = whatsapp_service
        
        self.timeout_sessao = int(os.getenv('TIMEOUT_SESSAO_MINUTOS', '60'))
        
        # Estados do fluxo de qualificação
        self.estados = [
            'inicio',
            'saudacao', 
            'pergunta_1',
            'pergunta_2',
            'pergunta_3',
            'pergunta_4',
            'calculando_score',
            'resultado',
            'finalizado'
        ]
    
    def iniciar_qualificacao(self, lead_id: str, telefone: str, canal: str) -> Dict[str, Any]:
        """Inicia processo de qualificação para um lead"""
        try:
            logger.info("Iniciando qualificação", lead_id=lead_id, canal=canal)
            
            # Verificar se já existe sessão ativa
            sessao_ativa = self.session_repo.get_active_session(lead_id)
            
            if sessao_ativa:
                logger.info("Sessão já ativa encontrada", 
                           lead_id=lead_id, 
                           session_id=sessao_ativa['id'])
                return {
                    'success': True,
                    'session_id': sessao_ativa['id'],
                    'message': 'Sessão já ativa'
                }
            
            # Criar nova sessão
            nova_sessao = Session(
                lead_id=lead_id,
                estado='inicio',
                contexto={'canal': canal, 'telefone': telefone}
            )
            
            sessao_data = self.session_repo.create_session(nova_sessao)
            
            if not sessao_data:
                raise Exception("Erro ao criar sessão")
            
            # Enviar mensagem inicial
            mensagem_inicial = self.whatsapp_service.obter_mensagem_inicial(canal)
            resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, mensagem_inicial)
            
            # Registrar mensagem enviada
            if resultado_envio['success']:
                self._registrar_mensagem(
                    sessao_data['id'], 
                    lead_id, 
                    mensagem_inicial, 
                    'enviada',
                    {'message_id': resultado_envio.get('message_id')}
                )
                
                # Atualizar estado da sessão
                self.session_repo.update_session(sessao_data['id'], {'estado': 'saudacao'})
                
                logger.info("Qualificação iniciada com sucesso", 
                           lead_id=lead_id,
                           session_id=sessao_data['id'])
                
                return {
                    'success': True,
                    'session_id': sessao_data['id'],
                    'message': 'Qualificação iniciada'
                }
            else:
                logger.error("Erro ao enviar mensagem inicial", 
                           lead_id=lead_id,
                           error=resultado_envio.get('error'))
                
                return {
                    'success': False,
                    'error': 'Erro ao enviar mensagem inicial',
                    'details': resultado_envio
                }
                
        except Exception as e:
            logger.error("Erro ao iniciar qualificação", lead_id=lead_id, error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def processar_mensagem_recebida(self, lead_id: str, mensagem: str) -> Dict[str, Any]:
        """Processa mensagem recebida do lead"""
        try:
            logger.info("Processando mensagem recebida", lead_id=lead_id, mensagem=mensagem[:100])
            
            # Buscar sessão ativa
            sessao = self.session_repo.get_active_session(lead_id)
            
            if not sessao:
                logger.info("Nenhuma sessão ativa, criando nova sessão", lead_id=lead_id)
                # Criar nova sessão automaticamente
                nova_sessao = Session(
                    lead_id=lead_id,
                    estado='inicio',
                    contexto={},
                    ativa=True
                )
                sessao_id = self.session_repo.create_session(nova_sessao)
                sessao = self.session_repo.get_session(sessao_id)
                
                if not sessao:
                    logger.error("Erro ao criar nova sessão", lead_id=lead_id)
                    return {
                        'success': False,
                        'error': 'Erro ao criar sessão'
                    }
                
                logger.info("Nova sessão criada", lead_id=lead_id, session_id=sessao_id)
            
            # Verificar timeout da sessão
            if self._verificar_timeout_sessao(sessao):
                return self._processar_timeout_sessao(sessao, lead_id)
            
            # Registrar mensagem recebida
            self._registrar_mensagem(sessao['id'], lead_id, mensagem, 'recebida')
            
            # Processar baseado no estado atual
            estado_atual = sessao['estado']
            
            if estado_atual == 'inicio':
                return self._processar_inicio(sessao, lead_id, mensagem)
            elif estado_atual == 'saudacao':
                return self._processar_saudacao(sessao, lead_id, mensagem)
            elif estado_atual.startswith('pergunta_'):
                return self._processar_resposta_pergunta(sessao, lead_id, mensagem)
            elif estado_atual == 'resultado':
                return self._processar_pos_resultado(sessao, lead_id, mensagem)
            else:
                logger.warning("Estado não reconhecido", lead_id=lead_id, estado=estado_atual)
                return {
                    'success': False,
                    'error': f'Estado não reconhecido: {estado_atual}'
                }
                
        except Exception as e:
            logger.error("Erro ao processar mensagem", lead_id=lead_id, error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _processar_inicio(self, sessao: Dict[str, Any], lead_id: str, mensagem: str) -> Dict[str, Any]:
        """Processa primeira mensagem do lead - envia saudação"""
        try:
            logger.info("Processando estado inicial", lead_id=lead_id)
            
            # Buscar dados do lead usando o repositório correto
            from backend.models.database_models import DatabaseConnection, LeadRepository
            db_conn = DatabaseConnection()
            lead_repo = LeadRepository(db_conn)
            
            # Buscar lead pelo ID
            lead_data = db_conn.get_client().table('leads').select('*').eq('id', lead_id).execute()
            if not lead_data.data:
                return {'success': False, 'error': 'Lead não encontrado'}
            
            lead = lead_data.data[0]
            telefone = lead['telefone']
            nome = lead['nome'] or 'amigo(a)'
            
            # Criar mensagem de saudação personalizada
            saudacao = f"""Olá {nome}! 👋

Sou o assistente da LDC Capital e vou te ajudar com algumas perguntas rápidas para entender melhor seu perfil de investimento.

Isso vai levar apenas 2 minutos e no final vou te dar uma recomendação personalizada! 

Vamos começar? 😊"""
            
            # Enviar saudação
            resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, saudacao)
            
            if resultado_envio['success']:
                # Registrar saudação enviada
                self._registrar_mensagem(sessao['id'], lead_id, saudacao, 'enviada')
                
                # Atualizar contexto e estado
                contexto_atualizado = sessao.get('contexto', {})
                contexto_atualizado.update({
                    'telefone': telefone,
                    'nome': nome,
                    'inicio_qualificacao': datetime.now().isoformat()
                })
                
                self.session_repo.update_session(sessao['id'], {
                    'estado': 'saudacao',
                    'contexto': contexto_atualizado
                })
                
                return {
                    'success': True,
                    'next_state': 'saudacao',
                    'message': 'Saudação enviada'
                }
            else:
                return {
                    'success': False,
                    'error': 'Erro ao enviar saudação',
                    'details': resultado_envio
                }
                
        except Exception as e:
            logger.error("Erro ao processar início", lead_id=lead_id, error=str(e))
            return {'success': False, 'error': str(e)}
    
    def _processar_saudacao(self, sessao: Dict[str, Any], lead_id: str, mensagem: str) -> Dict[str, Any]:
        """Processa resposta à saudação inicial"""
        telefone = sessao['contexto'].get('telefone')
        
        # Enviar primeira pergunta
        pergunta_1 = self.whatsapp_service.obter_pergunta(1)
        resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, pergunta_1)
        
        if resultado_envio['success']:
            # Registrar pergunta enviada
            self._registrar_mensagem(sessao['id'], lead_id, pergunta_1, 'enviada')
            
            # Atualizar estado
            self.session_repo.update_session(sessao['id'], {'estado': 'pergunta_1'})
            
            return {
                'success': True,
                'next_state': 'pergunta_1',
                'message': 'Primeira pergunta enviada'
            }
        else:
            return {
                'success': False,
                'error': 'Erro ao enviar primeira pergunta',
                'details': resultado_envio
            }
    
    def _processar_resposta_pergunta(self, sessao: Dict[str, Any], lead_id: str, mensagem: str) -> Dict[str, Any]:
        """Processa resposta a uma pergunta de qualificação"""
        estado_atual = sessao['estado']
        numero_pergunta = int(estado_atual.split('_')[1])
        telefone = sessao['contexto'].get('telefone')
        
        # Validar resposta
        tipo_pergunta = self._obter_tipo_pergunta(numero_pergunta)
        
        if not self.scoring_service.validar_resposta(mensagem, tipo_pergunta):
            # Resposta inválida - solicitar nova resposta
            mensagem_erro = self.whatsapp_service.gerar_mensagem_erro_resposta()
            resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, mensagem_erro)
            
            if resultado_envio['success']:
                self._registrar_mensagem(sessao['id'], lead_id, mensagem_erro, 'enviada')
            
            return {
                'success': True,
                'message': 'Resposta inválida - nova tentativa solicitada',
                'validation_error': True
            }
        
        # Armazenar resposta no contexto da sessão
        contexto = sessao['contexto'].copy()
        contexto[f'resposta_{numero_pergunta}'] = mensagem
        
        self.session_repo.update_session(sessao['id'], {'contexto': contexto})
        
        # Determinar próximo passo
        if numero_pergunta < 4:
            # Enviar próxima pergunta
            proxima_pergunta = numero_pergunta + 1
            pergunta = self.whatsapp_service.obter_pergunta(proxima_pergunta)
            
            resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, pergunta)
            
            if resultado_envio['success']:
                self._registrar_mensagem(sessao['id'], lead_id, pergunta, 'enviada')
                self.session_repo.update_session(sessao['id'], {'estado': f'pergunta_{proxima_pergunta}'})
                
                return {
                    'success': True,
                    'next_state': f'pergunta_{proxima_pergunta}',
                    'message': f'Pergunta {proxima_pergunta} enviada'
                }
            else:
                return {
                    'success': False,
                    'error': f'Erro ao enviar pergunta {proxima_pergunta}',
                    'details': resultado_envio
                }
        else:
            # Todas as perguntas respondidas - calcular score
            return self._finalizar_qualificacao(sessao, lead_id, contexto)
    
    def _finalizar_qualificacao(self, sessao: Dict[str, Any], lead_id: str, contexto: Dict[str, Any]) -> Dict[str, Any]:
        """Finaliza processo de qualificação calculando score"""
        try:
            telefone = contexto.get('telefone')
            
            # Calcular score
            resultado_scoring = self.scoring_service.calcular_score_completo(
                contexto.get('resposta_1', ''),
                contexto.get('resposta_2', ''),
                contexto.get('resposta_3', ''),
                contexto.get('resposta_4', '')
            )
            
            # Criar registro de qualificação
            qualificacao = Qualificacao(
                lead_id=lead_id,
                session_id=sessao['id'],
                patrimonio_resposta=contexto.get('resposta_1'),
                patrimonio_pontos=resultado_scoring.patrimonio_pontos,
                objetivo_resposta=contexto.get('resposta_2'),
                objetivo_pontos=resultado_scoring.objetivo_pontos,
                urgencia_resposta=contexto.get('resposta_3'),
                urgencia_pontos=resultado_scoring.urgencia_pontos,
                interesse_resposta=contexto.get('resposta_4'),
                interesse_pontos=resultado_scoring.interesse_pontos,
                resultado=resultado_scoring.resultado,
                observacoes=resultado_scoring.observacoes
            )
            
            qualificacao_data = self.qualificacao_repo.create_qualificacao(qualificacao)
            
            if not qualificacao_data:
                raise Exception("Erro ao salvar qualificação")
            
            # Gerar mensagem de resultado
            if resultado_scoring.resultado == 'qualificado':
                mensagem_resultado = self.whatsapp_service.gerar_mensagem_score_alto(
                    "Cliente",  # TODO: pegar nome real do lead
                    resultado_scoring.score_total
                )
            else:
                mensagem_resultado = self.whatsapp_service.gerar_mensagem_score_baixo(
                    "Cliente",  # TODO: pegar nome real do lead
                    resultado_scoring.score_total
                )
            
            # Enviar resultado
            resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, mensagem_resultado)
            
            if resultado_envio['success']:
                self._registrar_mensagem(sessao['id'], lead_id, mensagem_resultado, 'enviada')
                
                # Atualizar estado da sessão
                self.session_repo.update_session(sessao['id'], {
                    'estado': 'resultado',
                    'contexto': {**contexto, 'score': resultado_scoring.score_total}
                })
                
                logger.info("Qualificação finalizada com sucesso", 
                           lead_id=lead_id,
                           score=resultado_scoring.score_total,
                           resultado=resultado_scoring.resultado)
                
                return {
                    'success': True,
                    'score': resultado_scoring.score_total,
                    'resultado': resultado_scoring.resultado,
                    'qualificacao_id': qualificacao_data['id'],
                    'message': 'Qualificação finalizada'
                }
            else:
                logger.error("Erro ao enviar resultado", 
                           lead_id=lead_id,
                           error=resultado_envio.get('error'))
                
                return {
                    'success': False,
                    'error': 'Erro ao enviar resultado',
                    'details': resultado_envio
                }
                
        except Exception as e:
            logger.error("Erro ao finalizar qualificação", lead_id=lead_id, error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _processar_pos_resultado(self, sessao: Dict[str, Any], lead_id: str, mensagem: str) -> Dict[str, Any]:
        """Processa mensagens após o resultado da qualificação"""
        # TODO: Implementar lógica para agendamento de reuniões ou envio de conteúdo
        telefone = sessao['contexto'].get('telefone')
        score = sessao['contexto'].get('score', 0)
        
        if score >= 70:
            # Lead qualificado - processar agendamento
            resposta = """
Perfeito! Vou conectar você com nossa equipe de agendamento.

Em breve, um de nossos especialistas entrará em contato para agendar sua consulta.

Obrigado pela confiança! 🙏
            """.strip()
        else:
            # Lead não qualificado - oferecer conteúdo
            resposta = """
Ótimo! Vou enviar os materiais por email.

Se tiver alguma dúvida ou quiser conversar mais tarde, é só me chamar!

Sucesso na sua jornada financeira! 💪
            """.strip()
        
        resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, resposta)
        
        if resultado_envio['success']:
            self._registrar_mensagem(sessao['id'], lead_id, resposta, 'enviada')
            
            # Finalizar sessão
            self.session_repo.update_session(sessao['id'], {
                'estado': 'finalizado',
                'ativa': False
            })
            
            return {
                'success': True,
                'message': 'Processo finalizado'
            }
        else:
            return {
                'success': False,
                'error': 'Erro ao enviar resposta final',
                'details': resultado_envio
            }
    
    def _verificar_timeout_sessao(self, sessao: Dict[str, Any]) -> bool:
        """Verifica se a sessão expirou por timeout"""
        if not sessao.get('updated_at'):
            return False
        
        try:
            ultima_atualizacao = datetime.fromisoformat(sessao['updated_at'].replace('Z', '+00:00'))
            agora = datetime.utcnow().replace(tzinfo=ultima_atualizacao.tzinfo)
            
            diferenca = agora - ultima_atualizacao
            return diferenca > timedelta(minutes=self.timeout_sessao)
            
        except Exception:
            return False
    
    def _processar_timeout_sessao(self, sessao: Dict[str, Any], lead_id: str) -> Dict[str, Any]:
        """Processa sessão que expirou por timeout"""
        telefone = sessao['contexto'].get('telefone')
        
        # Enviar mensagem de timeout
        mensagem_timeout = self.whatsapp_service.gerar_mensagem_timeout()
        resultado_envio = self.whatsapp_service.enviar_mensagem(telefone, mensagem_timeout)
        
        if resultado_envio['success']:
            self._registrar_mensagem(sessao['id'], lead_id, mensagem_timeout, 'enviada')
        
        # Desativar sessão
        self.session_repo.update_session(sessao['id'], {'ativa': False})
        
        logger.info("Sessão finalizada por timeout", lead_id=lead_id, session_id=sessao['id'])
        
        return {
            'success': True,
            'message': 'Sessão expirada - mensagem de timeout enviada',
            'timeout': True
        }
    
    def _registrar_mensagem(self, session_id: str, lead_id: str, conteudo: str, tipo: str, metadata: Dict[str, Any] = None):
        """Registra mensagem no banco de dados"""
        mensagem = Message(
            session_id=session_id,
            lead_id=lead_id,
            conteudo=conteudo,
            tipo=tipo,
            metadata=metadata or {}
        )
        
        self.message_repo.create_message(mensagem)
    
    def _obter_tipo_pergunta(self, numero_pergunta: int) -> str:
        """Retorna o tipo da pergunta para validação"""
        tipos = {
            1: 'patrimonio',
            2: 'objetivo', 
            3: 'urgencia',
            4: 'interesse'
        }
        return tipos.get(numero_pergunta, 'geral')



