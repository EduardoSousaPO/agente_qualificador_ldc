"""
Serviço de Scoring para Qualificação de Leads
Algoritmo inteligente baseado em análise de respostas
"""
import re
from typing import Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class ScoringResult:
    """Resultado do scoring"""
    patrimonio_pontos: int
    objetivo_pontos: int
    urgencia_pontos: int
    interesse_pontos: int
    score_total: int
    resultado: str
    observacoes: str


class ScoringService:
    """Serviço de cálculo de score para qualificação"""
    
    def __init__(self):
        self.score_minimo_qualificacao = 70
        
        # Palavras-chave para análise das respostas
        self.patrimonio_keywords = {
            'muito_alto': [
                'acima de 5 milhões', 'mais de 5 milhões', '5 milhões', '10 milhões',
                'muitos milhões', 'bastante patrimônio', 'muito rico'
            ],
            'alto': [
                'acima de 1 milhão', 'mais de 1 milhão', '1 milhão', '2 milhões', '3 milhões',
                'muitos recursos', 'patrimônio alto', 'bem estruturado'
            ],
            'medio_alto': [
                'entre 500k e 1 milhão', '500 mil', '600 mil', '700 mil', '800 mil', '900 mil',
                'patrimônio médio alto', 'alguns recursos', 'bem capitalizado'
            ],
            'medio': [
                'entre 200k e 500k', '200 mil', '300 mil', '400 mil',
                'patrimônio médio', 'recursos moderados'
            ],
            'baixo': [
                'menos de 200k', 'pouco patrimônio', 'poucos recursos', 'iniciando',
                '50 mil', '100 mil', 'patrimônio baixo'
            ]
        }
        
        self.objetivo_keywords = {
            'investimento_agressivo': [
                'multiplicar', 'crescer rapidamente', 'ganhar muito', 'investimento agressivo',
                'alto retorno', 'renda variável', 'ações', 'cripto'
            ],
            'investimento': [
                'investir', 'aplicar', 'render', 'rentabilidade', 'fazer o dinheiro trabalhar',
                'investimento', 'aplicação', 'retorno'
            ],
            'crescimento': [
                'crescer', 'aumentar', 'expandir', 'ampliar', 'desenvolver',
                'crescimento patrimonial', 'aumentar patrimônio'
            ],
            'aposentadoria': [
                'aposentar', 'aposentadoria', 'futuro', 'longo prazo', 'previdência',
                'reserva para o futuro', 'independência financeira'
            ],
            'protecao': [
                'proteger', 'segurança', 'preservar', 'guardar', 'conservar',
                'proteção', 'segurança financeira', 'renda fixa'
            ]
        }
        
        self.urgencia_keywords = {
            'imediata': [
                'agora', 'imediatamente', 'urgente', 'já', 'hoje', 'esta semana',
                'preciso começar agora', 'é urgente', 'não posso esperar'
            ],
            'muito_curto': [
                'semana', 'próxima semana', '15 dias', 'duas semanas',
                'muito breve', 'rapidamente'
            ],
            'curto_prazo': [
                'mês', 'próximo mês', '30 dias', 'breve', 'logo', 'em breve',
                'nas próximas semanas'
            ],
            'medio_prazo': [
                'alguns meses', 'trimestre', 'meio ano', '3 meses', '6 meses',
                'médio prazo', 'durante o ano'
            ],
            'longo_prazo': [
                'ano', 'anos', 'futuro', 'sem pressa', 'quando possível',
                'longo prazo', 'não tenho pressa'
            ]
        }
        
        self.interesse_keywords = {
            'muito_alto': [
                'sim', 'claro', 'com certeza', 'definitivamente', 'muito interessado',
                'quero sim', 'seria ótimo', 'perfeito', 'excelente ideia'
            ],
            'alto': [
                'interessado', 'gostaria', 'seria bom', 'me interessa',
                'acho interessante', 'pode ser útil'
            ],
            'medio': [
                'talvez', 'possivelmente', 'não sei', 'vou pensar',
                'talvez seja interessante', 'preciso avaliar'
            ],
            'baixo': [
                'talvez não', 'não tenho certeza', 'não sei se preciso',
                'vou ver', 'não tenho pressa'
            ],
            'muito_baixo': [
                'não', 'não quero', 'não preciso', 'não tenho interesse',
                'não me interessa', 'prefiro não'
            ]
        }
    
    def analisar_patrimonio(self, resposta: str) -> Tuple[int, str]:
        """Analisa resposta sobre patrimônio e retorna pontuação"""
        resposta_lower = resposta.lower()
        observacao = ""
        
        # Procura por números específicos
        numeros = re.findall(r'(\d+(?:\.\d+)?)\s*(?:milhões?|milhão|mil|k)', resposta_lower)
        
        if numeros:
            try:
                valor = float(numeros[0])
                if 'milhão' in resposta_lower or 'milhões' in resposta_lower:
                    valor *= 1000000
                elif 'mil' in resposta_lower or 'k' in resposta_lower:
                    valor *= 1000
                
                if valor >= 5000000:
                    observacao = f"Patrimônio muito alto identificado: R$ {valor:,.0f}"
                    return 30, observacao
                elif valor >= 1000000:
                    observacao = f"Patrimônio alto identificado: R$ {valor:,.0f}"
                    return 28, observacao
                elif valor >= 500000:
                    observacao = f"Patrimônio médio-alto identificado: R$ {valor:,.0f}"
                    return 22, observacao
                elif valor >= 200000:
                    observacao = f"Patrimônio médio identificado: R$ {valor:,.0f}"
                    return 16, observacao
                else:
                    observacao = f"Patrimônio baixo identificado: R$ {valor:,.0f}"
                    return 10, observacao
            except:
                pass
        
        # Análise por palavras-chave
        if any(keyword in resposta_lower for keyword in self.patrimonio_keywords['muito_alto']):
            observacao = "Patrimônio muito alto identificado por palavras-chave"
            return 30, observacao
        elif any(keyword in resposta_lower for keyword in self.patrimonio_keywords['alto']):
            observacao = "Patrimônio alto identificado por palavras-chave"
            return 26, observacao
        elif any(keyword in resposta_lower for keyword in self.patrimonio_keywords['medio_alto']):
            observacao = "Patrimônio médio-alto identificado por palavras-chave"
            return 20, observacao
        elif any(keyword in resposta_lower for keyword in self.patrimonio_keywords['medio']):
            observacao = "Patrimônio médio identificado por palavras-chave"
            return 14, observacao
        elif any(keyword in resposta_lower for keyword in self.patrimonio_keywords['baixo']):
            observacao = "Patrimônio baixo identificado por palavras-chave"
            return 8, observacao
        else:
            observacao = "Patrimônio não classificado claramente - pontuação padrão"
            return 12, observacao
    
    def analisar_objetivo(self, resposta: str) -> Tuple[int, str]:
        """Analisa resposta sobre objetivo e retorna pontuação"""
        resposta_lower = resposta.lower()
        
        if any(keyword in resposta_lower for keyword in self.objetivo_keywords['investimento_agressivo']):
            return 25, "Objetivo de investimento agressivo - alta pontuação"
        elif any(keyword in resposta_lower for keyword in self.objetivo_keywords['investimento']):
            return 22, "Objetivo de investimento identificado"
        elif any(keyword in resposta_lower for keyword in self.objetivo_keywords['crescimento']):
            return 20, "Objetivo de crescimento patrimonial"
        elif any(keyword in resposta_lower for keyword in self.objetivo_keywords['aposentadoria']):
            return 18, "Objetivo de aposentadoria/longo prazo"
        elif any(keyword in resposta_lower for keyword in self.objetivo_keywords['protecao']):
            return 12, "Objetivo de proteção/conservação"
        else:
            return 15, "Objetivo não classificado claramente"
    
    def analisar_urgencia(self, resposta: str) -> Tuple[int, str]:
        """Analisa resposta sobre urgência e retorna pontuação"""
        resposta_lower = resposta.lower()
        
        if any(keyword in resposta_lower for keyword in self.urgencia_keywords['imediata']):
            return 25, "Urgência imediata identificada"
        elif any(keyword in resposta_lower for keyword in self.urgencia_keywords['muito_curto']):
            return 22, "Urgência muito curto prazo"
        elif any(keyword in resposta_lower for keyword in self.urgencia_keywords['curto_prazo']):
            return 18, "Urgência curto prazo"
        elif any(keyword in resposta_lower for keyword in self.urgencia_keywords['medio_prazo']):
            return 14, "Urgência médio prazo"
        elif any(keyword in resposta_lower for keyword in self.urgencia_keywords['longo_prazo']):
            return 8, "Urgência longo prazo"
        else:
            return 12, "Urgência não classificada claramente"
    
    def analisar_interesse(self, resposta: str) -> Tuple[int, str]:
        """Analisa resposta sobre interesse em especialista"""
        resposta_lower = resposta.lower()
        
        if any(keyword in resposta_lower for keyword in self.interesse_keywords['muito_alto']):
            return 20, "Muito interesse em conversar com especialista"
        elif any(keyword in resposta_lower for keyword in self.interesse_keywords['alto']):
            return 16, "Alto interesse em conversar com especialista"
        elif any(keyword in resposta_lower for keyword in self.interesse_keywords['medio']):
            return 12, "Interesse médio em conversar com especialista"
        elif any(keyword in resposta_lower for keyword in self.interesse_keywords['baixo']):
            return 6, "Baixo interesse em conversar com especialista"
        elif any(keyword in resposta_lower for keyword in self.interesse_keywords['muito_baixo']):
            return 0, "Sem interesse em conversar com especialista"
        else:
            return 10, "Interesse não classificado claramente"
    
    def calcular_score_completo(
        self,
        patrimonio_resposta: str,
        objetivo_resposta: str,
        urgencia_resposta: str,
        interesse_resposta: str
    ) -> ScoringResult:
        """Calcula o score completo baseado nas 4 respostas"""
        
        # Análise de cada pergunta
        patrimonio_pontos, obs_patrimonio = self.analisar_patrimonio(patrimonio_resposta)
        objetivo_pontos, obs_objetivo = self.analisar_objetivo(objetivo_resposta)
        urgencia_pontos, obs_urgencia = self.analisar_urgencia(urgencia_resposta)
        interesse_pontos, obs_interesse = self.analisar_interesse(interesse_resposta)
        
        # Score total
        score_total = patrimonio_pontos + objetivo_pontos + urgencia_pontos + interesse_pontos
        
        # Resultado da qualificação
        resultado = 'qualificado' if score_total >= self.score_minimo_qualificacao else 'nao_qualificado'
        
        # Observações consolidadas
        observacoes = f"""
ANÁLISE DETALHADA:
• Patrimônio ({patrimonio_pontos}/30): {obs_patrimonio}
• Objetivo ({objetivo_pontos}/25): {obs_objetivo}  
• Urgência ({urgencia_pontos}/25): {obs_urgencia}
• Interesse ({interesse_pontos}/20): {obs_interesse}

SCORE TOTAL: {score_total}/100
RESULTADO: {resultado.upper()}

PRÓXIMOS PASSOS: {"Agendar reunião com especialista" if resultado == 'qualificado' else "Enviar conteúdo educativo"}
        """.strip()
        
        return ScoringResult(
            patrimonio_pontos=patrimonio_pontos,
            objetivo_pontos=objetivo_pontos,
            urgencia_pontos=urgencia_pontos,
            interesse_pontos=interesse_pontos,
            score_total=score_total,
            resultado=resultado,
            observacoes=observacoes
        )
    
    def gerar_mensagem_resultado(self, scoring_result: ScoringResult, nome_lead: str) -> str:
        """Gera mensagem personalizada baseada no resultado"""
        
        if scoring_result.resultado == 'qualificado':
            return f"""
🎉 Olá {nome_lead}! 

Baseado nas suas respostas, vejo que você tem um perfil muito interessante para nossos serviços de consultoria financeira.

📊 **Sua pontuação: {scoring_result.score_total}/100**

Gostaria de agendar uma conversa de 30 minutos com um dos nossos especialistas? Eles poderão apresentar estratégias específicas para o seu perfil e objetivos.

📅 **Disponibilidade:**
• Segunda a Sexta: 9h às 18h  
• Sábado: 9h às 12h

Qual horário seria melhor para você?
            """.strip()
        else:
            return f"""
Obrigado pelas respostas, {nome_lead}! 

📊 **Sua pontuação: {scoring_result.score_total}/100**

Com base no seu perfil atual, preparei alguns materiais que podem ser muito úteis para você:

📚 **Conteúdo Recomendado:**
• E-book: "Primeiros Passos no Investimento"
• Webinar: "Como Organizar suas Finanças"
• Planilha: "Controle Financeiro Pessoal"

Esses materiais vão te ajudar a estruturar melhor seus objetivos financeiros. Quando se sentir pronto para dar o próximo passo, estarei aqui para ajudar!

Gostaria de receber esse conteúdo?
            """.strip()
    
    def validar_resposta(self, resposta: str, tipo_pergunta: str) -> bool:
        """Valida se a resposta é adequada para o tipo de pergunta"""
        if not resposta or len(resposta.strip()) < 5:
            return False
        
        # Validações específicas por tipo de pergunta
        resposta_lower = resposta.lower()
        
        if tipo_pergunta == 'patrimonio':
            # Deve mencionar valores ou indicadores de patrimônio
            indicadores = ['mil', 'milhão', 'reais', 'r$', 'patrimônio', 'recursos', 'dinheiro', 'valor']
            return any(ind in resposta_lower for ind in indicadores)
        
        elif tipo_pergunta == 'objetivo':
            # Deve mencionar objetivos ou intenções
            indicadores = ['quero', 'objetivo', 'pretendo', 'desejo', 'planejo', 'investir', 'aplicar']
            return any(ind in resposta_lower for ind in indicadores)
        
        elif tipo_pergunta == 'urgencia':
            # Deve mencionar tempo ou urgência
            indicadores = ['agora', 'hoje', 'semana', 'mês', 'ano', 'prazo', 'tempo', 'quando', 'urgente']
            return any(ind in resposta_lower for ind in indicadores)
        
        elif tipo_pergunta == 'interesse':
            # Deve indicar interesse ou não
            indicadores = ['sim', 'não', 'talvez', 'interesse', 'quero', 'gostaria', 'preciso']
            return any(ind in resposta_lower for ind in indicadores)
        
        return True



