"""
Serviço de Reconhecimento Flexível de Respostas
Melhora o entendimento das respostas dos leads com IA
"""

import re
from typing import Dict, Optional, List
import structlog

logger = structlog.get_logger(__name__)

class ReconhecimentoRespostasService:
    """Serviço para reconhecer e classificar respostas dos leads de forma flexível"""
    
    def __init__(self):
        # Mapeamentos flexíveis para classificação de respostas
        self.objetivos_map = {
            'crescimento': [
                'crescer', 'crescimento', 'aumentar', 'multiplicar', 'ficar rico', 
                'enriquecer', 'valorizar', 'ganhar mais', 'mais dinheiro', 'expandir',
                'ampliar', 'elevar', 'subir', 'render mais'
            ],
            'renda': [
                'renda', 'renda extra', 'renda passiva', 'dividendos', 
                'receber', 'gerar renda', 'complementar renda', 'renda mensal',
                'dinheiro todo mês', 'entrada extra', 'complemento'
            ],
            'aposentadoria': [
                'aposentar', 'aposentadoria', 'aposentado', 'futuro', 
                'longo prazo', 'previdência', 'idade', 'velhice',
                'quando parar de trabalhar', 'não trabalhar mais'
            ],
            'protecao': [
                'proteger', 'proteção', 'segurança', 'seguro', 'preservar',
                'manter', 'conservar', 'que já tenho', 'que tenho',
                'não perder', 'não quero perder', 'guardar', 'salvar'
            ]
        }
        
        self.patrimonio_map = {
            'baixo': [
                'pouco', 'começando', 'iniciante', 'zero', 'nada',
                'não tenho', 'sem dinheiro', 'apertado', 'pouco dinheiro'
            ],
            'baixo_medio': [
                'alguns milhares', 'poucos milhares', 'até 50', 'até 100',
                'menos de 100', 'abaixo de 100'
            ],
            'medio': [
                'médio', 'razoável', 'ok', 'uns 200', 'uns 300', 'uns 500',
                'entre 100 e 500', '100 a 500'
            ],
            'alto': [
                'bastante', 'bem', 'muito', 'mais de 500', 'acima de 500',
                'mais de meio milhão', 'uns milhões', 'alguns milhões'
            ]
        }
        
        self.urgencia_map = {
            'alta': [
                'urgente', 'rápido', 'logo', 'imediatamente', 'já',
                'o quanto antes', 'agora', 'hoje', 'esta semana'
            ],
            'media': [
                'alguns meses', 'uns meses', 'meio ano', 'este ano',
                'em breve', 'logo logo', 'nos próximos meses'
            ],
            'baixa': [
                'longo prazo', 'sem pressa', 'quando der', 'futuramente',
                'daqui uns anos', 'não tenho pressa', 'tranquilo'
            ]
        }
    
    def classificar_objetivo(self, resposta_usuario: str) -> str:
        """Classifica objetivo do usuário com maior flexibilidade"""
        resposta_lower = resposta_usuario.lower().strip()
        
        logger.info("Classificando objetivo", resposta=resposta_lower)
        
        # Buscar correspondência nos mapeamentos
        for objetivo, palavras_chave in self.objetivos_map.items():
            for palavra in palavras_chave:
                if palavra in resposta_lower:
                    logger.info("Objetivo identificado", objetivo=objetivo, palavra_chave=palavra)
                    return objetivo
        
        logger.warning("Objetivo não identificado", resposta=resposta_lower)
        return 'indefinido'  # Para tratamento especial
    
    def classificar_patrimonio(self, resposta_usuario: str) -> str:
        """Classifica patrimônio do usuário"""
        resposta_lower = resposta_usuario.lower().strip()
        
        logger.info("Classificando patrimônio", resposta=resposta_lower)
        
        # Primeiro tentar identificar valores numéricos
        valores_numericos = re.findall(r'(\d+(?:\.\d+)?)\s*(?:mil|k|milhão|milhões|m)?', resposta_lower)
        
        if valores_numericos:
            try:
                valor = float(valores_numericos[0])
                if 'milhão' in resposta_lower or 'milhões' in resposta_lower:
                    valor *= 1000  # Converter para milhares
                
                if valor <= 100:
                    return 'baixo_medio'
                elif valor <= 500:
                    return 'medio'
                else:
                    return 'alto'
            except ValueError:
                pass
        
        # Se não encontrou números, usar mapeamento por palavras
        for faixa, palavras_chave in self.patrimonio_map.items():
            for palavra in palavras_chave:
                if palavra in resposta_lower:
                    logger.info("Patrimônio identificado", faixa=faixa, palavra_chave=palavra)
                    return faixa
        
        logger.warning("Patrimônio não identificado", resposta=resposta_lower)
        return 'indefinido'
    
    def classificar_urgencia(self, resposta_usuario: str) -> str:
        """Classifica urgência/prazo do usuário"""
        resposta_lower = resposta_usuario.lower().strip()
        
        logger.info("Classificando urgência", resposta=resposta_lower)
        
        for urgencia, palavras_chave in self.urgencia_map.items():
            for palavra in palavras_chave:
                if palavra in resposta_lower:
                    logger.info("Urgência identificada", urgencia=urgencia, palavra_chave=palavra)
                    return urgencia
        
        logger.warning("Urgência não identificada", resposta=resposta_lower)
        return 'indefinido'
    
    def gerar_resposta_reconhecida(self, tipo: str, classificacao: str, lead_nome: str) -> str:
        """Gera resposta personalizada baseada na classificação"""
        
        if tipo == 'objetivo':
            respostas = {
                'crescimento': f"Legal, {lead_nome}! Crescer o patrimônio é um ótimo objetivo. 📈",
                'renda': f"Perfeito, {lead_nome}! Gerar renda extra é muito inteligente. 💰",
                'aposentadoria': f"Que planejamento bacana, {lead_nome}! Investir para aposentadoria é fundamental. 🎯",
                'protecao': f"Entendi, {lead_nome}! Proteger o patrimônio é muito importante. 🛡️",
                'indefinido': f"Interessante, {lead_nome}! Me conta mais sobre o que você gostaria de alcançar?"
            }
        
        elif tipo == 'patrimonio':
            respostas = {
                'baixo': f"Tranquilo, {lead_nome}! Todo mundo começou assim. 😊",
                'baixo_medio': f"Ótimo, {lead_nome}! Já é um bom começo. 👍",
                'medio': f"Bacana, {lead_nome}! Temos muito o que otimizar. 🚀",
                'alto': f"Perfeito, {lead_nome}! Vamos potencializar ainda mais. 💪",
                'indefinido': f"Me conta melhor, {lead_nome}: você já tem algum dinheiro investido hoje?"
            }
        
        elif tipo == 'urgencia':
            respostas = {
                'alta': f"Entendi, {lead_nome}! Vamos agilizar então. ⚡",
                'media': f"Perfeito, {lead_nome}! Temos um bom prazo para trabalhar. ✅",
                'baixa': f"Tranquilo, {lead_nome}! Longo prazo é ótimo para bons resultados. 📊",
                'indefinido': f"E sobre prazo, {lead_nome}? Tem pressa para ver resultados?"
            }
        
        else:
            return f"Entendi, {lead_nome}! Vamos continuar nossa conversa."
        
        return respostas.get(classificacao, respostas.get('indefinido', f"Obrigado pela informação, {lead_nome}!"))
    
    def verificar_interesse_agendamento(self, resposta_usuario: str) -> bool:
        """Verifica se o usuário demonstra interesse em agendar"""
        resposta_lower = resposta_usuario.lower().strip()
        
        palavras_positivas = [
            'sim', 'claro', 'pode ser', 'vamos', 'quero', 'gostaria',
            'tenho interesse', 'me interessa', 'legal', 'bacana',
            'ok', 'tudo bem', 'perfeito', 'ótimo'
        ]
        
        palavras_negativas = [
            'não', 'não quero', 'não tenho interesse', 'não posso',
            'não dá', 'outro dia', 'depois', 'mais tarde'
        ]
        
        # Verificar interesse positivo
        for palavra in palavras_positivas:
            if palavra in resposta_lower:
                return True
        
        # Verificar recusa (deve ser mais específica)
        for palavra in palavras_negativas:
            if resposta_lower.startswith(palavra) or f" {palavra} " in resposta_lower:
                return False
        
        # Se não identificou claramente, assume interesse moderado
        return True
    
    def extrair_disponibilidade(self, resposta_usuario: str) -> Optional[str]:
        """Extrai informações de disponibilidade da resposta"""
        resposta_lower = resposta_usuario.lower().strip()
        
        # Padrões de horário/dia
        padroes_tempo = [
            r'(segunda|terça|quarta|quinta|sexta|sábado|domingo)',
            r'(manhã|tarde|noite)',
            r'(hoje|amanhã|depois de amanhã)',
            r'(\d{1,2}h\d{0,2})',
            r'(esta semana|próxima semana|semana que vem)'
        ]
        
        disponibilidades = []
        for padrao in padroes_tempo:
            matches = re.findall(padrao, resposta_lower)
            disponibilidades.extend(matches)
        
        if disponibilidades:
            return ', '.join(disponibilidades)
        
        return None
