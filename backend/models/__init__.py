"""
Pacote de Modelos

Este pacote unifica todos os modelos de dados da aplicação, tanto
os modelos de conversação (Pydantic) quanto os de banco de dados (Dataclasses).

Isso permite importações mais limpas e centralizadas no resto do código, como:
from backend.models import Lead, RespostaIA, Estado
"""

# Modelos do Banco de Dados (dataclasses)
from .database_models import (
    DatabaseConnection,
    Lead,
    Session,
    Message,
    Qualificacao,
    SystemLog,
    LeadRepository,
    SessionRepository,
    MessageRepository,
    QualificacaoRepository,
    SystemLogRepository
)

# Modelos de Conversação (Pydantic)
from .conversation_models import (
    PatrimonioRange,
    Objetivo,
    Urgencia,
    Interesse,
    Autoridade,
    Acao,
    Estado,
    ContextoConversa,
    RespostaIA,
    IntencaoLead,
    PromptContext,
    SessionState,
    ValidacaoResposta
)
