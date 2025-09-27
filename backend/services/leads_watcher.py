"""Background watcher that polls the lead sheet and kicks off conversations."""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import structlog

from backend.models.database_models import Lead, LeadRepository
from backend.services.google_sheets_service import GoogleSheetsService
from backend.services.qualification_service import QualificationService

logger = structlog.get_logger()


class LeadsWatcher:
    """Periodically scans the Google Sheet and processes new leads."""

    def __init__(
        self,
        sheets_service: GoogleSheetsService,
        lead_repo: LeadRepository,
        qualification_service: QualificationService,
        poll_interval_seconds: int = 60,
    ) -> None:
        self.sheets_service = sheets_service
        self.lead_repo = lead_repo
        self.qualification_service = qualification_service
        self.poll_interval_seconds = max(15, poll_interval_seconds)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.sheets_service.service or not self.sheets_service.input_sheets_id:
            logger.info("Leads watcher not started: Google Sheets not configured")
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="LeadsWatcher", daemon=True)
        self._thread.start()
        logger.info("Leads watcher started", interval_seconds=self.poll_interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def process_once(self) -> None:
        headers, rows = self.sheets_service.read_input_sheet()
        if not headers:
            return

        header_map = {self._normalize_header_name(header): header for header in headers}
        _, start_row = self.sheets_service._parse_input_range()  # pylint: disable=protected-access
        for index, row in enumerate(rows):
            row_map = self._row_to_dict(headers, row)
            status = (row_map.get('status') or '').strip().lower()
            if status not in ('', 'novo', 'new'):
                continue

            now_iso = datetime.now(timezone.utc).isoformat()

            telefone_raw = (row_map.get('telefone') or '').strip()
            if not telefone_raw:
                continue

            telefone_normalizado = self.qualification_service.normalizar_telefone(telefone_raw)

            nome = (row_map.get('nome') or '').strip() or 'tudo bem'
            canal = (row_map.get('canal') or 'planilha').strip().lower() or 'planilha'
            contexto_extra = row_map.get('contexto') or ''
            mensagem_personalizada = (row_map.get('mensagem_inicial') or '').strip()

            lead = self.lead_repo.get_lead_by_phone(telefone_normalizado)
            if not lead:
                novo_lead = Lead(nome=nome, telefone=telefone_normalizado, canal=canal)
                lead = self.lead_repo.create_lead(novo_lead)
                if not lead:
                    logger.error("Failed to create lead from sheet", telefone=telefone_normalizado)
                    continue

            lead_id = lead['id']
            logger.info("Processing sheet lead", lead_id=lead_id, telefone=telefone_normalizado)

            start_result = self.qualification_service.iniciar_qualificacao(
                lead_id=lead_id,
                telefone=telefone_normalizado,
                nome=nome,
                origem_canal=canal,
                contexto_extra=contexto_extra,
                mensagem_inicial=mensagem_personalizada or None,
            )

            row_number = start_row + 1 + index
            updates: Dict[str, str] = {
                header_map.get('status', 'status'): 'contatado',
                header_map.get('lead_id', 'lead_id'): lead_id,
                header_map.get('observacao', 'observacao'): now_iso,
            }
            first_message = start_result.get('mensagem_inicial')
            if first_message:
                updates[header_map.get('mensagem_inicial', 'mensagem_inicial')] = first_message

            self.sheets_service.update_input_row(row_number, headers, row, updates)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.process_once()
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error processing leads from sheet", error=str(exc))
            finally:
                self._stop_event.wait(self.poll_interval_seconds)

    @staticmethod
    def _normalize_header_name(header: str) -> str:
        normalized = re.sub(r'[^0-9a-z]+', '_', header.strip().lower())
        return normalized.strip('_')

    @classmethod
    def _row_to_dict(cls, headers: List[str], row: List[str]) -> Dict[str, str]:
        data: Dict[str, str] = {}
        for idx, original in enumerate(headers):
            key = cls._normalize_header_name(original)
            value = row[idx] if idx < len(row) else ''
            data[key] = value
        return data
