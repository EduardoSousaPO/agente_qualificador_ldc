from backend.models.database_models import Lead
from backend.services.leads_watcher import LeadsWatcher


class FakeSheetsService:
    def __init__(self):
        self.service = True
        self.input_sheets_id = 'sheet-id'
        self.input_range = 'Leads!A1:H'
        self._updated = {}

    def read_input_sheet(self):
        headers = ['Status', 'Nome', 'Telefone', 'Canal', 'Contexto', 'Lead ID', 'Mensagem inicial', 'Observação']
        rows = [['', 'Maria', '5511988887777', 'ebook', 'baixou material', '', '', '']]
        return headers, rows

    def _parse_input_range(self):  # pylint: disable=unused-private-member
        return 'Leads', 1

    def update_input_row(self, row_number, headers, original_row, updates):
        self._updated[row_number] = updates


class FakeLeadRepository:
    def __init__(self):
        self.created = {}

    def get_lead_by_phone(self, telefone):
        return self.created.get(telefone)

    def create_lead(self, lead: Lead):
        lead_id = f'lead-{len(self.created) + 1}'
        data = {'id': lead_id, 'telefone': lead.telefone, 'nome': lead.nome, 'canal': lead.canal}
        self.created[lead.telefone] = data
        return data


class FakeQualificationService:
    def __init__(self):
        self.calls = []

    def normalizar_telefone(self, telefone):
        return telefone

    def iniciar_qualificacao(self, **kwargs):
        self.calls.append(kwargs)
        mensagem = (
            "Oi Maria! Aqui é a LDC Capital, consultoria independente e multibroker. "
            "Vi que você baixou nosso material sobre investimentos internacionais e queria entender "
            "rapidamente onde está hoje para te direcionar melhor. Tudo bem responder algumas perguntas?"
        )
        return {'success': True, 'session_id': 'sess-1', 'mensagem_inicial': mensagem}


def test_leads_watcher_marks_sheet_row_and_triggers_qualification():
    sheets = FakeSheetsService()
    lead_repo = FakeLeadRepository()
    qual_service = FakeQualificationService()

    watcher = LeadsWatcher(sheets, lead_repo, qual_service, poll_interval_seconds=60)
    watcher.process_once()

    assert qual_service.calls, 'Qualification service should be called for the new lead'
    called = qual_service.calls[0]
    assert called['nome'] == 'Maria'
    assert called['origem_canal'] == 'ebook'

    assert lead_repo.get_lead_by_phone('5511988887777')
    updates = sheets._updated[2]
    assert updates['Status'] == 'contatado'
    assert updates['Lead ID']
    assert 'LDC Capital' in updates['Mensagem inicial']
