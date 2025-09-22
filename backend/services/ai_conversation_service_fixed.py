"""
🔧 VERSÃO CORRIGIDA DO SERVIÇO DE CONVERSAÇÃO
Sistema simplificado que funciona com prompts profissionais
"""

import os
import json
import requests
import time
from typing import Dict, Any, List, Optional
import structlog

from .prompt_service_pro import PromptServicePro
from backend.models.conversation_models import Estado, PromptContext

logger = structlog.get_logger(__name__)

class AIConversationServiceFixed:
    """Versão simplificada e funcional do serviço de conversação"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-4o-mini"
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.prompt_service_pro = PromptServicePro()
    
    def gerar_resposta_humanizada(self, 
                                  lead_nome: str,
                                  lead_canal: str,
                                  mensagem_lead: str,
                                  historico_conversa: List[Dict[str, str]],
                                  estado_atual: str,
                                  session_id: str = None) -> Dict[str, Any]:
        """Gera resposta humanizada usando sistema profissional"""
        
        try:
            # Converter estado
            try:
                estado_enum = Estado(estado_atual)
            except:
                estado_enum = Estado.INICIO
            
            # Criar contexto
            context = PromptContext(
                estado_atual=estado_enum,
                slots_preenchidos={},
                slots_faltantes=[],
                nome_lead=lead_nome,
                canal=lead_canal,
                ultima_mensagem_lead=mensagem_lead,
                historico_compacto=historico_conversa[-6:] if historico_conversa else []
            )
            
            # Gerar resposta profissional
            resposta = self._chamar_openai_profissional(context)
            
            if resposta:
                logger.info("✅ Resposta profissional gerada", 
                           nome=lead_nome, 
                           estado=estado_atual,
                           resposta_preview=resposta[:50])
                
                return {
                    'success': True,
                    'resposta': resposta,
                    'acao': 'continuar',
                    'proximo_estado': self._determinar_proximo_estado(estado_atual),
                    'contexto_atualizado': {},
                    'score_parcial': 60
                }
            else:
                # Fallback profissional
                resposta_fallback = self._get_fallback_profissional(lead_nome, estado_atual)
                
                return {
                    'success': True,
                    'resposta': resposta_fallback,
                    'acao': 'continuar', 
                    'proximo_estado': self._determinar_proximo_estado(estado_atual),
                    'contexto_atualizado': {},
                    'score_parcial': 40,
                    'fallback_usado': True
                }
                
        except Exception as e:
            logger.error("Erro na geração de resposta", error=str(e))
            
            # Fallback de emergência
            return {
                'success': True,
                'resposta': f"Oi {lead_nome}! Sou Rafael da LDC Capital. Como posso te ajudar com investimentos? 1) quero saber mais 2) depois",
                'acao': 'continuar',
                'proximo_estado': 'inicio',
                'contexto_atualizado': {},
                'score_parcial': 30,
                'erro_recuperado': True
            }
    
    def _chamar_openai_profissional(self, context: PromptContext) -> Optional[str]:
        """Chama OpenAI com sistema profissional"""
        
        try:
            # Usar sistema profissional
            system_prompt = self.prompt_service_pro.system_prompt
            user_prompt = self.prompt_service_pro.build_contextualized_prompt(context)
            
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
                "max_tokens": 200,
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            
            # Extrair mensagem do JSON
            try:
                json_response = json.loads(content)
                return json_response.get('mensagem', '').strip()
            except:
                # Se não for JSON válido, usar como texto
                return content.strip()
                
        except Exception as e:
            logger.error("Erro na chamada OpenAI", error=str(e))
            return None
    
    def _get_fallback_profissional(self, nome: str, estado: str) -> str:
        """Fallback profissional por estado"""
        
        fallbacks = {
            'inicio': f"Oi {nome}! Sou Rafael, consultor da LDC Capital. Você tem interesse em investimentos? 1) sim, tenho interesse 2) não agora",
            
            'situacao': f"Legal, {nome}! Para te orientar melhor: você já investe hoje ou está começando? 1) já invisto 2) estou começando",
            
            'patrimonio': f"Entendi, {nome}. Você está mais na fase de acumular ainda ou já tem uma reserva boa formada? 1) ainda acumulando 2) já tenho reserva",
            
            'objetivo': f"Perfeito, {nome}! O que te atrai mais: 1) fazer o dinheiro crescer 2) gerar renda extra 3) preparar aposentadoria",
            
            'urgencia': f"Show, {nome}! E sobre timing: 1) quero começar logo 2) nos próximos meses 3) sem pressa",
            
            'interesse': f"Baseado no que você falou, {nome}, faz sentido um diagnóstico gratuito de 30 min. Te interessaria? 1) sim 2) talvez",
            
            'agendamento': f"Ótimo, {nome}! Posso te encaixar: 1) amanhã às 10h 2) amanhã às 16h 3) outro horário"
        }
        
        return fallbacks.get(estado, f"Entendi, {nome}! Como posso te ajudar melhor? 1) continuar conversa 2) agendar diagnóstico")
    
    def _determinar_proximo_estado(self, estado_atual: str) -> str:
        """Determina próximo estado logicamente"""
        
        fluxo = {
            'inicio': 'situacao',
            'situacao': 'patrimonio', 
            'patrimonio': 'objetivo',
            'objetivo': 'urgencia',
            'urgencia': 'interesse',
            'interesse': 'agendamento',
            'agendamento': 'finalizado'
        }
        
        return fluxo.get(estado_atual, 'finalizado')
