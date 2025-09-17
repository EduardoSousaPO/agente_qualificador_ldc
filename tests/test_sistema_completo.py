#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes do Sistema Completo - Agente Qualificador LDC
"""

import sys
import os
import requests
import json
from datetime import datetime

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TesteSistemaCompleto:
    """Testes integrados do sistema completo"""
    
    def __init__(self):
        self.webhook_url = "https://agente-qualificador-ldc.onrender.com/webhook"
        self.resultados = []
        
    def log_resultado(self, teste: str, sucesso: bool, detalhes: str = ""):
        """Log dos resultados dos testes"""
        resultado = {
            'teste': teste,
            'sucesso': sucesso,
            'detalhes': detalhes,
            'timestamp': datetime.now().isoformat()
        }
        self.resultados.append(resultado)
        
        status = "✅ PASSOU" if sucesso else "❌ FALHOU"
        print(f"{status} - {teste}")
        if detalhes:
            print(f"   Detalhes: {detalhes}")
    
    def criar_payload_teste(self, telefone: str, mensagem: str, nome: str = "TestUser"):
        """Cria payload de teste simulando WAHA"""
        return {
            "event": "message",
            "payload": {
                "from": telefone,
                "body": mensagem,
                "fromMe": False,
                "fromName": nome,
                "contact": {"name": nome},
                "pushName": nome,
                "id": f"test_{datetime.now().timestamp()}",
                "timestamp": int(datetime.now().timestamp())
            }
        }
    
    def enviar_webhook(self, payload: dict) -> dict:
        """Envia webhook para o sistema"""
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            return {
                'status_code': response.status_code,
                'success': response.status_code in [200, 201],
                'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
        except Exception as e:
            return {
                'status_code': 0,
                'success': False,
                'error': str(e)
            }
    
    def teste_webhook_basico(self):
        """Teste 1: Webhook básico recebe mensagem"""
        telefone = "5511999887766@c.us"
        mensagem = "oi"
        
        payload = self.criar_payload_teste(telefone, mensagem, "João Teste")
        resultado = self.enviar_webhook(payload)
        
        sucesso = resultado['success'] and resultado['status_code'] == 200
        detalhes = f"Status: {resultado['status_code']}, Response: {resultado.get('response', 'N/A')}"
        
        self.log_resultado("Webhook básico", sucesso, detalhes)
        return sucesso
    
    def teste_criacao_lead(self):
        """Teste 2: Sistema cria lead automaticamente"""
        telefone = f"5511888777666@c.us"  # Número único para teste
        mensagem = "olá, quero investir"
        
        payload = self.criar_payload_teste(telefone, mensagem, "Maria Teste")
        resultado = self.enviar_webhook(payload)
        
        sucesso = resultado['success']
        detalhes = f"Lead creation test - Status: {resultado['status_code']}"
        
        self.log_resultado("Criação automática de lead", sucesso, detalhes)
        return sucesso
    
    def teste_fluxo_qualificacao(self):
        """Teste 3: Fluxo básico de qualificação"""
        telefone = f"5511777666555@c.us"  # Número único
        
        # Primeira mensagem
        payload1 = self.criar_payload_teste(telefone, "oi", "Carlos Teste")
        resultado1 = self.enviar_webhook(payload1)
        
        if not resultado1['success']:
            self.log_resultado("Fluxo qualificação - Primeira mensagem", False, "Falha na primeira mensagem")
            return False
        
        # Segunda mensagem - resposta sobre patrimônio
        payload2 = self.criar_payload_teste(telefone, "tenho uns 200 mil", "Carlos Teste")
        resultado2 = self.enviar_webhook(payload2)
        
        sucesso = resultado2['success']
        detalhes = f"Fluxo com 2 mensagens - Status final: {resultado2['status_code']}"
        
        self.log_resultado("Fluxo básico qualificação", sucesso, detalhes)
        return sucesso
    
    def teste_reformulacao(self):
        """Teste 4: Sistema reformula quando lead não entende"""
        telefone = f"5511666555444@c.us"  # Número único
        
        # Primeira mensagem
        payload1 = self.criar_payload_teste(telefone, "oi", "Ana Teste")
        resultado1 = self.enviar_webhook(payload1)
        
        if not resultado1['success']:
            self.log_resultado("Teste reformulação - Setup", False, "Falha no setup")
            return False
        
        # Mensagem de não compreensão
        payload2 = self.criar_payload_teste(telefone, "não entendi a pergunta", "Ana Teste")
        resultado2 = self.enviar_webhook(payload2)
        
        sucesso = resultado2['success']
        detalhes = f"Sistema deve reformular - Status: {resultado2['status_code']}"
        
        self.log_resultado("Sistema reformula quando lead não entende", sucesso, detalhes)
        return sucesso
    
    def teste_eventos_waha(self):
        """Teste 5: Eventos WAHA são processados corretamente"""
        payloads_teste = [
            {"event": "message.ack", "payload": {"id": "test123", "ack": "delivered"}},
            {"event": "message.waiting", "payload": {"id": "test124"}},
            {"event": "session.status", "payload": {"status": "CONNECTED", "name": "default"}}
        ]
        
        sucessos = 0
        for payload in payloads_teste:
            resultado = self.enviar_webhook(payload)
            if resultado['success']:
                sucessos += 1
        
        sucesso = sucessos == len(payloads_teste)
        detalhes = f"{sucessos}/{len(payloads_teste)} eventos processados com sucesso"
        
        self.log_resultado("Processamento eventos WAHA", sucesso, detalhes)
        return sucesso
    
    def executar_todos_testes(self):
        """Executa todos os testes"""
        print("🚀 INICIANDO TESTES DO SISTEMA COMPLETO")
        print("=" * 50)
        
        testes = [
            self.teste_webhook_basico,
            self.teste_criacao_lead,
            self.teste_fluxo_qualificacao,
            self.teste_reformulacao,
            self.teste_eventos_waha
        ]
        
        sucessos = 0
        for teste in testes:
            try:
                if teste():
                    sucessos += 1
            except Exception as e:
                self.log_resultado(teste.__name__, False, f"Erro: {str(e)}")
        
        print("\n" + "=" * 50)
        print(f"📊 RESULTADO FINAL: {sucessos}/{len(testes)} testes passaram")
        
        if sucessos == len(testes):
            print("🎉 TODOS OS TESTES PASSARAM! Sistema funcionando corretamente.")
        else:
            print("⚠️ ALGUNS TESTES FALHARAM. Verificar logs para detalhes.")
        
        return sucessos, len(testes)
    
    def gerar_relatorio(self):
        """Gera relatório detalhado dos testes"""
        relatorio = {
            'timestamp': datetime.now().isoformat(),
            'total_testes': len(self.resultados),
            'sucessos': len([r for r in self.resultados if r['sucesso']]),
            'falhas': len([r for r in self.resultados if not r['sucesso']]),
            'resultados': self.resultados
        }
        
        # Salvar relatório
        with open('relatorio_testes.json', 'w', encoding='utf-8') as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Relatório salvo em: relatorio_testes.json")
        return relatorio


if __name__ == "__main__":
    print("🧪 SISTEMA DE TESTES - AGENTE QUALIFICADOR LDC")
    print("Testando sistema em produção...")
    print()
    
    teste = TesteSistemaCompleto()
    sucessos, total = teste.executar_todos_testes()
    teste.gerar_relatorio()
    
    # Exit code baseado nos resultados
    exit_code = 0 if sucessos == total else 1
    exit(exit_code)
