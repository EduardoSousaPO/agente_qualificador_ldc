import time

from backend.models.database_models import Message
from backend.services.messaging_service import MessagingService


class FakeWhatsAppService:
    def __init__(self):
        self.sent = []

    def enviar_mensagem(self, telefone: str, mensagem: str):
        self.sent.append((telefone, mensagem))
        return {'success': True, 'message_id': f'msg-{len(self.sent)}'}


class FakeMessageRepository:
    def __init__(self):
        self.messages = []

    def create_message(self, message: Message):
        self.messages.append(message)
        return message


def test_messaging_service_deduplicates_same_payload():
    whatsapp = FakeWhatsAppService()
    repo = FakeMessageRepository()
    service = MessagingService(whatsapp, repo, dedup_ttl_seconds=300)

    result_first = service.send_message('lead-1', '5511999999999', 'oi', session_id='sess-1')
    result_second = service.send_message('lead-1', '5511999999999', 'oi', session_id='sess-1')

    assert result_first['success'] is True
    assert result_second.get('skipped') == 'deduplicated'
    assert len(whatsapp.sent) == 1
    assert len(repo.messages) == 1
    metrics = service.get_metrics()
    assert metrics['sent_ok'] == 1
    assert metrics['skip_duplicate'] == 1


def test_messaging_service_processes_queue_in_order():
    whatsapp = FakeWhatsAppService()
    repo = FakeMessageRepository()
    service = MessagingService(whatsapp, repo, dedup_ttl_seconds=300)

    service.send_message('lead-1', '5511999999999', 'mensagem 1', session_id='sess-1')
    time.sleep(0.01)
    service.send_message('lead-1', '5511999999999', 'mensagem 2', session_id='sess-1')

    assert [msg[1] for msg in whatsapp.sent] == ['mensagem 1', 'mensagem 2']
    assert [m.conteudo for m in repo.messages] == ['mensagem 1', 'mensagem 2']
    metrics = service.get_metrics()
    assert metrics['sent_ok'] == 2
