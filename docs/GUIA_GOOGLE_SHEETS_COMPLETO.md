# 📊 **GUIA COMPLETO: Google Sheets + CRM Integration**

## 🎯 **VISÃO GERAL**

Sistema completo de integração:
- **ENTRADA**: Detecta novos leads de planilha Google Sheets
- **PROCESSAMENTO**: Qualifica leads via WhatsApp com IA
- **SAÍDA**: Envia resultados automaticamente para CRM (planilha)

---

## 📋 **PARTE 1: CONFIGURAR ENTRADA DE LEADS**

### **🔑 PASSO 1: Criar Credenciais Google (5 min)**

1. **Acesse**: https://console.cloud.google.com/
2. **Criar projeto**:
   - Nome: `LDC-Agente-Sheets`
   - Clique **CREATE**

3. **Ativar APIs**:
   - Vá em **APIs & Services** > **Library**
   - Busque e ative: **Google Sheets API**
   - Busque e ative: **Google Drive API**

4. **Criar Service Account**:
   - Vá em **APIs & Services** > **Credentials**
   - Clique **+ CREATE CREDENTIALS** > **Service Account**
   - Nome: `ldc-agente-sheets`
   - Clique **CREATE AND CONTINUE**
   - Role: **Editor** (ou **Project Editor**)
   - Clique **DONE**

5. **Baixar Credenciais**:
   - Clique na service account criada
   - Aba **KEYS** > **ADD KEY** > **Create new key**
   - Tipo: **JSON**
   - Clique **CREATE**
   - **SALVE O ARQUIVO** como `credentials.json`

---

### **📊 PASSO 2: Criar Planilha de Entrada (3 min)**

1. **Criar planilha**: https://sheets.google.com/
   - Nome: **"LDC - Leads Entrada"**

2. **Configurar cabeçalhos na linha 1**:
   ```
   A1: nome
   B1: telefone  
   C1: email
   D1: canal
   E1: processado
   ```

3. **Exemplo de dados (linha 2 em diante)**:
   ```
   João Silva | 11999998888 | joao@email.com | youtube | 
   Maria Santos | 21987654321 | maria@email.com | newsletter |
   ```

4. **Compartilhar planilha**:
   - Clique **Share** (Compartilhar)
   - Adicione o **email da service account** (do passo 1)
   - Permissão: **Editor**
   - Clique **Send**

5. **Copiar ID da planilha**:
   - Da URL: `https://docs.google.com/spreadsheets/d/ID_AQUI/edit`
   - Copie apenas o `ID_AQUI`

---

## 📊 **PARTE 2: CONFIGURAR SAÍDA PARA CRM**

### **📈 PASSO 3: Criar Planilha CRM (3 min)**

1. **Criar nova planilha**:
   - Nome: **"LDC - CRM Resultados"**

2. **Configurar cabeçalhos na linha 1**:
   ```
   A1: nome
   B1: telefone
   C1: email
   D1: canal
   E1: status
   F1: score
   G1: patrimonio_faixa
   H1: objetivo
   I1: prazo
   J1: data_qualificacao
   K1: resumo_conversa
   L1: proximo_passo
   ```

3. **Compartilhar** com a service account (mesmo processo)
4. **Copiar ID** desta planilha também

---

## ⚙️ **PARTE 3: CONFIGURAR NO RENDER**

### **📁 PASSO 4: Upload do credentials.json (2 min)**

**Opção A - Via Dashboard Render**:
1. Vá para seu serviço no Render
2. **Settings** > **Environment**
3. **Add Environment Variable**:
   - Key: `GOOGLE_CREDENTIALS_JSON`
   - Value: Cole todo o conteúdo do arquivo `credentials.json`

**Opção B - Via Código** (recomendado):
1. Coloque o arquivo `credentials.json` na pasta `agente_qualificador/`
2. Adicione ao `.gitignore`: `credentials.json`
3. Faça upload manual via Render dashboard

---

### **🔧 PASSO 5: Configurar Variáveis de Ambiente (3 min)**

No Render, adicione estas variáveis:

```bash
# Planilha de ENTRADA (leads)
GOOGLE_SHEETS_ID=SEU_ID_DA_PLANILHA_ENTRADA
GOOGLE_SHEETS_RANGE=Sheet1!A:E
GOOGLE_CREDENTIALS_PATH=/app/credentials.json

# Planilha de SAÍDA (CRM)
GOOGLE_CRM_SHEETS_ID=SEU_ID_DA_PLANILHA_CRM
GOOGLE_CRM_SHEETS_RANGE=Sheet1!A:L
```

**Substitua**:
- `SEU_ID_DA_PLANILHA_ENTRADA`: ID da planilha do Passo 2
- `SEU_ID_DA_PLANILHA_CRM`: ID da planilha do Passo 3

---

## 🚀 **PARTE 4: TESTAR E USAR**

### **✅ PASSO 6: Testar Conexão**

1. **Teste via API**:
   ```bash
   GET https://agente-qualificador-ldc.onrender.com/google-sheets/test
   ```

2. **Resposta esperada**:
   ```json
   {
     "success": true,
     "entrada": {
       "configurado": true,
       "nome": "LDC - Leads Entrada",
       "id": "1ABC..."
     },
     "crm": {
       "configurado": true,
       "nome": "LDC - CRM Resultados", 
       "id": "2DEF..."
     }
   }
   ```

---

### **🔄 PASSO 7: Processar Leads**

1. **Adicionar leads na planilha de entrada**:
   - Nome, telefone, email, canal
   - Deixar coluna "processado" vazia

2. **Executar detecção**:
   ```bash
   POST https://agente-qualificador-ldc.onrender.com/google-sheets/detectar-leads
   ```

3. **O sistema vai**:
   - Detectar novos leads
   - Criar no banco de dados
   - Iniciar qualificação via WhatsApp
   - Marcar como "processado" na planilha

---

### **📊 PASSO 8: Resultados Automáticos**

**O sistema envia automaticamente para CRM quando**:
- Lead é qualificado (score ≥ 70)
- Lead é semi-qualificado (score ≥ 40)
- Conversação é finalizada

**Dados enviados**:
- Informações básicas do lead
- Score de qualificação
- Patrimônio, objetivo, prazo coletados
- Resumo da conversa
- Próximo passo recomendado

---

## 🎯 **FLUXO COMPLETO DE FUNCIONAMENTO**

```
1. 📝 Adicionar lead na planilha entrada
2. 🔄 Sistema detecta novo lead
3. 💬 Inicia qualificação via WhatsApp  
4. 🤖 IA conduz conversa SPIN
5. 📊 Calcula score baseado no progresso
6. 📈 Envia resultado automaticamente para CRM
7. ✅ Lead aparece no CRM com todas as informações
```

---

## 🛠️ **ENDPOINTS DISPONÍVEIS**

### **Testar Conexão**:
```bash
GET /google-sheets/test
```

### **Detectar Novos Leads**:
```bash
POST /google-sheets/detectar-leads
```

### **Enviar Lead Específico para CRM**:
```bash
POST /google-sheets/enviar-crm
Content-Type: application/json

{
  "lead_id": "uuid-do-lead"
}
```

---

## 🎉 **RESULTADO FINAL**

✅ **Entrada automatizada** de leads via planilha  
✅ **Qualificação inteligente** com IA + SPIN Selling  
✅ **Saída automatizada** para CRM com dados completos  
✅ **Integração total** com sistema existente  

**Agora você tem um funil completo e automatizado!** 🚀

---

## 🆘 **TROUBLESHOOTING**

### **Erro: "credentials.json não encontrado"**
- Verifique se fez upload do arquivo
- Confirme a variável `GOOGLE_CREDENTIALS_PATH`

### **Erro: "Planilha não encontrada"**
- Verifique se compartilhou com service account
- Confirme os IDs das planilhas

### **Leads não sendo processados**
- Verifique formato dos dados na planilha
- Confirme que coluna "processado" está vazia

### **CRM não recebendo dados**
- Verifique se planilha CRM está compartilhada
- Confirme variável `GOOGLE_CRM_SHEETS_ID`
