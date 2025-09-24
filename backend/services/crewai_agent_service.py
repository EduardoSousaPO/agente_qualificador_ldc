"""
Serviço do Agente de IA construído com CrewAI.

Este serviço orquestra o processo de qualificação de leads usando
a estrutura de Agentes e Tarefas do CrewAI para garantir um fluxo
de conversa estruturado e robusto.
"""
import os
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

class CrewAIAgentService:
    def __init__(self):
        """Inicializa o serviço do agente CrewAI."""
        # Configura o modelo de linguagem que será usado pelos agentes
        self.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)

    def processar_mensagem(self, session_id: str, nome_lead: str, historico_conversa: list, ultima_mensagem: str):
        """
        Processa uma mensagem de um lead usando uma equipe (Crew) do CrewAI.
        """
        
        # 1. Definir o Agente
        # Este é o nosso especialista em qualificação.
        qualifier_agent = Agent(
            role='Especialista em Qualificação de Leads da LDC Capital',
            goal=f'Qualificar o lead chamado {nome_lead} para um diagnóstico de investimentos, seguindo um funil de perguntas estruturado.',
            backstory=(
                "Você é um consultor de investimentos sênior da LDC Capital. "
                "Sua especialidade é identificar rapidamente o potencial de um novo lead através de perguntas precisas e diretas. "
                "Você é profissional, valoriza o tempo do lead e não tem medo de fazer as perguntas importantes. "
                "Seu objetivo final é agendar uma reunião apenas com os leads mais promissores."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )

        # 2. Definir as Tarefas
        # Por enquanto, criaremos uma tarefa inicial para a PoC.
        # O contexto da conversa é passado aqui.
        task_qualificacao_inicial = Task(
            description=(
                f"Você está em uma conversa com um lead chamado {nome_lead}. "
                f"O histórico da conversa até agora é: {historico_conversa}. "
                f"A última mensagem do lead foi: '{ultima_mensagem}'. "
                "Com base nesse contexto, sua tarefa é dar o próximo passo no funil de qualificação. "
                "Siga o fluxo: Saudação -> Situação -> Patrimônio -> Objetivo -> Urgência -> Interesse -> Agendamento. "
                "Responda de forma curta e direta, sempre terminando com a próxima pergunta do funil."
            ),
            expected_output='A próxima mensagem a ser enviada para o lead, como uma string de texto simples.',
            agent=qualifier_agent
        )

        # 3. Montar a Equipe (Crew)
        # Nossa equipe tem apenas um agente e uma tarefa por enquanto.
        qualificacao_crew = Crew(
            agents=[qualifier_agent],
            tasks=[task_qualificacao_inicial],
            process=Process.sequential,
            verbose=2
        )

        # 4. Iniciar o Trabalho
        # O método kickoff inicia a execução das tarefas pela equipe.
        resposta = qualificacao_crew.kickoff()

        return resposta
