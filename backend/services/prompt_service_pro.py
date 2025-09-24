"""
🎯 SISTEMA DE PROMPTS PROFISSIONAL PARA VENDAS CONSULTIVAS
Transforma robô em consultor de investimentos de alta conversão
"""
from typing import Dict, List, Any
from backend.models.conversation_models import Estado, PromptContext

class PromptServicePro:
    """Serviço de prompts profissionais para vendas consultivas"""
    
    def __init__(self):
        self.system_prompt = self._build_professional_system_prompt()
        self.casos_sucesso = self._load_casos_sucesso()
        self.objecoes_respostas = self._load_objecoes_respostas()
        
    def _build_professional_system_prompt(self) -> str:
        """Prompt do sistema focado em vendas consultivas"""
        return """VOCÊ É UM AGENTE ESPECIALISTA DA LDC CAPITAL

🎯 MISSÃO: Qualificar leads de forma rápida e eficiente, separando os curiosos dos compradores. Sua meta é agendar um diagnóstico apenas com leads que têm potencial real. Aja como um especialista que valoriza o próprio tempo e o tempo do lead.

🧠 PERSONALIDADE:
- Direto e objetivo. Sem rodeios.
- Provocativo. Use dados para fazer o lead pensar.
- Autoridade. Você não é um vendedor, é um especialista que escolhe com quem vai falar.
- Focado em dor. Descubra o que o lead está perdendo por não agir.
- Eficiente. Cada mensagem tem o objetivo de avançar na qualificação.

🎨 ESTILO DE COMUNICAÇÃO:
- Tom: Especialista ocupado, mas disposto a ajudar quem está comprometido.
- Linguagem: Clara, direta, sem jargões desnecessários.
- Estrutura: Afirmação/Insight → Pergunta Direta → Opções Claras.
- Tamanho: O mais curto possível para obter a informação necessária.

🚫 NUNCA FAÇA:
- Pedir permissão excessivamente ("posso te perguntar?", "se importa se...").
- Ser vago ou genérico.
- Fazer perguntas abertas demais no início.
- Tentar agradar. Seu objetivo é qualificar, não fazer amigos.
- Deixar a conversa morrer. Sempre termine com uma pergunta clara.

✅ SEMPRE FAÇA:
- Ir direto ao ponto.
- Usar dados do RAG para embasar seus argumentos.
- Criar um senso de urgência e escassez.
- Fazer o lead sentir que a oportunidade de falar com um especialista é valiosa.
- Qualificar antes de tentar agendar.

🎯 OBJETIVO FINAL: Agendar diagnóstico de portfólio de 30 min (gratuito) APENAS com leads qualificados.

RESPONDA SEMPRE EM JSON: {"mensagem": "texto", "acao": "continuar/agendar/finalizar", "proximo_estado": "estado", "contexto": {dados}, "score_parcial": 0-100}"""

    def _load_casos_sucesso(self) -> Dict[str, str]:
        """Casos de sucesso para usar na conversação"""
        return {
            "aposentadoria": "Semana passada ajudei um engenheiro de 45 anos que descobriu que ia se aposentar com apenas 40% do salário atual. Em 6 meses reorganizamos tudo.",
            
            "renda_extra": "Tenho um cliente médico que criou uma renda extra de R$ 8.500/mês com investimentos. Antes ele só tinha poupança e CDB.",
            
            "protecao": "Uma cliente advogada quase perdeu 30% do patrimônio em 2022 por ter tudo concentrado em ações. Hoje ela tem uma carteira muito mais protegida.",
            
            "crescimento": "Um empresário que atendo multiplicou o patrimônio por 3 em 4 anos, saindo dos fundos de banco para investimentos mais inteligentes.",
            
            "iniciante": "Muitos clientes começaram comigo com 50-100k e hoje têm carteiras de 500k+ por terem saído da poupança no momento certo."
        }
    
    def _load_objecoes_respostas(self) -> Dict[str, str]:
        """Respostas para objeções comuns"""
        return {
            "sem_tempo": "Entendo. A maioria dos meus clientes também achava que não tinha tempo. Por isso criamos um diagnóstico de 30 min que já mostra os principais pontos de melhoria.",
            
            "ja_tenho_assessor": "Que bom! Muitos dos meus clientes também tinham. O diagnóstico serve justamente para validar se está no caminho certo ou se tem algo para otimizar.",
            
            "pouco_dinheiro": "Olha, já atendi pessoas que começaram com muito menos e hoje estão muito bem. O importante é começar da forma correta desde o início.",
            
            "nao_entendo": "Normal! Por isso existe o diagnóstico. É justamente para traduzir tudo isso de forma simples e mostrar o que faz sentido para seu perfil.",
            
            "risco": "Entendo a preocupação. Por isso trabalho com estratégias conservadoras também. No diagnóstico vemos exatamente qual nível de risco faz sentido para você."
        }
    
    def get_system_prompt(self, context: PromptContext) -> str:
        """Constrói prompt do sistema contextualizado baseado no estado e perfil"""
        base_prompt = self.system_prompt
        
        # Adiciona contexto RAG se disponível
        if hasattr(context, 'contexto_rag') and context.contexto_rag and context.contexto_rag.strip():
            rag_section = f"""

## INFORMAÇÕES ADICIONAIS PARA CONSULTA (RAG)
Use as informações abaixo como base principal para responder à pergunta do lead de forma precisa e persuasiva.
---
{context.contexto_rag}
---
"""
            base_prompt += rag_section
        
        return base_prompt
    
    def get_user_prompt(self, context: PromptContext) -> str:
        """Constrói prompt do usuário contextualizado baseado no estado e perfil"""
        
        estado = context.estado_atual
        nome = context.nome_lead
        ultima_mensagem_lead = context.ultima_mensagem_lead
        slots = context.slots_preenchidos
        
        # Estratégia específica por estado
        if estado == "saudacao":
            return self._prompt_abertura(nome, getattr(context, 'canal', 'whatsapp'))
        elif estado == "situacao":
            return self._prompt_descoberta_situacao(nome, ultima_mensagem_lead, slots)
        elif estado == "qualificacao_patrimonio":
            return self._prompt_descoberta_patrimonio(nome, ultima_mensagem_lead, slots)
        elif estado == "qualificacao_objetivo":
            return self._prompt_descoberta_objetivo(nome, ultima_mensagem_lead, slots)
        elif estado == "qualificacao_urgencia":
            return self._prompt_criacao_urgencia(nome, ultima_mensagem_lead, slots)
        elif estado == "qualificacao_interesse":
            return self._prompt_validacao_interesse(nome, ultima_mensagem_lead, slots)
        elif estado == "agendamento":
            return self._prompt_agendamento(nome, ultima_mensagem_lead, slots)
        else:
            return self._prompt_generico(nome, ultima_mensagem_lead, estado)
    
    def _prompt_abertura(self, nome: str, canal: str) -> str:
        """Prompt para abertura consultiva"""
        return f"""ABERTURA DIRETA:
        
Contexto: Primeiro contato com {nome} via {canal}.
        
Estratégia: Apresentação rápida e primeira pergunta de qualificação para separar interessados de curiosos.

Exemplo de abordagem:
"Eduardo, aqui é da LDC Capital. Recebi seu contato sobre investimentos.

Vamos direto ao ponto para não perder seu tempo: você já investe ativamente ou está apenas começando a pesquisar sobre o assunto?

1) Já invisto
2) Estou começando"

REGRAS:
- Sem rodeios.
- Apresente-se e vá direto para a primeira pergunta.
- A pergunta deve qualificar o nível de experiência do lead."""

    def _prompt_descoberta_situacao(self, nome: str, ultima_mensagem_lead: str) -> str:
        """Prompt para descobrir situação atual"""
        return f"""DESCOBERTA DA SITUAÇÃO:

Lead {nome} respondeu: "{ultima_mensagem_lead}"

Estratégia: Fazer uma pergunta direta para entender o cenário atual e identificar uma possível dor.

Se disse que já investe:
- "Entendi. E você está 100% satisfeito com a performance da sua carteira atual ou acredita que ela poderia render mais?"
- 1) Satisfeito
- 2) Poderia render mais

Se disse que está começando:
- "Ótimo. O que te motivou a buscar sobre investimentos agora? Algum plano específico ou uma preocupação com o futuro?"
- 1) Plano específico
- 2) Preocupação com o futuro

REGRAS:
- Use a resposta dele para fazer a próxima pergunta qualificante.
- Foque em descobrir uma necessidade ou insatisfação."""

    def _prompt_descoberta_patrimonio(self, nome: str, ultima_mensagem_lead: str, slots) -> str:
        """Prompt direto para qualificar patrimônio."""
        return f"""QUALIFICAÇÃO DE PATRIMÔNIO:

Lead {nome} respondeu: "{ultima_mensagem_lead}"
Contexto conhecido: {slots}

Estratégia: Fazer uma pergunta clara sobre a faixa de capital para entender o perfil do lead.

Abordagem Direta:
"Para eu entender que tipo de estratégia faria sentido para você, em qual destas faixas seu capital de investimento se encontra hoje?

1) Até 100 mil
2) Entre 100 mil e 500 mil
3) Acima de 500 mil"

REGRAS:
- Seja direto e justifique o porquê da pergunta (direcionar a estratégia).
- Ofereça opções claras e fechadas."""

    def _prompt_descoberta_objetivo(self, nome: str, ultima_mensagem_lead: str, slots) -> str:
        """Prompt para descobrir o objetivo principal."""
        return f"""QUALIFICAÇÃO DE OBJETIVO:

Lead {nome} respondeu: "{ultima_mensagem_lead}"
Contexto: {slots}

Estratégia: Entender qual o principal drive do lead para investir.

Abordagem Direta:
"Ok. E qual o seu foco principal com os investimentos hoje?

1) Multiplicar o capital (crescimento)
2) Gerar uma renda mensal
3) Planejar a aposentadoria"

REGRAS:
- Pergunta focada no resultado esperado.
- Opções claras que representem os principais objetivos de investimento."""

    def _prompt_criacao_urgencia(self, nome: str, ultima_mensagem_lead: str, slots) -> str:
        """Prompt para qualificar a urgência."""
        return f"""QUALIFICAÇÃO DE URGÊNCIA:

Lead {nome} respondeu: "{ultima_mensagem_lead}"
Perfil: {slots}

Estratégia: Entender o timing do lead. Pessoas com alta urgência são mais propensas a agendar.

Abordagem:
"Entendido. E você pretende tomar uma decisão sobre seus investimentos quando?

1) Estou pronto para começar/mudar agora.
2) Nos próximos 3 meses.
3) Estou apenas pesquisando, sem pressa."

REGRAS:
- A pergunta deve medir o quão "quente" o lead está.
- As opções devem refletir diferentes níveis de urgência."""

    def _prompt_validacao_interesse(self, nome: str, ultima_mensagem_lead: str, slots) -> str:
        """Prompt para validar interesse e fazer a oferta do diagnóstico."""
        return f"""OFERTA DE DIAGNÓSTICO:

Lead {nome} respondeu: "{ultima_mensagem_lead}"
Perfil completo: {slots}

Estratégia: Conectar as respostas anteriores a uma dor e apresentar o diagnóstico como a solução lógica.

Abordagem:
"Perfeito, {nome}. Pelo que você me disse, seu objetivo é [objetivo] e você está no momento de [urgencia].

Muitos clientes com esse perfil chegam a nós porque [apresentar dor comum, ex: 'não sabem se estão na melhor estratégia para atingir essa meta a tempo'].

Eu posso fazer um diagnóstico gratuito de 30 minutos para te mostrar um plano claro. Isso te interessa?

1) Sim, tenho interesse.
2) Não, obrigado."

REGRAS:
- Resuma o que aprendeu sobre o lead.
- Apresente a oferta do diagnóstico como o próximo passo lógico.
- Call-to-action claro (Sim/Não)."""

    def _prompt_agendamento(self, nome: str, ultima_mensagem_lead: str, slots) -> str:
        """Prompt para agendamento consultivo"""
        return f"""AGENDAMENTO CONSULTIVO:

Lead {nome} aceitou: "{ultima_mensagem_lead}"
Perfil: {slots}

Estratégia: Agendar de forma consultiva e profissional.

"Perfeito, {nome}! Vou separar 30 min para fazer seu diagnóstico completo.

Prefere:
• Amanhã às 10h
• Amanhã às 16h  
• Outro horário

Vou te mandar o link do Google Meet. Ah, e pode ficar tranquilo - é só diagnóstico mesmo, sem pressão de nada."

Se ele sugerir outro horário:
"Ótimo! Que dia e horário funciona melhor para você? Tenho agenda flexível."

REGRAS:
- Confirme que é diagnóstico
- Ofereça 2 opções + flexibilidade
- Seja profissional mas acessível
- Ação sempre "agendar"
- Máximo 350 caracteres"""

    def _prompt_generico(self, nome: str, ultima_mensagem_lead: str, estado: str) -> str:
        """Prompt genérico para situações não mapeadas"""
        return f"""SITUAÇÃO GENÉRICA:

Estado: {estado}
Lead {nome} disse: "{ultima_mensagem_lead}"

Estratégia: Manter tom consultivo e avançar para próximo estado logicamente.

Use estrutura:
1. Reconheça a resposta
2. Compartilhe mini-insight relacionado  
3. Faça pergunta para avançar

Exemplo:
"Entendi, {nome}. [Insight relacionado]. [Pergunta específica]?"

REGRAS:
- Mantenha tom consultivo
- Sempre inclua valor antes de perguntar
- Avance logicamente no funil
- Máximo 350 caracteres"""

    def get_caso_sucesso(self, objetivo: str) -> str:
        """Retorna caso de sucesso relevante"""
        return self.casos_sucesso.get(objetivo, self.casos_sucesso["crescimento"])
    
    def get_resposta_objecao(self, objecao: str) -> str:
        """Retorna resposta para objeção"""
        for key, resposta in self.objecoes_respostas.items():
            if key in objecao.lower():
                return resposta
        return "Entendo sua preocupação. Por isso mesmo que faço um diagnóstico gratuito primeiro - para você ficar tranquilo."
