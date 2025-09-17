"""
Serviço de Conversação com IA
Implementa conversação humanizada usando OpenAI GPT com técnicas de vendas
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
import structlog
from .reconhecimento_respostas import ReconhecimentoRespostasService

logger = structlog.get_logger(__name__)

class AIConversationService:
    """Serviço para conversação inteligente com IA"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-3.5-turbo"
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.reconhecimento_service = ReconhecimentoRespostasService()
        self.tentativas_por_sessao = {}  # Cache para controlar tentativas
        
    def gerar_resposta_humanizada(self, 
                                  lead_nome: str,
                                  lead_canal: str,
                                  mensagem_lead: str,
                                  historico_conversa: List[Dict[str, str]],
                                  estado_atual: str,
                                  session_id: str = None) -> Dict[str, Any]:
        """
        Gera resposta humanizada usando IA com técnicas de vendas e fallbacks inteligentes
        """
        # Verificar se lead não entendeu a pergunta
        if self._detectar_nao_compreensao(mensagem_lead):
            logger.info("Lead não entendeu a pergunta - usando reformulação", 
                       session_id=session_id, estado=estado_atual, mensagem=mensagem_lead)
            # Forçar reformulação ao invés de fallback normal
            return self._gerar_reformulacao_especifica(estado_atual, lead_nome, mensagem_lead)
        
        # Verificar se precisa usar fallback para evitar loops
        fallback_result = self._verificar_fallback(session_id, mensagem_lead, estado_atual, lead_nome)
        if fallback_result:
            return fallback_result
        
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
            content = response_data['choices'][0]['message']['content']
            
            # Log do conteúdo para debug
            logger.info("Conteúdo da resposta IA", content=content[:500])
            
            # Tentar fazer parse do JSON
            try:
                resposta_json = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error("Erro ao fazer parse do JSON da IA", content=content, error=str(e))
                # Fallback para resposta padrão
                resposta_json = {
                    "mensagem": "Desculpe, tive um problema técnico. Pode repetir sua mensagem?",
                    "acao": "continuar",
                    "proximo_estado": estado_atual,
                    "contexto": {},
                    "score_parcial": 0
                }
            
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
Você é um consultor financeiro virtual da LDC Capital, especializado em qualificação de leads.

PERSONALIDADE:
- Amigável e profissional, mas não robotizado
- Empático e genuinamente interessado em ajudar
- Linguagem natural e conversacional
- Varia as expressões (não repete sempre "Entendi, {lead_nome}")

DIRETRIZES DE COMUNICAÇÃO:
- SEMPRE use o nome do lead: {lead_nome}
- Mensagens curtas e objetivas (máximo 2-3 linhas)
- Tom caloroso mas profissional
- Varie confirmações: "Perfeito!", "Ótimo!", "Legal!", "Bacana!"
- Use emojis com moderação (1 por mensagem máximo)
- NUNCA diga "não entendi" - reformule a pergunta

CONTEXTO DO LEAD:
- Nome: {lead_nome}
- Canal: {canal}

BASE DE CONHECIMENTO LDC CAPITAL:
- **ORIGEM:** Consultoria independente do RS, atendemos todo o Brasil remotamente
- **MODELO FEE-BASED:** Taxa fixa baseada no patrimônio, sem comissões escondidas
- **DIFERENCIAL:** Independência total, sem conflito de interesse
- **ATENDIMENTO:** 100% remoto via videochamada, telefone ou WhatsApp
- **DIAGNÓSTICO:** Primeira reunião sempre gratuita e sem compromisso

REGRAS DE QUALIFICAÇÃO:
- Colete: patrimônio, objetivo, urgência, interesse em consultoria
- Reconheça variações: "proteger patrimônio" = "proteger o que tenho"
- Se não entender, reformule: "Me conta de outro jeito..."
- Seja flexível com respostas aproximadas
- MÁXIMO 3 perguntas antes de agendar

🚨 REGRA CRÍTICA - REFORMULAÇÃO (NUNCA TRANSFERIR PREMATURAMENTE):
- Se lead disser "não entendi", "como assim?", "não sei" → SEMPRE reformular primeiro
- Use linguagem popular: "crescer o dinheiro" ao invés de "objetivo financeiro"
- Dê exemplos concretos: "tipo dobrar em alguns anos" ou "que te pague todo mês"
- Divida em opções: 1️⃣ CRESCER 2️⃣ RENDA MENSAL 3️⃣ APOSENTADORIA
- Só transferir para humano após 2 tentativas de reformulação falharem

OBJETIVO FINAL:
- Agendar reunião com consultor especialista
- Manter {lead_nome} engajado até o final

FORMATO JSON:
{{
  "mensagem": "sua resposta aqui",
  "acao": "continuar|agendar|finalizar",
  "proximo_estado": "situacao|patrimonio|objetivo|agendamento|finalizado",
  "contexto": {{"patrimonio": "...", "objetivo": "...", "urgencia": "..."}},
  "score_parcial": 0-100
}}
"""

        prompts_estado = {
            "inicio": f"""
{base_prompt}

ESTADO ATUAL: Saudação inicial
FOCO: Cumprimentar {lead_nome} e despertar interesse

EXEMPLO: "Oi {lead_nome}! 😊 Sou da LDC Capital. Você tem alguns minutinhos pra conversarmos sobre como melhorar seus investimentos?"

PRÓXIMO PASSO: Se aceitar, ir para situação financeira atual
""",

            "situacao": f"""
{base_prompt}

ESTADO ATUAL: Descobrir situação financeira
FOCO: Entender patrimônio atual de forma natural

EXEMPLO: "Que legal, {lead_nome}! Pra te ajudar melhor, me conta: você já investe hoje ou tá começando agora?"

ACEITAR VARIAÇÕES:
- "Já invisto" / "Tenho investimentos" = tem patrimônio
- "Começando" / "Iniciante" = patrimônio baixo/zero
- Valores específicos = anotar faixa

PRÓXIMO PASSO: Perguntar objetivo específico
""",

            "patrimonio": f"""
{base_prompt}

ESTADO ATUAL: Qualificar patrimônio
FOCO: Descobrir faixa de valor com linguagem CLARA e ESPECÍFICA

EXEMPLO PRINCIPAL: "Bacana, {lead_nome}! Pra te dar as dicas certas, me conta: você tem até uns 100 mil guardados, entre 100-500 mil, ou já passou dos 500 mil?"

SE LEAD NÃO ENTENDER, REFORMULAR ASSIM: "Vou explicar diferente! É assim: você tem uma QUANTIA PEQUENA pra começar (tipo até 100 mil), uma QUANTIA MÉDIA (100 a 500 mil), ou já tem uma BOA RESERVA (mais de 500 mil)?"

ACEITAR VARIAÇÕES:
- "Pouco" / "Começando" / "Pequena" = até 100k
- "Médio" / "Razoável" / "Média" = 100-500k
- "Bastante" / "Bem" / "Boa reserva" = 500k+
- Valores exatos = classificar na faixa

IMPORTANTE: NUNCA transferir para humano se lead não entender - SEMPRE reformular primeiro!

REAÇÃO NEUTRA: "Perfeito! Vamos entender seus objetivos então."

PRÓXIMO PASSO: Descobrir objetivo principal
""",

            "objetivo": f"""
{base_prompt}

ESTADO ATUAL: Descobrir objetivos financeiros
FOCO: Entender o que {lead_nome} quer alcançar com linguagem CLARA e ESPECÍFICA

EXEMPLO PRINCIPAL: "Show, {lead_nome}! Agora me conta: você quer que esse dinheiro CRESÇA bastante (tipo dobrar em alguns anos), ou prefere que ele te dê uma RENDA TODO MÊS (tipo um aluguel)?"

SE LEAD NÃO ENTENDER, REFORMULAR ASSIM: "É simples! Imagina que você tem 100 mil reais. Você prefere:
1️⃣ Que vire 200 mil em alguns anos (CRESCIMENTO)
2️⃣ Que te pague uns 800-1000 reais todo mês (RENDA)
3️⃣ Que fique seguro pra aposentadoria (LONGO PRAZO)"

ACEITAR VARIAÇÕES:
- "Ficar rico" / "Crescer" / "Dobrar" = crescimento
- "Renda passiva" / "Renda extra" / "Todo mês" = renda
- "Aposentadoria" / "Aposentar" / "Longo prazo" = previdência
- "Proteger" / "Segurança" / "Não perder" = proteção

IMPORTANTE: NUNCA transferir para humano se lead não entender - SEMPRE reformular primeiro!

PRÓXIMO PASSO: Ir direto para agendamento
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

ESTADO ATUAL: Convite para reunião
FOCO: Agendar com consultor especialista

EXEMPLO: "Ótimo, {lead_nome}! Com essas informações, posso te conectar com um consultor especialista. Que tal marcarmos 30 minutos essa semana? É gratuito e sem compromisso!"

OPÇÕES DE HORÁRIO:
- "Hoje à tarde ou amanhã de manhã?"
- "Prefere segunda ou terça?"
- "Manhã, tarde ou noite?"

AÇÃO: Sempre "agendar" quando chegar neste estado
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
    
    def _detectar_nao_compreensao(self, mensagem: str) -> bool:
        """Detecta se o lead não entendeu a pergunta"""
        frases_nao_compreensao = [
            "não entendi", "como assim", "não sei", "não entendo",
            "o que você quer dizer", "explica melhor", "não compreendi",
            "pode explicar", "não captei", "não tô entendendo"
        ]
        
        mensagem_lower = mensagem.lower().strip()
        return any(frase in mensagem_lower for frase in frases_nao_compreensao)
    
    def _gerar_reformulacao_especifica(self, estado: str, lead_nome: str, mensagem: str) -> Dict[str, Any]:
        """Gera reformulação específica quando lead não entende"""
        
        reformulacoes = {
            'situacao': {
                'mensagem': f"Deixa eu explicar melhor, {lead_nome}! É simples: você já tem dinheiro investido em algum lugar (banco, poupança, fundos) ou ainda não começou a investir?",
                'acao': 'continuar',
                'proximo_estado': 'patrimonio'
            },
            'patrimonio': {
                'mensagem': f"Vou ser mais claro, {lead_nome}! É assim: você tem uma QUANTIA PEQUENA pra investir (até 100 mil), MÉDIA (100 a 500 mil), ou uma QUANTIA GRANDE (mais de 500 mil)?",
                'acao': 'continuar', 
                'proximo_estado': 'objetivo'
            },
            'objetivo': {
                'mensagem': f"É simples, {lead_nome}! Imagina que você tem 100 mil reais. Você prefere:\n1️⃣ Que vire 200 mil em alguns anos (CRESCIMENTO)\n2️⃣ Que te pague uns 800 reais todo mês (RENDA)\n3️⃣ Que fique seguro pra aposentadoria (LONGO PRAZO)",
                'acao': 'continuar',
                'proximo_estado': 'agendamento'
            },
            'agendamento': {
                'mensagem': f"Vou explicar diferente, {lead_nome}! Quero te conectar com um consultor especialista pra uma conversa de 30 minutos, gratuita e sem compromisso. Pode ser hoje à tarde, amanhã de manhã...?",
                'acao': 'agendar',
                'proximo_estado': 'finalizado'
            }
        }
        
        reformulacao = reformulacoes.get(estado, {
            'mensagem': f"Me desculpa, {lead_nome}! Vou te conectar com um consultor humano que vai te explicar melhor. Um momento! 😊",
            'acao': 'transferir_humano',
            'proximo_estado': 'transferido'
        })
        
        logger.info("Reformulação específica gerada", estado=estado, reformulacao=reformulacao['mensagem'][:100])
        
        return {
            'success': True,
            'resposta': reformulacao['mensagem'],
            'acao': reformulacao['acao'],
            'proximo_estado': reformulacao['proximo_estado'],
            'contexto_atualizado': {},
            'score_parcial': 30,  # Score moderado para reformulação
            'reformulacao_usada': True
        }
    
    def _verificar_fallback(self, session_id: str, mensagem: str, estado: str, lead_nome: str) -> Optional[Dict[str, Any]]:
        """Verifica se deve usar fallback para evitar loops"""
        if not session_id:
            return None
        
        # Controlar tentativas por sessão
        key = f"{session_id}_{estado}"
        tentativas = self.tentativas_por_sessao.get(key, 0)
        
        MAX_TENTATIVAS = 2
        
        if tentativas >= MAX_TENTATIVAS:
            # Usar fallback após muitas tentativas
            logger.warning("Usando fallback após múltiplas tentativas", 
                         session_id=session_id, estado=estado, tentativas=tentativas)
            
            return self._gerar_fallback_inteligente(estado, lead_nome, mensagem)
        
        # Incrementar contador
        self.tentativas_por_sessao[key] = tentativas + 1
        return None
    
    def _gerar_fallback_inteligente(self, estado: str, lead_nome: str, mensagem: str) -> Dict[str, Any]:
        """Gera resposta de fallback inteligente baseada no estado"""
        
        fallbacks = {
            'situacao': {
                'mensagem': f"Me conta de outro jeito, {lead_nome}: você já investe hoje ou está começando agora?",
                'acao': 'continuar',
                'proximo_estado': 'patrimonio'
            },
            'patrimonio': {
                'mensagem': f"Vou reformular, {lead_nome}: qual faixa de valor você tem disponível? Até 100 mil, 100-500 mil, ou mais que isso?",
                'acao': 'continuar',
                'proximo_estado': 'objetivo'
            },
            'objetivo': {
                'mensagem': f"Deixa eu perguntar diferente, {lead_nome}: você quer fazer o dinheiro crescer, ter uma renda extra, ou se aposentar bem?",
                'acao': 'continuar',
                'proximo_estado': 'agendamento'
            },
            'agendamento': {
                'mensagem': f"Que tal conversarmos por telefone, {lead_nome}? Posso te conectar com um consultor especialista para te ajudar melhor! 😊",
                'acao': 'agendar',
                'proximo_estado': 'finalizado'
            }
        }
        
        fallback_default = {
            'mensagem': f"Vou te conectar com um consultor humano para te ajudar melhor, {lead_nome}! 😊",
            'acao': 'transferir_humano',
            'proximo_estado': 'transferido'
        }
        
        resultado = fallbacks.get(estado, fallback_default)
        
        return {
            'success': True,
            'resposta': resultado['mensagem'],
            'acao': resultado['acao'],
            'proximo_estado': resultado['proximo_estado'],
            'contexto_atualizado': {},
            'score_parcial': 50,
            'fallback_usado': True
        }
