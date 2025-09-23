"""
Serviço de Guardrails e Controle de Fluxo
Sistema de validação e controle de qualidade das conversas
"""
import re
from typing import Dict, List, Any, Optional, Tuple
import structlog

from backend.models.conversation_models import (
    RespostaIA, SessionState, Estado, Acao, ContextoConversa
)

logger = structlog.get_logger(__name__)


class GuardrailsService:
    """Serviço para aplicar guardrails e controle de fluxo"""
    
    def __init__(self):
        self.frases_banidas = self._build_frases_banidas()
        self.guardrails_checklist = self._build_guardrails_checklist()
        self.limites_sistema = self._build_limites_sistema()
    
    def aplicar_guardrails(self, resposta: RespostaIA, session_state: SessionState, 
                          nome_lead: str) -> Tuple[bool, List[str], Optional[RespostaIA]]:
        """
        Aplica guardrails à resposta da IA
        Retorna: (passou_validacao, erros_encontrados, resposta_corrigida)
        """
        
        erros = []
        resposta_corrigida = None
        
        # Verificar checklist básico
        erros_checklist = self._verificar_checklist_basico(resposta, nome_lead)
        erros.extend(erros_checklist)
        
        # Verificar frases banidas
        erros_frases = self._verificar_frases_banidas(resposta.mensagem)
        erros.extend(erros_frases)
        
        # Verificar limites do sistema
        erros_limites = self._verificar_limites_sistema(resposta, session_state)
        erros.extend(erros_limites)
        
        # Verificar consistência de fluxo
        erros_fluxo = self._verificar_consistencia_fluxo(resposta, session_state)
        erros.extend(erros_fluxo)
        
        # Se há erros, tentar corrigir
        if erros:
            logger.warning("Guardrails violados", erros=erros, mensagem=resposta.mensagem[:100])
            resposta_corrigida = self._tentar_corrigir_resposta(resposta, erros, session_state, nome_lead)
            
            if resposta_corrigida:
                # Re-validar resposta corrigida
                erros_pos_correcao = []
                erros_pos_correcao.extend(self._verificar_checklist_basico(resposta_corrigida, nome_lead))
                erros_pos_correcao.extend(self._verificar_frases_banidas(resposta_corrigida.mensagem))
                
                if not erros_pos_correcao:
                    logger.info("Resposta corrigida com sucesso")
                    return True, [], resposta_corrigida
        
        passou_validacao = len(erros) == 0
        return passou_validacao, erros, resposta_corrigida
    
    def _verificar_checklist_basico(self, resposta: RespostaIA, nome_lead: str) -> List[str]:
        """Verifica checklist básico de guardrails"""
        
        erros = []
        mensagem = resposta.mensagem
        
        # 1. Contém nome do lead
        if nome_lead.lower() not in mensagem.lower():
            erros.append("Nome do lead ausente na mensagem")
        
        # 2. <= 350 caracteres
        if len(mensagem) > 350:
            erros.append(f"Mensagem muito longa: {len(mensagem)} caracteres (máx: 350)")
        
        # 3. 1 pergunta, 2-3 opções numeradas (se ação for continuar)
        if resposta.acao == Acao.CONTINUAR:
            if not self._tem_pergunta(mensagem):
                erros.append("Ação 'continuar' deveria ter uma pergunta")
            
            # if not self._tem_opcoes_numeradas(mensagem):
            #     erros.append("Deveria ter opções numeradas (2-3 opções)")
        
        # 4. No máximo 1 emoji
        emoji_count = self._contar_emojis(mensagem)
        if emoji_count > 1:
            erros.append(f"Muitos emojis: {emoji_count} (máx: 1)")
        
        # 5. Se agendamento, deve sugerir 2 horários concretos
        if resposta.acao == Acao.AGENDAR:
            if not self._tem_horarios_concretos(mensagem):
                erros.append("Agendamento deveria ter 2 horários concretos")
        
        return erros
    
    def _verificar_frases_banidas(self, mensagem: str) -> List[str]:
        """Verifica se mensagem contém frases banidas"""
        
        erros = []
        mensagem_lower = mensagem.lower()
        
        for frase_banida in self.frases_banidas:
            if frase_banida in mensagem_lower:
                erros.append(f"Frase banida detectada: '{frase_banida}'")
        
        return erros
    
    def _verificar_limites_sistema(self, resposta: RespostaIA, session_state: SessionState) -> List[str]:
        """Verifica limites do sistema"""
        
        erros = []
        
        # Limite de mensagens por conversa
        if session_state.mensagem_count >= self.limites_sistema['max_mensagens']:
            if resposta.acao not in [Acao.AGENDAR, Acao.FINALIZAR]:
                erros.append("Limite de mensagens atingido - deve agendar ou finalizar")
        
        # Score muito baixo após muitas tentativas
        if session_state.mensagem_count >= 5 and resposta.score_parcial < 30:
            if resposta.acao != Acao.FINALIZAR:
                erros.append("Score muito baixo - deveria finalizar ou educar")
        
        # Reformulações excessivas
        if session_state.reformulacoes_usadas >= self.limites_sistema['max_reformulacoes']:
            if resposta.acao != Acao.TRANSFERIR_HUMANO:
                erros.append("Muitas reformulações - deve transferir para humano")
        
        return erros
    
    def _verificar_consistencia_fluxo(self, resposta: RespostaIA, session_state: SessionState) -> List[str]:
        """Verifica consistência do fluxo de conversa"""
        
        erros = []
        
        # Não pode repetir pergunta sobre slot já preenchido
        slots_preenchidos = session_state.slots_preenchidos()
        
        if 'patrimonio_range' in slots_preenchidos:
            if self._pergunta_sobre_patrimonio(resposta.mensagem):
                erros.append("Perguntando sobre patrimônio já informado")
        
        if 'objetivo' in slots_preenchidos:
            if self._pergunta_sobre_objetivo(resposta.mensagem):
                erros.append("Perguntando sobre objetivo já informado")
        
        # Transição de estado deve ser lógica
        if not self._transicao_valida(session_state.estado_atual, resposta.proximo_estado):
            estado_atual_val = session_state.estado_atual.value if hasattr(session_state.estado_atual, 'value') else str(session_state.estado_atual)
            proximo_estado_val = resposta.proximo_estado.value if hasattr(resposta.proximo_estado, 'value') else str(resposta.proximo_estado)
            erros.append(f"Transição inválida: {estado_atual_val} -> {proximo_estado_val}")
        
        # Se pode agendar, não deveria continuar perguntando indefinidamente
        if session_state.pode_agendar() and session_state.mensagem_count >= 6:
            if resposta.acao == Acao.CONTINUAR:
                erros.append("Pode agendar mas continua perguntando - deve avançar para agendamento")
        
        return erros
    
    def _tentar_corrigir_resposta(self, resposta: RespostaIA, erros: List[str], 
                                 session_state: SessionState, nome_lead: str) -> Optional[RespostaIA]:
        """Tenta corrigir automaticamente a resposta"""
        
        # Criar cópia da resposta para correção
        try:
            resposta_data = resposta.model_dump()
        except AttributeError:
            # Fallback para objetos Mock ou outros tipos
            resposta_data = {
                'mensagem': resposta.mensagem,
                'acao': resposta.acao.value if hasattr(resposta.acao, 'value') else str(resposta.acao),
                'proximo_estado': resposta.proximo_estado.value if hasattr(resposta.proximo_estado, 'value') else str(resposta.proximo_estado),
                'contexto': resposta.contexto.model_dump() if hasattr(resposta.contexto, 'model_dump') else {},
                'score_parcial': resposta.score_parcial
            }
        
        mensagem_corrigida = resposta_data['mensagem']
        
        # Correção 1: Adicionar nome do lead se ausente
        if "Nome do lead ausente" in str(erros):
            if nome_lead.lower() not in mensagem_corrigida.lower():
                mensagem_corrigida = f"{nome_lead}, {mensagem_corrigida}"
        
        # Correção 2: Encurtar mensagem se muito longa
        if "muito longa" in str(erros):
            if len(mensagem_corrigida) > 350:
                mensagem_corrigida = mensagem_corrigida[:347] + "..."
        
        # Correção 3: Adicionar pergunta se necessário
        if "deveria ter uma pergunta" in str(erros):
            if '?' not in mensagem_corrigida:
                mensagem_corrigida += "?"
        
        # Correção 4: Adicionar opções numeradas se necessário
        if "opções numeradas" in str(erros):
            if not self._tem_opcoes_numeradas(mensagem_corrigida):
                mensagem_corrigida += " 1) sim 2) não"
        
        # Correção 5: Remover emojis excessivos
        if "Muitos emojis" in str(erros):
            mensagem_corrigida = self._remover_emojis_excessivos(mensagem_corrigida)
        
        # Correção 6: Adicionar horários se agendamento
        if "horários concretos" in str(erros):
            if resposta.acao == Acao.AGENDAR:
                mensagem_corrigida += " 1) amanhã 10h 2) amanhã 16h"
        
        # Correção 7: Ajustar ação se limite atingido
        if "Limite de mensagens atingido" in str(erros):
            if session_state.pode_agendar():
                resposta_data['acao'] = 'agendar'
                resposta_data['proximo_estado'] = 'agendamento'
            else:
                resposta_data['acao'] = 'finalizar'
                resposta_data['proximo_estado'] = 'educar'
        
        # Correção 8: Remover frases banidas
        for erro in erros:
            if "Frase banida detectada" in erro:
                frase_banida = erro.split("'")[1]
                mensagem_corrigida = mensagem_corrigida.replace(frase_banida, "")
        
        # Aplicar mensagem corrigida
        resposta_data['mensagem'] = mensagem_corrigida.strip()
        
        # Tentar criar nova resposta
        try:
            return RespostaIA(**resposta_data)
        except Exception as e:
            logger.error("Falha ao corrigir resposta", error=str(e))
            return None
    
    def _tem_pergunta(self, mensagem: str) -> bool:
        """Verifica se mensagem tem pergunta"""
        return '?' in mensagem
    
    def _tem_opcoes_numeradas(self, mensagem: str) -> bool:
        """Verifica se mensagem tem opções numeradas"""
        patterns = [
            r'1\)',  # 1)
            r'1\.',  # 1.
            r'1️⃣',   # emoji
            r'1\s+[a-zA-Z]',  # 1 seguido de espaço e texto
        ]
        return any(re.search(pattern, mensagem) for pattern in patterns)
    
    def _contar_emojis(self, mensagem: str) -> int:
        """Conta emojis na mensagem"""
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        return len(emoji_pattern.findall(mensagem))
    
    def _tem_horarios_concretos(self, mensagem: str) -> bool:
        """Verifica se tem horários concretos para agendamento"""
        horario_patterns = [
            r'\b\d{1,2}h\b',  # 10h, 16h
            r'\b\d{1,2}:\d{2}\b',  # 10:00, 16:30
            r'\b(manhã|manha|tarde|noite)\b',  # períodos
            r'\b(amanhã|amanha|segunda|terça|terca|quarta|quinta|sexta)\b'  # dias
        ]
        
        matches = sum(1 for pattern in horario_patterns if re.search(pattern, mensagem.lower()))
        return matches >= 2  # Pelo menos 2 referências temporais
    
    def _pergunta_sobre_patrimonio(self, mensagem: str) -> bool:
        """Verifica se está perguntando sobre patrimônio"""
        patrimonio_keywords = [
            'quanto você tem', 'qual faixa', 'patrimônio', 'patrimonio',
            'valor disponível', 'valor disponivel', 'quantia', 'reserva'
        ]
        return any(keyword in mensagem.lower() for keyword in patrimonio_keywords)
    
    def _pergunta_sobre_objetivo(self, mensagem: str) -> bool:
        """Verifica se está perguntando sobre objetivo"""
        objetivo_keywords = [
            'o que você busca', 'qual seu objetivo', 'o que quer',
            'finalidade', 'meta', 'propósito', 'proposito'
        ]
        return any(keyword in mensagem.lower() for keyword in objetivo_keywords)
    
    def _transicao_valida(self, estado_atual: Estado, proximo_estado: Estado) -> bool:
        """Verifica se transição de estado é válida"""
        transicoes_validas = {
            Estado.INICIO: [Estado.SITUACAO, Estado.FINALIZADO],
            Estado.SITUACAO: [Estado.PATRIMONIO, Estado.FINALIZADO],
            Estado.PATRIMONIO: [Estado.OBJETIVO, Estado.FINALIZADO],
            Estado.OBJETIVO: [Estado.URGENCIA, Estado.INTERESSE, Estado.AGENDAMENTO, Estado.FINALIZADO],
            Estado.URGENCIA: [Estado.INTERESSE, Estado.AGENDAMENTO, Estado.FINALIZADO],
            Estado.INTERESSE: [Estado.AGENDAMENTO, Estado.EDUCAR, Estado.FINALIZADO],
            Estado.AGENDAMENTO: [Estado.FINALIZADO],
            Estado.EDUCAR: [Estado.FINALIZADO],
            Estado.FINALIZADO: [Estado.FINALIZADO]
        }
        
        return proximo_estado in transicoes_validas.get(estado_atual, [])
    
    def _remover_emojis_excessivos(self, mensagem: str) -> str:
        """Remove emojis excessivos, mantendo apenas o primeiro"""
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        
        emojis = emoji_pattern.findall(mensagem)
        if len(emojis) <= 1:
            return mensagem
        
        # Remover todos os emojis exceto o primeiro
        mensagem_sem_emojis = emoji_pattern.sub('', mensagem)
        return mensagem_sem_emojis + emojis[0] if emojis else mensagem_sem_emojis
    
    def _build_frases_banidas(self) -> List[str]:
        """Constrói lista de frases banidas"""
        return [
            "não entendi",
            "descreva detalhadamente",
            "qual o valor exato",
            "defina um prazo exato",
            "quais são seus objetivos financeiros de curto, médio e longo prazo",
            "qualquer horário serve",
            "vamos marcar amanhã às",
            "ok.",  # resposta seca
            "entendeu?",
            "está claro?",
            "faz sentido?",
            "você compreendeu?",
            "ficou claro para você?"
        ]
    
    def _build_guardrails_checklist(self) -> List[str]:
        """Constrói checklist de guardrails"""
        return [
            "contém nome do lead",
            "<= 350 caracteres",
            "1 pergunta, 2–3 opções numeradas",
            "no máximo 1 emoji",
            "não repete slot já preenchido",
            "se em agendamento, sempre sugira 2 horários concretos",
            "confirma entendimento em 1 linha antes de avançar",
            "usa linguagem natural e conversacional",
            "oferece opções numeradas quando possível"
        ]
    
    def _build_limites_sistema(self) -> Dict[str, int]:
        """Constrói limites do sistema"""
        return {
            'max_mensagens': 8,
            'max_reformulacoes': 2,
            'min_score_continuacao': 30,
            'max_tentativas_por_estado': 3,
            'timeout_sessao_minutos': 30
        }
    
    def validar_qualidade_conversa(self, session_state: SessionState) -> Dict[str, Any]:
        """Valida qualidade geral da conversa"""
        
        qualidade = {
            'score_geral': 0,
            'pontos_positivos': [],
            'pontos_negativos': [],
            'recomendacoes': []
        }
        
        # Avaliar eficiência (slots preenchidos vs mensagens enviadas)
        slots_preenchidos = len(session_state.slots_preenchidos())
        eficiencia = slots_preenchidos / max(session_state.mensagem_count, 1)
        
        if eficiencia > 0.5:
            qualidade['pontos_positivos'].append("Boa eficiência na coleta de informações")
            qualidade['score_geral'] += 20
        else:
            qualidade['pontos_negativos'].append("Baixa eficiência - muitas mensagens para poucos slots")
            qualidade['recomendacoes'].append("Fazer perguntas mais diretas")
        
        # Avaliar progressão no funil
        if session_state.pode_agendar():
            qualidade['pontos_positivos'].append("Lead qualificado para agendamento")
            qualidade['score_geral'] += 30
        elif slots_preenchidos >= 2:
            qualidade['pontos_positivos'].append("Progresso moderado na qualificação")
            qualidade['score_geral'] += 15
        else:
            qualidade['pontos_negativos'].append("Pouco progresso na qualificação")
            qualidade['recomendacoes'].append("Focar em perguntas de qualificação")
        
        # Avaliar reformulações
        if session_state.reformulacoes_usadas == 0:
            qualidade['pontos_positivos'].append("Comunicação clara - sem reformulações")
            qualidade['score_geral'] += 10
        elif session_state.reformulacoes_usadas <= 2:
            qualidade['score_geral'] += 5
        else:
            qualidade['pontos_negativos'].append("Muitas reformulações - comunicação confusa")
            qualidade['recomendacoes'].append("Simplificar linguagem")
        
        # Avaliar duração da conversa
        if session_state.mensagem_count <= 6 and session_state.pode_agendar():
            qualidade['pontos_positivos'].append("Qualificação rápida e eficiente")
            qualidade['score_geral'] += 15
        elif session_state.mensagem_count >= 8:
            qualidade['pontos_negativos'].append("Conversa muito longa")
            qualidade['recomendacoes'].append("Ser mais direto e objetivo")
        
        # Score final (0-100)
        qualidade['score_geral'] = min(100, max(0, qualidade['score_geral']))
        
        return qualidade
    
    def gerar_relatorio_guardrails(self, violacoes_sessao: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Gera relatório de violações de guardrails na sessão"""
        
        if not violacoes_sessao:
            return {
                'status': 'excelente',
                'total_violacoes': 0,
                'categorias': {},
                'recomendacoes': ['Manter qualidade atual']
            }
        
        # Categorizar violações
        categorias = {}
        for violacao in violacoes_sessao:
            categoria = self._categorizar_violacao(violacao['erro'])
            categorias[categoria] = categorias.get(categoria, 0) + 1
        
        # Determinar status
        total_violacoes = len(violacoes_sessao)
        if total_violacoes <= 2:
            status = 'bom'
        elif total_violacoes <= 5:
            status = 'moderado'
        else:
            status = 'ruim'
        
        # Gerar recomendações
        recomendacoes = self._gerar_recomendacoes_por_categoria(categorias)
        
        return {
            'status': status,
            'total_violacoes': total_violacoes,
            'categorias': categorias,
            'recomendacoes': recomendacoes,
            'violacoes_detalhadas': violacoes_sessao
        }
    
    def _categorizar_violacao(self, erro: str) -> str:
        """Categoriza tipo de violação"""
        
        if 'nome' in erro.lower():
            return 'personalização'
        elif 'longa' in erro.lower() or 'caracteres' in erro.lower():
            return 'concisão'
        elif 'pergunta' in erro.lower() or 'opções' in erro.lower():
            return 'estrutura'
        elif 'emoji' in erro.lower():
            return 'formatação'
        elif 'frase banida' in erro.lower():
            return 'linguagem'
        elif 'transição' in erro.lower() or 'fluxo' in erro.lower():
            return 'fluxo'
        else:
            return 'outros'
    
    def _gerar_recomendacoes_por_categoria(self, categorias: Dict[str, int]) -> List[str]:
        """Gera recomendações baseadas nas categorias de violação"""
        
        recomendacoes = []
        
        if 'personalização' in categorias:
            recomendacoes.append("Sempre incluir o nome do lead na mensagem")
        
        if 'concisão' in categorias:
            recomendacoes.append("Manter mensagens mais curtas e diretas (máx 350 caracteres)")
        
        if 'estrutura' in categorias:
            recomendacoes.append("Fazer uma pergunta por mensagem com 2-3 opções numeradas")
        
        if 'linguagem' in categorias:
            recomendacoes.append("Evitar frases robotizadas - usar linguagem mais natural")
        
        if 'fluxo' in categorias:
            recomendacoes.append("Seguir sequência lógica de estados e não repetir perguntas")
        
        if not recomendacoes:
            recomendacoes.append("Continuar seguindo as boas práticas atuais")
        
        return recomendacoes
