"""Messaging service with deduplication and per-contact queue."""
from __future__ import annotations

import hashlib
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Optional, Tuple, Any

import structlog

from backend.models.database_models import Message, MessageRepository
from backend.services.metrics_service import metrics_service
from backend.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger()


class MessagingService:
    """Centralizes WhatsApp sending with deduplication and single queue per contact."""

    def __init__(
        self,
        whatsapp_service: WhatsAppService,
        message_repo: MessageRepository,
        dedup_ttl_seconds: int = 300,
    ) -> None:
        self.whatsapp_service = whatsapp_service
        self.message_repo = message_repo
        self._dedup_ttl = timedelta(seconds=dedup_ttl_seconds)
        self._dedup_cache: Dict[str, datetime] = {}
        self._queues: Dict[str, Deque[Tuple[str, Optional[str], str, str, Dict[str, Any]]]] = defaultdict(deque)
        self._locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.metrics = {
            "sent_ok": 0,
            "skip_duplicate": 0,
            "retry": 0,
            "failed": 0,
        }

    def send_message(
        self,
        lead_id: str,
        telefone: str,
        mensagem: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send message with dedup and in-order delivery for the recipient."""
        metadata = metadata or {}
        self._purge_cache()

        mensagem_normalizada = self._normalize_body(mensagem)
        dedup_key = self._make_dedup_key(telefone, mensagem_normalizada)
        if dedup_key in self._dedup_cache:
            logger.info(
                "Skipping duplicated message",
                telefone=telefone,
                message_hash=dedup_key,
            )
            self.metrics["skip_duplicate"] += 1
            # Registrar métrica de deduplicação
            metrics_service.record_message_deduped(telefone, "duplicate")
            return {"success": False, "skipped": "deduplicated"}

        queue = self._queues[telefone]
        queue.append((lead_id, session_id, mensagem, mensagem_normalizada, metadata))
        logger.debug("Queued message", telefone=telefone, queue_size=len(queue))

        lock = self._locks[telefone]
        if lock.locked():
            return {"success": True, "queued": True}

        with lock:
            result: Dict[str, Any] = {"success": True, "queued": False}
            while queue:
                lead_id_it, session_id_it, mensagem_it, mensagem_norm_it, metadata_it = queue.popleft()
                dedup_key_it = self._make_dedup_key(telefone, mensagem_norm_it)
                if dedup_key_it in self._dedup_cache:
                    logger.info(
                        "Skipping duplicated message inside queue",
                        telefone=telefone,
                        message_hash=dedup_key_it,
                    )
                    self.metrics["skip_duplicate"] += 1
                    continue

                send_result = self.whatsapp_service.enviar_mensagem(telefone, mensagem_it)
                logger.info(
                    "WhatsApp send result",
                    telefone=telefone,
                    success=send_result.get("success"),
                    details=send_result.get("details") or send_result.get("error"),
                )

                if send_result.get("success"):
                    self._dedup_cache[dedup_key_it] = datetime.now(timezone.utc)
                    if session_id_it:
                        self.message_repo.create_message(
                            Message(
                                session_id=session_id_it,
                                lead_id=lead_id_it,
                                conteudo=mensagem_it,
                                tipo="enviada",
                                metadata=metadata_it,
                            )
                        )
                    self.metrics["sent_ok"] += 1
                    # Registrar métrica de sucesso
                    metrics_service.record_message_sent(
                        telefone, 
                        True, 
                        send_result.get("details")
                    )
                    tentativa = send_result.get("tentativa", 1)
                    if tentativa and tentativa > 1:
                        self.metrics["retry"] += tentativa - 1
                else:
                    self.metrics["failed"] += 1
                    # Registrar métrica de falha
                    metrics_service.record_message_sent(
                        telefone, 
                        False, 
                        send_result.get("error") or send_result.get("details")
                    )
                result = send_result
            return result

    def _purge_cache(self) -> None:
        """Remove entries older than the deduplication TTL."""
        if not self._dedup_cache:
            return
        limit = datetime.now(timezone.utc) - self._dedup_ttl
        expired = [key for key, ts in self._dedup_cache.items() if ts < limit]
        for key in expired:
            self._dedup_cache.pop(key, None)

    @staticmethod
    def _make_dedup_key(telefone: str, mensagem_normalizada: str) -> str:
        payload = f"{telefone}|{mensagem_normalizada}".encode("utf-8")
        digest = hashlib.sha1(payload).hexdigest()
        bucket = int(datetime.now(timezone.utc).timestamp() // 300)
        return f"{telefone}:{bucket}:{digest}"

    @staticmethod
    def _normalize_body(texto: str) -> str:
        texto = (texto or "").strip().lower()
        texto = " ".join(texto.split())  # remove espaçamentos extras
        return texto

    def get_metrics(self) -> Dict[str, int]:
        """Return a copy of the delivery metrics."""
        return dict(self.metrics)
