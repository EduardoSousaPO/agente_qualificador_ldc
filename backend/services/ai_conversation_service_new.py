"""
Serviço de Conversação com IA Melhorado
Sistema de conversação estruturado com slot filling e validação robusta
"""

import os
import json
import requests
import time
from typing import Dict, Any, List, Optional, Tuple
import structlog
from pydantic import ValidationError

from .reconhecimento_respostas import ReconhecimentoRespostasService
from .prompt_service import PromptService
from .validation_service import ValidationService
from .slot_filling_service import SlotFillingService

from backend.models.conversation_models import (
    RespostaIA, IntencaoLead, PromptContext, SessionState, Estado, Acao,
    ContextoConversa, MAX_MENSAGENS_POR_CONVERSA, MAX_REFORMULACOES_POR_ESTADO,
    TEMPERATURA_IA, TOP_P_IA, TIMEOUT_IA_SEGUNDOS
)

logger = structlog.get_logger(__name__)


class AIConversationService:
    """Serviço para conversação inteligente com IA melhorado"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-4o-mini"  # Migrado para modelo mais atual
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
        # Novos serviços especializados
        self.prompt_service = PromptService()
        self.validation_service = ValidationService()
        self.slot_filling_service = SlotFillingService()
        self.reconhecimento_service = ReconhecimentoRespostasService()
        
        # Cache de sessões em memória (em produção usar Redis)
        self.session_cache = {}
        self.tentativas_reformulacao = {}  # Controle de reformulações
    
    def gerar_resposta_humanizada(self, 
                                  lead_nome: str,
                                  lead_canal: str,
                                  mensagem_lead: str,
                                  historico_conversa: List[Dict[str, str]],
                                  estado_atual: str,
                                  session_id: str = None) -> Dict[str, Any]:
        """
        Gera resposta humanizada usando novo sistema estruturado
        """
        try:
            # Converter estado para enum
            estado_enum = Estado(estado_atual)
            
            # Obter ou criar estado da sessão
            session_state = self._get_or_create_session_state(
                session_id, lead_nome, estado_enum, historico_conversa
            )
            
            # Verificar limites de mensagens
            if session_state.mensagem_count >= MAX_MENSAGENS_POR_CONVERSA:
                return self._finalizar_por_limite_mensagens(session_state, lead_nome)
            
            # Detectar se lead não compreendeu
            if self._detectar_nao_compreensao(mensagem_lead):
                return self._processar_reformulacao(session_state, mensagem_lead, lead_nome)
            
            # Extrair slots da mensagem do lead
            session_state.contexto = self.slot_filling_service.extrair_slots_da_mensagem(
                mensagem_lead, session_state.estado_atual, session_state.contexto
            )
            
            # Analisar intenção do lead
            intencao = self.analisar_intencao_lead(mensagem_lead)
            
            # Determinar próxima ação baseada na intenção e slots
            proxima_acao, proximo_estado = self._determinar_proxima_acao(
                session_state, intencao
            )
            
            # Gerar resposta usando IA
            resposta_ia = self._gerar_resposta_ia(
                session_state, mensagem_lead, lead_canal, proxima_acao, proximo_estado
            )
            
            if not resposta_ia:
                return self._gerar_fallback_response(session_state, lead_nome)
            
            # Atualizar estado da sessão
            session_state.estado_atual = resposta_ia.proximo_estado
            session_state.contexto = resposta_ia.contexto
            session_state.mensagem_count += 1
            
            # Salvar estado atualizado
            self._save_session_state(session_id, session_state)
            
            logger.info("Resposta gerada com sucesso", 
                       lead_nome=lead_nome, 
                       estado=resposta_ia.proximo_estado.value,
                       acao=resposta_ia.acao.value,
                       score=resposta_ia.score_parcial)
            
            return {
                'success': True,
                'resposta': resposta_ia.mensagem,
                'acao': resposta_ia.acao.value,
                'proximo_estado': resposta_ia.proximo_estado.value,
                'contexto_atualizado': resposta_ia.contexto.dict(),
                'score_parcial': resposta_ia.score_parcial,
                'slots_preenchidos': session_state.slots_preenchidos(),
                'pode_agendar': session_state.pode_agendar()
            }
            
        except Exception as e:
            logger.error("Erro ao gerar resposta IA", error=str(e), lead_nome=lead_nome)
            return self._gerar_erro_response(estado_atual, lead_nome, str(e))
    
    def _get_or_create_session_state(self, session_id: str, lead_nome: str, 
                                   estado_atual: Estado, historico: List[Dict[str, str]]) -> SessionState:
        """Obtém ou cria estado da sessão"""
        
        if session_id and session_id in self.session_cache:
            session_state = self.session_cache[session_id]
            # Atualizar histórico
            session_state.mensagem_count = len(historico)
            return session_state
        
        # Criar nova sessão
        session_state = SessionState(
            lead_id=session_id or f"temp_{int(time.time())}",
            session_id=session_id or f"session_{int(time.time())}",
            estado_atual=estado_atual,
            contexto=ContextoConversa(),
            mensagem_count=len(historico)
        )
        
        if session_id:
            self.session_cache[session_id] = session_state
        
        return session_state
    
    def _save_session_state(self, session_id: str, session_state: SessionState):
        """Salva estado da sessão"""
        if session_id:
            self.session_cache[session_id] = session_state
    
    def _detectar_nao_compreensao(self, mensagem: str) -> bool:
        """Detecta se o lead não entendeu a pergunta"""
        frases_nao_compreensao = [
            "não entendi", "como assim", "não sei", "não entendo",
            "o que você quer dizer", "explica melhor", "não compreendi",
            "pode explicar", "não captei", "não tô entendendo", "?",
            "hein", "oi", "o que", "que isso"
        ]
        
        mensagem_lower = mensagem.lower().strip()
        return any(frase in mensagem_lower for frase in frases_nao_compreensao)
    
    def _processar_reformulacao(self, session_state: SessionState, mensagem: str, 
                               lead_nome: str) -> Dict[str, Any]:
        """Processa reformulação quando lead não entende"""
        
        # Incrementar tentativas de reformulação
        key = f"{session_state.session_id}_{session_state.estado_atual.value}"
        tentativas = self.tentativas_reformulacao.get(key, 0) + 1
        self.tentativas_reformulacao[key] = tentativas
        
        logger.info("Processando reformulação", 
                   estado=session_state.estado_atual.value,
                   tentativa=tentativas,
                   lead_nome=lead_nome)
        
        # Após 2 tentativas, transferir para humano
        if tentativas > MAX_REFORMULACOES_POR_ESTADO:
            return {
                'success': True,
                'resposta': f"Me desculpa, {lead_nome}! Vou te conectar com um consultor humano que vai te explicar melhor. Um momento! 😊",
                'acao': 'transferir_humano',
                'proximo_estado': 'finalizado',
                'contexto_atualizado': session_state.contexto.dict(),
                'score_parcial': 20,
                'reformulacao_usada': True,
                'tentativa': tentativas
            }
        
        # Gerar reformulação específica
        reformulacao_prompt = self.prompt_service.build_reformulacao_prompt(
            session_state.estado_atual, lead_nome, tentativas
        )
        
        resposta_reformulada = self._chamar_openai(
            reformulacao_prompt, session_state.estado_atual, lead_nome
        )
        
        if resposta_reformulada:
            return {
                'success': True,
                'resposta': resposta_reformulada.mensagem,
                'acao': resposta_reformulada.acao.value,
                'proximo_estado': resposta_reformulada.proximo_estado.value,
                'contexto_atualizado': resposta_reformulada.contexto.dict(),
                'score_parcial': resposta_reformulada.score_parcial,
                'reformulacao_usada': True,
                'tentativa': tentativas
            }
        
        # Fallback se reformulação falhar
        return self._gerar_fallback_response(session_state, lead_nome)
    
    def _determinar_proxima_acao(self, session_state: SessionState, 
                                intencao: IntencaoLead) -> Tuple[Acao, Estado]:
        """Determina próxima ação baseada no estado atual e intenção"""
        
        # Se lead mostrou interesse em agendamento
        if intencao.intencao == "agendamento":
            return Acao.AGENDAR, Estado.AGENDAMENTO
        
        # Se lead recusou ou mostrou desinteresse
        if intencao.intencao == "recusa" or intencao.sentimento == "negativo":
            return Acao.FINALIZAR, Estado.EDUCAR
        
        # Se pode agendar baseado nos slots
        if session_state.pode_agendar():
            return Acao.AGENDAR, Estado.AGENDAMENTO
        
        # Continuar fluxo normal
        proximo_estado = session_state.proximo_estado_logico()
        
        if proximo_estado == Estado.FINALIZADO:
            return Acao.FINALIZAR, Estado.FINALIZADO
        else:
            return Acao.CONTINUAR, proximo_estado
    
    def _gerar_resposta_ia(self, session_state: SessionState, mensagem_lead: str,
                          lead_canal: str, acao: Acao, proximo_estado: Estado) -> Optional[RespostaIA]:
        """Gera resposta usando IA com novo sistema de prompts"""
        
        # Construir contexto do prompt
        prompt_context = PromptContext(
            estado_atual=session_state.estado_atual,
            slots_preenchidos=session_state.slots_preenchidos(),
            slots_faltantes=session_state.slots_faltantes(),
            nome_lead=session_state.lead_id.split('_')[0] if '_' in session_state.lead_id else "Amigo",
            canal=lead_canal,
            ultima_mensagem_lead=mensagem_lead,
            historico_compacto=[],  # Simplificado por ora
            tentativas_estado=self.tentativas_reformulacao.get(
                f"{session_state.session_id}_{session_state.estado_atual.value}", 0
            )
        )
        
        # Chamar OpenAI
        return self._chamar_openai_estruturado(prompt_context)
    
    def _chamar_openai_estruturado(self, context: PromptContext) -> Optional[RespostaIA]:
        """Chama OpenAI com novo sistema estruturado"""
        
        try:
            # Construir prompts
            system_prompt = self.prompt_service.system_prompt
            user_prompt = self.prompt_service.build_user_prompt(context)
            
            # Preparar chamada com responses API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 300,
                "temperature": TEMPERATURA_IA,
                "top_p": TOP_P_IA,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "resposta_agente",
                        "schema": self.prompt_service.json_schema
                    }
                },
                "stop": ["\n\n", "Mensagem:", "Lead:", "Agente:"]
            }
            
            # Fazer chamada com timeout
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=data, 
                timeout=TIMEOUT_IA_SEGUNDOS
            )
            response.raise_for_status()
            
            # Processar resposta
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            
            # Validar resposta
            validation_result = self.validation_service.validar_resposta_ia(
                content, context.estado_atual, context.nome_lead
            )
            
            if validation_result.valida and validation_result.resposta_corrigida:
                return validation_result.resposta_corrigida
            
            logger.warning("Resposta IA inválida", 
                          errors=validation_result.erros, 
                          content=content[:200])
            return None
            
        except requests.exceptions.Timeout:
            logger.error("Timeout na chamada OpenAI")
            return None
        except Exception as e:
            logger.error("Erro na chamada OpenAI", error=str(e))
            return None
    
    def _chamar_openai(self, prompt: str, estado: Estado, nome_lead: str) -> Optional[RespostaIA]:
        """Método auxiliar para chamadas simples"""
        
        context = PromptContext(
            estado_atual=estado,
            slots_preenchidos={},
            slots_faltantes=[],
            nome_lead=nome_lead,
            canal="whatsapp",
            ultima_mensagem_lead="",
            historico_compacto=[]
        )
        
        return self._chamar_openai_estruturado(context)
    
    def analisar_intencao_lead(self, mensagem: str) -> IntencaoLead:
        """Analisa a intenção por trás da mensagem do lead"""
        try:
            prompt = self.prompt_service.build_classificador_prompt(mensagem)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            response_data = response.json()
            content_json = json.loads(response_data['choices'][0]['message']['content'])
            
            return IntencaoLead(**content_json)
            
        except Exception as e:
            logger.error("Erro ao analisar intenção", error=str(e))
            return IntencaoLead(
                intencao="duvida",
                sentimento="neutro", 
                urgencia=5,
                qualificacao_score=50,
                principais_pontos=[]
            )
    
    def _finalizar_por_limite_mensagens(self, session_state: SessionState, 
                                       lead_nome: str) -> Dict[str, Any]:
        """Finaliza conversa por limite de mensagens"""
        
        if session_state.pode_agendar():
            return {
                'success': True,
                'resposta': f"Ótimo, {lead_nome}! Com base no que conversamos, posso te conectar com um consultor especialista. Que tal marcarmos 30 minutos? 1) amanhã 10h 2) amanhã 16h",
                'acao': 'agendar',
                'proximo_estado': 'agendamento',
                'contexto_atualizado': session_state.contexto.dict(),
                'score_parcial': self.slot_filling_service.calcular_score_parcial(session_state.contexto),
                'limite_atingido': True
            }
        else:
            return {
                'success': True,
                'resposta': f"Foi um prazer conversar, {lead_nome}! Vou te mandar um material sobre investimentos independentes. Posso entrar em contato em alguns dias? 1) pode sim 2) prefiro não",
                'acao': 'finalizar',
                'proximo_estado': 'educar',
                'contexto_atualizado': session_state.contexto.dict(),
                'score_parcial': self.slot_filling_service.calcular_score_parcial(session_state.contexto),
                'limite_atingido': True
            }
    
    def _gerar_fallback_response(self, session_state: SessionState, 
                                lead_nome: str) -> Dict[str, Any]:
        """Gera resposta de fallback quando IA falha"""
        
        fallback_resposta = self.validation_service.get_fallback_response(
            session_state.estado_atual, lead_nome
        )
        
        return {
            'success': True,
            'resposta': fallback_resposta.mensagem,
            'acao': fallback_resposta.acao.value,
            'proximo_estado': fallback_resposta.proximo_estado.value,
            'contexto_atualizado': fallback_resposta.contexto.dict(),
            'score_parcial': fallback_resposta.score_parcial,
            'fallback_usado': True
        }
    
    def _gerar_erro_response(self, estado_atual: str, lead_nome: str, 
                           erro: str) -> Dict[str, Any]:
        """Gera resposta de erro"""
        
        return {
            'success': False,
            'error': erro,
            'resposta': f"Desculpe, {lead_nome}. Tive um problema técnico. Pode repetir sua mensagem?",
            'acao': 'continuar',
            'proximo_estado': estado_atual,
            'contexto_atualizado': {},
            'score_parcial': 0
        }
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Retorna estatísticas da sessão"""
        
        if session_id not in self.session_cache:
            return {'error': 'Sessão não encontrada'}
        
        session_state = self.session_cache[session_id]
        
        return {
            'estado_atual': session_state.estado_atual.value,
            'mensagem_count': session_state.mensagem_count,
            'slots_preenchidos': session_state.slots_preenchidos(),
            'slots_faltantes': session_state.slots_faltantes(),
            'pode_agendar': session_state.pode_agendar(),
            'score_parcial': self.slot_filling_service.calcular_score_parcial(session_state.contexto),
            'reformulacoes_usadas': session_state.reformulacoes_usadas,
            'finalizada': session_state.finalizada
        }
    
    def reset_session(self, session_id: str):
        """Reseta uma sessão"""
        if session_id in self.session_cache:
            del self.session_cache[session_id]
        
        # Limpar tentativas de reformulação relacionadas
        keys_to_remove = [key for key in self.tentativas_reformulacao.keys() 
                         if key.startswith(session_id)]
        for key in keys_to_remove:
            del self.tentativas_reformulacao[key]
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """Remove sessões expiradas do cache"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session_state in self.session_cache.items():
            # Implementar lógica de expiração baseada em timestamp
            # Por ora, manter simples
            pass
        
        for session_id in expired_sessions:
            self.reset_session(session_id)
