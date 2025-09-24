"""
Serviço do Agente de IA construído com CrewAI.

Este serviço orquestra o processo de qualificação de leads usando
a estrutura de Agentes e Tarefas do CrewAI para garantir um fluxo
de conversa estruturado e robusto.
"""
import os
from typing import Any
import structlog
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

from backend.services.rag_service import RAGService

logger = structlog.get_logger(__name__)


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

        # Serviço opcional de RAG para reforçar argumentação consultiva
        self.rag_service = None
        try:
            self.rag_service = RAGService()
        except Exception as exc:  # pragma: no cover - fallback defensivo
            logger.warning("RAGService indisponível, seguindo sem contexto adicional", error=str(exc))

    def _build_task_description(
        self,
        session_id: str,
        nome_lead: str,
        historico_conversa: list[str],
        ultima_mensagem: str,
        rag_context: str,
    ) -> str:
        """Monta a descrição dinâmica da tarefa para o Crew."""
        historico_relevante = "\n".join(historico_conversa[-6:]) if historico_conversa else "Sem mensagens anteriores registradas."

        checklist = """CHECKLIST OBRIGATORIO
1. Quando historico estiver vazio ou o lead pedir recomeço, cumprimente de forma natural e apresente a LDC: consultoria independente do interior do RS, sem conflitos de interesse, multi-custodia (XP, BTG, Avenue) e processo R1/R2 estruturado.
2. Use linguagem humana, direta e variada. Evite frases mecanicas como 'estou aqui para ajudar' ou 'vou te ajudar'. Mostre que ouviu a resposta antes de seguir.
3. Consulte o historico: pergunte apenas sobre o proximo ponto em aberto. Nunca faça mais de uma pergunta por mensagem.
4. Quando fizer sentido, ofereça 2 ou 3 opcoes de resposta curtas (ex.: 'invisto sozinho / tenho assessor / ninguém cuida') para dar ritmo.
5. Descubra onde o lead investe hoje, se tem assessor, quanto confia nesse atendimento e quais dores percebe (taxas, proatividade, carteira engessada). Depois avance para objetivo, patrimonio, risco, urgencia e interesse.
6. Use o contexto RAG para embasar: diagnostico R1 gratuito com especialista CVM, estudo profundo na R2, modelo fee-based com cashback, independência e valores do interior, cases dos materiais.
7. Limite a mensagem a ate ~260 caracteres e finalize sempre com uma unica pergunta ou CTA clara.
8. Ao convidar para a R1, explique em duas frases que é um diagnóstico de 30 minutos sem conflito, mostra mapa de oportunidades e abre caminho para a R2. Sugira horarios concretos e confirme formato (virtual/presencial)."""

Fluxo sugerido (siga na ordem, uma etapa por mensagem):
- Que momento voce esta? (experiencia atual, plataformas/corretoras usadas)
- Voce conta com algum assessor hoje? Como avalia o atendimento?
- Objetivo principal (crescer patrimonio, renda, aposentadoria etc.)
- Patrimonio disponivel para investir agora
- Nivel de risco/experiencia (conservador, moderado, agressivo)
- Urgencia: quando pretende ajustar ou investir
- Dores especificas percebidas (taxas, resultados, falta de acompanhamento)
- Interesse e convite para a R1

Se o lead trouxer dúvida ou objeção, responda de forma breve antes de seguir para a próxima etapa.
"""

        if rag_context:
            descricao += f"""
Contexto estratégico da base de conhecimento LDC (use apenas o que fizer sentido na conversa):
{rag_context.strip()}
"""

        descricao += """
Entrega final esperada: uma única resposta em texto natural pronto para ser enviado no WhatsApp, seguindo o fluxo descrito."""

        return descricao

    def processar_mensagem(
        self,
        session_id: str,
        nome_lead: str,
        historico_conversa: list,
        ultima_mensagem: str,
    ) -> str:
        """Processa uma mensagem de um lead usando uma equipe (Crew) do CrewAI."""

        # Tenta coletar contexto adicional via RAG
        rag_context = ""
        if self.rag_service:
            try:
                consulta = " | ".join([msg for msg in historico_conversa[-5:] if msg])
                consulta = f"{consulta} | {ultima_mensagem}" if consulta else ultima_mensagem
                rag_context = self.rag_service.consultar_base_conhecimento(consulta)
            except Exception as exc:  # pragma: no cover - fallback defensivo
                logger.warning("Falha ao recuperar contexto RAG", error=str(exc))
                rag_context = ""

        # 1. Definir o Agente
        qualifier_agent = Agent(
            role="Especialista em Qualificação de Leads da LDC Capital",
            goal=f"Conduzir {nome_lead} por um funil consultivo até o agendamento da Reunião R1 com critérios claros.",
            backstory=(
                "Você é um consultor de investimentos sênior da LDC Capital. "
                "Sua especialidade é identificar rapidamente o potencial de um lead através de perguntas estruturadas, "
                "usando dados exclusivos e conhecimento do mercado. "
                "Você valoriza seu tempo e o tempo do lead, e só avança com quem demonstra fit verdadeiro."
            ),
            verbose=self._agent_verbose,
            llm=self.llm,
            allow_delegation=False,
        )

        # 2. Definir a Tarefa com checklist e contexto dinâmico
        task_description = self._build_task_description(
            session_id=session_id,
            nome_lead=nome_lead,
            historico_conversa=historico_conversa,
            ultima_mensagem=ultima_mensagem,
            rag_context=rag_context,
        )

        task_qualificacao_inicial = Task(
            description=task_description,
            expected_output="Resposta humana, consultiva e direta, com ate 280 caracteres e encerrada em pergunta ou CTA.",
            agent=qualifier_agent,
        )

        # 3. Montar a Equipe (Crew)
        qualificacao_crew = Crew(
            agents=[qualifier_agent],
            tasks=[task_qualificacao_inicial],
            process=Process.sequential,
            verbose=self._crew_verbose,
        )

        # 4. Iniciar o Trabalho e extrair o texto final
        resposta = qualificacao_crew.kickoff()
        return self._extract_response_text(resposta)

