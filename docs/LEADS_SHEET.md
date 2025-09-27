# LEADS SHEET

Guia operacional para a planilha monitorada pelo `LeadsWatcher`. A planilha é a porta de entrada dos leads outbound e precisa manter a estrutura abaixo para que o robô identifique e dispare os contatos corretamente.

## Colunas obrigatórias

| Coluna            | Descrição                                                                                              |
|-------------------|--------------------------------------------------------------------------------------------------------|
| `status`          | Novo lead deve estar vazio ou `novo`. O watcher preenche `contatado`, `nao_interessado` ou `reuniao_agendada`. |
| `nome`            | Primeiro nome ou nome completo. Usado para personalização.                                             |
| `telefone`        | Número em formato WhatsApp (somente dígitos, com DDI).                                                 |
| `canal`           | Origem do lead (`ebook`, `youtube`, `newsletter`, `instagram`, `linkedin`, `site`, `indicacao`, `default`). |
| `contexto`        | Observação rápida (campanha, parceiro, material). Vai para o contexto da sessão.                      |
| `lead_id`         | Preenchido automaticamente com o UUID gerado no Supabase.                                              |
| `mensagem_inicial`| Texto enviado no primeiro contato. Se já vier preenchido na planilha, o watcher respeita o conteúdo.   |
| `observacao`      | Timestamp ISO do disparo inicial (por padrão `YYYY-MM-DDTHH:MM:SSZ`) ou anotações posteriores do time. |

> A guia/aba monitorada precisa estar em `GOOGLE_SHEETS_RANGE` (default `Leads!A1:H`). Se mudar o nome da aba ou o intervalo, ajuste a variável de ambiente.

## Mensagem inicial por canal

Caso a planilha não traga uma mensagem customizada, os templates abaixo são usados automaticamente:

- `ebook`: "Oi {nome}! Aqui é da LDC Capital. Vi que baixou nosso e-book sobre investimentos internacionais, por isso estou entrando em contato. Podemos conversar rapidinho para entender seu perfil e ver se um diagnóstico financeiro gratuito te ajuda a dar o próximo passo?"
- `youtube`: "Oi {nome}! Aqui é da LDC Capital. Vi que chegou até nós pelo YouTube. Posso entender seu momento e, se fizer sentido, oferecer um diagnóstico financeiro gratuito com um especialista?"
- `newsletter`: "Oi {nome}! Aqui é da LDC Capital. Vi que você veio pela nossa newsletter. Podemos falar um pouco sobre seus objetivos e, se fizer sentido, agendo um diagnóstico financeiro gratuito?"
- `instagram`: "Oi {nome}! Aqui é da LDC Capital. Vi que nos encontrou pelo Instagram. Posso entender seus objetivos e te oferecer um diagnóstico financeiro gratuito?"
- `linkedin`: "Oi {nome}! Aqui é da LDC Capital. Vi que chegou pelo LinkedIn. Posso entender seu momento e te oferecer um diagnóstico financeiro gratuito?"
- `site`: "Oi {nome}! Aqui é da LDC Capital. Vi que chegou pelo nosso site. Podemos falar rapidinho e, se fizer sentido, marco um diagnóstico financeiro gratuito?"
- `indicacao`: "Oi {nome}! Aqui é da LDC Capital. Recebemos sua indicação. Posso entender seus objetivos e te oferecer um diagnóstico financeiro gratuito?"
- `default`: fallback para canais não mapeados.

## Funcionamento do watcher

- Roda em background sempre que a API Flask inicia. O intervalo padrão é 60 segundos (`LEADS_WATCHER_INTERVAL` permite ajustar entre 30 e 60 segundos conforme a operação).
- A cada ciclo, busca linhas com `status` vazio/`novo`, gera o `lead_id` (se ainda não existir), dispara a mensagem inicial e atualiza:
  - `status = contatado`
  - `lead_id = <uuid>`
  - `observacao = <timestamp ISO> contato inicial enviado`
  - `mensagem_inicial = <texto real enviado>`
- Se o lead já existir no banco, o watcher reutiliza o registro. Linhas sem telefone são ignoradas e logadas para conferência.
- O endpoint `POST /leads/run-watcher` força uma leitura imediata (útil para testes manuais).

## Boas práticas

- Telefone deve conter apenas dígitos. O serviço normaliza automaticamente para o formato aceito pelo WhatsApp.
- Use o campo `contexto` para qualquer informação que ajude a conversa (ex.: "baixou o e-book de internacionais").
- Não sobrescreva `lead_id`, `mensagem_inicial` ou `observacao` depois que o robô preencher — eles são utilizados como trilha de auditoria.
- Para pausar um lead, coloque `status = pausado` (qualquer valor diferente de vazio/`novo` faz o watcher ignorar a linha).

## Diagnóstico em caso de falhas

- Verifique credenciais (`GOOGLE_SHEETS_ID`, `GOOGLE_CREDENTIALS_PATH` ou `GOOGLE_SHEETS_CREDENTIALS_JSON`). Sem elas o serviço entra em modo somente leitura.
- Se o intervalo ficar menor que 15 segundos, o watcher usa automaticamente 15s para evitar rate limit.
- Mudanças na ordem ou nome das colunas exigem atualizar o cabeçalho ou restaurar o formato original.
