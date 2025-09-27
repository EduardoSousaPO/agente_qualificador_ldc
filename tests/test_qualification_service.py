import pytest

from backend.services.qualification_service import QualificationService


class DummyLeadRepository:
    def __init__(self):
        self.updated = {}
        self.created = {}

    def update_lead(self, lead_id, updates):
        self.updated[lead_id] = updates
        return True

    def get_lead_by_phone(self, telefone):
        return self.created.get(telefone)

    def create_lead(self, lead):
        raise AssertionError("Not expected in this test")


class DummySessionRepository:
    def __init__(self):
        self.sessions = {}
        self.created = None
        self.updated = []

    def get_active_session(self, lead_id: str):
        return self.sessions.get(lead_id)

    def create_session(self, session):
        self.created = session
        session_dict = {
            'id': 'sess-1',
            'lead_id': session.lead_id,
            'estado': session.estado,
            'contexto': session.contexto,
            'ativa': session.ativa,
        }
        self.sessions[session.lead_id] = session_dict
        return session_dict

    def update_session(self, session_id: str, updates):
        self.updated.append((session_id, updates))
        return True


class DummyMessageRepository:
    def create_message(self, message):
        self.last_message = message
        return {'id': 'msg-1'}


class DummyQualificacaoRepository:
    def get_lead_qualificacao(self, lead_id):
        return None

    def create_qualificacao(self, qualificacao):
        return {'id': 'qual-1'}

    def update_qualificacao(self, qualificacao_id, updates):
        self.last_update = (qualificacao_id, updates)
        return True


class DummyReuniaoRepository:
    def create_reuniao(self, reuniao):
        self.last_reuniao = reuniao
        return {'id': 'reuniao-1'}


class DummyMessagingService:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, **payload):
        self.sent_messages.append(payload)
        return {'success': True, 'queued': False}


class DummyWhatsAppService:
    def normalizar_telefone(self, telefone):
        return telefone

    def enviar_mensagem(self, telefone, mensagem):
        return {'success': True}


@pytest.fixture
def qualification_service():
    return QualificationService(
        lead_repo=DummyLeadRepository(),
        session_repo=DummySessionRepository(),
        message_repo=DummyMessageRepository(),
        qualificacao_repo=DummyQualificacaoRepository(),
        reuniao_repo=DummyReuniaoRepository(),
        messaging_service=DummyMessagingService(),
        whatsapp_service=DummyWhatsAppService(),
    )


def test_custom_message_formats_with_name(qualification_service):
    service = qualification_service
    messaging_service = service.messaging_service

    result = service.iniciar_qualificacao(
        lead_id='lead-123',
        telefone='5511999999999',
        nome='Walter Pires',
        origem_canal='ebook',
        contexto_extra='baixou planilha',
        mensagem_inicial='Oi {nome}! Tudo certo para falarmos hoje?',
    )

    assert result['mensagem_inicial'].startswith('Oi Walter'), 'mensagem deve ser personalizada'
    assert 'Vi aqui: baixou planilha.' in result['mensagem_inicial']

    sent = messaging_service.sent_messages[-1]
    assert sent['mensagem'].startswith('Oi Walter')
    assert sent['metadata']['etapa'] == 'mensagem_inicial'


def test_custom_message_replaces_generic_amigo(qualification_service):
    service = qualification_service
    messaging_service = service.messaging_service

    result = service.iniciar_qualificacao(
        lead_id='lead-456',
        telefone='551188887777',
        nome='Raimundo',
        origem_canal='youtube',
        mensagem_inicial='Oi Amigo(a)! Aqui é da LDC Capital, tudo bem?',
    )

    assert 'Oi Raimundo!' in result['mensagem_inicial']
    assert 'Oi Raimundo!' in messaging_service.sent_messages[-1]['mensagem']
