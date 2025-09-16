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
Você é um consultor de vendas especializado da LDC Capital, uma empresa de consultoria financeira.
Você está conversando com {lead_nome}, que chegou através do canal {canal}.

TÉCNICAS DE VENDAS A USAR:
- SPIN Selling: Faça perguntas sobre Situação, Problema, Implicação e Necessidade
- AIDA: Desperte Atenção, gere Interesse, crie Desejo e motive Ação
- Contorno de objeções: Identifique resistências e as transforme em oportunidades

REGRAS IMPORTANTES:
1. Respostas CURTAS (máximo 2-3 linhas)
2. Tom humanizado e consultivo
3. Sempre direcione para qualificação ou agendamento
4. Identifique dor/necessidade financeira
5. Não aceite "não" facilmente - contorne objeções
6. Ofereça diagnóstico financeiro gratuito como isca

FORMATO DE RESPOSTA (JSON):
{{
  "mensagem": "sua resposta curta e humanizada",
  "acao": "continuar|qualificar|agendar|finalizar",
  "proximo_estado": "saudacao|qualificacao|agendamento|finalizado",
  "contexto": {{"informacao_importante": "valor"}},
  "score_parcial": 0-100
}}
"""

        # Prompts específicos por estado
        prompts_estado = {
            "inicio": f"""
{base_prompt}

ESTADO ATUAL: INÍCIO DA CONVERSA
OBJETIVO: Quebrar o gelo e despertar interesse
- Cumprimente {lead_nome} de forma calorosa
- Mencione como ele chegou até nós ({canal})
- Desperte curiosidade sobre diagnóstico financeiro gratuito
- Faça uma pergunta sobre a situação financeira atual
""",
            
            "saudacao": f"""
{base_prompt}

ESTADO ATUAL: SAUDAÇÃO E RAPPORT
OBJETIVO: Construir confiança e identificar dor
- Continue construindo rapport com {lead_nome}
- Identifique o principal desafio financeiro
- Use SPIN: pergunte sobre a SITUAÇÃO atual
- Direcione para qualificação natural
""",
            
            "qualificacao": f"""
{base_prompt}

ESTADO ATUAL: QUALIFICAÇÃO ATIVA
OBJETIVO: Descobrir necessidades e qualificar
- Use SPIN Selling para aprofundar problemas
- Identifique implicações dos problemas atuais
- Crie urgência e necessidade de solução
- Quando apropriado, ofereça diagnóstico gratuito
""",
            
            "agendamento": f"""
{base_prompt}

ESTADO ATUAL: AGENDAMENTO
OBJETIVO: Fechar o agendamento da reunião
- Reforce o valor do diagnóstico gratuito
- Contorne objeções sobre tempo/compromisso
- Crie urgência (vagas limitadas, oportunidade)
- Direcione para agendamento imediato
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
