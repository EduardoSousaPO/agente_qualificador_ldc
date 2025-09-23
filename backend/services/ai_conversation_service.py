"""
Serviço de Conversação com IA Melhorado
Sistema de conversação estruturado com slot filling e validação robusta
"""

import os
import json
import requests
import time
import re
from typing import Dict, Any, List, Optional, Tuple
import structlog
from pydantic import ValidationError

from .prompt_service_pro import PromptServicePro
from .validation_service import ValidationService
from .slot_filling_service import SlotFillingService
from .guardrails_service import GuardrailsService
from .intention_classifier import IntentionClassifier
from .rag_service import RAGService

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
        self.prompt_service_pro = PromptServicePro()  # 🆕 NOVO SISTEMA PROFISSIONAL
        self.validation_service = ValidationService()
        self.slot_filling_service = SlotFillingService()
        self.guardrails_service = GuardrailsService()
        self.intention_classifier = IntentionClassifier()
        self.rag_service = RAGService()
        
        # Cache de sessões em memória (em produção usar Redis)
        self.session_cache = {}
        self.tentativas_reformulacao = {}  # Controle de reformulações
        self.error_counts = {}  # NOVO: Contador de erros por sessão para anti-loop
    
    def _coerce_to_text(self, raw: str) -> str:
        """Coerção robusta de dados para texto limpo (HOTFIX GRACIOSO)"""
        if not raw:
            return ""
        
        # Remove code fences e markdown
        raw = re.sub(r"^```(?:json|md)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        
        # Tenta extrair JSON se houver
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                # Procura por campos comuns de resposta
                for field in ['text', 'mensagem', 'resposta', 'content', 'message']:
                    if field in obj and isinstance(obj[field], str):
                        return obj[field].strip()
        except Exception:
            pass
        
        # Se ainda não for JSON, devolve texto cru truncado
        return raw.strip()[:900]
    
    def _detectar_loop_erro(self, session_id: str, mensagem: str) -> bool:
        """NOVO: Detecta se está em loop de mensagens de erro"""
        if not session_id:
            return False
            
        # Frases que indicam erro/não compreensão
        frases_erro = [
            'não consegui entender',
            'não compreendi',
            'pode reformular',
            'tente novamente',
            'não ficou claro'
        ]
        
        mensagem_lower = mensagem.lower()
        is_error_message = any(frase in mensagem_lower for frase in frases_erro)
        
        if is_error_message:
            # Incrementar contador de erro para esta sessão
            self.error_counts[session_id] = self.error_counts.get(session_id, 0) + 1
            
            # Se já teve 2 ou mais erros consecutivos, está em loop
            if self.error_counts[session_id] >= 2:
                logger.warning("Loop de erro detectado", 
                             session_id=session_id, 
                             count=self.error_counts[session_id])
                return True
        else:
            # Reset contador se não é mensagem de erro
            self.error_counts[session_id] = 0
            
        return False
    
    def _gerar_resposta_transicao(self, session_state, nome_lead: str) -> Dict[str, Any]:
        """NOVO: Gera resposta de transição para quebrar loops de erro"""
        
        # Respostas específicas por estado que mudam o foco da conversa
        transicoes = {
            Estado.PATRIMONIO: f"Sem problemas, {nome_lead}! Vamos simplificar: você tem mais ou menos de 100 mil reais para investir? 1) Mais 2) Menos",
            Estado.OBJETIVO: f"Tranquilo, {nome_lead}! É simples: você quer que o dinheiro CRESÇA (tipo dobrar) ou que te PAGUE todo mês? 1) Crescer 2) Pagar mensalmente",
            Estado.URGENCIA: f"Ok {nome_lead}! Vou perguntar diferente: você quer começar a investir esta semana ou pode esperar uns meses? 1) Esta semana 2) Posso esperar",
            Estado.INTERESSE: f"Perfeito, {nome_lead}! Que tal conversarmos com um especialista que pode te ajudar melhor? 1) Sim, quero conversar 2) Não agora"
        }
        
        resposta_transicao = transicoes.get(
            session_state.estado_atual, 
            f"Vamos recomeçar, {nome_lead}! Me conta: você tem interesse em investimentos? 1) Sim 2) Não"
        )
        
        # Reset do contador de erros
        if hasattr(session_state, 'session_id'):
            self.error_counts[session_state.session_id] = 0
            
            return {
                'success': True,
            'resposta': resposta_transicao,
            'proximo_estado': session_state.estado_atual.value,
            'contexto': {},
            'score_parcial': 10,
            'loop_recovery': True  # Flag para identificar recuperação de loop
        }
    
    def _get_fallback_by_state(self, estado: Estado, nome_lead: str) -> str:
        """Fallback inteligente por estado (evita loops de desculpa)"""
        fallbacks = {
            Estado.INICIO: f"Oi {nome_lead}! Sou da LDC Capital. Posso te fazer 2 perguntas rápidas sobre investimentos? 1) Sim 2) Agora não",
            Estado.SITUACAO: f"{nome_lead}, você já investe hoje ou está começando? 1) Já invisto 2) Começando",
            Estado.PATRIMONIO: f"Perfeito {nome_lead}! Qual sua faixa de patrimônio? 1) Até 100k 2) 100k-500k 3) 500k+",
            Estado.OBJETIVO: f"Legal {nome_lead}! Qual seu principal objetivo? 1) Crescimento 2) Renda 3) Aposentadoria",
            Estado.URGENCIA: f"Entendi {nome_lead}. Quando pretende começar/aumentar? 1) Imediatamente 2) Em alguns meses",
            Estado.INTERESSE: f"Show {nome_lead}! Te interessaria um diagnóstico gratuito? 1) Sim, quero 2) Talvez depois",
            Estado.AGENDAMENTO: f"Ótimo {nome_lead}! Quando você tem 15min livres? 1) Hoje 16h 2) Amanhã 10h",
            Estado.EDUCAR: f"Sem problemas {nome_lead}! Posso te enviar material sobre investimentos? 1) Sim 2) Não",
            Estado.FINALIZADO: f"Obrigado {nome_lead}! Qualquer dúvida, estou aqui! 😊"
        }
        return fallbacks.get(estado, f"Vamos seguir {nome_lead}? Me diga como posso ajudar!")
        
    def gerar_resposta_humanizada(
        self,
        nome_lead: str,
        lead_canal: str,
        mensagem_lead: str,
        historico_conversa: List[Dict[str, str]],
        estado_atual: str,
        session_id: str = None
    ) -> Dict[str, Any]:
        """
        Gera resposta humanizada usando novo sistema estruturado
        """
        try:
            # Converter estado para enum
            estado_enum = Estado(estado_atual)

            # Obter ou criar estado da sessão
            session_state = self._get_or_create_session_state(
                session_id, nome_lead, estado_enum, historico_conversa
            )

            # Verificar limites de mensagens
            if session_state.mensagem_count >= MAX_MENSAGENS_POR_CONVERSA:
                return self._finalizar_por_limite_mensagens(session_state, nome_lead)

            # NOVO: Detectar se lead não compreendeu
            if self._detectar_nao_compreensao(mensagem_lead):
                return self._processar_reformulacao(session_state, mensagem_lead, nome_lead)

            # NOVO: Verificar se a resposta gerada anteriormente causou loop
            # (isso previne que o sistema fique gerando mensagens de erro repetidas)
            if session_id and len(historico_conversa) >= 2:
                ultima_resposta_agente = None
                for msg in reversed(historico_conversa):
                    if msg.get('tipo') == 'enviada':
                        ultima_resposta_agente = msg.get('conteudo', '')
                        break

                if ultima_resposta_agente and self._detectar_loop_erro(session_id, ultima_resposta_agente):
                    logger.info("Loop detectado, enviando mensagem de transição", session_id=session_id)
                    return self._gerar_resposta_transicao(session_state, nome_lead)

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
                session_state, mensagem_lead, lead_canal, proxima_acao, proximo_estado, nome_lead
            )

            if not resposta_ia:
                return self._gerar_fallback_response(session_state, nome_lead)

            # Atualizar estado da sessão
            session_state.estado_atual = resposta_ia.proximo_estado
            session_state.contexto = resposta_ia.contexto
            session_state.mensagem_count += 1

            # Salvar estado atualizado
            self._save_session_state(session_id, session_state)

            logger.info(
                "Resposta gerada com sucesso",
                nome_lead=nome_lead,
                estado=resposta_ia.proximo_estado,
                acao=resposta_ia.acao,
                score=resposta_ia.score_parcial
            )

            return {
                'success': True,
                'resposta': resposta_ia.mensagem,
                'acao': resposta_ia.acao,
                'proximo_estado': resposta_ia.proximo_estado,
                'contexto_atualizado': resposta_ia.contexto.model_dump(),
                'score_parcial': resposta_ia.score_parcial,
                'slots_preenchidos': session_state.slots_preenchidos(),
                'pode_agendar': session_state.pode_agendar()
            }

        except Exception as e:
            logger.error("Erro ao gerar resposta IA", error=str(e), nome_lead=nome_lead)
            return self._gerar_erro_response(estado_atual, nome_lead, str(e))
    def _get_or_create_session_state(self, session_id: str, nome_lead: str, 
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
                               nome_lead: str) -> Dict[str, Any]:
        """Processa reformulação quando lead não entende"""
        
        # Incrementar tentativas de reformulação
        key = f"{session_state.session_id}_{session_state.estado_atual}"
        tentativas = self.tentativas_reformulacao.get(key, 0) + 1
        self.tentativas_reformulacao[key] = tentativas
        
        logger.info("Processando reformulação", 
                   estado=session_state.estado_atual,
                   tentativa=tentativas,
                   nome_lead=nome_lead)
        
        # Após 2 tentativas, transferir para humano
        if tentativas > MAX_REFORMULACOES_POR_ESTADO:
            return {
                'success': True,
                'resposta': f"Me desculpa, {nome_lead}! Vou te conectar com um consultor humano que vai te explicar melhor. Um momento! 😊",
                'acao': 'transferir_humano',
                'proximo_estado': 'finalizado',
                'contexto_atualizado': session_state.contexto.model_dump(),
                'score_parcial': 20,
                'reformulacao_usada': True,
                'tentativa': tentativas
            }
        
        # Gerar reformulação específica
        reformulacao_prompt = self._gerar_prompt_reformulacao_simples(
            session_state, nome_lead, tentativas
        )
        
        resposta_reformulada = self._chamar_openai(
            reformulacao_prompt, session_state.estado_atual, nome_lead
        )
        
        if resposta_reformulada:
            return {
                'success': True,
                'resposta': resposta_reformulada.mensagem,
                'acao': resposta_reformulada.acao,
                'proximo_estado': resposta_reformulada.proximo_estado,
                'contexto_atualizado': resposta_reformulada.contexto.model_dump(),
                'score_parcial': resposta_reformulada.score_parcial,
                'reformulacao_usada': True,
                'tentativa': tentativas
            }
        
        # Fallback se reformulação falhar
        return self._gerar_fallback_response(session_state, nome_lead)
    
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
    
    def _gerar_resposta_ia(self, session_state: SessionState, ultima_mensagem_lead: str,
                          lead_canal: str, acao: Acao, proximo_estado: Estado, nome_lead: str) -> Optional[RespostaIA]:
        """Gera resposta usando IA com novo sistema de prompts"""
        
        # Construir contexto do prompt
        prompt_context = PromptContext(
            estado_atual=session_state.estado_atual,
            slots_preenchidos=session_state.slots_preenchidos(),
            slots_faltantes=session_state.slots_faltantes(),
            nome_lead=nome_lead,
            canal=lead_canal,
            ultima_mensagem_lead=ultima_mensagem_lead,
            historico_compacto=[],  # Simplificado por ora
            tentativas_estado=self.tentativas_reformulacao.get(
                f"{session_state.session_id}_{session_state.estado_atual}", 0
            ),
            contexto_rag=self.rag_service.consultar_base_conhecimento(ultima_mensagem_lead)
        )
        
        # Chamar OpenAI
        return self._chamar_openai_estruturado(prompt_context)
    
    def _chamar_openai_estruturado(self, context: PromptContext) -> Optional[RespostaIA]:
        """Chama OpenAI com novo sistema estruturado"""
        
        try:
            # 🆕 USAR NOVO SISTEMA PROFISSIONAL - FORÇA SEMPRE
            system_prompt = self.prompt_service_pro.get_system_prompt(context)
            user_prompt = self.prompt_service_pro.get_user_prompt(context)
            
            # LOG DEBUG
            logger.info("🆕 Usando sistema profissional", 
                       estado=context.estado_atual,
                       nome=context.nome_lead,
                       prompt_length=len(user_prompt))
            
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
                        "schema": {
                            "type": "object",
                            "required": ["mensagem", "acao", "proximo_estado", "contexto", "score_parcial"],
                            "properties": {
                                "mensagem": {"type": "string", "maxLength": 400},
                                "acao": {"type": "string", "enum": ["continuar", "agendar", "finalizar", "transferir_humano"]},
                                "proximo_estado": {"type": "string", "enum": ["inicio", "situacao", "patrimonio", "objetivo", "urgencia", "interesse", "agendamento", "educar", "finalizado"]},
                                "contexto": {"type": "object"},
                                "score_parcial": {"type": "integer", "minimum": 0, "maximum": 100}
                            }
                        }
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
            
            # 🔧 HOTFIX: Log detalhado do payload bruto da IA
            logger.info("🤖 IA RAW RESPONSE", 
                       raw_content=content[:1000], 
                       content_length=len(content),
                       estado=str(context.estado_atual),
                       lead=context.nome_lead)
            
            # Validar resposta
            validation_result = self.validation_service.validar_resposta_ia(
                content, context.estado_atual, context.nome_lead
            )
            
            if validation_result.valida and validation_result.resposta_corrigida:
                # Aplicar guardrails na resposta validada
                session_state = SessionState(
                    lead_id=context.nome_lead,
                    session_id=f"temp_{int(time.time())}",
                    estado_atual=context.estado_atual,
                    contexto=ContextoConversa()
                )
                
                passou, erros, resposta_corrigida = self.guardrails_service.aplicar_guardrails(
                    validation_result.resposta_corrigida, session_state, context.nome_lead
                )
                
                if passou:
                    # Se passou nos guardrails, usar resposta corrigida se existe, senão a original
                    return resposta_corrigida if resposta_corrigida else validation_result.resposta_corrigida
                else:
                    # 🔧 HOTFIX: Fallback gracioso - não quebrar a conversa
                    logger.warning("Resposta falhou nos guardrails - aplicando fallback gracioso", 
                                 errors=erros,
                                 raw_content=content[:500],
                                 estado=str(context.estado_atual))
                    
                    # Tentar coerção de dados primeiro
                    texto_coercao = self._coerce_to_text(content)
                    if texto_coercao and len(texto_coercao) > 10:
                        # Criar resposta com texto coagido
                        from backend.models.conversation_models import RespostaIA, Acao
                        return RespostaIA(
                            mensagem=texto_coercao,
                            acao=Acao.CONTINUAR,
                            proximo_estado=context.estado_atual,
                            contexto=ContextoConversa(),
                            score_parcial=50  # Score médio para fallback
                        )
                    
                    # Se coerção falhar, usar fallback por estado
                    texto_fallback = self._get_fallback_by_state(context.estado_atual, context.nome_lead)
                    return RespostaIA(
                        mensagem=texto_fallback,
                        acao=Acao.CONTINUAR,
                        proximo_estado=context.estado_atual,
                        contexto=ContextoConversa(),
                        score_parcial=40  # Score baixo para fallback
                    )
            
            # 🔧 HOTFIX: Se validação falhar, também aplicar fallback gracioso
            logger.warning("Validação IA falhou - aplicando fallback gracioso", 
                          errors=validation_result.erros, 
                          raw_content=content[:500],
                          estado=str(context.estado_atual))
            
            # Tentar coerção como último recurso
            texto_coercao = self._coerce_to_text(content)
            if texto_coercao and len(texto_coercao) > 10:
                from backend.models.conversation_models import RespostaIA, Acao
                return RespostaIA(
                    mensagem=texto_coercao,
                    acao=Acao.CONTINUAR,
                    proximo_estado=context.estado_atual,
                    contexto=ContextoConversa(),
                    score_parcial=30
                )
            
            # Fallback final por estado
            texto_fallback = self._get_fallback_by_state(context.estado_atual, context.nome_lead)
            from backend.models.conversation_models import RespostaIA, Acao
            return RespostaIA(
                mensagem=texto_fallback,
                acao=Acao.CONTINUAR,
                proximo_estado=context.estado_atual,
                contexto=ContextoConversa(),
                score_parcial=20
            )
            
        except requests.exceptions.Timeout:
            logger.error("Timeout na chamada OpenAI")

    def _gerar_prompt_reformulacao_simples(self, session_state: SessionState, nome_lead: str, tentativa: int) -> str:
        """NOVO: Gera um prompt de reformulação simples e direto."""
        
        instrucao_base = f"O lead {nome_lead} não entendeu sua última pergunta sobre {session_state.estado_atual.value}."
        
        if tentativa == 1:
            return f"{instrucao_base} Explique o mesmo ponto de uma forma diferente e mais simples. Mantenha a pergunta final."
        else: # tentativa == 2
            return f"{instrucao_base} Tente uma analogia ou um exemplo prático para explicar. Simplifique ao máximo e termine com uma pergunta de 'sim' ou 'não'."

    def _chamar_openai(self, prompt: str, estado: Estado, nome_lead: str) -> Optional[RespostaIA]:
        """Método auxiliar para chamadas simples"""
        
        context = PromptContext(
            estado_atual=estado,
            slots_preenchidos={},
            slots_faltantes=[],
            nome_lead=nome_lead,
            canal="whatsapp",
            ultima_mensagem_lead=prompt,  # Usar o prompt como a "última mensagem" para reformulação
            historico_compacto=[]
        )
        
        return self._chamar_openai_estruturado(context)
    
    def analisar_intencao_lead(self, mensagem: str) -> IntencaoLead:
        """Analisa a intenção por trás da mensagem do lead"""
        return self.intention_classifier.classificar_intencao_rapida(mensagem)
    
    def _finalizar_por_limite_mensagens(self, session_state: SessionState, 
                                       nome_lead: str) -> Dict[str, Any]:
        """Finaliza conversa por limite de mensagens"""
        
        if session_state.pode_agendar():
            return {
                'success': True,
                'resposta': f"Ótimo, {nome_lead}! Com base no que conversamos, posso te conectar com um consultor especialista. Que tal marcarmos 30 minutos? 1) amanhã 10h 2) amanhã 16h",
                'acao': 'agendar',
                'proximo_estado': 'agendamento',
                'contexto_atualizado': session_state.contexto.model_dump(),
                'score_parcial': self.slot_filling_service.calcular_score_parcial(session_state.contexto),
                'limite_atingido': True
            }
        else:
            return {
                'success': True,
                'resposta': f"Foi um prazer conversar, {nome_lead}! Vou te mandar um material sobre investimentos independentes. Posso entrar em contato em alguns dias? 1) pode sim 2) prefiro não",
                'acao': 'finalizar',
                'proximo_estado': 'educar',
                'contexto_atualizado': session_state.contexto.model_dump(),
                'score_parcial': self.slot_filling_service.calcular_score_parcial(session_state.contexto),
                'limite_atingido': True
            }
    
    def _gerar_fallback_response(self, session_state: SessionState, 
                                nome_lead: str) -> Dict[str, Any]:
        """Gera resposta de fallback quando IA falha"""
        
        fallback_resposta = self.validation_service.get_fallback_response(
            session_state.estado_atual, nome_lead
        )
        
        return {
            'success': True,
            'resposta': fallback_resposta.mensagem,
            'acao': fallback_resposta.acao,
            'proximo_estado': fallback_resposta.proximo_estado,
            'contexto_atualizado': fallback_resposta.contexto.model_dump(),
            'score_parcial': fallback_resposta.score_parcial,
            'fallback_usado': True
        }
    
    def _gerar_erro_response(self, estado_atual: str, nome_lead: str, 
                           erro: str) -> Dict[str, Any]:
        """Gera resposta de erro"""
        
        return {
            'success': False,
            'error': erro,
            'resposta': f"Desculpe, {nome_lead}. Tive um problema técnico. Pode repetir sua mensagem?",
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
            'estado_atual': session_state.estado_atual,
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
