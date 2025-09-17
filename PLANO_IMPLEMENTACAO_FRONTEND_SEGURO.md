# 🛡️ PLANO DE IMPLEMENTAÇÃO SEGURA - FRONTEND ADMINISTRATIVO

## 📋 VISÃO GERAL DO PLANO

Este documento detalha um **plano de implementação faseada e segura** do frontend administrativo, utilizando todos os MCPs disponíveis para garantir que o sistema atual continue funcionando perfeitamente durante e após a implementação.

### 🎯 OBJETIVOS PRINCIPAIS
- ✅ **Zero Downtime**: Sistema atual nunca para de funcionar
- ✅ **Isolamento Completo**: Frontend não interfere no backend atual
- ✅ **Rollback Imediato**: Capacidade de reverter qualquer mudança
- ✅ **Monitoramento Contínuo**: Alertas em tempo real de problemas
- ✅ **Validação Rigorosa**: Cada etapa testada exaustivamente

### 🧠 ESTRATÉGIA DE MCPs
Cada MCP será usado de forma específica e coordenada para maximizar a segurança:

| MCP | Função Principal | Fase de Uso |
|-----|------------------|-------------|
| **Sequential Thinking** | Planejamento estruturado | Todas as fases |
| **Memory** | Documentação e checkpoints | Todas as fases |
| **Supabase** | Análise e monitoramento do banco | Fases 1, 4, 5 |
| **Vercel** | Deploy seguro do frontend | Fases 2, 5 |
| **Render** | Ambiente de staging e backup | Fases 2, 4, 5 |
| **Prisma** | Schema isolado para leitura | Fase 2 |
| **Firecrawl** | Monitoramento de logs e performance | Fases 3, 4, 5 |

---

## 🔍 FASE 1: ANÁLISE PROFUNDA DE RISCOS (1 semana)

### 🎯 OBJETIVO
Mapear completamente o sistema atual e identificar todos os pontos de risco antes de qualquer implementação.

### 🛠️ MCPs UTILIZADOS

#### **1.1 Sequential Thinking MCP**
```markdown
PLANEJAMENTO ESTRUTURADO:
1. Análise da arquitetura atual
2. Identificação de dependências críticas
3. Mapeamento de pontos de falha
4. Definição de critérios de segurança
5. Criação de planos de contingência
```

#### **1.2 Supabase MCP**
```sql
-- ANÁLISE DO BANCO ATUAL
-- Verificar connections ativas
SELECT * FROM pg_stat_activity WHERE datname = 'postgres';

-- Analisar performance das queries críticas
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
WHERE query LIKE '%leads%' OR query LIKE '%sessions%'
ORDER BY total_time DESC;

-- Verificar locks e bloqueios
SELECT * FROM pg_locks WHERE NOT granted;

-- Analisar tamanho das tabelas
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

#### **1.3 Memory MCP**
```markdown
DOCUMENTAÇÃO DE RISCOS IDENTIFICADOS:
- Endpoints críticos que não podem ser alterados
- Tabelas com alta frequência de escrita
- Integrações sensíveis (WAHA, OpenAI, Google Sheets)
- Limites de performance atuais
- Pontos de falha conhecidos
```

### 📊 ENTREGÁVEIS DA FASE 1
1. **Mapa de Riscos Completo** (Memory MCP)
2. **Análise de Performance Atual** (Supabase MCP)
3. **Plano de Mitigação Detalhado** (Sequential Thinking MCP)
4. **Critérios Go/No-Go** para próximas fases

### ✅ CHECKPOINT FASE 1
**Critério de Aprovação**: Sistema atual deve estar 100% estável e documentado antes de prosseguir.

---

## 🏗️ FASE 2: ARQUITETURA ISOLADA (2 semanas)

### 🎯 OBJETIVO
Criar infraestrutura completamente isolada para o frontend, sem qualquer impacto no sistema atual.

### 🛠️ MCPs UTILIZADOS

#### **2.1 Render MCP**
```yaml
# AMBIENTE DE STAGING ISOLADO
services:
  - type: web
    name: agente-frontend-staging
    env: node
    buildCommand: npm run build
    startCommand: npm start
    envVars:
      - key: NODE_ENV
        value: staging
      - key: API_URL
        value: https://staging-backend.onrender.com
      - key: SUPABASE_URL
        value: [URL_STAGING_SEPARADO]
```

#### **2.2 Vercel MCP**
```typescript
// CONFIGURAÇÃO DE DEPLOY SEGURO
// vercel.json
{
  "builds": [
    { "src": "package.json", "use": "@vercel/next" }
  ],
  "env": {
    "NEXT_PUBLIC_API_URL": "https://staging-api.vercel.app",
    "NEXT_PUBLIC_ENVIRONMENT": "staging"
  },
  "functions": {
    "app/api/**/*.ts": {
      "maxDuration": 10
    }
  }
}
```

#### **2.3 Prisma MCP**
```prisma
// SCHEMA ISOLADO PARA LEITURA
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_READ_REPLICA_URL")
}

// Modelos READ-ONLY para o frontend
model Lead {
  id          String   @id @default(uuid())
  nome        String
  telefone    String   @unique
  canal       String
  status      String
  score       Int      @default(0)
  created_at  DateTime @default(now())
  
  // Relacionamentos somente leitura
  sessions    Session[]
  messages    Message[]
  
  @@map("leads")
}

model Session {
  id         String   @id @default(uuid())
  lead_id    String
  estado     String
  contexto   Json
  ativa      Boolean  @default(true)
  created_at DateTime @default(now())
  
  lead       Lead     @relation(fields: [lead_id], references: [id])
  messages   Message[]
  
  @@map("sessions")
}
```

#### **2.4 Supabase MCP**
```sql
-- CRIAÇÃO DE READ REPLICA ISOLADA
-- Configurar usuário com permissões limitadas
CREATE ROLE frontend_readonly;
GRANT CONNECT ON DATABASE postgres TO frontend_readonly;
GRANT USAGE ON SCHEMA public TO frontend_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO frontend_readonly;

-- Criar views otimizadas para o frontend
CREATE VIEW v_leads_dashboard AS
SELECT 
  id, nome, telefone, canal, status, score, created_at,
  (SELECT COUNT(*) FROM messages WHERE lead_id = leads.id) as total_messages,
  (SELECT MAX(created_at) FROM messages WHERE lead_id = leads.id) as last_activity
FROM leads;

-- View para estatísticas sem impacto
CREATE VIEW v_stats_realtime AS
SELECT 
  COUNT(*) as total_leads,
  COUNT(*) FILTER (WHERE status = 'qualificado') as qualificados,
  COUNT(*) FILTER (WHERE status = 'nao_qualificado') as nao_qualificados,
  AVG(score) as score_medio,
  COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as leads_hoje
FROM leads;
```

### 📊 ENTREGÁVEIS DA FASE 2
1. **Ambiente de Staging Completo** (Render MCP)
2. **Frontend Base Deployado** (Vercel MCP)
3. **Schema Isolado Funcionando** (Prisma MCP)
4. **Views Otimizadas Criadas** (Supabase MCP)

### ✅ CHECKPOINT FASE 2
**Critério de Aprovação**: 
- Sistema atual funcionando normalmente ✅
- Ambiente isolado 100% operacional ✅
- Zero impacto na performance atual ✅

---

## 🔧 FASE 3: IMPLEMENTAÇÃO FASEADA (8 semanas)

### 🎯 OBJETIVO
Implementar funcionalidades do frontend de forma incremental, sempre validando o impacto no sistema atual.

### 🛠️ MCPs UTILIZADOS

#### **3.1 Sequential Thinking MCP - Subfases**

##### **SUBFASE 3.1: Dashboard Read-Only (2 semanas)**
```markdown
PLANEJAMENTO:
1. Implementar componentes de visualização
2. Conectar com views otimizadas
3. Implementar cache inteligente
4. Testar performance com dados reais
5. Validar zero impacto no sistema atual
```

##### **SUBFASE 3.2: Kanban Visualização (2 semanas)**
```markdown
PLANEJAMENTO:
1. Criar componentes de Kanban
2. Implementar filtros e busca
3. Conectar com dados em tempo real
4. Otimizar queries para performance
5. Testar com alto volume de leads
```

##### **SUBFASE 3.3: Visualizador de Conversas (2 semanas)**
```markdown
PLANEJAMENTO:
1. Implementar interface de chat
2. Otimizar carregamento de mensagens
3. Implementar paginação inteligente
4. Adicionar análise de IA visual
5. Testar com conversas longas
```

##### **SUBFASE 3.4: Relatórios e Exportação (2 semanas)**
```markdown
PLANEJAMENTO:
1. Implementar geração de relatórios
2. Otimizar queries de agregação
3. Implementar exportação assíncrona
4. Adicionar cache de relatórios
5. Testar com grandes volumes
```

#### **3.2 Firecrawl MCP - Monitoramento Contínuo**
```typescript
// MONITORAMENTO DE PERFORMANCE EM TEMPO REAL
const monitoringConfig = {
  endpoints: [
    'https://agente-backend.onrender.com/health',
    'https://agente-backend.onrender.com/stats',
    'https://agente-backend.onrender.com/webhook'
  ],
  metrics: [
    'response_time',
    'error_rate',
    'memory_usage',
    'database_connections'
  ],
  alerts: {
    response_time_threshold: 2000, // 2s
    error_rate_threshold: 0.05,    // 5%
    memory_threshold: 0.85         // 85%
  }
}
```

#### **3.3 Memory MCP - Documentação de Cada Subfase**
```markdown
TEMPLATE DE DOCUMENTAÇÃO POR SUBFASE:
- Funcionalidades implementadas
- Impacto na performance medido
- Problemas encontrados e soluções
- Métricas antes/depois
- Validações de segurança realizadas
- Plano de rollback específico
```

### 📊 ENTREGÁVEIS DA FASE 3
1. **Dashboard Funcional** com métricas em tempo real
2. **Kanban Completo** com gestão visual de leads
3. **Visualizador de Conversas** otimizado
4. **Sistema de Relatórios** com exportação
5. **Documentação Completa** de cada implementação

### ✅ CHECKPOINTS DA FASE 3
**Critério de Aprovação para cada Subfase**:
- Performance do sistema atual mantida ✅
- Métricas de monitoramento estáveis ✅
- Testes de carga aprovados ✅
- Rollback testado e funcional ✅

---

## 🧪 FASE 4: TESTES E VALIDAÇÃO EXAUSTIVA (2 semanas)

### 🎯 OBJETIVO
Realizar testes completos e rigorosos para garantir que o sistema está pronto para produção.

### 🛠️ MCPs UTILIZADOS

#### **4.1 Render MCP - Testes de Carga**
```yaml
# CONFIGURAÇÃO DE TESTE DE CARGA
services:
  - type: worker
    name: load-tester
    env: node
    buildCommand: npm install
    startCommand: npm run load-test
    envVars:
      - key: TARGET_URL
        value: https://agente-backend.onrender.com
      - key: CONCURRENT_USERS
        value: 100
      - key: TEST_DURATION
        value: 300 # 5 minutos
```

#### **4.2 Supabase MCP - Validação de Integridade**
```sql
-- TESTES DE INTEGRIDADE DO BANCO
-- Verificar se dados não foram corrompidos
SELECT 
  COUNT(*) as total_leads_before,
  (SELECT COUNT(*) FROM leads_backup) as total_leads_backup,
  CASE 
    WHEN COUNT(*) = (SELECT COUNT(*) FROM leads_backup) 
    THEN 'INTEGRO' 
    ELSE 'CORROMPIDO' 
  END as status
FROM leads;

-- Verificar performance das queries críticas
EXPLAIN ANALYZE 
SELECT * FROM leads 
WHERE status = 'em_qualificacao' 
AND created_at >= CURRENT_DATE - INTERVAL '1 day';

-- Testar locks e concorrência
SELECT 
  pid, state, query_start, query
FROM pg_stat_activity 
WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%';
```

#### **4.3 Sequential Thinking MCP - Planos de Rollback**
```markdown
PLANO DE ROLLBACK DETALHADO:
1. Identificar sinais de problema
2. Parar tráfego para frontend imediatamente
3. Verificar integridade do sistema atual
4. Restaurar configurações anteriores
5. Validar funcionamento normal
6. Documentar causa raiz do problema
7. Planejar correção para próxima tentativa
```

#### **4.4 Memory MCP - Documentação de Testes**
```markdown
RESULTADOS DE TESTES:
- Testes de performance: APROVADO/REPROVADO
- Testes de carga: X usuários simultâneos
- Testes de integridade: ÍNTEGRO/CORROMPIDO
- Testes de rollback: FUNCIONAL/FALHOU
- Métricas de impacto: 0% degradação
- Problemas identificados: [lista]
- Ações corretivas: [lista]
```

### 📊 ENTREGÁVEIS DA FASE 4
1. **Relatório Completo de Testes** com todas as métricas
2. **Validação de Zero Impacto** no sistema atual
3. **Planos de Rollback Testados** e funcionais
4. **Documentação de Problemas** e soluções
5. **Aprovação Final** para produção

### ✅ CHECKPOINT FASE 4
**Critérios Obrigatórios para Produção**:
- Sistema atual 100% estável durante todos os testes ✅
- Performance mantida ou melhorada ✅
- Zero corrupção de dados ✅
- Rollback testado e funcional ✅
- Todos os alertas configurados e funcionando ✅

---

## 🚀 FASE 5: DEPLOY SEGURO EM PRODUÇÃO (1 semana)

### 🎯 OBJETIVO
Deploy gradual e monitorado do frontend em produção, com capacidade de rollback imediato.

### 🛠️ MCPs UTILIZADOS

#### **5.1 Vercel MCP - Deploy Gradual**
```typescript
// CONFIGURAÇÃO DE DEPLOY BLUE-GREEN
// vercel.json
{
  "builds": [
    { "src": "package.json", "use": "@vercel/next" }
  ],
  "regions": ["gru1"], // São Paulo
  "env": {
    "NEXT_PUBLIC_API_URL": "https://agente-backend.onrender.com",
    "NEXT_PUBLIC_ENVIRONMENT": "production"
  },
  "functions": {
    "app/api/**/*.ts": {
      "maxDuration": 10,
      "memory": 1024
    }
  },
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "s-maxage=60, stale-while-revalidate"
        }
      ]
    }
  ]
}
```

#### **5.2 Render MCP - Backup Automático**
```yaml
# SERVIÇO DE BACKUP AUTOMÁTICO
services:
  - type: cron
    name: backup-monitor
    schedule: "*/5 * * * *" # A cada 5 minutos
    buildCommand: npm install
    startCommand: npm run backup-check
    envVars:
      - key: SUPABASE_URL
        value: $SUPABASE_URL
      - key: BACKUP_WEBHOOK
        value: $SLACK_WEBHOOK
```

#### **5.3 Supabase MCP - Monitoramento em Tempo Real**
```sql
-- ALERTAS AUTOMÁTICOS DE PERFORMANCE
CREATE OR REPLACE FUNCTION monitor_performance()
RETURNS void AS $$
DECLARE
  current_connections int;
  slow_queries int;
  error_rate float;
BEGIN
  -- Verificar conexões ativas
  SELECT count(*) INTO current_connections 
  FROM pg_stat_activity 
  WHERE state = 'active';
  
  -- Verificar queries lentas
  SELECT count(*) INTO slow_queries
  FROM pg_stat_activity 
  WHERE state = 'active' 
  AND query_start < NOW() - INTERVAL '30 seconds';
  
  -- Alertar se limites excedidos
  IF current_connections > 50 THEN
    PERFORM pg_notify('performance_alert', 
      json_build_object(
        'type', 'high_connections',
        'value', current_connections,
        'threshold', 50
      )::text
    );
  END IF;
  
  IF slow_queries > 5 THEN
    PERFORM pg_notify('performance_alert',
      json_build_object(
        'type', 'slow_queries', 
        'value', slow_queries,
        'threshold', 5
      )::text
    );
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Executar monitoramento a cada minuto
SELECT cron.schedule('monitor-performance', '* * * * *', 'SELECT monitor_performance()');
```

#### **5.4 Sequential Thinking MCP - Procedimento de Deploy**
```markdown
PROCEDIMENTO DE DEPLOY STEP-BY-STEP:
1. Verificar que todos os testes foram aprovados
2. Criar backup completo do sistema atual
3. Configurar monitoramento intensivo
4. Deploy do frontend em modo "canary" (5% tráfego)
5. Monitorar métricas por 30 minutos
6. Se OK, aumentar para 25% do tráfego
7. Monitorar por mais 30 minutos
8. Se OK, aumentar para 50% do tráfego
9. Monitorar por mais 30 minutos
10. Se OK, liberar 100% do tráfego
11. Monitorar intensivamente por 24h
12. Se qualquer problema: ROLLBACK IMEDIATO
```

#### **5.5 Memory MCP - Documentação do Deploy**
```markdown
LOG DE DEPLOY EM PRODUÇÃO:
- Data/hora do deploy
- Versão deployada
- Percentual de tráfego em cada etapa
- Métricas coletadas em cada checkpoint
- Problemas identificados (se houver)
- Ações tomadas
- Status final: SUCESSO/ROLLBACK
- Lições aprendidas
```

### 📊 ENTREGÁVEIS DA FASE 5
1. **Frontend em Produção** funcionando perfeitamente
2. **Sistema de Monitoramento** ativo 24/7
3. **Backups Automáticos** configurados
4. **Documentação Completa** do processo
5. **Planos de Manutenção** estabelecidos

### ✅ CHECKPOINT FASE 5
**Critérios de Sucesso**:
- Sistema atual funcionando normalmente ✅
- Frontend acessível e estável ✅
- Zero impacto na performance ✅
- Monitoramento ativo e alertas funcionando ✅
- Equipe treinada para manutenção ✅

---

## 🛡️ PLANOS DE CONTINGÊNCIA

### 🚨 CENÁRIO 1: DEGRADAÇÃO DE PERFORMANCE
```markdown
SINAIS DE ALERTA:
- Tempo de resposta > 2 segundos
- Taxa de erro > 5%
- Uso de memória > 85%

AÇÕES IMEDIATAS:
1. Alertar equipe via Slack/Discord
2. Reduzir tráfego do frontend para 0%
3. Investigar causa raiz
4. Aplicar correção ou rollback
5. Validar normalização
```

### 🚨 CENÁRIO 2: CORRUPÇÃO DE DADOS
```markdown
SINAIS DE ALERTA:
- Inconsistências nos dados
- Erros de integridade referencial
- Dados faltando ou duplicados

AÇÕES IMEDIATAS:
1. PARAR TUDO imediatamente
2. Isolar sistema do tráfego
3. Restaurar backup mais recente
4. Validar integridade completa
5. Investigar causa raiz
```

### 🚨 CENÁRIO 3: SOBRECARGA DO BACKEND
```markdown
SINAIS DE ALERTA:
- Conexões de banco esgotadas
- Timeout nas APIs externas
- Sistema principal lento

AÇÕES IMEDIATAS:
1. Desconectar frontend imediatamente
2. Liberar recursos do backend
3. Validar sistema principal
4. Identificar causa da sobrecarga
5. Implementar limitações adicionais
```

---

## 📊 MÉTRICAS DE MONITORAMENTO CONTÍNUO

### 🎯 MÉTRICAS CRÍTICAS (Alertas Imediatos)
| Métrica | Limite | Ação |
|---------|--------|------|
| Tempo de Resposta API | > 2s | Alerta Crítico |
| Taxa de Erro | > 5% | Rollback Automático |
| Conexões DB | > 80% | Reduzir Tráfego |
| Uso de Memória | > 85% | Scale Up |
| Uptime Sistema Principal | < 99% | Investigação Urgente |

### 📈 MÉTRICAS DE PERFORMANCE (Monitoramento)
| Métrica | Meta | Frequência |
|---------|------|------------|
| Leads Processados/hora | Manter atual | Contínua |
| Score Médio | Manter atual | Diária |
| Taxa de Conversão | Manter/Melhorar | Diária |
| Satisfação Usuário | > 4.5/5 | Semanal |

### 🔍 MÉTRICAS DE QUALIDADE (Validação)
| Métrica | Meta | Frequência |
|---------|------|------------|
| Integridade de Dados | 100% | Contínua |
| Sincronização Frontend/Backend | < 1s | Contínua |
| Disponibilidade | > 99.9% | Contínua |
| Tempo de Rollback | < 5min | Testado Semanalmente |

---

## 📅 CRONOGRAMA DETALHADO

### 🗓️ TIMELINE COMPLETA (14 semanas)

```
SEMANA 1: FASE 1 - Análise de Riscos
├── Dias 1-2: Sequential Thinking (Planejamento)
├── Dias 3-4: Supabase MCP (Análise do Banco)
├── Dias 5-6: Memory MCP (Documentação)
└── Dia 7: Checkpoint e Aprovação

SEMANAS 2-3: FASE 2 - Arquitetura Isolada
├── Semana 2: Render + Vercel (Infraestrutura)
├── Semana 3: Prisma + Supabase (Schema Isolado)
└── Checkpoint: Ambiente Isolado Funcional

SEMANAS 4-11: FASE 3 - Implementação Faseada
├── Semanas 4-5: Dashboard Read-Only
├── Semanas 6-7: Kanban Visualização  
├── Semanas 8-9: Visualizador de Conversas
├── Semanas 10-11: Relatórios e Exportação
└── Checkpoint: Frontend Completo em Staging

SEMANAS 12-13: FASE 4 - Testes e Validação
├── Semana 12: Testes de Performance e Carga
├── Semana 13: Validação de Integridade
└── Checkpoint: Aprovação para Produção

SEMANA 14: FASE 5 - Deploy Seguro
├── Dias 1-3: Deploy Gradual
├── Dias 4-5: Monitoramento Intensivo
├── Dias 6-7: Validação Final e Documentação
└── Checkpoint: Sistema em Produção
```

---

## 🎯 CRITÉRIOS DE SUCESSO FINAIS

### ✅ CRITÉRIOS TÉCNICOS
- [ ] Sistema atual funcionando com **0% degradação**
- [ ] Frontend operacional com **99.9% uptime**
- [ ] Tempo de resposta médio **< 1 segundo**
- [ ] Zero corrupção ou perda de dados
- [ ] Rollback funcional em **< 5 minutos**

### ✅ CRITÉRIOS DE NEGÓCIO  
- [ ] **80% redução** no tempo de gestão de leads
- [ ] **100% visibilidade** do pipeline em tempo real
- [ ] Relatórios gerados **90% mais rápido**
- [ ] Satisfação da equipe **> 4.5/5**
- [ ] ROI positivo em **< 2 meses**

### ✅ CRITÉRIOS DE QUALIDADE
- [ ] Documentação **100% completa**
- [ ] Equipe **totalmente treinada**
- [ ] Monitoramento **24/7 ativo**
- [ ] Backups **automáticos funcionando**
- [ ] Planos de contingência **testados**

---

## 🎉 CONCLUSÃO

Este plano de implementação garante que:

1. **🛡️ SEGURANÇA TOTAL**: O sistema atual nunca será comprometido
2. **📊 VISIBILIDADE COMPLETA**: Monitoramento em todas as etapas
3. **⚡ ROLLBACK IMEDIATO**: Capacidade de reverter qualquer problema
4. **🎯 QUALIDADE GARANTIDA**: Testes exaustivos antes de produção
5. **📚 DOCUMENTAÇÃO COMPLETA**: Tudo registrado para manutenção futura

### 🚀 PRÓXIMOS PASSOS IMEDIATOS

1. **Aprovação do Plano**: Validar estratégia com stakeholders
2. **Setup dos MCPs**: Configurar todos os MCPs necessários
3. **Início da Fase 1**: Começar análise de riscos detalhada
4. **Formação da Equipe**: Treinar equipe nos procedimentos
5. **Configuração de Alertas**: Implementar monitoramento básico

---

**💎 GARANTIA DE SUCESSO**: Este plano foi estruturado usando Sequential Thinking MCP para garantir que cada etapa seja logicamente conectada e validada, com uso coordenado de todos os MCPs disponíveis para maximizar a segurança e minimizar os riscos.

**🔒 COMPROMISSO**: Zero impacto no sistema atual funcionando + Frontend profissional entregue com qualidade máxima.

---

*Plano elaborado com Sequential Thinking MCP e validado para uso coordenado de todos os MCPs disponíveis (Supabase, Vercel, Render, Prisma, Memory, Firecrawl) para garantir implementação 100% segura.*
