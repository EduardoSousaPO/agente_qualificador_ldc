from backend.services.qualification_flow import QualificationFlow, FlowContext, FlowState


def test_flow_collects_answers_and_offers_meeting():
    flow = QualificationFlow()
    context = flow.initial_context('Eduardo')

    step = flow.next_step(FlowState.WAITING_FIRST_REPLY, context, 'Tenho assessor hoje')
    assert step.next_state == FlowState.ASK_PATRIMONY
    assert 'faixa de patrimônio' in step.reply.lower()

    step = flow.next_step(step.next_state, context, 'Entre 500k e 1 milhão')
    assert step.next_state == FlowState.ASK_INVESTMENT_PLACES

    step = flow.next_step(step.next_state, context, 'Uso XP e Avenue')
    assert step.next_state == FlowState.ASK_SUPPORT

    step = flow.next_step(step.next_state, context, 'Suporte fraco e rentabilidade abaixo do CDI')
    assert step.next_state == FlowState.ASK_OBJECTIVE

    step = flow.next_step(step.next_state, context, 'Quero diversificar e proteger em dólar')
    assert step.next_state == FlowState.ASK_TIMEFRAME

    step = flow.next_step(step.next_state, context, 'Médio prazo')
    assert step.next_state == FlowState.OFFER_MEETING
    assert 'reunião gratuita' in step.reply.lower()
    assert step.lead_status == 'qualificado'
    assert 'fraco' in context.responses['avaliacao_suporte'].lower()
    assert context.responses['prazo'] == 'Médio prazo'


def test_flow_handles_meeting_confirmation():
    flow = QualificationFlow()
    context = FlowContext(first_name='Ana')
    context.responses = {
        'patrimonio_faixa': 'acima de 500k',
        'onde_investe': 'BTG',
        'avaliacao_suporte': 'bem fraco',
        'objetivo': 'focar em dolar e renda',
        'prazo': 'médio prazo',
    }
    context.qualified = True

    offer = flow._offer_meeting(context)  # pylint: disable=protected-access
    assert offer.next_state == FlowState.OFFER_MEETING

    accept = flow.next_step(FlowState.OFFER_MEETING, context, 'Sim, esta semana pode ser')
    assert accept.next_state == FlowState.SCHEDULING

    finish = flow.next_step(FlowState.SCHEDULING, context, 'Prefiro terça às 10h')
    assert finish.finalize_session is True
    assert finish.lead_status == 'reuniao_agendada'
    assert finish.context.meeting_preference == 'Prefiro terça às 10h'
