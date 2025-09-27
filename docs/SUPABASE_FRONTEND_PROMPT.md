Objetivo: ajustar Supabase para o novo frontend (somente leitura de dados operacionais pelo app, sem quebrar o backend atual) e, se desejado, criar views/índices úteis.

Instruções para o agente do Cursor com MCP do Supabase executar:

1) Políticas de RLS (read-only para usuários autenticados)

Para as tabelas já existentes `leads`, `sessions`, `messages`, `qualificacoes`, `reunioes`:

```sql
-- Habilitar RLS (se ainda não estiver habilitado)
alter table public.leads enable row level security;
alter table public.sessions enable row level security;
alter table public.messages enable row level security;
alter table public.qualificacoes enable row level security;
alter table public.reunioes enable row level security;

-- Política de leitura para usuários autenticados
create policy "leads_read_authenticated" on public.leads
for select using ( auth.role() = 'authenticated' );

create policy "sessions_read_authenticated" on public.sessions
for select using ( auth.role() = 'authenticated' );

create policy "messages_read_authenticated" on public.messages
for select using ( auth.role() = 'authenticated' );

create policy "qualificacoes_read_authenticated" on public.qualificacoes
for select using ( auth.role() = 'authenticated' );

create policy "reunioes_read_authenticated" on public.reunioes
for select using ( auth.role() = 'authenticated' );

-- Bloquear insert/update/delete pelo cliente (sem políticas de escrita)
```

Observação: O backend atual usa Service Role (chave do servidor) para escrever. Não crie políticas de escrita públicas.

2) Views auxiliares (opcional)

```sql
create or replace view public.vw_lead_overview as
select
  l.id as lead_id,
  l.nome,
  l.telefone,
  l.canal,
  l.status,
  l.created_at,
  q.resultado as qualificacao_resultado,
  r.status as reuniao_status
from public.leads l
left join public.qualificacoes q on q.lead_id = l.id
left join public.reunioes r on r.lead_id = l.id;

grant select on public.vw_lead_overview to anon, authenticated;
```

3) Índices para performance (se não existirem)

```sql
create index if not exists idx_leads_created_at on public.leads(created_at desc);
create index if not exists idx_messages_session on public.messages(session_id);
create index if not exists idx_sessions_lead on public.sessions(lead_id);
```

4) Teste rápido (SQL)

```sql
-- Deve retornar linhas com usuário autenticado (supabase-js anon key + login)
select * from public.leads limit 5;
select * from public.vw_lead_overview limit 5;
```

5) Segurança

- Mantenha apenas SELECT para `anon`/`authenticated` via políticas acima.
- Toda escrita continua via backend com chave Service Role.

