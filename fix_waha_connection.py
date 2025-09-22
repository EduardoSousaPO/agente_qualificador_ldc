#!/usr/bin/env python3
"""
🔧 CORREÇÃO DEFINITIVA DA CONEXÃO WAHA
Encontra e configura a URL correta do WAHA
"""

import requests
import json

# Possíveis variações de URL do WAHA
WAHA_VARIATIONS = [
    "https://agenteia-waha.dqhjk.easypanel.host",
    "https://agenteia-waha.dqlhjk.easypanel.host", 
    "http://agenteia-waha.dqhjk.easypanel.host",
    "https://agenteia-waha.dqhjk.easypanel.host:3000",
    "http://agenteia-waha.dqhjk.easypanel.host:3000",
    "https://waha.agenteia.dqhjk.easypanel.host",
    "http://waha.agenteia.dqhjk.easypanel.host"
]

API_KEY = "x3TnwERN5YpdSE6hGLJEWJPvPu3vJMjFuQ8ZfOPdulKzlu4pZfGciwYv75uwdBeHPcedm"

def test_waha_api(base_url):
    """Testa se uma URL é realmente do WAHA"""
    headers = {"X-API-KEY": API_KEY}
    
    try:
        # Teste 1: Endpoint de sessões
        response = requests.get(f"{base_url}/api/sessions", headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # Verificar se a resposta tem formato de WAHA
            if isinstance(data, list):
                print(f"✅ WAHA encontrado: {base_url}")
                print(f"   📱 Sessões: {len(data)}")
                
                for session in data:
                    name = session.get('name', 'unknown')
                    status = session.get('status', 'unknown')
                    print(f"   - {name}: {status}")
                
                return True
        elif response.status_code == 401:
            print(f"🔑 API Key inválida para: {base_url}")
        else:
            print(f"⚠️  HTTP {response.status_code}: {base_url}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Conexão recusada: {base_url}")
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout: {base_url}")
    except Exception as e:
        print(f"❌ Erro: {base_url} - {str(e)[:50]}")
    
    return False

def configure_webhook(waha_url):
    """Configura webhook no WAHA"""
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    webhook_config = {
        "url": "https://agente-qualificador-ldc.onrender.com/webhook",
        "events": ["message"],
        "session": "default"
    }
    
    try:
        response = requests.post(
            f"{waha_url}/api/webhooks",
            headers=headers,
            json=webhook_config,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Webhook configurado: {response.json()}")
            return True
        else:
            print(f"❌ Erro webhook: HTTP {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao configurar webhook: {e}")
        return False

def main():
    """Encontra e configura WAHA"""
    print("🔍 PROCURANDO WAHA FUNCIONANDO...")
    print("=" * 50)
    
    working_url = None
    
    for url in WAHA_VARIATIONS:
        if test_waha_api(url):
            working_url = url
            break
    
    if working_url:
        print(f"\n✅ WAHA ENCONTRADO: {working_url}")
        
        # Verificar webhooks atuais
        try:
            response = requests.get(f"{working_url}/api/webhooks", 
                                  headers={"X-API-KEY": API_KEY}, timeout=5)
            if response.status_code == 200:
                webhooks = response.json()
                print(f"\n📋 Webhooks atuais: {len(webhooks)}")
                for webhook in webhooks:
                    print(f"   - {webhook.get('url', 'N/A')}")
                
                # Configurar webhook se não existir
                webhook_exists = any('agente-qualificador-ldc' in w.get('url', '') for w in webhooks)
                
                if not webhook_exists:
                    print("\n🔧 Configurando webhook...")
                    configure_webhook(working_url)
                else:
                    print("\n✅ Webhook já configurado!")
                    
        except Exception as e:
            print(f"❌ Erro ao verificar webhooks: {e}")
        
        print(f"\n📝 VARIÁVEL DE AMBIENTE:")
        print(f"WAHA_BASE_URL={working_url}")
        
    else:
        print("\n❌ NENHUM WAHA ENCONTRADO")
        print("\n🔧 SOLUÇÕES:")
        print("1. Verificar se WAHA está rodando no EasyPanel")
        print("2. Verificar se API key está correta")
        print("3. Verificar se domínio mudou")

if __name__ == "__main__":
    main()
