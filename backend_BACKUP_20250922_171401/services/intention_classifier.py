"""
Classificador de Intenção Melhorado
Sistema de análise de intenção com padrões pré-definidos e fallback de IA
"""
import re
from typing import Dict, List, Tuple, Optional
import structlog

from backend.models.conversation_models import IntencaoLead

logger = structlog.get_logger(__name__)


class IntentionClassifier:
    """Classificador de intenção híbrido (regras + IA)"""
    
    def __init__(self):
        self.interesse_patterns = self._build_interesse_patterns()
        self.objecao_patterns = self._build_objecao_patterns()
        self.agendamento_patterns = self._build_agendamento_patterns()
        self.recusa_patterns = self._build_recusa_patterns()
        self.duvida_patterns = self._build_duvida_patterns()
        self.informacao_patterns = self._build_informacao_patterns()
    
    def classificar_intencao_rapida(self, mensagem: str) -> IntencaoLead:
        """Classificação rápida usando regras pré-definidas"""
        
        mensagem_lower = mensagem.lower().strip()
        
        # Classificar intenção
        intencao = self._detectar_intencao_principal(mensagem_lower)
        
        # Analisar sentimento
        sentimento = self._analisar_sentimento(mensagem_lower)
        
        # Calcular urgência
        urgencia = self._calcular_urgencia(mensagem_lower)
        
        # Calcular score de qualificação
        qualificacao_score = self._calcular_qualificacao_score(mensagem_lower, intencao)
        
        # Extrair pontos principais
        principais_pontos = self._extrair_pontos_principais(mensagem_lower)
        
        logger.info("Intenção classificada", 
                   intencao=intencao, 
                   sentimento=sentimento,
                   urgencia=urgencia,
                   score=qualificacao_score)
        
        return IntencaoLead(
            intencao=intencao,
            sentimento=sentimento,
            urgencia=urgencia,
            qualificacao_score=qualificacao_score,
            principais_pontos=principais_pontos
        )
    
    def _detectar_intencao_principal(self, mensagem: str) -> str:
        """Detecta intenção principal usando padrões"""
        
        # Verificar agendamento (prioridade alta)
        if self._match_patterns(mensagem, self.agendamento_patterns):
            return "agendamento"
        
        # Verificar recusa (prioridade alta)
        if self._match_patterns(mensagem, self.recusa_patterns):
            return "recusa"
        
        # Verificar interesse
        if self._match_patterns(mensagem, self.interesse_patterns):
            return "interesse"
        
        # Verificar objeção
        if self._match_patterns(mensagem, self.objecao_patterns):
            return "objecao"
        
        # Verificar dúvida
        if self._match_patterns(mensagem, self.duvida_patterns):
            return "duvida"
        
        # Verificar pedido de informação
        if self._match_patterns(mensagem, self.informacao_patterns):
            return "informacao"
        
        # Default
        return "duvida"
    
    def _analisar_sentimento(self, mensagem: str) -> str:
        """Analisa sentimento da mensagem"""
        
        # Padrões positivos
        positivos = [
            r'\b(sim|claro|ótimo|otimo|perfeito|legal|bacana|massa|show)\b',
            r'\b(quero|gostaria|interessante|bom|boa|excelente)\b',
            r'\b(adorei|amei|curtir|gostar|positivo)\b',
            r'[!]{1,3}(?![!])',  # Exclamações moderadas
            r'😊|😄|😁|👍|✅'  # Emojis positivos
        ]
        
        # Padrões negativos
        negativos = [
            r'\b(não|nao|nunca|jamais|impossível|impossivel)\b',
            r'\b(ruim|péssimo|pessimo|horrível|horrivel|terrível|terrivel)\b',
            r'\b(chato|irritante|problema|complicado|difícil|dificil)\b',
            r'\b(desculpa|desculpe|me perdoe|sinto muito)\b',
            r'😞|😢|😠|😡|👎|❌'  # Emojis negativos
        ]
        
        # Contar matches
        score_positivo = sum(1 for pattern in positivos if re.search(pattern, mensagem))
        score_negativo = sum(1 for pattern in negativos if re.search(pattern, mensagem))
        
        if score_positivo > score_negativo:
            return "positivo"
        elif score_negativo > score_positivo:
            return "negativo"
        else:
            return "neutro"
    
    def _calcular_urgencia(self, mensagem: str) -> int:
        """Calcula urgência de 1-10"""
        
        urgencia_alta = [
            r'\b(agora|hoje|já|ja|imediato|urgente|rápido|rapido)\b',
            r'\b(preciso|necessário|necessario|importante|crítico|critico)\b',
            r'\b(logo|breve|quanto antes|o mais rápido|o mais rapido)\b'
        ]
        
        urgencia_baixa = [
            r'\b(depois|mais tarde|futuramente|eventualmente)\b',
            r'\b(sem pressa|tranquilo|calma|devagar|quando der)\b',
            r'\b(talvez|quem sabe|pode ser|vou pensar)\b'
        ]
        
        score_alta = sum(1 for pattern in urgencia_alta if re.search(pattern, mensagem))
        score_baixa = sum(1 for pattern in urgencia_baixa if re.search(pattern, mensagem))
        
        if score_alta > 0:
            return min(8 + score_alta, 10)
        elif score_baixa > 0:
            return max(3 - score_baixa, 1)
        else:
            return 5  # Neutro
    
    def _calcular_qualificacao_score(self, mensagem: str, intencao: str) -> int:
        """Calcula score de qualificação 0-100"""
        
        base_scores = {
            "agendamento": 90,
            "interesse": 80,
            "informacao": 60,
            "duvida": 50,
            "objecao": 30,
            "recusa": 10
        }
        
        score_base = base_scores.get(intencao, 50)
        
        # Modificadores
        qualificadores_positivos = [
            r'\b(investir|investimento|dinheiro|patrimônio|patrimonio)\b',
            r'\b(crescer|lucrar|ganhar|rentabilidade|retorno)\b',
            r'\b(consultor|consultoria|orientação|orientacao|ajuda)\b',
            r'\b(reunião|reuniao|conversar|falar|explicar)\b'
        ]
        
        qualificadores_negativos = [
            r'\b(não tenho|nao tenho|sem dinheiro|sem grana)\b',
            r'\b(muito ocupado|sem tempo|corrido|atarefado)\b',
            r'\b(já tenho|ja tenho|satisfeito|não preciso|nao preciso)\b'
        ]
        
        bonus = sum(5 for pattern in qualificadores_positivos if re.search(pattern, mensagem))
        penalidade = sum(10 for pattern in qualificadores_negativos if re.search(pattern, mensagem))
        
        score_final = max(0, min(100, score_base + bonus - penalidade))
        
        return score_final
    
    def _extrair_pontos_principais(self, mensagem: str) -> List[str]:
        """Extrai pontos principais da mensagem"""
        
        pontos = []
        
        # Padrões para capturar informações importantes
        patterns_info = {
            'valor_mencionado': r'\b(\d+(?:\.\d+)?)\s*(mil|k|milhão|milhao|reais?|R\$)\b',
            'tempo_mencionado': r'\b(\d+)\s*(ano|anos|mês|mes|meses|semana|semanas|dia|dias)\b',
            'produto_financeiro': r'\b(poupança|cdb|lci|lca|tesouro|ações|acoes|fundos?|bitcoin|cripto)\b',
            'objetivo_claro': r'\b(aposentadoria|renda|crescer|proteger|dobrar|multiplicar)\b',
            'disponibilidade': r'\b(manhã|manha|tarde|noite|segunda|terça|terca|quarta|quinta|sexta)\b'
        }
        
        for categoria, pattern in patterns_info.items():
            matches = re.findall(pattern, mensagem)
            if matches:
                if isinstance(matches[0], tuple):
                    pontos.append(f"{categoria}: {' '.join(matches[0])}")
                else:
                    pontos.append(f"{categoria}: {matches[0]}")
        
        # Limitar a 5 pontos principais
        return pontos[:5]
    
    def _match_patterns(self, mensagem: str, patterns: List[str]) -> bool:
        """Verifica se mensagem combina com algum padrão"""
        return any(re.search(pattern, mensagem) for pattern in patterns)
    
    def _build_interesse_patterns(self) -> List[str]:
        """Padrões para detectar interesse"""
        return [
            r'\b(sim|claro|com certeza|certamente|quero|gostaria)\b',
            r'\b(interessante|interessado|interessada|me interessa)\b',
            r'\b(adoraria|seria ótimo|seria otimo|seria bom|seria legal)\b',
            r'\b(vamos|bora|quando|onde|como faço|como faco)\b',
            r'\b(me conte|me fale|explique|quero saber)\b',
            r'opção\s*1|^1\b',  # Primeira opção
            r'👍|✅|😊|😄'  # Emojis positivos
        ]
    
    def _build_objecao_patterns(self) -> List[str]:
        """Padrões para detectar objeções"""
        return [
            r'\b(mas|porém|porem|entretanto|contudo|no entanto)\b',
            r'\b(caro|custoso|não tenho|nao tenho|sem dinheiro|sem grana)\b',
            r'\b(não confio|nao confio|desconfio|duvidoso|suspeito)\b',
            r'\b(já tentei|ja tentei|já perdi|ja perdi|ruim|péssimo|pessimo)\b',
            r'\b(complicado|difícil|dificil|impossível|impossivel)\b',
            r'\b(banco|corretora|já tenho|ja tenho|satisfeito)\b'
        ]
    
    def _build_agendamento_patterns(self) -> List[str]:
        """Padrões para detectar interesse em agendamento"""
        return [
            r'\b(agendar|marcar|reunião|reuniao|encontro|conversa)\b',
            r'\b(quando|que horas|horário|horario|disponível|disponivel)\b',
            r'\b(manhã|manha|tarde|noite|amanhã|amanha|hoje)\b',
            r'\b(segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo)\b',
            r'\b(pode ser|tudo bem|ok|beleza|fechado)\b',
            r'\b(vamos marcar|podemos falar|me liga|me chama)\b'
        ]
    
    def _build_recusa_patterns(self) -> List[str]:
        """Padrões para detectar recusa"""
        return [
            r'\b(não|nao|nunca|jamais|de jeito nenhum)\b',
            r'\b(agora não|agora nao|não quero|nao quero|não preciso|nao preciso)\b',
            r'\b(ocupado|sem tempo|corrido|atarefado|cheio)\b',
            r'\b(outro momento|outra hora|depois|mais tarde)\b',
            r'\b(não me interessa|nao me interessa|não é pra mim|nao e pra mim)\b',
            r'opção\s*2|^2\b.*não|opção\s*3|^3\b.*não'  # Opções de recusa
        ]
    
    def _build_duvida_patterns(self) -> List[str]:
        """Padrões para detectar dúvidas"""
        return [
            r'\?',  # Qualquer pergunta
            r'\b(como|o que|que|qual|onde|quando|por que|porque)\b',
            r'\b(não entendi|nao entendi|não sei|nao sei|dúvida|duvida)\b',
            r'\b(explica|esclareça|esclareca|me ajuda|não compreendi|nao compreendi)\b',
            r'\b(pode repetir|repete|de novo|novamente)\b',
            r'\b(hein|oi|que isso|como assim)\b'
        ]
    
    def _build_informacao_patterns(self) -> List[str]:
        """Padrões para detectar pedidos de informação"""
        return [
            r'\b(material|informação|informacao|conteúdo|conteudo|documento)\b',
            r'\b(me manda|me envia|pode enviar|tem algo|alguma coisa)\b',
            r'\b(quero saber|gostaria de saber|me conte|me fale)\b',
            r'\b(detalhes|mais informações|mais informacoes|especificações|especificacoes)\b',
            r'\b(site|link|telefone|contato|endereço|endereco)\b'
        ]
    
    def detectar_trigger_agendamento(self, mensagem: str) -> bool:
        """Detecta se mensagem contém trigger direto para agendamento"""
        
        triggers_diretos = [
            r'\b(quero agendar|vamos marcar|pode marcar)\b',
            r'\b(estou livre|tenho tempo|disponível|disponivel)\b',
            r'\b(amanhã|amanha|hoje|segunda|terça|terca)\s+(de manhã|de manha|à tarde|a tarde|de noite)\b',
            r'\b(\d{1,2}h|\d{1,2}:\d{2})\b',  # Horários específicos
            r'\b(sim.*reunião|sim.*reuniao|aceito.*conversa)\b'
        ]
        
        return any(re.search(trigger, mensagem.lower()) for trigger in triggers_diretos)
    
    def detectar_trigger_recusa(self, mensagem: str) -> bool:
        """Detecta se mensagem contém trigger direto para recusa"""
        
        triggers_recusa = [
            r'\b(não quero|nao quero|não preciso|nao preciso|não me interessa|nao me interessa)\b',
            r'\b(já tenho|ja tenho|estou satisfeito|não é pra mim|nao e pra mim)\b',
            r'\b(ocupado demais|muito corrido|sem tempo|não posso|nao posso)\b',
            r'\b(talvez depois|outro momento|mais tarde|futuramente)\b'
        ]
        
        return any(re.search(trigger, mensagem.lower()) for trigger in triggers_recusa)
    
    def extrair_disponibilidade(self, mensagem: str) -> Optional[str]:
        """Extrai informações de disponibilidade da mensagem"""
        
        disponibilidade_patterns = [
            r'\b(manhã|manha|10h|9h|11h)\b',
            r'\b(tarde|14h|15h|16h|17h)\b',
            r'\b(noite|19h|20h|21h)\b',
            r'\b(segunda|terça|terca|quarta|quinta|sexta)\b',
            r'\b(amanhã|amanha|hoje|depois de amanhã|depois de amanha)\b'
        ]
        
        matches = []
        for pattern in disponibilidade_patterns:
            match = re.search(pattern, mensagem.lower())
            if match:
                matches.append(match.group(0))
        
        return ", ".join(matches) if matches else None
