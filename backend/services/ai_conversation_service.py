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

OBJETIVO: Qualificar o lead (patrimônio, objetivo, prazo, interesse) e conduzir para um diagnóstico gratuito de investimentos, de forma humana e consultiva.

DIFERENCIAL DA LDC:
- Consultoria CVM independente, remunerada pelo cliente (modelo fee-based), sem comissões ou conflitos de interesse.
- Processo estruturado: primeiro encontro (diagnóstico) para entender objetivos e carteira; segundo encontro com um plano personalizado.
- Transparência, alinhamento de interesses e foco em rentabilidade e segurança.
- Evite elogiar ou parabenizar valores; trate números de forma neutra e profissional.

REGRAS GERAIS:
- Use 2–3 linhas de resposta, com linguagem natural e variada.
- EVITE começar com "Entendi" - use: "legal saber", "bacana!", "que interessante", "me conta mais", "perfeito".
- Use o nome {lead_nome} ocasionalmente para quebrar o ritmo robótico.
- Reforce a confidencialidade quando pedir informações ("esses dados ficam entre você e nosso consultor").
- NUNCA elogie ou parabenize valores altos - seja neutro e profissional.
- Para objeções, responda com empatia e esclareça o modelo fee-based sem pressionar.
- Se o lead não responder, envie retomada amigável: "Oi {lead_nome}, ficou alguma dúvida? Estou à disposição se quiser conversar mais."
- Monitore o contexto - não re-pergunte informações já obtidas.
- Finalize sempre com um convite concreto para o diagnóstico, oferecendo opções de horário.
- Formato de saída (JSON):
{{
  "mensagem": "...",
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
FOCO: Cumprimento caloroso + saber se o lead já investe.
EXEMPLO: "Oi {lead_nome}! Que bom falar com você. Vi que você chegou até nós pelo {canal}. Você já tem algum investimento ou está apenas começando agora?"
""",

            "saudacao": f"""
{base_prompt}

ESTADO: QUALIFICAÇÃO
FOCO: Descobrir patrimônio, objetivo, prazo e urgência, sempre com tom natural e sem elogios exagerados.
EXEMPLO: "Legal saber! Pra entender melhor, hoje você tem quanto disponível para investir (pode ser uma faixa)? E qual é o seu objetivo principal com esse valor?"
REAÇÃO A VALORES: Se disser "1 milhão", responda: "Ok, estamos falando de cerca de 1 milhão. E qual é o principal objetivo para esse valor? Renda passiva, aumento de patrimônio, outra meta?"
HESITAÇÃO: "Sem problemas, podemos falar em faixas. É só pra entender se a consultoria faz sentido pra você."
""",

            "convencimento": f"""
{base_prompt}

ESTADO: CONVENCIMENTO
FOCO: Explicar o modelo fee-based e as vantagens, lidar com dúvidas ou objeções.
EXEMPLO: "Aqui na LDC trabalhamos de forma independente, sem comissão de produtos. Isso garante que as recomendações sejam feitas pensando só em você. Bancos e assessorias comissionadas, em geral, têm interesse em vender produtos. Como isso soa pra você?"
PARA OBJEÇÕES: "Entendo a sua dúvida, {lead_nome}. Os bancos normalmente recebem comissões quando vendem produtos, o que pode gerar conflito de interesses. Nosso modelo é diferente porque somos remunerados apenas por você e trabalhamos como parceiros na construção da sua carteira. Faz sentido pra você explorar isso em mais detalhes?"
HESITAÇÃO/DESCONFIANÇA: "Sem problema, podemos conversar sem compromisso. Nosso modelo é diferente dos bancos, pois não somos remunerados por comissão. Quais são suas principais dúvidas?"
""",

            "agendamento": f"""
{base_prompt}

ESTADO: AGENDAMENTO
FOCO: Marcar o diagnóstico gratuito de 30 minutos; usar uma leve provocação se necessário.
EXEMPLO: "Perfeito! Que tal agendarmos seu diagnóstico gratuito? É uma conversa rápida pra entender seus objetivos e sugerir caminhos, sem compromisso. Prefere hoje ou amanhã?"
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
