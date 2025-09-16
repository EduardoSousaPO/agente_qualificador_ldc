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

OBJETIVO PRINCIPAL: Agendar um DIAGNÓSTICO GRATUITO de carteira de investimentos.

ESTRATÉGIA SIMPLES:
1. Seja caloroso e direto
2. Identifique rapidamente a situação financeira atual
3. Ofereça o diagnóstico gratuito como solução
4. Direcione para agendamento o mais rápido possível
5. Não faça muitas perguntas - seja consultivo

ABORDAGEM:
- Cumprimente e identifique o interesse
- Pergunte sobre a situação atual de investimentos (1-2 perguntas máximo)
- Ofereça diagnóstico gratuito personalizado
- Agende a conversa com consultor especializado

REGRAS:
- Respostas de 1-2 linhas máximo
- Foque no VALOR do diagnóstico gratuito
- Crie urgência mas sem pressão
- Seja natural e consultivo

FORMATO DE RESPOSTA (JSON):
{{
  "mensagem": "resposta curta focada no agendamento",
  "acao": "continuar|agendar|finalizar",
  "proximo_estado": "saudacao|agendamento|finalizado",
  "contexto": {{"info": "valor"}},
  "score_parcial": 0-100
}}
"""

        # Prompts específicos por estado
        prompts_estado = {
            "inicio": f"""
{base_prompt}

ESTADO: INÍCIO - Primeira impressão é tudo!
FOCO: Cumprimento caloroso + oferta direta
EXEMPLO: "Oi {lead_nome}! Vi que você se interessou por investimentos através do {canal}. Que bom! 
Você já tem algum investimento ou está começando agora? Posso te oferecer um diagnóstico gratuito da sua carteira!"
""",
            
            "saudacao": f"""
{base_prompt}

ESTADO: CONSTRUINDO CONFIANÇA
FOCO: Identificar situação + oferecer diagnóstico
EXEMPLO: "Entendi! Então você quer fazer seu dinheiro render mais, né? 
Olha, faço diagnósticos gratuitos de carteira pra pessoas como você. Quer que eu analise sua situação?"
""",
            
            "agendamento": f"""
{base_prompt}

ESTADO: FECHAMENTO DO AGENDAMENTO
FOCO: Agendar a conversa com consultor
EXEMPLO: "Perfeito! Vou te conectar com um dos nossos consultores especialistas. 
É uma conversa de 30 minutos, sem compromisso. Prefere hoje à tarde ou amanhã de manhã?"
AÇÃO: Sempre termine direcionando para agendamento específico
"""
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
