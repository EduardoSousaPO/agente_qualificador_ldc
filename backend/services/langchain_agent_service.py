"""
Serviço do Agente de IA construído com LangChain.

Este serviço encapsula a lógica principal do agente de qualificação,
utilizando as abstrações do LangChain para gerenciar estado, memória,
ferramentas e a interação com a LLM.
"""
import os
from langchain_openai import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

# NOVO: Gerenciador de memória para persistir conversas por sessão
# Em um ambiente de produção, isso seria substituído por um banco de dados como Redis.
MEMORIES = {}

def get_memory_for_session(session_id: str) -> ConversationBufferMemory:
    """Retorna a memória para uma sessão específica, ou cria uma nova se não existir."""
    if session_id not in MEMORIES:
        MEMORIES[session_id] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    return MEMORIES[session_id]


class LangchainAgentService:
    def __init__(self):
        """Inicializa o serviço do agente LangChain."""
        self.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)

    def _get_system_prompt_template(self, nome_lead: str) -> str:
        """Retorna o template do prompt de sistema com base no nome do lead."""
        if nome_lead == "Amigo(a)":
            return """Você é um agente especialista da LDC Capital. Sua primeira tarefa é descobrir o nome do lead.
Se apresente profissionalmente e pergunte o nome do lead antes de qualquer outra coisa.
Exemplo: 'Olá! Aqui é da LDC Capital. Com quem eu falo, por favor?'"""
        else:
            return f"""Você é um agente especialista da LDC Capital conversando com {nome_lead}.
Sua missão é qualificar esse lead para um diagnóstico de investimentos.
Seja direto, profissional e siga o fluxo de qualificação.
Comece com a primeira pergunta do fluxo: 'Vamos direto ao ponto, {nome_lead}: você já investe ativamente ou está apenas começando a pesquisar?'"""

    def processar_mensagem(self, session_id: str, nome_lead: str, mensagem: str):
        """
        Processa uma mensagem de um lead usando uma conversation chain do LangChain.
        """
        # Obter a memória específica para esta sessão
        memory = get_memory_for_session(session_id)

        # Selecionar o prompt de sistema com base no nome
        system_prompt_template = self._get_system_prompt_template(nome_lead)

        # Criar o template do prompt de chat
        prompt = ChatPromptTemplate(
            messages=[
                SystemMessagePromptTemplate.from_template(system_prompt_template),
                MessagesPlaceholder(variable_name="chat_history"),
                HumanMessagePromptTemplate.from_template("{question}")
            ]
        )

        # Criar a Conversation Chain
        conversation_chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=True, # Importante para debug nos logs do Render
            memory=memory
        )

        # Executar a chain com a mensagem do lead
        resposta = conversation_chain.run({"question": mensagem})

        return resposta
