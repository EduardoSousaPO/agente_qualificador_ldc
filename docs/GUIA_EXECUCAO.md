# 🚀 Guia de Execução - Agente Qualificador de Leads

## 📋 Visão Geral

O **Agente Qualificador de Leads** é um sistema completo que monitora planilhas de leads, realiza abordagem ativa personalizada via WhatsApp, conduz qualificação automatizada com IA e calcula scoring inteligente.

### 🎯 Funcionalidades Principais

- ✅ Monitoramento automático de planilha Google Sheets
- ✅ Abordagem inicial personalizada por canal (YouTube, Newsletter, E-book, Meta Ads)
- ✅ Qualificação automática com 4 perguntas estruturadas
- ✅ Sistema de scoring 0-100 pontos
- ✅ Integração com WhatsApp via WAHA
- ✅ Persistência completa no Supabase
- ✅ API REST para monitoramento e controle
- ✅ Logs estruturados e rastreamento de erros

## 🛠️ Pré-requisitos

### Infraestrutura
- VPS Hostinger com EasyPanel
- WAHA (WhatsApp HTTP API) já instalado
- Banco Supabase configurado (ID: `wsoxukpeyzmpcngjugie`)

### APIs e Integrações
- OpenAI API Key (GPT-4/3.5)
- Google Sheets API (credentials.json)
- Supabase Service Role Key

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Copie `.env.template` para `.env` e configure:

```bash
# Supabase
SUPABASE_URL=https://wsoxukpeyzmpcngjugie.supabase.co
SUPABASE_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview

# WAHA (WhatsApp HTTP API)
WAHA_BASE_URL=http://your-vps-ip:3000
WAHA_SESSION_NAME=default
WAHA_WEBHOOK_URL=http://your-vps-ip:5000/webhook

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_RANGE=Sheet1!A:D

# Flask
FLASK_ENV=production
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
SECRET_KEY=your_secret_key_here
```

### 2. Instalação de Dependências

```bash
cd agente_qualificador
pip install -r requirements.txt
```

### 3. Configuração Google Sheets

1. Baixe `credentials.json` do Google Cloud Console
2. Coloque na raiz do projeto
3. Configure a planilha com headers: `nome`, `telefone`, `email`, `canal`

### 4. Configuração WAHA

Certifique-se que WAHA está rodando e configure o webhook:

```bash
curl -X POST http://your-vps-ip:3000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://your-vps-ip:5000/webhook",
    "events": ["message"],
    "session": "default"
  }'
```

## 🚀 Execução

### Desenvolvimento
```bash
cd agente_qualificador/backend
python app.py
```

### Produção (Docker)
```bash
docker-compose up -d
```

### Produção (EasyPanel)
1. Fazer upload dos arquivos para VPS
2. Configurar aplicação no EasyPanel
3. Definir variáveis de ambiente
4. Deploy da aplicação

## 📊 Endpoints da API

### Health Check
```
GET /health
```

### Webhook WhatsApp
```
POST /webhook
```

### Gerenciamento de Leads
```
GET /leads                    # Listar leads
GET /leads/{id}               # Detalhes do lead
POST /leads/{id}/requalify    # Requalificar lead
```

### Processamento
```
POST /process-new-leads       # Processar novos leads da planilha
```

### Monitoramento
```
GET /stats                    # Estatísticas gerais
GET /logs                     # Logs do sistema
```

### Testes
```
POST /test-scoring           # Testar algoritmo de scoring
```

## 🔄 Fluxo de Funcionamento

### 1. Detecção de Leads
- Sistema monitora planilha Google Sheets
- Detecta novos leads automaticamente
- Valida dados obrigatórios (nome, telefone, canal)

### 2. Abordagem Inicial
- Mensagem personalizada por canal:
  - **YouTube**: Foco em diagnóstico gratuito
  - **Newsletter**: Referência ao acesso da newsletter
  - **E-book**: Menção ao download do e-book
  - **Meta Ads**: Agradecimento pela inscrição

### 3. Qualificação (4 Perguntas)

#### Pergunta 1: Patrimônio (0-30 pontos)
- Valor disponível para investimentos
- Análise por faixas de valores
- Detecção automática de números mencionados

#### Pergunta 2: Objetivo (0-25 pontos)
- Principal objetivo com investimentos
- Categorias: Investimento, Crescimento, Aposentadoria, Proteção
- Pontuação baseada em potencial de retorno

#### Pergunta 3: Urgência (0-25 pontos)
- Prazo para começar a investir
- Escala: Imediato → Longo prazo
- Maior urgência = maior pontuação

#### Pergunta 4: Interesse (0-20 pontos)
- Interesse em conversar com especialista
- Validação do engajamento do lead
- Indicador de conversão

### 4. Scoring e Resultado

#### Score ≥ 70: QUALIFICADO
- Convite para reunião com especialista
- Agendamento direto via WhatsApp
- Encaminhamento para equipe comercial

#### Score < 70: NÃO QUALIFICADO
- Envio de conteúdo educativo
- E-books, webinars, planilhas
- Nutrição para futuro reengajamento

## 📈 Sistema de Scoring

### Algoritmo Inteligente
- **Análise semântica** das respostas
- **Detecção de números** e valores específicos
- **Palavras-chave contextuais** por categoria
- **Validação automática** de respostas

### Pontuação Detalhada

| Categoria | Pontos | Critérios |
|-----------|--------|-----------|
| Patrimônio | 0-30 | Valor disponível, faixas de investimento |
| Objetivo | 0-25 | Tipo de investimento, potencial de retorno |
| Urgência | 0-25 | Prazo para início, necessidade imediata |
| Interesse | 0-20 | Engajamento, disposição para conversar |

## 🗄️ Estrutura do Banco

### Tabelas Principais

#### `leads`
- Informações básicas do lead
- Status e score atual
- Controle de processamento

#### `sessions`
- Sessões de conversa ativas
- Estado atual do fluxo
- Contexto da conversa

#### `messages`
- Histórico completo de mensagens
- Tipo (enviada/recebida)
- Metadata adicional

#### `qualificacoes`
- Respostas detalhadas
- Pontuação por categoria
- Observações e resultado

#### `system_logs`
- Logs estruturados
- Rastreamento de erros
- Auditoria do sistema

## 🔧 Monitoramento

### Métricas Importantes
- Taxa de conversão (leads → qualificados)
- Score médio por canal
- Tempo médio de qualificação
- Taxa de resposta no WhatsApp

### Logs Estruturados
- Todos os eventos são logados
- Níveis: INFO, WARNING, ERROR, DEBUG
- Contexto completo para debugging

### Alertas
- Erros de integração (WAHA, Supabase, Google Sheets)
- Sessões com timeout
- Falhas no envio de mensagens

## 🧪 Testes

### Teste de Scoring
```bash
curl -X POST http://localhost:5000/test-scoring \
  -H "Content-Type: application/json" \
  -d '{
    "patrimonio": "Tenho 1 milhão para investir",
    "objetivo": "Quero fazer meu dinheiro render",
    "urgencia": "Preciso começar agora",
    "interesse": "Sim, tenho muito interesse"
  }'
```

### Teste de Processamento
```bash
curl -X POST http://localhost:5000/process-new-leads
```

### Verificação de Health
```bash
curl http://localhost:5000/health
```

## 🚨 Troubleshooting

### Problemas Comuns

#### WAHA não responde
- Verificar se serviço está rodando
- Conferir URL base e session name
- Testar conectividade de rede

#### Google Sheets não autorizado
- Verificar credentials.json
- Renovar token de acesso
- Conferir permissões da planilha

#### Supabase connection error
- Verificar URL e keys
- Testar conectividade
- Conferir limites de conexão

#### Mensagens não enviadas
- Verificar status da sessão WhatsApp
- Conferir formato dos telefones
- Verificar logs de erro

### Logs para Debugging
```bash
# Ver logs de erro
curl http://localhost:5000/logs?nivel=ERROR

# Ver estatísticas
curl http://localhost:5000/stats

# Verificar lead específico
curl http://localhost:5000/leads/{lead_id}
```

## 🔄 Manutenção

### Backup
- Dados no Supabase (backup automático)
- Configurações e credenciais
- Logs importantes

### Atualizações
- Monitorar performance do scoring
- Ajustar mensagens baseado no feedback
- Otimizar algoritmos de qualificação

### Escalabilidade
- Monitorar uso de recursos
- Configurar auto-scaling se necessário
- Otimizar queries do banco

## 📞 Suporte

Para questões técnicas:
1. Verificar logs do sistema
2. Consultar documentação de APIs
3. Testar componentes individualmente
4. Revisar configurações de ambiente

---

*Sistema desenvolvido com MCPs do Cursor.ai para máxima eficiência e qualidade.*



