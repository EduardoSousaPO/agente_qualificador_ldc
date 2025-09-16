# 🚀 Configuração Render - Agente Qualificador LDC

## ✅ Status do Deploy

**URL da Aplicação:** https://agente-qualificador-ldc.onrender.com
**Status:** ✅ LIVE
**Última Correção:** Google Sheets configurado para produção

## 🔧 Variáveis de Ambiente Configuradas

```bash
SUPABASE_URL=https://wsoxukpeyzmpcngjugie.supabase.co
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=render_production_secret_key_2025
PYTHONPATH=/opt/render/project/src
LOG_LEVEL=INFO
SCORE_MINIMO_QUALIFICACAO=70
TIMEOUT_SESSAO_MINUTOS=60
MAX_TENTATIVAS_ENVIO=3
WAHA_SESSION_NAME=default
```

## ⚠️ Variáveis Pendentes (Adicionar via Render Dashboard)

```bash
# Supabase
SUPABASE_SERVICE_ROLE_KEY=sua_service_role_key_aqui

# OpenAI
OPENAI_API_KEY=sua_openai_api_key_aqui

# WAHA (WhatsApp)
WAHA_BASE_URL=http://sua-instancia-waha.com
WAHA_API_KEY=sua_waha_api_key_aqui

# Google Sheets (Opcional - para produção)
GOOGLE_SHEETS_ID=sua_planilha_id_aqui
```

## 🔍 Endpoints Disponíveis

1. **GET /** - Health check
2. **POST /webhook/whatsapp** - Webhook do WhatsApp
3. **POST /leads/processar** - Processar novos leads
4. **GET /leads** - Listar leads
5. **GET /sessions** - Listar sessões
6. **POST /qualification/start** - Iniciar qualificação
7. **POST /qualification/answer** - Responder pergunta
8. **GET /qualification/score** - Calcular score
9. **POST /meetings/schedule** - Agendar reunião
10. **GET /system/logs** - Logs do sistema

## 🛠️ Próximos Passos

1. **Adicionar as variáveis de ambiente pendentes** no Dashboard do Render
2. **Configurar WAHA** para receber mensagens do WhatsApp
3. **Configurar Supabase** com as tabelas necessárias
4. **Testar endpoints** da API
5. **Configurar Google Sheets** (opcional)

## 📊 Monitoramento

- **Logs:** Render Dashboard > Service > Logs
- **Métricas:** Render Dashboard > Service > Metrics
- **Status:** https://agente-qualificador-ldc.onrender.com/

## 🔧 Comandos Úteis (via MCP Render)

```bash
# Listar serviços
"Mostre meus serviços no Render"

# Ver logs
"Mostre os logs do agente qualificador"

# Atualizar variáveis
"Adicione a variável OPENAI_API_KEY no serviço agente_qualificador_ldc"

# Ver métricas
"Mostre as métricas de CPU e memória do agente qualificador"
```

## ✅ Correções Aplicadas

- ✅ Google Sheets funciona sem credentials.json em produção
- ✅ Logs de warning em vez de error
- ✅ Variáveis de ambiente básicas configuradas
- ✅ PYTHONPATH configurado corretamente
- ✅ Flask em modo produção
