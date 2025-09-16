"""
Serviço de Conversação com IA
Implementa conversação humanizada usando OpenAI GPT com técnicas de vendas
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
import structlog

logger = structlog.get_logger(__name__)

class AIConversationService:
    """Serviço para conversação inteligente com IA"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-3.5-turbo"
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
    def gerar_resposta_humanizada(self, 
                                  lead_nome: str,
                                  lead_canal: str,
                                  mensagem_lead: str,
                                  historico_conversa: List[Dict[str, str]],
                                  estado_atual: str) -> Dict[str, Any]:
        """
        Gera resposta humanizada usando IA com técnicas de vendas
        """
        try:
            # Construir contexto da conversa
            contexto_historico = self._construir_contexto_historico(historico_conversa)
            
            # Definir prompt baseado no estado atual
            prompt_sistema = self._get_prompt_sistema(estado_atual, lead_nome, lead_canal)
            
            # Preparar mensagens para o GPT
            messages = [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Histórico da conversa:\n{contexto_historico}\n\nÚltima mensagem do lead: {mensagem_lead}"}
            ]
            
            # Chamar OpenAI via requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            # Processar resposta
            response_data = response.json()
            resposta_json = json.loads(response_data['choices'][0]['message']['content'])
            
            logger.info("Resposta IA gerada", 
                       lead_nome=lead_nome, 
                       estado=estado_atual,
                       resposta_tipo=resposta_json.get('acao'))
            
            return {
                'success': True,
                'resposta': resposta_json.get('mensagem', ''),
                'acao': resposta_json.get('acao', 'continuar'),
                'proximo_estado': resposta_json.get('proximo_estado', estado_atual),
                'contexto_atualizado': resposta_json.get('contexto', {}),
                'score_parcial': resposta_json.get('score_parcial', 0)
            }
            
        except Exception as e:
            logger.error("Erro ao gerar resposta IA", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'resposta': "Desculpe, tive um problema técnico. Pode repetir sua mensagem?",
                'acao': 'continuar',
                'proximo_estado': estado_atual
            }
    
    def _construir_contexto_historico(self, historico: List[Dict[str, str]]) -> str:
        """Constrói contexto do histórico de conversa"""
        if not historico:
            return "Primeira interação com o lead."
        
        contexto_lines = []
        for msg in historico[-6:]:  # Últimas 6 mensagens para contexto
            tipo = "Agente" if msg['tipo'] == 'enviada' else "Lead"
            contexto_lines.append(f"{tipo}: {msg['conteudo']}")
        
        return "\n".join(contexto_lines)
    
    def _get_prompt_sistema(self, estado: str, lead_nome: str, canal: str) -> str:
        """Define prompt do sistema baseado no estado da conversa"""

        base_prompt = f"""
Você é um consultor da LDC Capital conversando com {lead_nome} (canal: {canal}).

OBJETIVO PRINCIPAL: Qualificar o lead (patrimônio, objetivo, urgência, interesse) e conduzir para um DIAGNÓSTICO GRATUITO de investimentos.

ESTRATÉGIA:
1. Abertura calorosa: cumprimente, cite o canal de origem e puxe o lead para conversa.
2. Faça no máximo 4 perguntas curtas (patrimônio, objetivo, prazo, interesse).
3. Explique brevemente o diferencial da LDC:
   - Consultoria CVM independente, modelo Fee-Based (sem comissões, sem conflito de interesse).
   - Processo estruturado: R1 (diagnóstico) → R2 (plano e carteira personalizada).
   - Mais segurança, clareza e rentabilidade do que bancos e assessorias.
4. Tom consultivo e amigável; no fechamento use leve provocação.
5. Fechamento sempre com CTA claro para agendar o diagnóstico gratuito.

REGRAS:
- Respostas de 2-3 linhas, naturais e humanizadas.
- Nunca repetir mensagens; se o lead não responder, retome de forma acolhedora.
- Finalize conduzindo ao agendamento (ex.: "Prefere hoje ou amanhã?").

FORMATO DE RESPOSTA (JSON):
{{
  "mensagem": "texto da resposta humanizada",
  "acao": "continuar|agendar|finalizar",
  "proximo_estado": "inicio|qualificacao|convencimento|agendamento|finalizado",
  "contexto": {{"patrimonio": "...", "objetivo": "...", "prazo": "..."}},
  "score_parcial": 0-100
}}
"""

        # Prompts específicos por estado
        prompts_estado = {
            "inicio": f"""
{base_prompt}

ESTADO: INÍCIO
FOCO: Cumprimento caloroso + curiosidade inicial
EXEMPLO: "Oi {lead_nome}, tudo bem? Vi que você chegou até nós pelo {canal}. Você já tem algum investimento hoje ou está começando agora?"
""",

            "saudacao": f"""
{base_prompt}

ESTADO: QUALIFICAÇÃO + CONVENCIMENTO
FOCO: Perguntas leves (patrimônio, objetivo, prazo) + diferencial LDC
EXEMPLO: "Entendi, obrigado por compartilhar! Só pra eu entender melhor: hoje você tem quanto disponível para investir? Aqui na LDC trabalhamos no modelo Fee-Based, ou seja, não ganhamos comissão de produtos, nosso único foco é você."
""",

            "agendamento": f"""
{base_prompt}

ESTADO: FECHAMENTO DO AGENDAMENTO
FOCO: Direcionar para marcar a reunião de diagnóstico gratuito
EXEMPLO: "Perfeito! Posso te agendar uma conversa de 30 minutos com um de nossos consultores. É gratuita, sem compromisso, e pode mudar completamente a forma como você investe. Prefere hoje à tarde ou amanhã de manhã?"
""",
        }

        return prompts_estado.get(estado, base_prompt)
    
    def analisar_intencao_lead(self, mensagem: str) -> Dict[str, Any]:
        """Analisa a intenção por trás da mensagem do lead"""
        try:
            prompt = f"""
Analise a mensagem do lead e identifique:

Mensagem: "{mensagem}"

Responda em JSON:
{{
  "intencao": "interesse|objecao|duvida|informacao|agendamento|recusa",
  "sentimento": "positivo|neutro|negativo",
  "urgencia": 1-10,
  "qualificacao_score": 0-100,
  "principais_pontos": ["ponto1", "ponto2"]
}}
"""
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            response_data = response.json()
            return json.loads(response_data['choices'][0]['message']['content'])
            
        except Exception as e:
            logger.error("Erro ao analisar intenção", error=str(e))
            return {
                "intencao": "duvida",
                "sentimento": "neutro", 
                "urgencia": 5,
                "qualificacao_score": 50,
                "principais_pontos": []
            }
