"""Deterministic qualification flow state machine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

import structlog

from backend.services.metrics_service import metrics_service

logger = structlog.get_logger()


INITIAL_MESSAGE = (
    "Oi {nome}! Aqui é a LDC Capital, consultoria independente e multibroker. "
    "Vi que você baixou nosso material sobre investimentos internacionais e queria entender "
    "rapidamente onde está hoje para te direcionar melhor. Tudo bem responder algumas perguntas?"
)


class FlowState(str, Enum):
    WAITING_FIRST_REPLY = "inicio"
    ASK_PATRIMONY = "perguntar_patrimonio"
    ASK_INVESTMENT_PLACES = "perguntar_onde_investe"
    ASK_SUPPORT = "perguntar_qualidade_suporte"
    ASK_OBJECTIVE = "perguntar_objetivo"
    ASK_TIMEFRAME = "perguntar_prazo"
    OFFER_MEETING = "oferecer_reuniao"
    SCHEDULING = "agendamento"
    FINISHED = "finalizado"
    NOT_INTERESTED = "finalizado_nao_interessado"


@dataclass
class FlowContext:
    first_name: str = "tudo bem"
    bot_messages: int = 0
    responses: Dict[str, str] = field(default_factory=dict)
    lead_id: Optional[str] = None
    qualified: Optional[bool] = None
    meeting_preference: Optional[str] = None


@dataclass
class FlowResult:
    reply: Optional[str]
    next_state: FlowState
    context: FlowContext
    lead_status: Optional[str] = None
    notes: Dict[str, str] = field(default_factory=dict)
    finalize_session: bool = False


class QualificationFlow:
    """Implements the qualification decision tree."""

    def __init__(self) -> None:
        self.max_bot_messages_before_offer = 6

    def initial_context(self, first_name: Optional[str]) -> FlowContext:
        nome = (first_name or "tudo bem").strip()
        return FlowContext(first_name=nome if nome else "tudo bem")

    def initial_message(self, context: FlowContext) -> str:
        return INITIAL_MESSAGE.format(nome=context.first_name)

    def next_step(
        self,
        state: FlowState,
        context: FlowContext,
        incoming_message: str,
    ) -> FlowResult:
        message = incoming_message.strip()
        logger.debug("Flow step", state=state.value, incoming=message)

        if state == FlowState.WAITING_FIRST_REPLY:
            context.responses["primeira_interacao"] = message
            return self._ask_patrimony(context)

        if state == FlowState.ASK_PATRIMONY:
            context.responses["patrimonio_faixa"] = message
            return self._ask_investment_places(context)

        if state == FlowState.ASK_INVESTMENT_PLACES:
            context.responses["onde_investe"] = message
            return self._ask_support(context)

        if state == FlowState.ASK_SUPPORT:
            context.responses["avaliacao_suporte"] = message
            return self._ask_objective(context)

        if state == FlowState.ASK_OBJECTIVE:
            context.responses["objetivo"] = message
            return self._ask_timeframe(context)

        if state == FlowState.ASK_TIMEFRAME:
            context.responses["prazo"] = message
            qualified = self._is_qualified(context)
            context.qualified = qualified
            if qualified:
                return self._offer_meeting(context)
            # Registrar métrica de qualificação não aprovada
            lead_id = context.lead_id or "test_lead"
            metrics_service.record_qualification_completed(
                lead_id, 0, False
            )
            
            return FlowResult(
                reply=(
                    "Obrigado por compartilhar! Pelo que entendi, podemos continuar "
                    "com conteúdos sob medida e aviso você quando houver algo muito aderente."
                ),
                next_state=FlowState.FINISHED,
                context=context,
                lead_status="nao_qualificado",
                notes=context.responses.copy(),
                finalize_session=True,
            )

        if state == FlowState.OFFER_MEETING:
            if self._is_positive(message):
                context.meeting_preference = None
                return self._ask_scheduling(context)
            if self._is_negative(message):
                return FlowResult(
                    reply="Sem problemas! Fico à disposição caso mude de ideia.",
                    next_state=FlowState.NOT_INTERESTED,
                    context=context,
                    lead_status="nao_interessado",
                    notes=context.responses.copy(),
                    finalize_session=True,
                )
            # Request clarification if answer unclear
            return FlowResult(
                reply=(
                    "Perfeito. Prefere conversar ainda esta semana ou posso olhar agenda para a próxima?"
                ),
                next_state=FlowState.OFFER_MEETING,
                context=context,
            )

        if state == FlowState.SCHEDULING:
            context.meeting_preference = message
            return FlowResult(
                reply=(
                    "Anotei sua preferência. Um especialista da LDC Capital vai confirmar o horário "
                    "com você ainda hoje."
                ),
                next_state=FlowState.FINISHED,
                context=context,
                lead_status="reuniao_agendada",
                notes={**context.responses, "preferencia_agenda": message},
                finalize_session=True,
            )

        # Default fallback keeps session finished
        return FlowResult(
            reply=None,
            next_state=FlowState.FINISHED,
            context=context,
            finalize_session=True,
        )

    def _ask_patrimony(self, context: FlowContext) -> FlowResult:
        primeira_mencao = context.responses.get("primeira_interacao", "")
        saudacao = (
            f"Legal ouvir você, {context.first_name}. "
            if context.first_name and context.first_name != "tudo bem"
            else "Perfeito. "
        )
        if primeira_mencao:
            saudacao += f"Sobre o que comentou (\"{primeira_mencao}\"), quero entender melhor o seu momento. "
        mensagem = (
            saudacao
            + "Hoje qual faixa de patrimônio você mantém aplicada? Pode ser em faixas, tipo até 100 mil, "
            + "entre 100k e 500k, acima de 500k..."
        )
        return FlowResult(
            reply=mensagem,
            next_state=FlowState.ASK_PATRIMONY,
            context=context,
        )

    def _ask_investment_places(self, context: FlowContext) -> FlowResult:
        return FlowResult(
            reply=(
                "Obrigado por compartilhar. Hoje você investe por qual plataforma ou corretora? "
                "Se for XP, BTG, Avenue ou outra instituição, é só me contar."
            ),
            next_state=FlowState.ASK_INVESTMENT_PLACES,
            context=context,
        )

    def _ask_support(self, context: FlowContext) -> FlowResult:
        onde = context.responses.get("onde_investe")
        prefixo = f"Pensando na experiência com {onde}, " if onde else ""
        return FlowResult(
            reply=(
                prefixo
                + "como você avalia o suporte que recebe hoje? Está satisfeito ou sente que "
                + "poderia ter um acompanhamento mais próximo, inclusive em rentabilidade?"
            ),
            next_state=FlowState.ASK_SUPPORT,
            context=context,
        )

    def _ask_objective(self, context: FlowContext) -> FlowResult:
        return FlowResult(
            reply=(
                "Legal. Qual é o principal objetivo com esses investimentos hoje?"
            ),
            next_state=FlowState.ASK_OBJECTIVE,
            context=context,
        )

    def _ask_timeframe(self, context: FlowContext) -> FlowResult:
        return FlowResult(
            reply="Pensando nesse objetivo, em qual prazo gostaria de ver resultados? Curto, médio ou longo?",
            next_state=FlowState.ASK_TIMEFRAME,
            context=context,
        )

    def _offer_meeting(self, context: FlowContext) -> FlowResult:
        nome = context.first_name
        
        # Registrar métrica de qualificação aprovada
        lead_id = context.lead_id or "test_lead"
        metrics_service.record_qualification_completed(
            lead_id, 100, True  # Score 100 para qualificados
        )
        
        return FlowResult(
            reply=(
                f"Entendi, {nome}. Para ajudar você a estruturar melhor sua estratégia, "
                "posso agendar uma reunião gratuita de diagnóstico financeiro com um especialista "
                "da LDC Capital. Prefere esta semana ou na próxima?"
            ),
            next_state=FlowState.OFFER_MEETING,
            context=context,
            lead_status="qualificado",
            notes=context.responses.copy(),
        )

    def _ask_scheduling(self, context: FlowContext) -> FlowResult:
        return FlowResult(
            reply=(
                "Ótimo! Temos janelas na terça às 10h ou quinta às 16h. Alguma delas funciona?"
            ),
            next_state=FlowState.SCHEDULING,
            context=context,
        )

    @staticmethod
    def _is_positive(message: str) -> bool:
        lowered = message.lower()
        positives = [
            "sim",
            "claro",
            "vamos",
            "pode ser",
            "topo",
            "ok",
            "perfeito",
            "combinado",
            "esta semana",
            "bora",
            "fechado",
        ]
        return any(word in lowered for word in positives)

    @staticmethod
    def _is_negative(message: str) -> bool:
        lowered = message.lower()
        negatives = [
            "nao",
            "não",
            "depois",
            "sem interesse",
            "agora nao",
            "talvez depois",
            "outro momento",
            "prefiro nao",
            "mais pra frente",
        ]
        return any(word in lowered for word in negatives)

    def _is_qualified(self, context: FlowContext) -> bool:
        suporte = context.responses.get("avaliacao_suporte", "").lower()
        objetivo = context.responses.get("objetivo", "").lower()

        suportes_baixos = ["fraco", "ruim", "poderia", "melhor", "insatis", "sem", "pouco"]
        objetivos_relevantes = [
            "renda",
            "aposent",
            "protec",
            "divers",
            "patrim",
            "dolar",
            "internacional",
        ]

        suporte_ruim = any(token in suporte for token in suportes_baixos)
        objetivo_claro = any(token in objetivo for token in objetivos_relevantes) or len(objetivo) >= 12
        return suporte_ruim and objetivo_claro
