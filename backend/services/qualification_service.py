"""Service orchestrating deterministic qualification flow."""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import structlog

from backend.services.metrics_service import metrics_service
from backend.models.database_models import (
    Session,
    SessionRepository,
    MessageRepository,
    QualificacaoRepository,
    Qualificacao,
    LeadRepository,
    Message,
    ReuniaoRepository,
    Reuniao,
)
from backend.services.messaging_service import MessagingService
from backend.services.qualification_flow import (
    QualificationFlow,
    FlowState,
    FlowContext,
    FlowResult,
)
from backend.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger()


class _SafeFormatDict(dict):
    """Keeps unresolved placeholders intact when formatting custom messages."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - simple helper
        return "{" + key + "}"


class QualificationService:
    """Handles session lifecycle, flow execution and persistence."""

    def __init__(
        self,
        lead_repo: LeadRepository,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        qualificacao_repo: QualificacaoRepository,
        reuniao_repo: ReuniaoRepository,
        messaging_service: MessagingService,
        whatsapp_service: WhatsAppService,
    ) -> None:
        self.lead_repo = lead_repo
        self.session_repo = session_repo
        self.message_repo = message_repo
        self.qualificacao_repo = qualificacao_repo
        self.reuniao_repo = reuniao_repo
        self.messaging_service = messaging_service
        self.whatsapp_service = whatsapp_service
        self.flow = QualificationFlow()
        self.agenda_slots = self._load_agenda_slots()
        self.agenda_link = os.getenv('AGENDA_DIAGNOSTICO_URL')

    def _load_agenda_slots(self) -> List[str]:
        raw = os.getenv('AGENDA_DIAGNOSTICO_SLOTS', '')
        slots = [slot.strip() for slot in raw.split(';') if slot.strip()]
        return slots or [
            'Terça às 10h',
            'Quinta às 16h',
            'Sexta às 14h',
        ]

    def iniciar_qualificacao(
        self,
        lead_id: str,
        telefone: str,
        nome: Optional[str] = None,
        origem_canal: str = "planilha",
        contexto_extra: Optional[str] = None,
        mensagem_inicial: Optional[str] = None,
        usar_template: bool = True,
    ) -> Dict[str, Any]:
        """Starts a new qualification session and sends the initial message."""
        telefone_normalizado = self.normalizar_telefone(telefone)
        session = self.session_repo.get_active_session(lead_id)
        if session:
            logger.info("Session already active", lead_id=lead_id, session_id=session['id'])
            return {"success": True, "session_id": session['id'], "mensagem_inicial": None}

        context = self.flow.initial_context(self._first_name(nome))
        context.lead_id = lead_id
        session_model = Session(
            lead_id=lead_id,
            estado=FlowState.WAITING_FIRST_REPLY.value,
            contexto=self._context_to_dict(context, origem_canal, contexto_extra),
            ativa=True,
        )
        created = self.session_repo.create_session(session_model)
        if not created:
            logger.error("Failed to create session", lead_id=lead_id)
            return {"success": False, "error": "session_creation_failed"}

        custom_message = None
        if mensagem_inicial:
            custom_message = self._render_custom_initial_message(
                mensagem_inicial,
                context=context,
                canal=origem_canal,
                contexto_extra=contexto_extra,
            )

        initial_message = custom_message or self._build_initial_message(
            context=context,
            canal=origem_canal,
            contexto_extra=contexto_extra,
            usar_template=usar_template,
        )
        send_result = self.messaging_service.send_message(
            lead_id=lead_id,
            telefone=telefone_normalizado,
            mensagem=initial_message,
            session_id=created['id'],
            metadata={"etapa": "mensagem_inicial", "canal": origem_canal},
        )
        if not send_result.get("success"):
            logger.error("Failed to send initial message", lead_id=lead_id, reason=send_result)
            return {"success": False, "error": "whatsapp_send_failed", "details": send_result}

        self.session_repo.update_session(
            created['id'],
            {
                'estado': FlowState.WAITING_FIRST_REPLY.value,
                'contexto': self._context_to_dict(context, origem_canal, contexto_extra),
            },
        )
        self.lead_repo.update_lead(lead_id, {'status': 'em_qualificacao'})

        return {
            "success": True,
            "session_id": created['id'],
            "mensagem_inicial": initial_message,
        }

    def processar_mensagem_recebida(
        self,
        lead_id: str,
        telefone: str,
        mensagem: str,
        nome: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Processes an inbound message from the lead."""
        telefone_normalizado = self.normalizar_telefone(telefone)
        session = self.session_repo.get_active_session(lead_id)
        contexto_extra = None
        origem = "whatsapp"

        if not session:
            logger.info("No active session found, creating a new one on the fly", lead_id=lead_id)
            init = self.iniciar_qualificacao(
                lead_id=lead_id,
                telefone=telefone_normalizado,
                nome=nome,
                origem_canal=origem,
                usar_template=False,
            )
            if not init.get("success"):
                return init
            session = self.session_repo.get_active_session(lead_id)

        session_id = session['id']
        context = self._context_from_session(session)
        context.lead_id = lead_id
        estado_atual = FlowState(session.get('estado', FlowState.WAITING_FIRST_REPLY.value))

        self.message_repo.create_message(
            Message(
                session_id=session_id,
                lead_id=lead_id,
                conteudo=mensagem,
                tipo='recebida',
                metadata={'fonte': origem},
            )
        )

        flow_result = self.flow.next_step(estado_atual, context, mensagem)

        # Ajustar mensagens para estados específicos antes do envio
        if flow_result.next_state == FlowState.OFFER_MEETING:
            flow_result.reply = self._format_offer_message(flow_result.context)
        elif flow_result.next_state == FlowState.SCHEDULING and not flow_result.finalize_session:
            flow_result.reply = self._format_scheduling_prompt(flow_result.context)
        elif flow_result.lead_status == 'reuniao_agendada':
            flow_result.reply = self._format_confirmation_message(flow_result.context)

        reply_sent = None
        if flow_result.reply:
            send_metadata = {"etapa": flow_result.next_state.value}
            send_result = self.messaging_service.send_message(
                lead_id=lead_id,
                telefone=telefone_normalizado,
                mensagem=flow_result.reply,
                session_id=session_id,
                metadata=send_metadata,
            )
            reply_sent = send_result

        self.session_repo.update_session(
            session_id,
            {
                'estado': flow_result.next_state.value,
                'contexto': self._context_to_dict(flow_result.context, origem, contexto_extra),
                'ativa': not flow_result.finalize_session,
            },
        )

        if flow_result.lead_status:
            self.lead_repo.update_lead(lead_id, {'status': flow_result.lead_status})

        if flow_result.notes:
            self._persist_qualificacao(lead_id, session_id, flow_result)
        if flow_result.lead_status == 'reuniao_agendada':
            self._registrar_reuniao(lead_id, session_id, flow_result.context.meeting_preference)
            # Registrar métrica de reunião agendada
            slot = flow_result.context.meeting_preference or "não especificado"
            metrics_service.record_meeting_scheduled(lead_id, slot, True)

        return {
            "success": True,
            "session_id": session_id,
            "estado": flow_result.next_state.value,
            "mensagem_enviada": flow_result.reply,
            "whatsapp": reply_sent,
            "finalizada": flow_result.finalize_session,
        }

    # ------------------------------------------------------------------
    # Helpers

    def _persist_qualificacao(self, lead_id: str, session_id: str, flow_result: FlowResult) -> None:
        registro = self.qualificacao_repo.get_lead_qualificacao(lead_id)
        if not registro:
            registro = self.qualificacao_repo.create_qualificacao(
                Qualificacao(lead_id=lead_id, session_id=session_id)
            )
        if not registro:
            return

        updates: Dict[str, Any] = {}
        notas = flow_result.notes
        if 'patrimonio_faixa' in notas:
            updates['patrimonio_resposta'] = notas['patrimonio_faixa']
        if 'objetivo' in notas:
            updates['objetivo_resposta'] = notas['objetivo']
        if 'prazo' in notas:
            updates['urgencia_resposta'] = notas['prazo']
        if flow_result.lead_status == 'reuniao_agendada':
            updates['resultado'] = 'reuniao_agendada'
        elif flow_result.lead_status == 'qualificado':
            updates['resultado'] = 'qualificado'
        elif flow_result.lead_status == 'nao_interessado':
            updates['resultado'] = 'nao_interessado'
        updates['observacoes'] = json.dumps(notas)
        self.qualificacao_repo.update_qualificacao(registro['id'], updates)

    def _registrar_reuniao(self, lead_id: str, session_id: str, preferencia: Optional[str]) -> None:
        if not preferencia:
            return
        try:
            reuniao = Reuniao(
                lead_id=lead_id,
                status='agendado',
                link_reuniao=self.agenda_link,
                observacoes=f"Sessão {session_id}: {preferencia}",
            )
            self.reuniao_repo.create_reuniao(reuniao)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Erro ao registrar reunião",
                lead_id=lead_id,
                session_id=session_id,
                error=str(exc),
                preferencia=preferencia,
            )

    def _context_to_dict(
        self,
        context: FlowContext,
        origem_canal: Optional[str],
        contexto_extra: Optional[str],
    ) -> Dict[str, Any]:
        data = asdict(context)
        data['origem_canal'] = origem_canal
        if contexto_extra:
            data['contexto_extra'] = contexto_extra
        return data

    def _context_from_session(self, session: Dict[str, Any]) -> FlowContext:
        raw = session.get('contexto') or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = {}
        context = FlowContext(
            first_name=raw.get('first_name', 'tudo bem'),
            bot_messages=raw.get('bot_messages', 0),
            responses=raw.get('responses', {}) or {},
            lead_id=raw.get('lead_id') or session.get('lead_id'),
            qualified=raw.get('qualified'),
            meeting_preference=raw.get('meeting_preference'),
        )
        return context

    def normalizar_telefone(self, telefone: str) -> str:
        try:
            return self.whatsapp_service.normalizar_telefone(telefone)
        except Exception:  # pylint: disable=broad-except
            return telefone

    @staticmethod
    def _first_name(nome: Optional[str]) -> str:
        if not nome:
            return 'tudo bem'
        primeiro = nome.strip().split()[0]
        return primeiro or 'tudo bem'

    CHANNEL_TEMPLATES = {
        "ebook": "Oi {nome}! Aqui é da LDC Capital. Vi que baixou nosso e-book sobre investimentos internacionais, por isso estou entrando em contato. Podemos conversar rapidinho para entender seu perfil e ver se um diagnóstico financeiro gratuito te ajuda a dar o próximo passo?",
        "youtube": "Oi {nome}! Aqui é da LDC Capital. Vi que chegou até nós pelo YouTube. Posso entender seu momento e, se fizer sentido, oferecer um diagnóstico financeiro gratuito com um especialista?",
        "newsletter": "Oi {nome}! Aqui é da LDC Capital. Vi que você veio pela nossa newsletter. Podemos falar um pouco sobre seus objetivos e, se fizer sentido, agendo um diagnóstico financeiro gratuito?",
        "instagram": "Oi {nome}! Aqui é da LDC Capital. Vi que nos encontrou pelo Instagram. Posso entender seus objetivos e te oferecer um diagnóstico financeiro gratuito?",
        "linkedin": "Oi {nome}! Aqui é da LDC Capital. Vi que chegou pelo LinkedIn. Posso entender seu momento e te oferecer um diagnóstico financeiro gratuito?",
        "site": "Oi {nome}! Aqui é da LDC Capital. Vi que chegou pelo nosso site. Podemos falar rapidinho e, se fizer sentido, marco um diagnóstico financeiro gratuito?",
        "indicacao": "Oi {nome}! Aqui é da LDC Capital. Recebemos sua indicação. Posso entender seus objetivos e te oferecer um diagnóstico financeiro gratuito?",
        "default": "Oi {nome}! Aqui é da LDC Capital. Recebemos seu contato. Posso entender seu momento e, se fizer sentido, agendo um diagnóstico financeiro gratuito?",
        "whatsapp": "Oi {nome}! Aqui é da LDC Capital. Obrigado por chamar a gente! Vou te fazer algumas perguntas rápidas para ver se um diagnóstico financeiro gratuito ajuda você agora, tudo bem?",
    }

    def _build_initial_message(
        self,
        context: FlowContext,
        canal: str,
        contexto_extra: Optional[str],
        usar_template: bool,
    ) -> str:
        if not usar_template:
            return self.flow.initial_message(context)

        canal_key = (canal or "default").strip().lower()
        template = self.CHANNEL_TEMPLATES.get(canal_key, self.CHANNEL_TEMPLATES["default"])
        mensagem = template.format(nome=context.first_name)
        if contexto_extra:
            mensagem += f" Vi aqui: {contexto_extra.strip()}."
        return mensagem

    def _render_custom_initial_message(
        self,
        mensagem_inicial: str,
        context: FlowContext,
        canal: Optional[str],
        contexto_extra: Optional[str],
    ) -> str:
        base = (mensagem_inicial or "").strip()
        if not base:
            return ""

        tokens = {
            "nome": context.first_name,
            "first_name": context.first_name,
            "lead": context.first_name,
            "canal": canal or "",
            "origem": canal or "",
            "origem_canal": canal or "",
            "contexto": contexto_extra or "",
            "contexto_extra": contexto_extra or "",
        }

        try:
            rendered = base.format_map(_SafeFormatDict(tokens))
        except Exception:  # pylint: disable=broad-except
            rendered = base

        if context.first_name and context.first_name.lower() != "tudo bem":
            rendered = self._personalize_generic_salutation(rendered, context.first_name)

        if contexto_extra:
            placeholder_present = re.search(r"\{contexto(_extra)?\}", base, re.IGNORECASE)
            if not placeholder_present:
                rendered = rendered.rstrip()
                if rendered and rendered[-1].isalnum():
                    rendered += "."
                rendered += f" Vi aqui: {contexto_extra.strip()}."

        return rendered.strip()

    @staticmethod
    def _personalize_generic_salutation(mensagem: str, first_name: str) -> str:
        if not mensagem:
            return mensagem

        result = mensagem
        patterns = [
            r"amigo\s*\(a\)",
            r"amiga",
            r"amigo",
        ]
        for pattern in patterns:
            result = re.sub(pattern, first_name, result, flags=re.IGNORECASE)
        return result

    def _format_offer_message(self, context: FlowContext) -> str:
        nome = context.first_name
        slots = self.agenda_slots[:3]
        if len(slots) == 1:
            slots_text = slots[0]
        elif len(slots) == 2:
            slots_text = f"{slots[0]} ou {slots[1]}"
        else:
            slots_text = f"{', '.join(slots[:-1])} ou {slots[-1]}"

        mensagem = (
            f"Entendi, {nome}. Posso agendar um diagnóstico financeiro gratuito com um especialista. "
            f"Tenho {slots_text}. Algum funciona para você?"
        )
        if self.agenda_link:
            mensagem += f" Se preferir outro horário, escolha aqui: {self.agenda_link}."
        return mensagem

    def _format_scheduling_prompt(self, context: FlowContext) -> str:
        slots = self.agenda_slots[:3]
        if len(slots) == 1:
            sugestao = slots[0]
        elif len(slots) == 2:
            sugestao = f"{slots[0]} ou {slots[1]}"
        else:
            sugestao = f"{', '.join(slots[:-1])} ou {slots[-1]}"
        mensagem = (
            "Perfeito! Qual desses horários prefere para o diagnóstico gratuito? "
            f"Posso reservar {sugestao}."
        )
        if self.agenda_link:
            mensagem += f" Se nenhum servir, tem outros horários aqui: {self.agenda_link}."
        return mensagem

    def _format_confirmation_message(self, context: FlowContext) -> str:
        preferencia = context.meeting_preference or 'horário a combinar'
        mensagem = (
            f"Anotado! Vou reservar {preferencia}. Um especialista da LDC Capital "
            "confirma com você em instantes."
        )
        if self.agenda_link:
            mensagem += f" Se precisar ajustar, use este link: {self.agenda_link}."
        return mensagem
