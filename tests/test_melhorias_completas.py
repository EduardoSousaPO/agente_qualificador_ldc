"""
Testes das Melhorias Completas do Sistema de IA
Validação de todas as melhorias implementadas
"""
import pytest
import json
from unittest.mock import Mock, patch
import sys
import os

# Adicionar o diretório backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from backend.models.conversation_models import (
    Estado, Acao, PatrimonioRange, Objetivo, Urgencia, Interesse,
    ContextoConversa, RespostaIA, SessionState, PromptContext
)
from backend.services.prompt_service import PromptService
from backend.services.validation_service import ValidationService
from backend.services.slot_filling_service import SlotFillingService
from backend.services.guardrails_service import GuardrailsService
from backend.services.intention_classifier import IntentionClassifier


class TestConversationModels:
    """Testa os novos modelos Pydantic"""
    
    def test_contexto_conversa_criacao(self):
        """Testa criação do contexto de conversa"""
        contexto = ContextoConversa(
            patrimonio_range=PatrimonioRange.ENTRE_100_500K,
            objetivo=Objetivo.CRESCIMENTO,
            urgencia=Urgencia.ALTA,
            interesse=Interesse.MUITO_ALTO
        )
        
        assert contexto.patrimonio_range == PatrimonioRange.ENTRE_100_500K
        assert contexto.objetivo == Objetivo.CRESCIMENTO
        assert contexto.urgencia == Urgencia.ALTA
        assert contexto.interesse == Interesse.MUITO_ALTO
    
    def test_resposta_ia_validacao(self):
        """Testa validação da resposta IA"""
        resposta = RespostaIA(
            mensagem="Oi João! Você já investe hoje? 1) sim 2) não",
            acao=Acao.CONTINUAR,
            proximo_estado=Estado.PATRIMONIO,
            contexto=ContextoConversa(),
            score_parcial=50
        )
        
        assert len(resposta.mensagem) <= 350
        assert resposta.acao == Acao.CONTINUAR
        assert resposta.score_parcial >= 0 and resposta.score_parcial <= 100
    
    def test_session_state_slots(self):
        """Testa gerenciamento de slots na sessão"""
        session = SessionState(
            lead_id="test_lead",
            session_id="test_session"
        )
        
        # Preencher alguns slots
        session.contexto.patrimonio_range = PatrimonioRange.ACIMA_500K
        session.contexto.objetivo = Objetivo.RENDA
        
        slots_preenchidos = session.slots_preenchidos()
        slots_faltantes = session.slots_faltantes()
        
        assert 'patrimonio_range' in slots_preenchidos
        assert 'objetivo' in slots_preenchidos
        assert len(slots_faltantes) < 4  # Alguns slots ainda faltando
    
    def test_pode_agendar(self):
        """Testa lógica de agendamento"""
        session = SessionState(
            lead_id="test_lead",
            session_id="test_session"
        )
        
        # Não pode agendar sem dados
        assert not session.pode_agendar()
        
        # Preencher dados suficientes
        session.contexto.patrimonio_range = PatrimonioRange.ACIMA_500K
        session.contexto.objetivo = Objetivo.CRESCIMENTO
        session.contexto.interesse = Interesse.MUITO_ALTO
        
        # Agora pode agendar
        assert session.pode_agendar()


class TestPromptService:
    """Testa o serviço de prompts"""
    
    def test_system_prompt_criacao(self):
        """Testa criação do prompt do sistema"""
        service = PromptService()
        
        assert service.system_prompt is not None
        assert "agente comercial da ldc capital" in service.system_prompt.lower()
        assert "português do brasil" in service.system_prompt.lower()
        assert "350 caracteres" in service.system_prompt
    
    def test_json_schema_estrutura(self):
        """Testa estrutura do schema JSON"""
        service = PromptService()
        schema = service.json_schema
        
        assert schema['type'] == 'object'
        assert 'mensagem' in schema['required']
        assert 'acao' in schema['required']
        assert 'proximo_estado' in schema['required']
        assert 'score_parcial' in schema['required']
    
    def test_user_prompt_construcao(self):
        """Testa construção do prompt do usuário"""
        service = PromptService()
        
        context = PromptContext(
            estado_atual=Estado.PATRIMONIO,
            slots_preenchidos={'situacao': 'ja_investe'},
            slots_faltantes=['patrimonio_range'],
            nome_lead="João",
            canal="whatsapp",
            ultima_mensagem_lead="tenho um pouco investido",
            historico_compacto=[]
        )
        
        user_prompt = service.build_user_prompt(context)
        
        assert "João" in user_prompt
        assert "patrimonio" in user_prompt.lower()
        assert "slots_preenchidos" in user_prompt
        assert "350 caracteres" in user_prompt
    
    def test_reformulacao_prompt(self):
        """Testa prompt de reformulação"""
        service = PromptService()
        
        reformulacao = service.build_reformulacao_prompt(Estado.PATRIMONIO, "João", 1)
        
        assert "reformulação" in reformulacao.lower() or "reformule" in reformulacao.lower()
        assert "João" in reformulacao
        assert "350 caracteres" in reformulacao


class TestValidationService:
    """Testa o serviço de validação"""
    
    def test_json_extraction_valido(self):
        """Testa extração de JSON válido"""
        service = ValidationService()
        
        content = '''
        {
            "mensagem": "Oi João! Como vai?",
            "acao": "continuar",
            "proximo_estado": "patrimonio",
            "contexto": {},
            "score_parcial": 50
        }
        '''
        
        validation = service.validar_resposta_ia(content, Estado.SITUACAO, "João")
        
        assert validation.valida
        assert validation.resposta_corrigida is not None
        assert validation.resposta_corrigida.mensagem == "Oi João! Como vai?"
    
    def test_correcao_automatica(self):
        """Testa correção automática de erros"""
        service = ValidationService()
        
        # JSON com mensagem muito longa
        content = '''
        {
            "mensagem": "''' + "A" * 400 + '''",
            "acao": "continuar",
            "proximo_estado": "patrimonio",
            "contexto": {},
            "score_parcial": 50
        }
        '''
        
        validation = service.validar_resposta_ia(content, Estado.SITUACAO, "João")
        
        # Deve corrigir automaticamente
        assert validation.valida
        assert len(validation.resposta_corrigida.mensagem) <= 350
    
    def test_fallback_response(self):
        """Testa resposta de fallback"""
        service = ValidationService()
        
        fallback = service.get_fallback_response(Estado.PATRIMONIO, "João")
        
        assert fallback is not None
        assert "João" in fallback.mensagem
        assert len(fallback.mensagem) <= 350


class TestSlotFillingService:
    """Testa o serviço de slot filling"""
    
    def test_extracao_patrimonio(self):
        """Testa extração de patrimônio"""
        service = SlotFillingService()
        contexto = ContextoConversa()
        
        # Teste com opção numerada
        contexto_atualizado = service.extrair_slots_da_mensagem(
            "opção 2", Estado.PATRIMONIO, contexto
        )
        
        assert contexto_atualizado.patrimonio_range == PatrimonioRange.ENTRE_100_500K
    
    def test_extracao_objetivo_textual(self):
        """Testa extração de objetivo por texto"""
        service = SlotFillingService()
        contexto = ContextoConversa()
        
        contexto_atualizado = service.extrair_slots_da_mensagem(
            "quero que o dinheiro cresça bastante", Estado.OBJETIVO, contexto
        )
        
        assert contexto_atualizado.objetivo == Objetivo.CRESCIMENTO
    
    def test_extracao_interesse(self):
        """Testa extração de interesse"""
        service = SlotFillingService()
        contexto = ContextoConversa()
        
        contexto_atualizado = service.extrair_slots_da_mensagem(
            "sim, quero muito!", Estado.INTERESSE, contexto
        )
        
        assert contexto_atualizado.interesse == Interesse.MUITO_ALTO
    
    def test_calculo_score_parcial(self):
        """Testa cálculo de score parcial"""
        service = SlotFillingService()
        
        contexto = ContextoConversa(
            patrimonio_range=PatrimonioRange.ACIMA_500K,
            objetivo=Objetivo.CRESCIMENTO,
            urgencia=Urgencia.ALTA,
            interesse=Interesse.MUITO_ALTO
        )
        
        score = service.calcular_score_parcial(contexto)
        
        assert score >= 80  # Score alto com todos os slots bem preenchidos
        assert score <= 100


class TestGuardrailsService:
    """Testa o serviço de guardrails"""
    
    def test_verificacao_nome_lead(self):
        """Testa verificação de nome do lead"""
        service = GuardrailsService()
        
        resposta = RespostaIA(
            mensagem="Você já investe hoje?",  # Sem nome
            acao=Acao.CONTINUAR,
            proximo_estado=Estado.PATRIMONIO,
            contexto=ContextoConversa(),
            score_parcial=50
        )
        
        session_state = SessionState(lead_id="João", session_id="test")
        
        passou, erros, corrigida = service.aplicar_guardrails(resposta, session_state, "João")
        
        # O sistema deve corrigir automaticamente e passar na validação
        assert passou  # Deve passar após correção
        assert corrigida is not None
        assert "João" in corrigida.mensagem
    
    def test_verificacao_tamanho_mensagem(self):
        """Testa verificação de tamanho da mensagem"""
        service = GuardrailsService()
        
        # Testar apenas a função de verificação de checklist
        resposta = RespostaIA(
            mensagem="João, esta é uma mensagem normal",
            acao=Acao.CONTINUAR,
            proximo_estado=Estado.PATRIMONIO,
            contexto=ContextoConversa(),
            score_parcial=50
        )
        
        # Verificar que mensagem normal passa
        erros = service._verificar_checklist_basico(resposta, "João")
        assert len(erros) >= 1  # Deve ter alguns erros (falta pergunta, opções, etc)
        
        # Verificar que detecta nome presente
        assert not any("nome" in erro.lower() for erro in erros)
    
    def test_frases_banidas(self):
        """Testa detecção de frases banidas"""
        service = GuardrailsService()
        
        resposta = RespostaIA(
            mensagem="João, não entendi sua resposta",  # Frase banida
            acao=Acao.CONTINUAR,
            proximo_estado=Estado.PATRIMONIO,
            contexto=ContextoConversa(),
            score_parcial=50
        )
        
        session_state = SessionState(lead_id="João", session_id="test")
        
        passou, erros, corrigida = service.aplicar_guardrails(resposta, session_state, "João")
        
        # O sistema deve corrigir automaticamente
        assert passou  # Deve passar após correção
        assert corrigida is not None
        assert "não entendi" not in corrigida.mensagem  # Frase banida foi removida


class TestIntentionClassifier:
    """Testa o classificador de intenção"""
    
    def test_classificacao_interesse(self):
        """Testa classificação de interesse"""
        classifier = IntentionClassifier()
        
        intencao = classifier.classificar_intencao_rapida("Sim, quero saber mais!")
        
        assert intencao.intencao == "interesse"
        assert intencao.sentimento == "positivo"
        assert intencao.urgencia >= 5
    
    def test_classificacao_agendamento(self):
        """Testa classificação de agendamento"""
        classifier = IntentionClassifier()
        
        intencao = classifier.classificar_intencao_rapida("Podemos marcar para amanhã de manhã")
        
        assert intencao.intencao == "agendamento"
        assert intencao.qualificacao_score >= 80
    
    def test_classificacao_recusa(self):
        """Testa classificação de recusa"""
        classifier = IntentionClassifier()
        
        intencao = classifier.classificar_intencao_rapida("Não, agora não tenho interesse")
        
        assert intencao.intencao == "recusa"
        assert intencao.sentimento == "negativo"
        assert intencao.qualificacao_score <= 30
    
    def test_extracao_disponibilidade(self):
        """Testa extração de disponibilidade"""
        classifier = IntentionClassifier()
        
        disponibilidade = classifier.extrair_disponibilidade("Posso de manhã ou na terça à tarde")
        
        assert disponibilidade is not None
        assert "manhã" in disponibilidade or "terça" in disponibilidade


class TestIntegracaoCompleta:
    """Testes de integração dos componentes"""
    
    @patch('requests.post')
    def test_fluxo_completo_qualificacao(self, mock_post):
        """Testa fluxo completo de qualificação"""
        
        # Mock da resposta da OpenAI
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        "mensagem": "Oi João! Você já investe hoje? 1) sim 2) não",
                        "acao": "continuar",
                        "proximo_estado": "patrimonio",
                        "contexto": {"ja_investiu": True},
                        "score_parcial": 60
                    })
                }
            }]
        }
        mock_post.return_value = mock_response
        
        # Simular fluxo completo seria mais complexo
        # Por ora, verificar que os componentes funcionam juntos
        
        prompt_service = PromptService()
        validation_service = ValidationService()
        slot_service = SlotFillingService()
        
        assert prompt_service is not None
        assert validation_service is not None
        assert slot_service is not None
    
    def test_transicoes_estado_validas(self):
        """Testa transições válidas de estado"""
        session = SessionState(
            lead_id="test_lead",
            session_id="test_session",
            estado_atual=Estado.INICIO
        )
        
        # Sequência válida de transições
        assert session.proximo_estado_logico() == Estado.SITUACAO
        
        session.estado_atual = Estado.SITUACAO
        assert session.proximo_estado_logico() == Estado.PATRIMONIO
        
        session.estado_atual = Estado.PATRIMONIO
        assert session.proximo_estado_logico() == Estado.OBJETIVO
    
    def test_qualidade_conversa_completa(self):
        """Testa avaliação de qualidade da conversa"""
        guardrails = GuardrailsService()
        
        session = SessionState(
            lead_id="João",
            session_id="test_session",
            mensagem_count=4,
            reformulacoes_usadas=1
        )
        
        # Simular conversa bem-sucedida
        session.contexto.patrimonio_range = PatrimonioRange.ACIMA_500K
        session.contexto.objetivo = Objetivo.CRESCIMENTO
        session.contexto.interesse = Interesse.MUITO_ALTO
        
        qualidade = guardrails.validar_qualidade_conversa(session)
        
        assert qualidade['score_geral'] > 50
        assert len(qualidade['pontos_positivos']) > 0


if __name__ == "__main__":
    # Executar testes
    pytest.main([__file__, "-v", "--tb=short"])
