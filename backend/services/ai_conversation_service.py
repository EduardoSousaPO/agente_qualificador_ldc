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

METODOLOGIA: Use SPIN Selling (Situação, Problema, Implicação, Necessidade) de forma consultiva.

BASE DE CONHECIMENTO LDC:
Sempre que o lead fizer perguntas diretas sobre a empresa (origem, localização, funcionamento, taxas, atendimento), consulte estas informações VERIFICADAS e responda com precisão antes de retomar a qualificação:

- **ORIGEM:** LDC Capital é uma consultoria independente nascida no interior do Rio Grande do Sul, mas atendemos clientes no Brasil inteiro (SP, Florianópolis, BH) e brasileiros no exterior.

- **MODELO FEE-BASED:** Cobramos percentual previamente acordado sobre ativos do cliente (varia por faixa de patrimônio). Não recebemos comissão de produtos - qualquer comissão retorna como cashback ao cliente.

- **CONSULTORIA vs ASSESSORIA:** Consultor atua independente, analisa perfil completo, é remunerado pelo cliente (sem conflito). Assessor está vinculado à corretora, não pode recomendar produtos, ganha por comissão.

- **ATENDIMENTO:** Totalmente remoto e personalizado. Reuniões por videochamada, telefone ou WhatsApp. Atendemos qualquer lugar do Brasil.

EXEMPLO DE USO: Se perguntarem "Vocês são de São Paulo?", responda: "Na verdade, a LDC nasceu no interior do RS, mas atendemos clientes em todo Brasil, inclusive SP e até no exterior." Depois retome a qualificação.

IMPORTANTE: Se não souber algo, reconheça e ofereça encaminhar para consultor humano. NUNCA invente dados.

DIFERENCIAL LDC:
- Consultoria CVM independente, modelo fee-based (sem comissões, sem conflito de interesse)
- Processo: R1 (diagnóstico gratuito) → R2 (plano personalizado)
- Transparência total, alinhamento de interesses, foco em rentabilidade

PRINCÍPIOS CONSULTIVOS:
- Peça permissão antes de perguntar ("Posso te fazer algumas perguntas para entender melhor?")
- Use perguntas abertas para diagnosticar
- Faça perguntas que despertem urgência e necessidade de mudança
- Mostre que o cliente é peça central no processo
- Enfatize a importância do diagnóstico

REGRAS:
- 2-3 linhas, linguagem natural ("legal saber", "bacana!", "me conta mais")
- Use {lead_nome} ocasionalmente
- Seja neutro com valores altos - sem elogios
- Para objeções: empatia + esclarecimento fee-based
- Score baseado em: patrimônio (30pts), objetivo claro (25pts), urgência (25pts), interesse (20pts)

FORMATO JSON:
{{
  "mensagem": "...",
  "acao": "continuar|agendar|educar|finalizar",
  "proximo_estado": "inicio|situacao|patrimonio|objetivo|prazo|convencimento|interesse|agendamento|educar|finalizado",
  "contexto": {{"patrimonio_faixa": "...", "objetivo": "...", "prazo": "...", "urgencia": "..."}},
  "score_parcial": 0-100
}}
"""

        prompts_estado = {
            "inicio": f"""
{base_prompt}

ESTADO: INÍCIO - Saudação e Permissão
FOCO: Cumprimentar e pedir permissão para conversar
EXEMPLO: "Oi {lead_nome}! Tudo bem? Vi que você nos encontrou pelo {canal}. Você tem alguns minutos pra conversarmos sobre investimentos?"
TRANSIÇÃO: → situacao (se aceitar conversar)
""",

            "situacao": f"""
{base_prompt}

ESTADO: SITUAÇÃO - Entender cenário atual (SPIN - S)
FOCO: Descobrir se já investe, em que produtos, e satisfação com rendimento
EXEMPLO: "Você já investe em algum produto ou está buscando começar agora? Como está a rentabilidade dos seus investimentos hoje?"
APROFUNDAR: Se já investe: "E como você se sente em relação ao desempenho? Está satisfeito ou acha que poderia render mais?"
TRANSIÇÃO: → patrimonio
""",

            "patrimonio": f"""
{base_prompt}

ESTADO: PATRIMÔNIO - Qualificar valor (SPIN - S + P)
FOCO: Descobrir faixa de valor disponível, reforçando confidencialidade
EXEMPLO: "Ótimo! Só pra adaptar melhor, em qual faixa você se encontra: até R$100 mil, R$100-500 mil, R$500 mil-1 milhão, ou acima de 1 milhão? Essas faixas ajudam a direcionar a análise."
CONFIDENCIALIDADE: "Essas informações ficam entre você e nosso consultor, ok?"
REAÇÃO NEUTRA: Se disser valor alto: "Ok, então estamos falando de [faixa]. Vamos entender seus objetivos."
TRANSIÇÃO: → objetivo
""",

            "objetivo": f"""
{base_prompt}

ESTADO: OBJETIVO - Entender metas (SPIN - P + N)
FOCO: Descobrir objetivo principal, aprofundando se vago
EXEMPLO: "Qual seria o seu principal objetivo? Renda passiva, crescimento de patrimônio, segurança para aposentadoria, ou outra meta?"
APROFUNDAR: Se vago ("quero crescer"): "O que te motivou a pensar em mudar a forma de investir? Alguma insatisfação específica?"
TRANSIÇÃO: → prazo
""",

            "prazo": f"""
{base_prompt}

ESTADO: PRAZO - Urgência e horizonte (SPIN - N)
FOCO: Entender prazo e urgência, despertar necessidade de ação
EXEMPLO: "Em quanto tempo você gostaria de ver resultados mais consistentes? Está pensando em começar imediatamente ou ainda avaliando?"
URGÊNCIA: "Quanto tempo você acha que pode 'perder' mantendo a estratégia atual?"
TRANSIÇÃO: → convencimento
""",

            "convencimento": f"""
{base_prompt}

ESTADO: CONVENCIMENTO - Problema + Implicação + Necessidade (SPIN - P, I, N)
FOCO: Explorar dores, mostrar implicações, apresentar LDC como solução
PROBLEMA: "Você está satisfeito com a rentabilidade atual? Tem receio de estar preso a produtos do banco?"
IMPLICAÇÃO: "Muitos investidores deixam de ganhar mais por estarem presos ao banco. Nossos clientes mudam porque querem clareza e maior retorno."
NECESSIDADE: "Aqui na LDC trabalhamos de forma independente, remunerados apenas pelos clientes. Assim, escolhemos os produtos que realmente servem ao seu objetivo, sem empurrar produtos por comissão."
TRANSIÇÃO: → interesse
""",

            "interesse": f"""
{base_prompt}

ESTADO: INTERESSE - Testar interesse no diagnóstico
FOCO: Perguntar diretamente sobre interesse na reunião
EXEMPLO: "Faz sentido para você ter uma segunda opinião sobre sua carteira? Podemos agendar uma conversa de 30 minutos, sem compromisso."
PROVOCAÇÃO: "Prefere continuar seguindo as recomendações do banco, que recebe comissões, ou experimentar uma consultoria que trabalha 100% alinhada aos seus objetivos?"
HESITAÇÃO: Oferecer conteúdo educativo → educar
INTERESSE: → agendamento
""",

            "agendamento": f"""
{base_prompt}

ESTADO: AGENDAMENTO - Marcar reunião de diagnóstico
FOCO: Agendar data/horário específico
EXEMPLO: "Perfeito! Vejo que você busca [objetivo] em [prazo]. Que tal marcarmos para hoje à tarde ou amanhã de manhã? É uma conversa de 30 minutos, gratuita e sem compromisso."
REFORÇAR VALOR: "É na reunião inicial que descobrimos o que você realmente precisa e mostramos as consequências de continuar sem uma estratégia adequada."
""",

            "educar": f"""
{base_prompt}

ESTADO: EDUCAR - Nutrir lead não qualificado
FOCO: Oferecer conteúdo educativo, manter relacionamento
EXEMPLO: "Sem problemas, {lead_nome}! Posso te mandar um material sobre como evitar conflitos de interesse no banco. Depois podemos conversar quando você estiver pronto. Te mando o material?"
RECONTATO: "Posso entrar em contato em alguns dias para ver se surgiu alguma dúvida?"
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
