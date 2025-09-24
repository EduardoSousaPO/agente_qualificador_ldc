"""
Serviço do Agente de IA construído com CrewAI.

Este serviço orquestra o processo de qualificação de leads usando
a estrutura de Agentes e Tarefas do CrewAI para garantir um fluxo
de conversa estruturado e robusto.
"""
import os
from typing import Any
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI


class CrewAIAgentService:
    @staticmethod
    def _sanitize_bool(value: Any, default: bool = False) -> bool:
        """Normaliza entradas para booleanos aceitos pelo CrewAI."""
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
            if normalized.isdigit():
                return int(normalized) != 0
        return default

    @staticmethod
    def _extract_response_text(output: Any) -> str:
        """Converte o resultado do CrewAI em texto simples."""

        def _coerce(value: Any, depth: int = 0) -> str | None:
            if depth > 5:
                return None
            if value is None:
                return None
            if isinstance(value, str):
                return value
            if isinstance(value, (list, tuple)):
                for item in value:
                    coerced = _coerce(item, depth + 1)
                    if coerced:
                        return coerced
                return None
            if isinstance(value, dict):
                for key in ("final_output", "output", "raw", "response", "text", "content"):
                    if key in value:
                        coerced = _coerce(value[key], depth + 1)
                        if coerced:
                            return coerced
                return None
            if hasattr(value, "get"):
                try:
                    for key in ("final_output", "output", "raw", "response", "text", "content"):
                        coerced = _coerce(value.get(key), depth + 1)
                        if coerced:
                            return coerced
                except Exception:
                    pass
            for key in ("final_output", "output", "raw", "response", "text", "content"):
                if hasattr(value, key):
                    coerced = _coerce(getattr(value, key), depth + 1)
                    if coerced:
                        return coerced
            try:
                return str(value)
            except Exception:
                return None

        texto = _coerce(output)
        return texto.strip() if texto else ""

    def __init__(self):
        """Inicializa o serviço do agente CrewAI."""
        # Configura o modelo de linguagem que será usado pelos agentes
        self.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.7)

        # Normaliza flags de verbosidade para evitar valores inválidos no CrewAI
        self._agent_verbose = self._sanitize_bool(os.getenv("CREW_AGENT_VERBOSE", "true"), default=True)
        self._crew_verbose = self._sanitize_bool(os.getenv("CREW_VERBOSE", "true"), default=True)

    def processar_mensagem(self, session_id: str, nome_lead: str, historico_conversa: list, ultima_mensagem: str):
        """Processa uma mensagem de um lead usando uma equipe (Crew) do CrewAI."""

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
            verbose=self._agent_verbose,
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
            verbose=self._crew_verbose
        )

        # 4. Iniciar o Trabalho
        # O método kickoff inicia a execução das tarefas pela equipe.
        resposta = qualificacao_crew.kickoff()

        return self._extract_response_text(resposta)

