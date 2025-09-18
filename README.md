# 🤖 Agente Qualificador de Leads via WhatsApp

Sistema completo de qualificação automática de leads via WhatsApp usando IA, desenvolvido com Flask e Supabase.

## 🎯 Funcionalidades

- ✅ Monitoramento automático de planilha Google Sheets
- ✅ Abordagem inicial personalizada por canal (YouTube, Newsletter, E-book, Meta Ads)
- ✅ Qualificação automática com 4 perguntas estruturadas
- ✅ Sistema de scoring inteligente 0-100 pontos
- ✅ Integração com WhatsApp via WAHA
- ✅ Persistência completa no Supabase
- ✅ API REST para monitoramento e controle
- ✅ Logs estruturados e rastreamento de erros

## 🏗️ Arquitetura

- **Backend**: Flask + Python 3.11
- **Database**: Supabase (PostgreSQL)
- **WhatsApp**: WAHA (WhatsApp HTTP API)
- **IA**: OpenAI GPT-4/3.5
- **Deploy**: Render (recomendado)

## 🚀 Deploy no Render

### 1. Configuração Rápida

1. Fork este repositório
2. Conecte com Render.com
3. Configure as variáveis de ambiente
4. Deploy automático!

### 2. Variáveis de Ambiente Obrigatórias

```env
SUPABASE_URL=sua_url_supabase
SUPABASE_SERVICE_ROLE_KEY=sua_service_key
OPENAI_API_KEY=sua_openai_key
WAHA_BASE_URL=sua_url_waha
WAHA_SESSION_NAME=default
FLASK_ENV=production
SECRET_KEY=sua_chave_secreta
```

## 📊 Sistema de Scoring

### Algoritmo Inteligente (0-100 pontos)

- **Patrimônio** (0-30 pontos): Valor disponível para investimento
- **Objetivo** (0-25 pontos): Tipo de investimento desejado
- **Urgência** (0-25 pontos): Prazo para começar
- **Interesse** (0-20 pontos): Disposição para conversar com especialista

### Resultado da Qualificação

- **≥ 70 pontos**: Lead qualificado → Agendamento de reunião
- **< 70 pontos**: Lead não qualificado → Conteúdo educativo

## 🔄 Fluxo de Funcionamento

1. **Detecção**: Sistema monitora planilha Google Sheets
2. **Abordagem**: Mensagem personalizada por canal via WhatsApp
3. **Qualificação**: 4 perguntas estruturadas conduzidas pela IA
4. **Scoring**: Cálculo automático baseado nas respostas
5. **Ação**: Agendamento ou envio de conteúdo educativo

## 🛠️ Desenvolvimento Local

```bash
# Clonar repositório
git clone https://github.com/EduardoSousaPO/agente_qualificador_ldc.git

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.template .env
# Editar .env com suas credenciais

# Executar aplicação
python backend/app.py
```

## 📚 Documentação

- [Guia de Execução](docs/GUIA_EXECUCAO.md)
- [Status Report](docs/STATUS_REPORT.md)
- [Bug Tracker](docs/BUGS_TRACKER.md)

## 🧪 Testes

```bash
# Executar teste completo do sistema
python tests/test_sistema_completo.py

# Testar endpoints
curl http://localhost:5000/health
```

## 📈 Monitoramento

- **Health Check**: `/health`
- **Estatísticas**: `/stats`
- **Logs**: `/logs`
- **Teste de Scoring**: `/test-scoring`

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 🆘 Suporte

Para questões técnicas, consulte a [documentação](docs/) ou abra uma issue.

---

**Desenvolvido com ❤️ usando MCPs do Cursor.ai**
