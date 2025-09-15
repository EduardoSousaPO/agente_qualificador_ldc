# 🤖 Agente de IA Qualificador com Abordagem Ativa

## 🎯 Visão Geral
Este projeto tem como objetivo desenvolver um **Agente de IA Qualificador de Leads via WhatsApp**, que **não apenas responde**, mas também **inicia conversas ativamente** com leads assim que eles entram em uma planilha (Google Sheets ou Excel Online).  

O agente respeita o **canal de origem** do lead (YouTube, Newsletter, Meta Ads, E-book, etc.) e adapta a abordagem inicial de acordo com esse contexto.  

## 🔄 Mudança de Paradigma
- **Antes:** O WAHA ficava apenas **esperando** mensagens recebidas no WhatsApp.  
- **Agora:** O agente também tem um **gatilho proativo**:
  1. Detecta entrada de novo lead na planilha.  
  2. Identifica o canal de origem.  
  3. Dispara mensagem inicial personalizada via WAHA.  

## 🏗️ Arquitetura Atualizada

### 📌 Componentes
- **Google Sheets / Excel Online:** fonte dos leads. Cada linha contém nome, telefone, email e canal.  
- **Backend (Flask):**
  - Roda na VPS Hostinger (EasyPanel).  
  - Conecta-se periodicamente à planilha (via API do Google Sheets) e detecta novos leads.  
  - Identifica canal de origem.  
  - Dispara mensagem inicial personalizada via WAHA.  
  - Conduz qualificação (4 perguntas → score → decisão).  
  - Salva histórico no Supabase.  
- **WAHA:** já rodando na VPS, envia e recebe mensagens WhatsApp.  
- **Supabase:** armazena leads, mensagens, qualificações e status.  
- **OpenAI GPT-4/3.5:** conduz conversa em tom humano e natural.  

### 📌 Fluxo Detalhado
1. **Lead entra via canal** (YouTube, Newsletter, E-book, Meta Ads).  
2. **Lead é registrado na planilha** (linha com dados).  
3. **Agente detecta novo lead:**
   - Via integração com Google Sheets API (polling ou webhook).  
   - Extrai nome, telefone e canal.  
4. **Agente inicia contato ativo:**
   - YouTube → “Olá [Nome], vi que você se aplicou no YouTube pedindo um diagnóstico gratuito…”  
   - Newsletter → “Olá [Nome], notei que você baixou nosso material pela newsletter…”  
   - E-book → “Olá [Nome], vi que você baixou nosso e-book [Título]…”  
   - Meta Ads → “Olá [Nome], obrigado por se inscrever através da nossa campanha…”  
5. **Agente conduz qualificação (4 perguntas):**
   - Patrimônio (0–30 pts)  
   - Objetivo (0–25 pts)  
   - Urgência (0–25 pts)  
   - Interesse em especialista (0–20 pts)  
6. **Score é calculado:**  
   - ≥70 → convite para reunião com especialista.  
   - <70 → conteúdo educativo + encerramento.  
7. **Supabase atualizado:**  
   - Dados do lead, canal de origem, histórico de mensagens e score.  
8. **Relatórios gerados:**  
   - Status do sistema, bugs encontrados, documentação de uso.  

---

## ✅ Resultado Esperado
Um MVP funcional rodando 24/7 na VPS, capaz de:  
- Detectar novos leads automaticamente em planilhas.  
- Iniciar conversas ativas no WhatsApp de forma personalizada.  
- Conduzir qualificação estruturada com base em 4 perguntas.  
- Calcular score e decidir próximo passo.  
- Persistir informações no Supabase.  
- Gerar relatórios de status e bugs para acompanhamento.  
