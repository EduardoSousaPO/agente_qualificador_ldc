"""
Testes para as melhorias da Fase 1
Testa personalização, prompts melhorados, reconhecimento e fallbacks
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Adicionar path do projeto
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.app import extrair_nome_lead
from backend.services.reconhecimento_respostas import ReconhecimentoRespostasService
from backend.services.ai_conversation_service import AIConversationService


class TestFase1Melhorias(unittest.TestCase):
    """Testes das melhorias implementadas na Fase 1"""
    
    def setUp(self):
        """Setup dos testes"""
        self.reconhecimento_service = ReconhecimentoRespostasService()
        self.ai_service = AIConversationService()
    
    def test_extracao_nome_lead(self):
        """Teste da extração de nomes de leads do payload WhatsApp"""
        
        # Teste com fromName
        payload1 = {'fromName': 'João Silva', 'from': '5511999999999@c.us'}
        nome1 = extrair_nome_lead(payload1)
        self.assertEqual(nome1, 'João')
        
        # Teste com contact.name
        payload2 = {'contact': {'name': 'Maria Santos'}, 'from': '5511888888888@c.us'}
        nome2 = extrair_nome_lead(payload2)
        self.assertEqual(nome2, 'Maria')
        
        # Teste com pushName
        payload3 = {'pushName': 'Pedro Costa', 'from': '5511777777777@c.us'}
        nome3 = extrair_nome_lead(payload3)
        self.assertEqual(nome3, 'Pedro')
        
        # Teste sem nome
        payload4 = {'from': '5511666666666@c.us'}
        nome4 = extrair_nome_lead(payload4)
        self.assertIsNone(nome4)
        
        # Teste com nome em minúsculas
        payload5 = {'fromName': 'ana silva', 'from': '5511555555555@c.us'}
        nome5 = extrair_nome_lead(payload5)
        self.assertEqual(nome5, 'Ana')
    
    def test_reconhecimento_objetivos(self):
        """Teste do reconhecimento flexível de objetivos"""
        
        casos_teste = [
            # Crescimento
            ('quero ficar rico', 'crescimento'),
            ('crescer meu patrimônio', 'crescimento'),
            ('multiplicar meu dinheiro', 'crescimento'),
            ('ganhar mais dinheiro', 'crescimento'),
            
            # Renda
            ('gerar renda extra', 'renda'),
            ('renda passiva', 'renda'),
            ('quero receber dividendos', 'renda'),
            ('complementar minha renda', 'renda'),
            
            # Aposentadoria
            ('me aposentar bem', 'aposentadoria'),
            ('aposentadoria tranquila', 'aposentadoria'),
            ('para o futuro', 'aposentadoria'),
            ('longo prazo', 'aposentadoria'),
            
            # Proteção
            ('proteger o que já tenho', 'protecao'),
            ('proteger meu patrimônio', 'protecao'),
            ('segurança financeira', 'protecao'),
            ('não quero perder dinheiro', 'protecao'),
        ]
        
        for resposta, esperado in casos_teste:
            with self.subTest(resposta=resposta):
                resultado = self.reconhecimento_service.classificar_objetivo(resposta)
                self.assertEqual(resultado, esperado, 
                               f"Resposta '{resposta}' deveria ser classificada como '{esperado}', mas foi '{resultado}'")
    
    def test_reconhecimento_patrimonio(self):
        """Teste do reconhecimento flexível de patrimônio"""
        
        casos_teste = [
            # Baixo
            ('estou começando', 'baixo'),
            ('não tenho nada', 'baixo'),
            ('pouco dinheiro', 'baixo'),
            
            # Baixo-médio
            ('uns 50 mil', 'baixo_medio'),
            ('até 100 mil', 'baixo_medio'),
            ('alguns milhares', 'baixo_medio'),
            
            # Médio
            ('uns 300 mil', 'medio'),
            ('entre 100 e 500', 'medio'),
            ('razoável', 'medio'),
            
            # Alto
            ('mais de 500 mil', 'alto'),
            ('alguns milhões', 'alto'),
            ('bastante dinheiro', 'alto'),
        ]
        
        for resposta, esperado in casos_teste:
            with self.subTest(resposta=resposta):
                resultado = self.reconhecimento_service.classificar_patrimonio(resposta)
                self.assertEqual(resultado, esperado,
                               f"Resposta '{resposta}' deveria ser classificada como '{esperado}', mas foi '{resultado}'")
    
    def test_interesse_agendamento(self):
        """Teste do reconhecimento de interesse em agendamento"""
        
        # Respostas positivas
        respostas_positivas = [
            'sim', 'claro', 'pode ser', 'vamos', 'quero',
            'tenho interesse', 'me interessa', 'legal', 'bacana',
            'ok', 'tudo bem', 'perfeito', 'ótimo'
        ]
        
        for resposta in respostas_positivas:
            with self.subTest(resposta=resposta):
                resultado = self.reconhecimento_service.verificar_interesse_agendamento(resposta)
                self.assertTrue(resultado, f"'{resposta}' deveria indicar interesse positivo")
        
        # Respostas negativas
        respostas_negativas = [
            'não', 'não quero', 'não tenho interesse', 'não posso',
            'não dá', 'outro dia', 'depois', 'mais tarde'
        ]
        
        for resposta in respostas_negativas:
            with self.subTest(resposta=resposta):
                resultado = self.reconhecimento_service.verificar_interesse_agendamento(resposta)
                self.assertFalse(resultado, f"'{resposta}' deveria indicar falta de interesse")
    
    def test_fallback_inteligente(self):
        """Teste dos fallbacks inteligentes para evitar loops"""
        
        # Simular múltiplas tentativas no mesmo estado
        session_id = "test_session_123"
        lead_nome = "João"
        mensagem = "resposta confusa"
        
        # Primeira tentativa - não deve usar fallback
        resultado1 = self.ai_service._verificar_fallback(session_id, mensagem, "objetivo", lead_nome)
        self.assertIsNone(resultado1)
        
        # Segunda tentativa - não deve usar fallback ainda
        resultado2 = self.ai_service._verificar_fallback(session_id, mensagem, "objetivo", lead_nome)
        self.assertIsNone(resultado2)
        
        # Terceira tentativa - deve usar fallback
        resultado3 = self.ai_service._verificar_fallback(session_id, mensagem, "objetivo", lead_nome)
        self.assertIsNotNone(resultado3)
        self.assertIn("fallback_usado", resultado3)
        self.assertTrue(resultado3["fallback_usado"])
    
    def test_fallback_por_estado(self):
        """Teste dos fallbacks específicos por estado"""
        
        lead_nome = "Maria"
        mensagem = "não entendi"
        
        # Teste fallback para cada estado
        estados_teste = ['situacao', 'patrimonio', 'objetivo', 'agendamento']
        
        for estado in estados_teste:
            with self.subTest(estado=estado):
                resultado = self.ai_service._gerar_fallback_inteligente(estado, lead_nome, mensagem)
                
                self.assertIn('success', resultado)
                self.assertTrue(resultado['success'])
                self.assertIn('resposta', resultado)
                self.assertIn(lead_nome, resultado['resposta'])
                self.assertIn('acao', resultado)
                self.assertIn('proximo_estado', resultado)
    
    def test_geracoes_resposta_personalizada(self):
        """Teste das respostas personalizadas por classificação"""
        
        lead_nome = "Carlos"
        
        # Teste respostas para objetivos
        objetivo_crescimento = self.reconhecimento_service.gerar_resposta_reconhecida('objetivo', 'crescimento', lead_nome)
        self.assertIn(lead_nome, objetivo_crescimento)
        self.assertIn('crescer', objetivo_crescimento.lower())
        
        # Teste respostas para patrimônio
        patrimonio_alto = self.reconhecimento_service.gerar_resposta_reconhecida('patrimonio', 'alto', lead_nome)
        self.assertIn(lead_nome, patrimonio_alto)
        
        # Teste respostas para urgência
        urgencia_alta = self.reconhecimento_service.gerar_resposta_reconhecida('urgencia', 'alta', lead_nome)
        self.assertIn(lead_nome, urgencia_alta)
    
    def test_prompts_melhorados(self):
        """Teste dos prompts melhorados com linguagem natural"""
        
        lead_nome = "Ana"
        lead_canal = "whatsapp"
        
        # Testar prompt para estado inicial
        prompt_inicio = self.ai_service._get_prompt_sistema('inicio', lead_nome, lead_canal)
        
        # Verificar se contém elementos de personalização
        self.assertIn(lead_nome, prompt_inicio)
        self.assertIn('Amigável', prompt_inicio)
        self.assertIn('natural', prompt_inicio)
        self.assertIn('NUNCA diga "não entendi"', prompt_inicio)
        
        # Testar prompt para objetivo
        prompt_objetivo = self.ai_service._get_prompt_sistema('objetivo', lead_nome, lead_canal)
        self.assertIn(lead_nome, prompt_objetivo)
        self.assertIn('ACEITAR VARIAÇÕES', prompt_objetivo)


class TestIntegracaoFase1(unittest.TestCase):
    """Testes de integração das melhorias da Fase 1"""
    
    def setUp(self):
        """Setup para testes de integração"""
        self.reconhecimento_service = ReconhecimentoRespostasService()
    
    def test_fluxo_completo_reconhecimento(self):
        """Teste do fluxo completo de reconhecimento"""
        
        lead_nome = "Roberto"
        
        # Simular sequência de respostas
        respostas = [
            ("já tenho uns 200 mil investidos", "patrimonio", "medio"),
            ("quero gerar renda passiva", "objetivo", "renda"),
            ("tenho pressa, quero começar logo", "urgencia", "alta")
        ]
        
        for resposta, tipo, esperado in respostas:
            with self.subTest(resposta=resposta, tipo=tipo):
                if tipo == "patrimonio":
                    resultado = self.reconhecimento_service.classificar_patrimonio(resposta)
                elif tipo == "objetivo":
                    resultado = self.reconhecimento_service.classificar_objetivo(resposta)
                elif tipo == "urgencia":
                    resultado = self.reconhecimento_service.classificar_urgencia(resposta)
                
                self.assertEqual(resultado, esperado)
                
                # Testar geração de resposta personalizada
                resposta_personalizada = self.reconhecimento_service.gerar_resposta_reconhecida(tipo, resultado, lead_nome)
                self.assertIn(lead_nome, resposta_personalizada)


if __name__ == '__main__':
    # Executar testes
    unittest.main(verbosity=2)
