"""Legacy placeholder for the CrewAI agent service."""

from __future__ import annotations

from typing import Any, Dict

import structlog

logger = structlog.get_logger()


class CrewAIAgentService:
    """Skeleton implementation kept for backward compatibility."""

    def processar_mensagem(self, **_: Dict[str, Any]) -> Dict[str, Any]:
        logger.warning("CrewAI agent service is disabled in the deterministic flow")
        return {
            'mensagem': (
                "No momento o agente baseado em IA está desativado. "
                "O fluxo determinístico deve ser utilizado."
            )
        }
