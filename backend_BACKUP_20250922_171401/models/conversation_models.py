"""
Modelos Pydantic para o Sistema de Conversação IA
Sistema de slot filling e controle de estado melhorado
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class PatrimonioRange(str, Enum):
    """Faixas de patrimônio"""
    ATE_100K = "<=100k"
    ENTRE_100_500K = "100-500k"
    ACIMA_500K = ">500k"


class Objetivo(str, Enum):
    """Objetivos financeiros"""
    CRESCIMENTO = "crescimento"
    RENDA = "renda"
    APOSENTADORIA = "aposentadoria"
    PROTECAO = "protecao"


class Urgencia(str, Enum):
    """Níveis de urgência"""
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class Interesse(str, Enum):
    """Níveis de interesse"""
    MUITO_ALTO = "muito_alto"
    ALTO = "alto"
    MEDIO = "medio"
    BAIXO = "baixo"
    MUITO_BAIXO = "muito_baixo"


class Autoridade(str, Enum):
    """Nível de autoridade de decisão"""
    DECISOR = "decisor"
    INFLUENCIADOR = "influenciador"
    DESCONHECIDO = "desconhecido"


class Acao(str, Enum):
    """Ações possíveis do agente"""
    CONTINUAR = "continuar"
    AGENDAR = "agendar"
    FINALIZAR = "finalizar"
    TRANSFERIR_HUMANO = "transferir_humano"


class Estado(str, Enum):
    """Estados da máquina de conversação"""
    INICIO = "inicio"
    SITUACAO = "situacao"
    PATRIMONIO = "patrimonio"
    OBJETIVO = "objetivo"
    URGENCIA = "urgencia"
    INTERESSE = "interesse"
    AGENDAMENTO = "agendamento"
    EDUCAR = "educar"
    FINALIZADO = "finalizado"


class ContextoConversa(BaseModel):
    """Contexto da conversa com slots preenchidos"""
    patrimonio_range: Optional[PatrimonioRange] = None
    objetivo: Optional[Objetivo] = None
    urgencia: Optional[Urgencia] = None
    interesse: Optional[Interesse] = None
    autoridade: Optional[Autoridade] = None
    timing: Optional[str] = None
    budget: Optional[str] = None
    disponibilidade: Optional[str] = None
    
    # Campos adicionais para controle
    tentativas_reformulacao: int = 0
    mensagens_enviadas: int = 0
    ja_investiu: Optional[bool] = None
    
    model_config = ConfigDict(use_enum_values=True)


class RespostaIA(BaseModel):
    """Schema de resposta da IA"""
    mensagem: str = Field(..., max_length=350, description="Mensagem para o lead")
    acao: Acao = Field(..., description="Próxima ação do agente")
    proximo_estado: Estado = Field(..., description="Próximo estado da conversa")
    contexto: ContextoConversa = Field(default_factory=ContextoConversa, description="Contexto atualizado")
    score_parcial: int = Field(..., ge=0, le=100, description="Score parcial de qualificação")
    
    @field_validator('mensagem')
    @classmethod
    def validar_mensagem(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("Mensagem não pode estar vazia")
        if len(v) > 350:
            raise ValueError("Mensagem muito longa (máximo 350 caracteres)")
        return v.strip()
    
    model_config = ConfigDict(use_enum_values=True)


class IntencaoLead(BaseModel):
    """Análise de intenção do lead"""
    intencao: Literal["interesse", "objecao", "duvida", "informacao", "agendamento", "recusa"]
    sentimento: Literal["positivo", "neutro", "negativo"]
    urgencia: int = Field(..., ge=1, le=10)
    qualificacao_score: int = Field(..., ge=0, le=100)
    principais_pontos: List[str] = Field(default_factory=list)


class PromptContext(BaseModel):
    """Contexto para geração de prompts"""
    estado_atual: Estado
    slots_preenchidos: Dict[str, Any]
    slots_faltantes: List[str]
    nome_lead: str
    canal: str
    ultima_mensagem_lead: str
    historico_compacto: List[Dict[str, str]]
    tentativas_estado: int = 0
    
    def get_slots_preenchidos_str(self) -> str:
        """Retorna slots preenchidos como string JSON"""
        return str(self.slots_preenchidos) if self.slots_preenchidos else "{}"
    
    def get_slots_faltantes_str(self) -> str:
        """Retorna lista de slots faltantes como string"""
        return ", ".join(self.slots_faltantes) if self.slots_faltantes else "nenhum"


class SessionState(BaseModel):
    """Estado da sessão de conversa"""
    lead_id: str
    session_id: str
    estado_atual: Estado = Estado.INICIO
    contexto: ContextoConversa = Field(default_factory=ContextoConversa)
    mensagem_count: int = 0
    reformulacoes_usadas: int = 0
    transferir_humano: bool = False
    finalizada: bool = False
    
    def slots_preenchidos(self) -> Dict[str, Any]:
        """Retorna slots que já foram preenchidos"""
        slots = {}
        if self.contexto.patrimonio_range:
            slots['patrimonio_range'] = self.contexto.patrimonio_range
        if self.contexto.objetivo:
            slots['objetivo'] = self.contexto.objetivo
        if self.contexto.urgencia:
            slots['urgencia'] = self.contexto.urgencia
        if self.contexto.interesse:
            slots['interesse'] = self.contexto.interesse
        if self.contexto.autoridade:
            slots['autoridade'] = self.contexto.autoridade
        if self.contexto.timing:
            slots['timing'] = self.contexto.timing
        if self.contexto.disponibilidade:
            slots['disponibilidade'] = self.contexto.disponibilidade
        return slots
    
    def slots_faltantes(self) -> List[str]:
        """Retorna lista de slots que ainda precisam ser preenchidos"""
        faltantes = []
        if not self.contexto.patrimonio_range and self.estado_atual != Estado.INICIO:
            faltantes.append('patrimonio_range')
        if not self.contexto.objetivo and self.estado_atual not in [Estado.INICIO, Estado.SITUACAO, Estado.PATRIMONIO]:
            faltantes.append('objetivo')
        if not self.contexto.urgencia and self.estado_atual in [Estado.URGENCIA, Estado.INTERESSE, Estado.AGENDAMENTO]:
            faltantes.append('urgencia')
        if not self.contexto.interesse and self.estado_atual in [Estado.INTERESSE, Estado.AGENDAMENTO]:
            faltantes.append('interesse')
        return faltantes
    
    def pode_agendar(self) -> bool:
        """Verifica se já tem dados suficientes para agendamento"""
        return (
            self.contexto.patrimonio_range is not None and
            self.contexto.objetivo is not None and
            (self.contexto.interesse in [Interesse.MUITO_ALTO, Interesse.ALTO] or
             self.contexto.urgencia == Urgencia.ALTA)
        )
    
    def proximo_estado_logico(self) -> Estado:
        """Determina o próximo estado baseado nos slots preenchidos"""
        if self.estado_atual == Estado.INICIO:
            return Estado.SITUACAO
        elif self.estado_atual == Estado.SITUACAO:
            return Estado.PATRIMONIO
        elif self.estado_atual == Estado.PATRIMONIO:
            return Estado.OBJETIVO
        elif self.estado_atual == Estado.OBJETIVO:
            if self.pode_agendar():
                return Estado.AGENDAMENTO
            return Estado.URGENCIA
        elif self.estado_atual == Estado.URGENCIA:
            return Estado.INTERESSE
        elif self.estado_atual == Estado.INTERESSE:
            if self.contexto.interesse in [Interesse.MUITO_ALTO, Interesse.ALTO]:
                return Estado.AGENDAMENTO
            else:
                return Estado.EDUCAR
        elif self.estado_atual == Estado.AGENDAMENTO:
            return Estado.FINALIZADO
        else:
            return Estado.FINALIZADO


class ValidacaoResposta(BaseModel):
    """Resultado da validação de resposta da IA"""
    valida: bool
    erros: List[str] = Field(default_factory=list)
    resposta_corrigida: Optional[RespostaIA] = None
    
    def adicionar_erro(self, erro: str):
        """Adiciona um erro à lista"""
        self.erros.append(erro)
        self.valida = False


class FewShotExample(BaseModel):
    """Exemplo para few-shot learning"""
    situacao: str
    resposta_boa: str
    resposta_ruim: str
    explicacao: str


# Constantes para configuração
MAX_MENSAGENS_POR_CONVERSA = 8
MAX_REFORMULACOES_POR_ESTADO = 2
TEMPERATURA_IA = 0.3
TOP_P_IA = 1.0
TIMEOUT_IA_SEGUNDOS = 15

# Few-shot examples por estado
FEW_SHOTS_EXEMPLOS = {
    Estado.SITUACAO: [
        FewShotExample(
            situacao='lead: "não sei bem"',
            resposta_boa='show, {nome}. só pra eu te orientar melhor: 1) já investe hoje 2) está começando. 🙂',
            resposta_ruim='descreva detalhadamente sua situação financeira atual.',
            explicacao='Sempre oferecer opções numeradas simples'
        ),
        FewShotExample(
            situacao='lead: "tenho um pouco investido"',
            resposta_boa='legal, {nome}. entendi que já investe! vamos ver quanto você tem disponível então.',
            resposta_ruim='quanto exatamente você tem investido em reais?',
            explicacao='Confirmar entendimento antes de avançar'
        )
    ],
    Estado.PATRIMONIO: [
        FewShotExample(
            situacao='lead: "tenho um pouco"',
            resposta_boa='legal, {nome}. qual faixa fica mais perto. 1) até 100 mil 2) 100–500 mil 3) acima de 500 mil',
            resposta_ruim='qual o valor exato do seu patrimônio total em reais.',
            explicacao='Usar faixas ao invés de valores exatos'
        ),
        FewShotExample(
            situacao='lead: "não sei bem quanto tenho"',
            resposta_boa='sem problema, {nome}. é mais ou menos assim: 1) comecinho (até 100k) 2) médio (100-500k) 3) já bem (500k+)',
            resposta_ruim='você precisa saber o valor exato para continuar',
            explicacao='Reformular com linguagem simples'
        )
    ],
    Estado.OBJETIVO: [
        FewShotExample(
            situacao='lead: "quero melhorar"',
            resposta_boa='entendi. o que te atrai mais. 1) crescer ao longo dos anos 2) renda todo mês 3) aposentadoria 4) proteger o que tem',
            resposta_ruim='quais são seus objetivos financeiros de curto, médio e longo prazo.',
            explicacao='Opções claras e específicas'
        ),
        FewShotExample(
            situacao='lead: "não sei o que quero"',
            resposta_boa='normal, {nome}. imagina: você prefere 1) ver o dinheiro crescer bastante 2) receber uma renda extra 3) se aposentar bem?',
            resposta_ruim='você deve definir objetivos claros primeiro',
            explicacao='Dar exemplos concretos'
        )
    ]
}
