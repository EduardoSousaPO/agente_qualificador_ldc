# CHANGES RECENTES

_Período: últimos 7 dias (`git log --since="7 days ago"`) + alterações locais._

## Fluxo de qualificação
- `backend/services/qualification_flow.py`
- `backend/services/qualification_service.py`
- `backend/app.py`

Impacto: a conversa passou a usar máquina de estados determinística (patrimônio → onde investe → suporte → objetivo → prazo → reunião), com oferta do diagnóstico e confirmação de horário em até 6 mensagens. Criação de reuniões gravadas no Supabase (`reunioes`) e reutilização das preferências para follow-up.

Riscos/TODOs: validar manualmente os gatilhos de qualificação com leads reais; definir modelo de dados definitivo para armazenar `data_agendada` quando houver integração de calendário.

## Mensageria e deduplicação
- `backend/services/messaging_service.py`
- `backend/services/whatsapp_service.py`

Impacto: envio centralizado com chave idempotente (telefone + mensagem normalizada + janela 5 min), fila por contato e métricas (`sent_ok`, `skip_duplicate`, `retry`, `failed`). Falhas/429 continuam com retentativas exponenciais do próprio WhatsAppService.

Riscos/TODOs: expor as métricas via endpoint/observabilidade para monitoramento contínuo.

## Watcher de Google Sheets
- `backend/services/leads_watcher.py`
- `docs/LEADS_SHEET.md`

Impacto: polling a cada 30–60s com geração de UUID, personalização da mensagem por canal (templates default) e atualização dos campos (`status`, `lead_id`, `observacao`, `mensagem_inicial`). Suporte a mensagem inicial pré-preenchida na planilha.

Riscos/TODOs: confirmar se o intervalo configurado atende ao volume real de leads; adicionar alerta caso o watcher detecte credenciais inválidas.

## Agenda / Templates
- `.env.example`
- `docs/QUALIFICACAO.md`

Impacto: novos parâmetros `AGENDA_DIAGNOSTICO_SLOTS` e `AGENDA_DIAGNOSTICO_URL` para reutilizar links/horários. Documentação descreve estados, condições de qualificação e mensagens.

## Testes
- `tests/test_messaging_service.py`
- `tests/test_qualification_flow.py`
- `tests/test_leads_watcher.py`

Impacto: cobertura para deduplicação (incluindo métricas), jornada de qualificação até oferta/agendamento e disparo outbound no Sheets com template por canal.

Riscos/TODOs: instalar `pytest` no ambiente local antes de executar `python3 -m pytest tests` (não incluso por padrão).
