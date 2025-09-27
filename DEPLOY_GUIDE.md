# 🚀 GUIA COMPLETO DE DEPLOY - Frontend LDC Qualificador

## 📋 RESUMO DA ARQUITETURA

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   VERCEL    │    │   RENDER    │    │  SUPABASE   │
│ (Frontend)  │◄──►│ (Backend)   │◄──►│ (Database)  │
│   Next.js   │    │   Flask     │    │   + Auth    │
└─────────────┘    └─────────────┘    └─────────────┘
```

## ✅ PASSOS EXECUTADOS:

### 1. ✅ Estrutura do Frontend Criada
- **Localização**: `../frontend_agente_qualificador/`
- **Tecnologia**: Next.js 14 + TypeScript
- **Configuração**: package.json, tsconfig.json, .env.example

### 2. ✅ Supabase Configurado para Frontend
- **RLS habilitado** em todas as tabelas
- **Políticas de leitura** para usuários autenticados
- **View auxiliar** `vw_lead_overview` criada
- **Índices de performance** implementados

### 3. ✅ Arquivos de Deploy Preparados
- **vercel.json**: Configuração de build
- **.env.example**: Variáveis de ambiente
- **.gitignore**: Arquivos ignorados
- **README.md**: Documentação completa

## 🎯 PRÓXIMOS PASSOS (MANUAL):

### PASSO 1: Configurar Repositório GitHub

```bash
# Navegar para o diretório preparado
cd ../frontend_agente_qualificador

# Inicializar Git
git init

# Adicionar arquivos
git add .

# Commit inicial
git commit -m "Initial frontend setup for Vercel deploy"

# Conectar ao repositório remoto
git remote add origin https://github.com/EduardoSousaPO/frontend_agente_qualificador.git

# Push para main
git branch -M main
git push -u origin main
```

### PASSO 2: Conectar Vercel ao GitHub

1. **Acesse**: https://vercel.com/dashboard
2. **New Project** → **Import Git Repository**
3. **Selecione**: `frontend_agente_qualificador`
4. **Framework Preset**: Next.js (detectado automaticamente)
5. **Deploy**

### PASSO 3: Configurar Variáveis de Ambiente

**No Dashboard da Vercel → Settings → Environment Variables:**

#### 🔑 OBRIGATÓRIAS:
- `NEXT_PUBLIC_SUPABASE_URL`: `https://wsoxukpeyzmpcngjugie.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- `NEXT_PUBLIC_BACKEND_BASE_URL`: `https://agente-ldc.onrender.com`
- `NODE_ENV`: `production`

#### 📊 OPCIONAIS:
- `GOOGLE_SHEETS_ID`: `17TMF5z6CNzHPxzYg43uU-dR6Qyd1mWgUq-cYlkXnGYE`
- `GOOGLE_SHEETS_RANGE`: `Leads!A1:H`

### PASSO 4: Redeploy Após Configuração

1. **Deployments** → **Redeploy** (após configurar env vars)
2. **Aguardar build** completar
3. **Verificar URL** do deploy

## 🧪 TESTES PÓS-DEPLOY:

### ✅ Checklist de Verificação:

- [ ] **Frontend carrega** sem erros
- [ ] **Login funciona** via Supabase Auth
- [ ] **Dashboard exibe** dados dos leads
- [ ] **Conexão com backend** funcional
- [ ] **Métricas** são exibidas
- [ ] **Responsivo** em mobile

### 🔗 URLs Esperadas:

- **Frontend**: `https://frontend-agente-qualificador.vercel.app`
- **Backend**: `https://agente-ldc.onrender.com`
- **Database**: `https://wsoxukpeyzmpcngjugie.supabase.co`

## 🔧 TROUBLESHOOTING:

### Problema: Build falha
**Solução**: Verificar se todas as dependências estão no package.json

### Problema: Variáveis de ambiente não funcionam
**Solução**: Certificar que começam com `NEXT_PUBLIC_` para serem expostas

### Problema: Erro de CORS
**Solução**: Backend no Render deve aceitar requests do domínio da Vercel

### Problema: Autenticação falha
**Solução**: Verificar se RLS e políticas estão configuradas no Supabase

## 📞 SUPORTE:

- **Frontend Issues**: Vercel Dashboard → Functions → Logs
- **Backend Issues**: Render Dashboard → Logs
- **Database Issues**: Supabase Dashboard → Logs

## 🎊 CONCLUSÃO:

Após seguir estes passos, você terá:
- ✅ **Frontend na Vercel** (deploy automático via GitHub)
- ✅ **Backend no Render** (independente, já funcionando)
- ✅ **Database no Supabase** (configurado com RLS)
- ✅ **Arquitetura separada** e escalável

**🚀 Sistema pronto para produção com deploy automatizado!**
