"""
Serviço de Slot Filling Inteligente
Sistema de preenchimento automático de slots baseado em respostas do lead
"""
import re
from typing import Dict, Any, Optional, List, Tuple
import structlog

from backend.models.conversation_models import (
    ContextoConversa, PatrimonioRange, Objetivo, Urgencia, Interesse, Autoridade, Estado
)

logger = structlog.get_logger(__name__)


class SlotFillingService:
    """Serviço para preenchimento inteligente de slots"""
    
    def __init__(self):
        # Lógica de reconhecimento foi internalizada para simplificar o design.
        self.patrimonio_patterns = self._build_patrimonio_patterns()
        self.objetivo_patterns = self._build_objetivo_patterns()
        self.urgencia_patterns = self._build_urgencia_patterns()
        self.interesse_patterns = self._build_interesse_patterns()
        self.autoridade_patterns = self._build_autoridade_patterns()
    
    def extrair_slots_da_mensagem(self, mensagem: str, estado_atual: Estado, 
                                 contexto_atual: ContextoConversa) -> ContextoConversa:
        """Extrai e preenche slots baseado na mensagem do lead"""
        
        mensagem_lower = mensagem.lower().strip()
        logger.info("Extraindo slots", mensagem=mensagem_lower[:100], estado=str(estado_atual))
        
        # Criar nova instância do contexto para não mudar o original
        novo_contexto = ContextoConversa(**contexto_atual.model_dump())
        
        # Extrair slots baseado no estado atual
        if estado_atual == Estado.SITUACAO:
            novo_contexto = self._extrair_situacao_investimento(mensagem_lower, novo_contexto)
        
        elif estado_atual == Estado.PATRIMONIO:
            novo_contexto = self._extrair_patrimonio(mensagem_lower, novo_contexto)
        
        elif estado_atual == Estado.OBJETIVO:
            novo_contexto = self._extrair_objetivo(mensagem_lower, novo_contexto)
        
        elif estado_atual == Estado.URGENCIA:
            novo_contexto = self._extrair_urgencia(mensagem_lower, novo_contexto)
        
        elif estado_atual == Estado.INTERESSE:
            novo_contexto = self._extrair_interesse(mensagem_lower, novo_contexto)
        
        # Extrair informações transversais (podem aparecer em qualquer estado)
        novo_contexto = self._extrair_autoridade(mensagem_lower, novo_contexto)
        novo_contexto = self._extrair_timing(mensagem_lower, novo_contexto)
        novo_contexto = self._extrair_disponibilidade(mensagem_lower, novo_contexto)
        
        # Log das mudanças
        mudancas = self._detectar_mudancas(contexto_atual, novo_contexto)
        if mudancas:
            logger.info("Slots extraídos", mudancas=mudancas, estado=str(estado_atual))
        
        return novo_contexto
    
    def _extrair_situacao_investimento(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai se o lead já investe ou está começando"""
        
        # Padrões para "já investe"
        ja_investe_patterns = [
            r'\b(já|ja)\s+(invisto|tenho|possuo)\b',
            r'\b(tenho|possuo)\s+(investimento|aplicação|aplicado)\b',
            r'\b(invisto|aplico)\s+(já|ja|hoje)\b',
            r'\b(banco|corretora|xp|btg|nubank)\b',
            r'\b(cdb|lci|lca|tesouro|ações|fundos)\b',
            r'\b(poupança|conta|aplicação)\b',
            r'opção\s*1',  # Se ofereceu opções numeradas
            r'^1\b'  # Resposta "1"
        ]
        
        # Padrões para "começando"
        comecando_patterns = [
            r'\b(começando|comecando|iniciando|inicio)\b',
            r'\b(novo|novato|primeira|primeiro)\s+(vez|experiência|experiencia)\b',
            r'\b(não|nao)\s+(invisto|tenho|sei)\b',
            r'\b(zero|nada|nenhum)\b',
            r'opção\s*2',  # Se ofereceu opções numeradas
            r'^2\b'  # Resposta "2"
        ]
        
        if any(re.search(pattern, mensagem) for pattern in ja_investe_patterns):
            contexto.ja_investiu = True
            logger.info("Detectado: lead já investe")
        elif any(re.search(pattern, mensagem) for pattern in comecando_patterns):
            contexto.ja_investiu = False
            # Assumir patrimônio baixo se está começando
            if not contexto.patrimonio_range:
                contexto.patrimonio_range = PatrimonioRange.ATE_100K
                logger.info("Assumindo patrimônio <=100k para iniciante")
        
        return contexto
    
    def _extrair_patrimonio(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai faixa de patrimônio"""
        
        # Verificar opções numeradas primeiro
        if re.search(r'opção\s*1|^1\b', mensagem):
            contexto.patrimonio_range = PatrimonioRange.ATE_100K
        elif re.search(r'opção\s*2|^2\b', mensagem):
            contexto.patrimonio_range = PatrimonioRange.ENTRE_100_500K
        elif re.search(r'opção\s*3|^3\b', mensagem):
            contexto.patrimonio_range = PatrimonioRange.ACIMA_500K
        else:
            # Usar padrões textuais
            for range_value, patterns in self.patrimonio_patterns.items():
                if any(re.search(pattern, mensagem) for pattern in patterns):
                    contexto.patrimonio_range = range_value
                    break
        
        if contexto.patrimonio_range:
            logger.info("Patrimônio extraído", faixa=str(contexto.patrimonio_range))
        
        return contexto
    
    def _extrair_objetivo(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai objetivo financeiro"""
        
        # Verificar opções numeradas primeiro
        if re.search(r'opção\s*1|^1\b', mensagem):
            contexto.objetivo = Objetivo.CRESCIMENTO
        elif re.search(r'opção\s*2|^2\b', mensagem):
            contexto.objetivo = Objetivo.RENDA
        elif re.search(r'opção\s*3|^3\b', mensagem):
            contexto.objetivo = Objetivo.APOSENTADORIA
        elif re.search(r'opção\s*4|^4\b', mensagem):
            contexto.objetivo = Objetivo.PROTECAO
        else:
            # Usar padrões textuais
            for objetivo_value, patterns in self.objetivo_patterns.items():
                if any(re.search(pattern, mensagem) for pattern in patterns):
                    contexto.objetivo = objetivo_value
                    break
        
        if contexto.objetivo:
            logger.info("Objetivo extraído", objetivo=str(contexto.objetivo))
        
        return contexto
    
    def _extrair_urgencia(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai nível de urgência"""
        
        # Verificar opções numeradas primeiro
        if re.search(r'opção\s*1|^1\b', mensagem):
            contexto.urgencia = Urgencia.ALTA
        elif re.search(r'opção\s*2|^2\b', mensagem):
            contexto.urgencia = Urgencia.MEDIA
        elif re.search(r'opção\s*3|^3\b', mensagem):
            contexto.urgencia = Urgencia.BAIXA
        else:
            # Usar padrões textuais
            for urgencia_value, patterns in self.urgencia_patterns.items():
                if any(re.search(pattern, mensagem) for pattern in patterns):
                    contexto.urgencia = urgencia_value
                    break
        
        if contexto.urgencia:
            logger.info("Urgência extraída", urgencia=str(contexto.urgencia))
        
        return contexto
    
    def _extrair_interesse(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai nível de interesse"""
        
        # Verificar opções numeradas primeiro
        if re.search(r'opção\s*1|^1\b', mensagem):
            contexto.interesse = Interesse.MUITO_ALTO
        elif re.search(r'opção\s*2|^2\b', mensagem):
            contexto.interesse = Interesse.MEDIO
        elif re.search(r'opção\s*3|^3\b', mensagem):
            contexto.interesse = Interesse.BAIXO
        else:
            # Usar padrões textuais
            for interesse_value, patterns in self.interesse_patterns.items():
                if any(re.search(pattern, mensagem) for pattern in patterns):
                    contexto.interesse = interesse_value
                    break
        
        if contexto.interesse:
            logger.info("Interesse extraído", interesse=str(contexto.interesse))
        
        return contexto
    
    def _extrair_autoridade(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai nível de autoridade de decisão"""
        
        for autoridade_value, patterns in self.autoridade_patterns.items():
            if any(re.search(pattern, mensagem) for pattern in patterns):
                contexto.autoridade = autoridade_value
                logger.info("Autoridade extraída", autoridade=str(autoridade_value))
                break
        
        return contexto
    
    def _extrair_timing(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai informações de timing"""
        
        timing_patterns = [
            r'\b(hoje|agora|imediato|urgente)\b',
            r'\b(semana|próxima|próximo|próximos)\b',
            r'\b(mês|meses|trimestre)\b',
            r'\b(ano|anos|longo prazo)\b',
            r'\b(sem pressa|tranquilo|calma)\b'
        ]
        
        for pattern in timing_patterns:
            match = re.search(pattern, mensagem)
            if match:
                contexto.timing = match.group(0)
                logger.info("Timing extraído", timing=contexto.timing)
                break
        
        return contexto
    
    def _extrair_disponibilidade(self, mensagem: str, contexto: ContextoConversa) -> ContextoConversa:
        """Extrai informações de disponibilidade para reunião"""
        
        disponibilidade_patterns = [
            r'\b(manhã|manha|10h|9h|11h)\b',
            r'\b(tarde|14h|15h|16h|17h)\b',
            r'\b(noite|19h|20h|21h)\b',
            r'\b(segunda|terça|terca|quarta|quinta|sexta)\b',
            r'\b(fim de semana|sábado|sabado|domingo)\b',
            r'\b(qualquer|flexível|flexivel)\b'
        ]
        
        matches = []
        for pattern in disponibilidade_patterns:
            match = re.search(pattern, mensagem)
            if match:
                matches.append(match.group(0))
        
        if matches:
            contexto.disponibilidade = ", ".join(matches)
            logger.info("Disponibilidade extraída", disponibilidade=contexto.disponibilidade)
        
        return contexto
    
    def _build_patrimonio_patterns(self) -> Dict[PatrimonioRange, List[str]]:
        """Constrói padrões para detecção de patrimônio"""
        
        return {
            PatrimonioRange.ATE_100K: [
                r'\b(até|ate|menos|abaixo)\s+(100|cem)\s*(mil|k)\b',
                r'\b(pouco|pequeno|baixo|começo|comeco)\b',
                r'\b(10|20|30|40|50|60|70|80|90)\s*(mil|k)\b',
                r'\b(poupança|conta|básico|basico)\b'
            ],
            PatrimonioRange.ENTRE_100_500K: [
                r'\b(100|200|300|400|500)\s*(mil|k)\b',
                r'\b(entre|médio|medio|razoável|razoavel)\b',
                r'\b(cem|duzentos|trezentos|quatrocentos|quinhentos)\s*mil\b'
            ],
            PatrimonioRange.ACIMA_500K: [
                r'\b(acima|mais|superior)\s+(500|quinhentos)\s*(mil|k)\b',
                r'\b(muito|bastante|bem|boa|grande)\s*(reserva|quantia)\b',
                r'\b(600|700|800|900|1000|milhão|milhao)\b'
            ]
        }
    
    def _build_objetivo_patterns(self) -> Dict[Objetivo, List[str]]:
        """Constrói padrões para detecção de objetivo"""
        
        return {
            Objetivo.CRESCIMENTO: [
                r'\b(crescer|crescimento|dobrar|multiplicar|valorizar|cresça)\b',
                r'\b(longo prazo|anos|décadas|decadas)\b',
                r'\b(ficar rico|enriquecer|patrimônio|patrimonio)\b',
                r'\b(ganhar mais|lucrar|rentabilidade)\b'
            ],
            Objetivo.RENDA: [
                r'\b(renda|renda passiva|mensal|todo mês|mes)\b',
                r'\b(dividendos|juros|rendimento)\b',
                r'\b(complementar|extra|adicional)\b',
                r'\b(pagar|conta|despesa|gasto)\b'
            ],
            Objetivo.APOSENTADORIA: [
                r'\b(aposentadoria|aposentar|aposentado)\b',
                r'\b(velhice|idoso|futuro|previdência|previdencia)\b',
                r'\b(parar de trabalhar|independência|independencia)\b'
            ],
            Objetivo.PROTECAO: [
                r'\b(proteger|proteção|protecao|segurança|seguranca)\b',
                r'\b(preservar|manter|conservar|guardar)\b',
                r'\b(inflação|inflacao|desvalorização|desvalorizacao)\b',
                r'\b(não perder|nao perder|seguro)\b'
            ]
        }
    
    def _build_urgencia_patterns(self) -> Dict[Urgencia, List[str]]:
        """Constrói padrões para detecção de urgência"""
        
        return {
            Urgencia.ALTA: [
                r'\b(agora|hoje|imediato|urgente|já|ja)\b',
                r'\b(preciso|necessário|necessario|importante)\b',
                r'\b(começar|comecar|iniciar|partir)\b'
            ],
            Urgencia.MEDIA: [
                r'\b(próximo|proximo|próximos|proximos|mês|mes|meses)\b',
                r'\b(breve|logo|em breve|semana|semanas)\b',
                r'\b(planejando|pensando|avaliando)\b'
            ],
            Urgencia.BAIXA: [
                r'\b(sem pressa|tranquilo|calma|devagar)\b',
                r'\b(futuro|mais tarde|depois|eventualmente)\b',
                r'\b(estudando|pesquisando|vendo|analisando)\b'
            ]
        }
    
    def _build_interesse_patterns(self) -> Dict[Interesse, List[str]]:
        """Constrói padrões para detecção de interesse"""
        
        return {
            Interesse.MUITO_ALTO: [
                r'\b(sim|claro|certamente|com certeza|quero|adoraria)\b',
                r'\b(interessado|interessada|animado|animada)\b',
                r'\b(vamos|bora|quando|onde|como)\b'
            ],
            Interesse.ALTO: [
                r'\b(talvez|pode ser|possivelmente|interessante)\b',
                r'\b(gostaria|seria bom|seria legal)\b',
                r'\b(vou pensar|considerar|avaliar)\b'
            ],
            Interesse.MEDIO: [
                r'\b(material|informação|informacao|conteúdo|conteudo)\b',
                r'\b(depois|mais tarde|futuramente)\b',
                r'\b(não sei|nao sei|incerto|dúvida|duvida)\b'
            ],
            Interesse.BAIXO: [
                r'\b(não|nao|agora não|agora nao)\b',
                r'\b(ocupado|sem tempo|corrido)\b',
                r'\b(talvez depois|outro momento)\b'
            ],
            Interesse.MUITO_BAIXO: [
                r'\b(não quero|nao quero|não preciso|nao preciso)\b',
                r'\b(satisfeito|contente|bem assim)\b',
                r'\b(já tenho|ja tenho|não me interessa|nao me interessa)\b'
            ]
        }
    
    def _build_autoridade_patterns(self) -> Dict[Autoridade, List[str]]:
        """Constrói padrões para detecção de autoridade"""
        
        return {
            Autoridade.DECISOR: [
                r'\b(eu decido|minha decisão|minha decisao|sozinho|sozinha)\b',
                r'\b(sou eu|responsável|responsavel|dono|dona)\b',
                r'\b(posso|consigo|tenho autonomia)\b'
            ],
            Autoridade.INFLUENCIADOR: [
                r'\b(esposa|esposo|marido|família|familia)\b',
                r'\b(conversar|discutir|falar|consultar)\b',
                r'\b(junto|juntos|em conjunto|casal)\b'
            ],
            Autoridade.DESCONHECIDO: [
                r'\b(não sei|nao sei|depende|talvez)\b',
                r'\b(complicado|difícil|dificil)\b'
            ]
        }
    
    def _detectar_mudancas(self, contexto_anterior: ContextoConversa, 
                          contexto_novo: ContextoConversa) -> Dict[str, Any]:
        """Detecta mudanças entre contextos"""
        
        mudancas = {}
        
        campos = [
            'patrimonio_range', 'objetivo', 'urgencia', 'interesse', 
            'autoridade', 'timing', 'disponibilidade', 'ja_investiu'
        ]
        
        for campo in campos:
            valor_anterior = getattr(contexto_anterior, campo)
            valor_novo = getattr(contexto_novo, campo)
            
            if valor_anterior != valor_novo:
                mudancas[campo] = {
                    'anterior': valor_anterior,
                    'novo': valor_novo
                }
        
        return mudancas
    
    def calcular_score_parcial(self, contexto: ContextoConversa) -> int:
        """Calcula score parcial baseado nos slots preenchidos"""
        
        score = 0
        
        # Patrimônio (30 pontos)
        if contexto.patrimonio_range:
            if contexto.patrimonio_range == PatrimonioRange.ACIMA_500K:
                score += 30
            elif contexto.patrimonio_range == PatrimonioRange.ENTRE_100_500K:
                score += 20
            else:
                score += 10
        
        # Objetivo (20 pontos)
        if contexto.objetivo:
            if contexto.objetivo in [Objetivo.CRESCIMENTO, Objetivo.RENDA]:
                score += 20
            else:
                score += 15
        
        # Urgência (20 pontos)
        if contexto.urgencia:
            if contexto.urgencia == Urgencia.ALTA:
                score += 20
            elif contexto.urgencia == Urgencia.MEDIA:
                score += 15
            else:
                score += 10
        
        # Interesse (30 pontos)
        if contexto.interesse:
            if contexto.interesse == Interesse.MUITO_ALTO:
                score += 30
            elif contexto.interesse == Interesse.ALTO:
                score += 25
            elif contexto.interesse == Interesse.MEDIO:
                score += 15
            elif contexto.interesse == Interesse.BAIXO:
                score += 5
            else:  # MUITO_BAIXO
                score += 0
        
        return min(score, 100)
    
    def slots_obrigatorios_preenchidos(self, contexto: ContextoConversa) -> bool:
        """Verifica se slots obrigatórios estão preenchidos"""
        
        return (
            contexto.patrimonio_range is not None and
            contexto.objetivo is not None
        )
    
    def pode_agendar(self, contexto: ContextoConversa) -> bool:
        """Verifica se tem dados suficientes para agendamento"""
        
        return (
            self.slots_obrigatorios_preenchidos(contexto) and
            (
                contexto.interesse in [Interesse.MUITO_ALTO, Interesse.ALTO] or
                contexto.urgencia == Urgencia.ALTA or
                self.calcular_score_parcial(contexto) >= 70
            )
        )
