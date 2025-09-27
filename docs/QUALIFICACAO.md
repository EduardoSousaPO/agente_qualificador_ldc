# QUALIFICACAO

Visão geral da máquina de estados utilizada pelo `QualificationService`. O objetivo é qualificar o lead com no máximo seis mensagens do bot, sem repetir perguntas e sempre oferecendo o diagnóstico financeiro gratuito quando os critérios forem atingidos.

## Estados e transições

1. **Mensagem inicial** – saudação curta (e se o lead veio do Sheets, mensagem personalizada por canal). Não conta pergunta.
2. **ASK_PATRIMONY** – pergunta a faixa de patrimônio investido.
3. **ASK_INVESTMENT_PLACES** – pergunta em qual corretora/plataforma o lead investe hoje.
4. **ASK_SUPPORT** – pergunta como está o suporte atual / percepção de acompanhamento (uma pergunta, resposta livre).
5. **ASK_OBJECTIVE** – pergunta o objetivo principal com os investimentos.
6. **ASK_TIMEFRAME** – pergunta o prazo/horizonte desejado.
7. **OFFER_MEETING** – se suportes ruins + objetivo claro ⇒ oferta imediata da reunião com 2–3 janelas ou link.
8. **SCHEDULING** – após resposta positiva, pede para o lead escolher uma janela específica. Ao receber o horário, confirma, registra a reunião e finaliza.
9. **NOT_INTERESTED / FINISHED** – respostas negativas geram despedida cordial e status `nao_interessado`; respostas incompletas voltam para o estado correspondente sem repetir perguntas já respondidas.

## Critério de qualificação

O lead é considerado qualificado quando:

- A resposta em `avaliacao_suporte` contém sinais de dor (ex.: "fraco", "ruim", "sem acompanhamento", "pouco retorno").
- O objetivo menciona termos relevantes (`renda`, `aposent`, `protec`, `divers`, `patrim`, `dolar`, `internacional`) ou possui ao menos 12 caracteres.

Ao qualificar, o bot oferece o diagnóstico gratuito e registra `lead.status = qualificado`. Se o lead aceitar e escolher um horário, o status muda para `reuniao_agendada` e uma entrada é criada na tabela `reunioes` (campo `observacoes` guarda a preferência e o link da agenda, se configurado).

## Persistência

- Todas as respostas ficam em `sessions.contexto.responses` (JSON). Chaves principais: `patrimonio_faixa`, `onde_investe`, `avaliacao_suporte`, `objetivo`, `prazo` e `preferencia_agenda`.
- `qualificacoes` recebe `patrimonio_resposta`, `objetivo_resposta`, `urgencia_resposta` e `observacoes` com o snapshot completo.
- `reunioes` guarda agendamentos confirmados (`status=agendado`, `observacoes` com a preferência e `link_reuniao` quando disponível).
- `lead.status` é atualizado para `em_qualificacao`, `qualificado`, `nao_interessado` ou `reuniao_agendada` conforme as transições.

## Deduplicação e limites

- `MessagingService` gera uma chave de idempotência (`telefone + mensagem_normalizada + janela 5 min`). Mensagens duplicadas na janela são descartadas com métrica `skip_duplicate`.
- Há fila por contato e lock (garante ordem e elimina race conditions).
- Retry com backoff exponencial é herdado do `WhatsAppService`; métricas (`sent_ok`, `retry`, `failed`) ficam disponíveis para monitoramento.
- A oferta de reunião acontece até a 6ª mensagem útil do bot (considerando a saudação como mensagem 0).

## Agendamento e follow-up

- Slots padrão: obtidos da env `AGENDA_DIAGNOSTICO_SLOTS` (formato `Terça 10h;Quinta 16h;...`). Caso vazio, usa `Terça 10h`, `Quinta 16h`, `Sexta 14h`.
- Link opcional (`AGENDA_DIAGNOSTICO_URL`) é informado nas mensagens de oferta e confirmação.
- Se o lead não informar horário após aceitar, o bot reapresenta os slots (permite insistir sem repetir perguntas anteriores).
- Leads que recusam explicitamente recebem despedida e `status=nao_interessado`; o fluxo encerra sem voltar estados.
