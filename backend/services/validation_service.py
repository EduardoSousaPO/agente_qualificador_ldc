"""
Serviço de Validação JSON Robusto
Sistema de validação e correção automática de respostas da IA
"""
import json
import re
from typing import Dict, Any, Optional, List
from pydantic import ValidationError
import structlog

from backend.models.conversation_models import (
    RespostaIA, ValidacaoResposta, Estado, Acao, ContextoConversa
)

logger = structlog.get_logger(__name__)


class ValidationService:
    """Serviço para validação robusta de respostas JSON da IA"""
    
    def __init__(self):
        self.max_retries = 3
        self.fallback_responses = self._build_fallback_responses()
    
    def validar_resposta_ia(self, content: str, estado_atual: Estado, nome_lead: str) -> ValidacaoResposta:
        """Valida resposta da IA e tenta corrigir se necessário"""
        
        try:
            # Tentar extrair JSON do conteúdo
            json_data = self._extract_json(content)
            
            if not json_data:
                logger.warning("Nenhum JSON válido encontrado no conteúdo", content=content[:200])
                return self._create_fallback_validation(estado_atual, nome_lead, "JSON não encontrado")
            
            # Validar estrutura básica
            validation_result = ValidacaoResposta(valida=True)
            
            # Validar campos obrigatórios
            required_fields = ['mensagem', 'acao', 'proximo_estado', 'score_parcial']
            for field in required_fields:
                if field not in json_data:
                    validation_result.adicionar_erro(f"Campo obrigatório '{field}' ausente")
            
            if not validation_result.valida:
                return self._try_fix_missing_fields(json_data, estado_atual, nome_lead, validation_result)
            
            # Tentar criar objeto Pydantic
            try:
                resposta_ia = RespostaIA(**json_data)
                
                # Validações adicionais
                additional_validation = self._validate_business_rules(resposta_ia, estado_atual, nome_lead)
                if not additional_validation.valida:
                    return additional_validation
                
                validation_result.resposta_corrigida = resposta_ia
                return validation_result
                
            except ValidationError as e:
                logger.warning("Erro de validação Pydantic", errors=str(e), json_data=json_data)
                return self._try_fix_pydantic_errors(json_data, e, estado_atual, nome_lead)
                
        except Exception as e:
            logger.error("Erro inesperado na validação", error=str(e), content=content[:200])
            return self._create_fallback_validation(estado_atual, nome_lead, f"Erro inesperado: {str(e)}")
    
    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Extrai JSON do conteúdo, tentando múltiplas estratégias"""
        
        # Limpar conteúdo
        content = content.strip()
        
        # Estratégia 1: JSON direto
        try:
            return json.loads(content)
        except:
            pass
        
        # Estratégia 2: Buscar JSON entre chaves
        json_pattern = r'\{.*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except:
                continue
        
        # Estratégia 3: Buscar por campos conhecidos
        try:
            return self._extract_json_by_fields(content)
        except:
            pass
        
        return None
    
    def _extract_json_by_fields(self, content: str) -> Optional[Dict[str, Any]]:
        """Extrai campos JSON conhecidos do texto"""
        
        result = {}
        
        # Padrões para extração de campos
        patterns = {
            'mensagem': r'"mensagem":\s*"([^"]+)"',
            'acao': r'"acao":\s*"([^"]+)"',
            'proximo_estado': r'"proximo_estado":\s*"([^"]+)"',
            'score_parcial': r'"score_parcial":\s*(\d+)'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                value = match.group(1)
                if field == 'score_parcial':
                    result[field] = int(value)
                else:
                    result[field] = value
        
        # Adicionar contexto vazio se não encontrado
        if 'contexto' not in result:
            result['contexto'] = {}
        
        return result if len(result) >= 4 else None
    
    def _validate_business_rules(self, resposta: RespostaIA, estado_atual: Estado, nome_lead: str) -> ValidacaoResposta:
        """Valida regras de negócio específicas"""
        
        validation = ValidacaoResposta(valida=True)
        
        # Verificar se nome do lead está na mensagem
        if nome_lead.lower() not in resposta.mensagem.lower():
            validation.adicionar_erro("Nome do lead não encontrado na mensagem")
        
        # Verificar tamanho da mensagem
        if len(resposta.mensagem) > 350:
            validation.adicionar_erro("Mensagem muito longa (>350 caracteres)")
        
        # Verificar se tem pergunta quando deveria ter
        if resposta.acao == Acao.CONTINUAR and '?' not in resposta.mensagem:
            validation.adicionar_erro("Ação 'continuar' deveria ter uma pergunta")
        
        # Verificar opções numeradas
        if resposta.acao == Acao.CONTINUAR:
            if not self._has_numbered_options(resposta.mensagem):
                validation.adicionar_erro("Deveria ter opções numeradas")
        
        # Verificar transição de estado válida
        if not self._is_valid_state_transition(estado_atual, resposta.proximo_estado):
            validation.adicionar_erro(f"Transição inválida: {estado_atual} -> {resposta.proximo_estado}")
        
        # Se há erros, tentar corrigir
        if not validation.valida:
            corrected = self._try_correct_business_rules(resposta, validation.erros, estado_atual, nome_lead)
            if corrected:
                validation.resposta_corrigida = corrected
                validation.valida = True
                validation.erros = []
        else:
            validation.resposta_corrigida = resposta
        
        return validation
    
    def _has_numbered_options(self, mensagem: str) -> bool:
        """Verifica se a mensagem tem opções numeradas"""
        patterns = [
            r'1\)',  # 1)
            r'1\.',  # 1.
            r'1️⃣',   # emoji
            r'1\s',  # 1 seguido de espaço
        ]
        
        return any(re.search(pattern, mensagem) for pattern in patterns)
    
    def _is_valid_state_transition(self, current: Estado, next_state: Estado) -> bool:
        """Verifica se a transição de estado é válida"""
        
        valid_transitions = {
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
        
        return next_state in valid_transitions.get(current, [])
    
    def _try_fix_missing_fields(self, json_data: Dict[str, Any], estado_atual: Estado, 
                               nome_lead: str, validation: ValidacaoResposta) -> ValidacaoResposta:
        """Tenta corrigir campos ausentes"""
        
        # Adicionar campos padrão se ausentes
        if 'contexto' not in json_data:
            json_data['contexto'] = {}
        
        if 'score_parcial' not in json_data:
            json_data['score_parcial'] = 50  # Score neutro
        
        if 'acao' not in json_data:
            json_data['acao'] = 'continuar'
        
        if 'proximo_estado' not in json_data:
            json_data['proximo_estado'] = self._get_default_next_state(estado_atual)
        
        if 'mensagem' not in json_data:
            json_data['mensagem'] = self._get_fallback_message(estado_atual, nome_lead)
        
        # Tentar validar novamente
        try:
            resposta_corrigida = RespostaIA(**json_data)
            validation.resposta_corrigida = resposta_corrigida
            validation.valida = True
            validation.erros = []
            return validation
        except Exception as e:
            logger.warning("Falha ao corrigir campos ausentes", error=str(e))
            return self._create_fallback_validation(estado_atual, nome_lead, "Correção falhou")
    
    def _try_fix_pydantic_errors(self, json_data: Dict[str, Any], error: ValidationError, 
                                estado_atual: Estado, nome_lead: str) -> ValidacaoResposta:
        """Tenta corrigir erros de validação Pydantic"""
        
        # Corrigir valores de enum inválidos
        for err in error.errors():
            field = err['loc'][0] if err['loc'] else None
            
            if field == 'acao' and 'acao' in json_data:
                json_data['acao'] = self._fix_acao_enum(json_data['acao'])
            
            elif field == 'proximo_estado' and 'proximo_estado' in json_data:
                json_data['proximo_estado'] = self._fix_estado_enum(json_data['proximo_estado'])
            
            elif field == 'mensagem' and 'mensagem' in json_data:
                if len(json_data['mensagem']) > 350:
                    json_data['mensagem'] = json_data['mensagem'][:347] + "..."
        
        # Tentar validar novamente
        try:
            resposta_corrigida = RespostaIA(**json_data)
            return ValidacaoResposta(valida=True, resposta_corrigida=resposta_corrigida)
        except Exception as e:
            logger.warning("Falha ao corrigir erros Pydantic", error=str(e))
            return self._create_fallback_validation(estado_atual, nome_lead, "Correção Pydantic falhou")
    
    def _fix_acao_enum(self, value: str) -> str:
        """Corrige valores inválidos de ação"""
        value_lower = value.lower()
        
        if 'continuar' in value_lower or 'prosseguir' in value_lower:
            return 'continuar'
        elif 'agendar' in value_lower or 'marcar' in value_lower:
            return 'agendar'
        elif 'finalizar' in value_lower or 'terminar' in value_lower:
            return 'finalizar'
        elif 'transferir' in value_lower or 'humano' in value_lower:
            return 'transferir_humano'
        else:
            return 'continuar'
    
    def _fix_estado_enum(self, value: str) -> str:
        """Corrige valores inválidos de estado"""
        value_lower = value.lower()
        
        state_mapping = {
            'inicio': 'inicio',
            'situacao': 'situacao', 
            'patrimonio': 'patrimonio',
            'objetivo': 'objetivo',
            'urgencia': 'urgencia',
            'interesse': 'interesse',
            'agendamento': 'agendamento',
            'educar': 'educar',
            'finalizado': 'finalizado'
        }
        
        for key, mapped_value in state_mapping.items():
            if key in value_lower:
                return mapped_value
        
        return 'finalizado'
    
    def _try_correct_business_rules(self, resposta: RespostaIA, erros: List[str], 
                                   estado_atual: Estado, nome_lead: str) -> Optional[RespostaIA]:
        """Tenta corrigir violações de regras de negócio"""
        
        # Criar cópia para correção
        data = resposta.model_dump()
        
        # Corrigir nome do lead ausente
        if "Nome do lead não encontrado" in str(erros):
            if not nome_lead.lower() in data['mensagem'].lower():
                # Inserir nome no início
                data['mensagem'] = f"{nome_lead}, {data['mensagem']}"
        
        # Corrigir mensagem muito longa
        if "muito longa" in str(erros):
            data['mensagem'] = data['mensagem'][:347] + "..."
        
        # Adicionar pergunta se necessário
        if "deveria ter uma pergunta" in str(erros):
            if '?' not in data['mensagem']:
                data['mensagem'] += "?"
        
        # Adicionar opções numeradas
        if "opções numeradas" in str(erros):
            if not self._has_numbered_options(data['mensagem']):
                data['mensagem'] += " 1) sim 2) não"
        
        try:
            return RespostaIA(**data)
        except:
            return None
    
    def _get_default_next_state(self, current_state: Estado) -> str:
        """Retorna próximo estado padrão"""
        next_states = {
            Estado.INICIO: Estado.SITUACAO,
            Estado.SITUACAO: Estado.PATRIMONIO,
            Estado.PATRIMONIO: Estado.OBJETIVO,
            Estado.OBJETIVO: Estado.AGENDAMENTO,
            Estado.URGENCIA: Estado.INTERESSE,
            Estado.INTERESSE: Estado.AGENDAMENTO,
            Estado.AGENDAMENTO: Estado.FINALIZADO,
            Estado.EDUCAR: Estado.FINALIZADO,
            Estado.FINALIZADO: Estado.FINALIZADO
        }
        
        return str(next_states.get(current_state, Estado.FINALIZADO))
    
    def _get_fallback_message(self, estado: Estado, nome_lead: str) -> str:
        """Retorna mensagem de fallback por estado"""
        
        fallbacks = {
            Estado.INICIO: f"Oi {nome_lead}! Sou da LDC Capital. Posso te ajudar com investimentos? 1) sim 2) agora não",
            Estado.SITUACAO: f"Legal, {nome_lead}! Você já investe hoje ou está começando? 1) já invisto 2) começando",
            Estado.PATRIMONIO: f"Show, {nome_lead}! Qual faixa você tem? 1) até 100k 2) 100-500k 3) +500k",
            Estado.OBJETIVO: f"Perfeito, {nome_lead}! O que busca? 1) crescimento 2) renda mensal 3) aposentadoria",
            Estado.AGENDAMENTO: f"Ótimo, {nome_lead}! Posso agendar 30min? 1) amanhã 10h 2) amanhã 16h",
            Estado.FINALIZADO: f"Obrigado, {nome_lead}! Foi um prazer conversar com você! 😊"
        }
        
        return fallbacks.get(estado, f"Desculpe, {nome_lead}. Pode repetir?")
    
    def _create_fallback_validation(self, estado: Estado, nome_lead: str, erro: str) -> ValidacaoResposta:
        """Cria validação com resposta de fallback"""
        
        fallback_resposta = RespostaIA(
            mensagem=self._get_fallback_message(estado, nome_lead),
            acao=Acao.CONTINUAR,
            proximo_estado=Estado(self._get_default_next_state(estado)),
            contexto=ContextoConversa(),
            score_parcial=30
        )
        
        return ValidacaoResposta(
            valida=True,
            erros=[f"Fallback usado: {erro}"],
            resposta_corrigida=fallback_resposta
        )
    
    def _build_fallback_responses(self) -> Dict[Estado, RespostaIA]:
        """Constrói respostas de fallback por estado"""
        
        fallbacks = {}
        
        for estado in Estado:
            fallbacks[estado] = RespostaIA(
                mensagem=self._get_fallback_message(estado, "Amigo"),
                acao=Acao.CONTINUAR if estado != Estado.FINALIZADO else Acao.FINALIZAR,
                proximo_estado=Estado(self._get_default_next_state(estado)),
                contexto=ContextoConversa(),
                score_parcial=30
            )
        
        return fallbacks
    
    def get_fallback_response(self, estado: Estado, nome_lead: str) -> RespostaIA:
        """Retorna resposta de fallback para um estado"""
        
        base_response = self.fallback_responses.get(estado)
        if base_response and nome_lead != "Amigo":
            # Personalizar com nome real
            data = base_response.model_dump()
            data['mensagem'] = data['mensagem'].replace("Amigo", nome_lead)
            return RespostaIA(**data)
        
        return base_response or self.fallback_responses[Estado.FINALIZADO]
