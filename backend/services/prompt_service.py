"""
Serviço de Prompts Estruturados
Sistema de geração de prompts por estado com few-shots
"""
from typing import Dict, List, Any
from backend.models.conversation_models import (
    Estado, PromptContext, FewShotExample, FEW_SHOTS_EXEMPLOS
)


class PromptService:
    """Serviço para geração de prompts estruturados"""
    
    def __init__(self):
        self.system_prompt = self._build_system_prompt()
        self.json_schema = self._build_json_schema()
    
    def _build_system_prompt(self) -> str:
        """Constrói o prompt do sistema global"""
        return """você é o agente comercial da ldc capital. objetivo: qualificar leads em até 8 mensagens e agendar uma reunião de 30 minutos com um consultor. fale sempre em português do brasil, tom humano, curto e direto.

regras de estilo:
- use o nome do lead sempre
- 1 pergunta por mensagem
- máximo 350 caracteres
- ofereça 2–3 opções numeradas quando possível
- 1 emoji no máximo por mensagem
- confirme entendimento em 1 linha antes de avançar
- nunca repita perguntas já respondidas; não peça dados que já vieram nos slots
- se o lead não entender, siga o protocolo de reformulação em 3 passos: reformule simples → dê exemplo com números → ofereça opções
- só transfira para humano após 2 reformulações falharem

sobre a ldc capital:
- consultoria independente (fee-based), 100% remota, primeira reunião gratuita

seu objetivo em cada turno:
- preencher slots faltantes ou avançar para agendamento

saída:
- responda somente em json válido conforme o schema fornecido pelo chamador. não inclua texto fora do json."""
    
    def _build_json_schema(self) -> Dict[str, Any]:
        """Constrói o schema JSON de resposta"""
        return {
            "type": "object",
            "required": ["mensagem", "acao", "proximo_estado", "contexto", "score_parcial"],
            "properties": {
                "mensagem": {"type": "string", "maxLength": 350},
                "acao": {
                    "type": "string", 
                    "enum": ["continuar", "agendar", "finalizar", "transferir_humano"]
                },
                "proximo_estado": {
                    "type": "string",
                    "enum": ["inicio", "situacao", "patrimonio", "objetivo", "urgencia", "interesse", "agendamento", "educar", "finalizado"]
                },
                "contexto": {
                    "type": "object",
                    "properties": {
                        "patrimonio_range": {
                            "type": "string",
                            "enum": ["<=100k", "100-500k", ">500k"],
                            "nullable": True
                        },
                        "objetivo": {
                            "type": "string",
                            "enum": ["crescimento", "renda", "aposentadoria", "protecao"],
                            "nullable": True
                        },
                        "urgencia": {
                            "type": "string",
                            "enum": ["alta", "media", "baixa"],
                            "nullable": True
                        },
                        "interesse": {
                            "type": "string",
                            "enum": ["muito_alto", "alto", "medio", "baixo", "muito_baixo"],
                            "nullable": True
                        },
                        "autoridade": {
                            "type": "string",
                            "enum": ["decisor", "influenciador", "desconhecido"],
                            "nullable": True
                        },
                        "timing": {"type": "string", "nullable": True},
                        "budget": {"type": "string", "nullable": True},
                        "disponibilidade": {"type": "string", "nullable": True}
                    },
                    "additionalProperties": True
                },
                "score_parcial": {"type": "integer", "minimum": 0, "maximum": 100}
            },
            "additionalProperties": False
        }
    
    def build_user_prompt(self, context: PromptContext) -> str:
        """Constrói o prompt do usuário baseado no contexto"""
        
        # Instruções de execução
        execucao = f"""instruções de execução
- estado_atual: {context.estado_atual.value}
- slots_preenchidos: {context.get_slots_preenchidos_str()}
- slots_faltantes: {context.get_slots_faltantes_str()}
- nome_lead: {context.nome_lead}
- canal: {context.canal}
- ultima_mensagem_do_lead: "{context.ultima_mensagem_lead}"
- historico_resumido (máx 6 interações): {self._format_historico(context.historico_compacto)}

tarefa
- produza uma única mensagem que:
  1) confirme entendimento em 1 linha se já houver slots preenchidos,
  2) faça exatamente 1 pergunta para capturar o próximo slot faltante,
  3) ofereça 2–3 opções numeradas claras,
  4) se nenhum slot faltar, avance para agendamento com 2 alternativas de horário.

limites
- usar o nome {context.nome_lead}
- máximo 350 caracteres
- 1 emoji opcional
- não repita perguntas já respondidas

formato de saída
- responda somente em json válido conforme o schema"""
        
        # Instruções específicas por estado
        contexto_estado = self._get_contexto_estado(context.estado_atual, context.nome_lead)
        
        # Few-shots examples
        few_shots = self._get_few_shots(context.estado_atual, context.nome_lead)
        
        return f"{execucao}\n\n{contexto_estado}\n\n{few_shots}"
    
    def _format_historico(self, historico: List[Dict[str, str]]) -> str:
        """Formata histórico de forma compacta"""
        if not historico:
            return "primeira interação"
        
        formatted = []
        for msg in historico[-6:]:  # Últimas 6 mensagens
            tipo = "A:" if msg.get('tipo') == 'enviada' else "L:"
            formatted.append(f"{tipo} {msg.get('conteudo', '')[:100]}")
        
        return " | ".join(formatted)
    
    def _get_contexto_estado(self, estado: Estado, nome_lead: str) -> str:
        """Retorna instruções específicas por estado"""
        
        contextos = {
            Estado.INICIO: f"""estado=inicio
objetivo: obter permissão para conversar e preparar transição.
mensagem-alvo: apresentação breve + pergunta de continuidade.
exemplo bom: "oi, {nome_lead}. sou agente comercial da ldc capital (consultoria independente). posso te fazer 2 perguntas rápidas pra te ajudar melhor. 1) sim 2) agora não"
próximo: situacao.""",
            
            Estado.SITUACAO: f"""estado=situacao
objetivo: saber se já investe.
pergunta: "você já investe hoje ou está começando."
opções: 1) já invisto 2) estou começando.
mapear: já invisto → prossiga patrimônio; começando → patrimônio (assumir <=100k se confirmar).
próximo: patrimonio.""",
            
            Estado.PATRIMONIO: f"""estado=patrimonio
objetivo: faixa de valor.
pergunta: "pra te orientar certo, qual faixa você tem hoje."
opções: 1) até 100 mil 2) 100–500 mil 3) acima de 500 mil.
se não entender: exemplo com números e linguagem simples.
próximo: objetivo.""",
            
            Estado.OBJETIVO: f"""estado=objetivo
objetivo: intenção financeira.
pergunta: "o que você busca com esse dinheiro."
opções: 1) crescer no longo prazo 2) renda mensal 3) aposentadoria 4) proteger.
próximo: urgencia (se necessário) ou direto interesse/agendamento se claro.""",
            
            Estado.URGENCIA: f"""estado=urgencia
objetivo: horizonte temporal.
pergunta: "quando quer ver resultados mais consistentes."
opções: 1) começar agora 2) próximos meses 3) sem pressa.
mapear: alta, média, baixa.
próximo: interesse/agendamento.""",
            
            Estado.INTERESSE: f"""estado=interesse
objetivo: validar apetite por diagnóstico.
pergunta: "faz sentido uma segunda opinião na sua carteira em 30 min, sem compromisso."
opções: 1) sim, quero 2) me manda material 3) agora não.
sim → agendamento; material → educar; não → educar.""",
            
            Estado.AGENDAMENTO: f"""estado=agendamento
objetivo: marcar reunião.
mensagem: "ótimo, {nome_lead}. posso te encaixar em um papo de 30 min."
opções (duas janelas): 1) amanhã 10h 2) amanhã 16h 3) sugerir outro horário.
se escolher 3, peça dia/horário livre.
sempre acao=agendar.""",
            
            Estado.EDUCAR: f"""estado=educar
objetivo: nutrir e pedir permissão de recontato.
mensagem: oferecer material sobre independência x banco e pedir ok para retorno.
opções: 1) pode enviar 2) prefiro depois.
se 1, registre interesse baixo e colete e-mail se fizer sentido."""
        }
        
        return contextos.get(estado, f"estado={estado.value}\nobjetivo: continuar conversa de forma natural.")
    
    def _get_few_shots(self, estado: Estado, nome_lead: str) -> str:
        """Retorna exemplos few-shot para o estado"""
        
        if estado not in FEW_SHOTS_EXEMPLOS:
            return ""
        
        examples = FEW_SHOTS_EXEMPLOS[estado][:2]  # Máximo 2 exemplos
        
        few_shots = f"exemplos para {estado.value}:\n"
        
        for i, example in enumerate(examples, 1):
            few_shots += f"""
exemplo {i}:
situação: {example.situacao}
✅ bom: {example.resposta_boa.replace('{nome}', nome_lead)}
❌ evitar: {example.resposta_ruim}
"""
        
        return few_shots
    
    def build_reformulacao_prompt(self, estado: Estado, nome_lead: str, tentativa: int) -> str:
        """Constrói prompt para reformulação quando lead não entende"""
        
        reformulacoes = {
            1: f"reformule de forma mais simples para {nome_lead}. use linguagem popular e direta.",
            2: f"dê um exemplo concreto com números para {nome_lead} entender melhor.",
            3: f"ofereça 2-3 opções numeradas bem claras para {nome_lead} escolher."
        }
        
        instrucao = reformulacoes.get(tentativa, reformulacoes[3])
        
        return f"""REFORMULAÇÃO (tentativa {tentativa}):
{instrucao}

estado: {estado.value}
máximo 350 caracteres
use o nome {nome_lead}
responda somente em json válido"""
    
    def build_classificador_prompt(self, mensagem: str) -> str:
        """Constrói prompt para classificador de intenção"""
        
        return f"""tarefa: classifique a mensagem abaixo.
mensagem: "{mensagem}"

responda em json:
{{
  "intencao": "interesse|objecao|duvida|informacao|agendamento|recusa",
  "sentimento": "positivo|neutro|negativo",
  "urgencia": 1-10,
  "qualificacao_score": 0-100,
  "principais_pontos": [".", "."]
}}

regras:
- se contiver disponibilidade ou aceite explícito, intencao=agendamento
- se contiver "não", "depois", "sem tempo", avaliar como recusa ou baixa urgência
- mantenha consistente e curto"""
    
    def get_guardrails_checklist(self) -> List[str]:
        """Retorna checklist de guardrails de estilo"""
        return [
            "contém nome do lead",
            "<= 350 caracteres",
            "1 pergunta, 2–3 opções numeradas",
            "no máximo 1 emoji",
            "não repete slot já preenchido",
            "se em agendamento, sempre sugira 2 horários concretos"
        ]
    
    def get_frases_banidas(self) -> List[str]:
        """Retorna lista de frases que devem ser evitadas"""
        return [
            "não entendi",
            "descreva detalhadamente",
            "qual o valor exato",
            "defina um prazo exato",
            "quais são seus objetivos financeiros de curto, médio e longo prazo",
            "qualquer horário serve",
            "vamos marcar amanhã às",
            "ok."  # resposta seca
        ]
