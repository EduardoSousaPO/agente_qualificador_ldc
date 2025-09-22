#!/usr/bin/env python3
"""
🧪 SCRIPT DE TESTE - INTEGRAÇÃO N8N PARALELA
Testa a integração entre N8N e o backend Flask sem afetar o sistema principal
"""

import requests
import json
import time
from datetime import datetime

# URLs de teste
BACKEND_URL = "https://agente-qualificador-ldc.onrender.com"
N8N_WEBHOOK_URL = "https://agenteia-n8n.dqlhjk.easypanel.host/webhook/waha-webhook-processor"

def test_backend_endpoints():
    """Testa se os novos endpoints estão funcionando"""
    print("🔧 Testando endpoints do backend...")
    
    # Teste 1: Status da integração
    try:
        response = requests.get(f"{BACKEND_URL}/n8n-integration-status")
        print(f"✅ Status integração: {response.status_code}")
        if response.status_code == 200:
            print(f"   📊 Dados: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Erro status integração: {e}")
    
    # Teste 2: Health check
    try:
        response = requests.get(f"{BACKEND_URL}/health")
        print(f"✅ Health check: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   🏥 Status: {health_data.get('status')}")
    except Exception as e:
        print(f"❌ Erro health check: {e}")

def test_webhook_endpoint():
    """Testa o endpoint de webhook de teste"""
    print("\n🧪 Testando webhook de teste...")
    
    # Payload de teste simulando uma mensagem do N8N
    test_payload = {
        "status": "processed",
        "messageId": "test_123456",
        "phone": "5511999999999",
        "processedBy": "n8n",
        "timestamp": datetime.now().isoformat(),
        "test_data": {
            "message": "Teste de integração N8N",
            "contactName": "Usuario Teste"
        }
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/webhook-n8n-test",
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"✅ Webhook teste: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   📦 Resposta: {json.dumps(result, indent=2)}")
        else:
            print(f"   ❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro webhook teste: {e}")

def test_n8n_webhook():
    """Testa o webhook do N8N (se disponível)"""
    print("\n🔗 Testando webhook N8N...")
    
    # Payload simulando uma mensagem WAHA
    waha_payload = {
        "event": "message",
        "payload": {
            "id": "test_msg_789",
            "from": "5511999999999@c.us",
            "fromName": "Usuario Teste N8N",
            "body": "Olá, esta é uma mensagem de teste para o N8N",
            "fromMe": False,
            "timestamp": int(time.time() * 1000)
        }
    }
    
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=waha_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"✅ N8N webhook: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   📦 Resposta N8N: {json.dumps(result, indent=2)}")
        else:
            print(f"   ⚠️  Resposta: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout no N8N webhook (normal se credenciais não configuradas)")
    except Exception as e:
        print(f"❌ Erro N8N webhook: {e}")

def main():
    """Executa todos os testes"""
    print("🚀 INICIANDO TESTES DE INTEGRAÇÃO N8N PARALELA")
    print("=" * 60)
    
    test_backend_endpoints()
    test_webhook_endpoint()
    test_n8n_webhook()
    
    print("\n" + "=" * 60)
    print("✅ TESTES CONCLUÍDOS!")
    print("\n📋 PRÓXIMOS PASSOS:")
    print("1. Configurar credenciais Supabase no N8N")
    print("2. Ativar workflows no N8N")
    print("3. Testar com mensagens reais")
    print("4. Migrar webhook WAHA quando validado")

if __name__ == "__main__":
    main()
