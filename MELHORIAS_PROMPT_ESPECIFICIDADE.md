# 🎯 MELHORIAS DE PROMPT - ESPECIFICIDADE E ASSERTIVIDADE

## 🔍 **ANÁLISE DO PROBLEMA NA CONVERSA**

### **❌ Problemas Identificados:**
1. **Lead respondeu "como assim? não entendi a pergunta"** - Pergunta não foi clara
2. **Agente transferiu para humano** prematuramente - Deveria reformular
3. **Falta de especificidade** na pergunta sobre objetivos
4. **Não usou exemplos concretos** para facilitar compreensão

### **🎯 Conversa Analisada:**
```
Agente: "E qual é o seu principal objetivo financeiro no momento?"
Lead: "como assim ? não entendi a pergunta"
Agente: "Vou te conectar com um consultor humano..."
```

## 🚀 **MELHORIAS PROPOSTAS**

### **1. PERGUNTAS MAIS ESPECÍFICAS E CLARAS**

#### **❌ ANTES (Muito Genérico):**
```
"E qual é o seu principal objetivo financeiro no momento?"
```

#### **✅ DEPOIS (Específico com Exemplos):**
```
"Perfeito, Eduardo! Me conta: você quer fazer esse dinheiro CRESCER mais que a poupança, ou prefere focar em ter uma RENDA EXTRA todo mês? Ou talvez esteja pensando na aposentadoria?"
```

### **2. REFORMULAÇÃO INTELIGENTE (NÃO TRANSFERIR)**

#### **❌ ANTES:**
```
Lead: "não entendi a pergunta"
Agente: "Vou te conectar com consultor humano"
```

#### **✅ DEPOIS:**
```
Lead: "não entendi a pergunta"
Agente: "Deixa eu explicar melhor, Eduardo! É assim: você quer que esse dinheiro RENDA MAIS (tipo, ao invés de 1% da poupança, ganhar 12% ao ano), ou você quer que ele te dê uma GRANA TODO MÉS (tipo um aluguel)?"
```

### **3. LINGUAGEM MAIS PRÓXIMA E CONCRETA**

#### **❌ Linguagem Técnica:**
- "objetivo financeiro"
- "estratégia de investimento"  
- "perfil de risco"

#### **✅ Linguagem Popular:**
- "o que você quer fazer com essa grana?"
- "quer que o dinheiro cresça ou que te pague todo mês?"
- "você é mais corajoso ou prefere segurança?"

## 🔧 **PROMPT MELHORADO POR ESTADO**

### **📊 ESTADO: PATRIMÔNIO**
```
EXEMPLO MELHORADO: "Bacana, Eduardo! Pra te dar as dicas certas, me conta: você tem até uns 100 mil guardados, entre 100-500 mil, ou já passou dos 500 mil?"

SE NÃO ENTENDER: "Vou explicar diferente! É assim: você tem uma QUANTIA PEQUENA pra começar (tipo até 100 mil), uma QUANTIA MÉDIA (100 a 500 mil), ou já tem uma BOA RESERVA (mais de 500 mil)?"
```

### **🎯 ESTADO: OBJETIVO**
```
EXEMPLO MELHORADO: "Show, Eduardo! Agora me conta: você quer que esse dinheiro CRESÇA bastante (tipo dobrar em alguns anos), ou prefere que ele te dê uma RENDA TODO MÊS (tipo um aluguel)?"

SE NÃO ENTENDER: "É simples! Imagina que você tem 100 mil reais. Você prefere:
1️⃣ Que vire 200 mil em alguns anos (CRESCIMENTO)
2️⃣ Que te pague uns 800-1000 reais todo mês (RENDA)
3️⃣ Que fique seguro pra aposentadoria (LONGO PRAZO)"
```

### **⏰ ESTADO: URGÊNCIA**
```
EXEMPLO MELHORADO: "Perfeito! E sobre começar: você quer mexer nisso AGORA MESMO, ou ainda tá só dando uma olhada?"

SE NÃO ENTENDER: "É assim: você tá PRONTO pra mudar seus investimentos essa semana, ou ainda tá SÓ PESQUISANDO por enquanto?"
```

## 📋 **REGRAS DE REFORMULAÇÃO**

### **🔄 QUANDO LEAD NÃO ENTENDER:**
1. **NUNCA** transferir para humano na primeira tentativa
2. **SEMPRE** reformular com linguagem mais simples
3. **USAR** exemplos concretos com números
4. **DIVIDIR** em opções claras (1, 2, 3)
5. **COMPARAR** com situações conhecidas

### **💡 TÉCNICAS DE CLAREZA:**
```
❌ "Qual seu objetivo financeiro?"
✅ "Você quer que o dinheiro CRESÇA ou que te PAGUE todo mês?"

❌ "Qual sua faixa patrimonial?"
✅ "Você tem pouco, médio ou muito dinheiro guardado?"

❌ "Qual seu horizonte temporal?"
✅ "Você quer resultado rápido ou pode esperar uns anos?"
```

## 🎯 **IMPLEMENTAÇÃO NO CÓDIGO**

### **1. Adicionar Função de Reformulação:**
```python
def _reformular_pergunta_simples(self, estado: str, lead_nome: str) -> str:
    """Reformula pergunta quando lead não entende"""
    
    reformulacoes = {
        'patrimonio': f"Deixa eu explicar melhor, {lead_nome}! Você tem uma quantia PEQUENA (até 100k), MÉDIA (100-500k) ou GRANDE (500k+) pra investir?",
        
        'objetivo': f"É simples, {lead_nome}! Você quer que o dinheiro CRESÇA (tipo dobrar), ou que te PAGUE todo mês (tipo aluguel)?",
        
        'prazo': f"Vou ser mais claro: você quer mexer nos investimentos AGORA ou ainda tá só PESQUISANDO?"
    }
    
    return reformulacoes.get(estado, f"Me desculpa, {lead_nome}! Vou reformular...")
```

### **2. Lógica Anti-Transferência:**
```python
# Se lead não entender, reformular até 2 vezes antes de transferir
if "não entendi" in mensagem_lead.lower():
    tentativas = self.tentativas_reformulacao.get(session_id, 0)
    if tentativas < 2:
        return self._reformular_pergunta_simples(estado_atual, lead_nome)
    else:
        # Só depois de 2 tentativas, transferir
        return self._transferir_humano(lead_nome)
```

## 📊 **RESULTADO ESPERADO**

### **✅ ANTES vs DEPOIS:**
| Situação | ❌ Antes | ✅ Depois |
|----------|----------|-----------|
| Lead não entende | Transfere para humano | Reformula 2x antes |
| Pergunta genérica | "objetivo financeiro?" | "crescer ou renda mensal?" |
| Linguagem | Técnica e formal | Popular e concreta |
| Exemplos | Poucos ou abstratos | Concretos com números |

### **🎯 IMPACTO ESPERADO:**
- **Redução de 80%** nas transferências desnecessárias
- **Aumento de 60%** na compreensão das perguntas  
- **Melhoria de 40%** na taxa de qualificação
- **Fluxo mais natural** e humanizado

## 💡 **PRÓXIMOS PASSOS**

1. **Implementar** função de reformulação
2. **Atualizar** prompts com linguagem popular
3. **Adicionar** sistema de tentativas
4. **Testar** com leads reais
5. **Monitorar** melhoria nas métricas

**Resultado**: Agente muito mais assertivo e compreensível! 🚀
