#!/usr/bin/env python3
"""
🔧 TESTE DE CONECTIVIDADE WAHA
Testa diferentes URLs e variações do WAHA
"""

import requests
import time

# URLs possíveis do WAHA
WAHA_URLS = [
    "https://agenteia-waha.dqlhjk.easypanel.host",
    "https://agenteia-waha.dqhjk.easypanel.host", 
    "http://agenteia-waha.dqlhjk.easypanel.host",
    "https://212.85.22.148:3000",
    "http://212.85.22.148:3000"
]

API_KEY = "x3TnwERN5YpdSE6hGLJEWJPvPu3vJMjFuQ8ZfOPdulKzlu4pZfGciwYv75uwdBeHPcedm"

def test_waha_url(base_url):
    """Testa uma URL do WAHA"""
    print(f"\n🔍 Testando: {base_url}")
    
    headers = {"X-API-KEY": API_KEY}
    endpoints = ["/api/sessions", "/api/webhooks", "/health", "/"]
    
    for endpoint in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                print(f"  ✅ {endpoint}: HTTP {response.status_code}")
                if endpoint == "/api/sessions":
                    try:
                        data = response.json()
                        print(f"      📱 Sessões: {len(data) if isinstance(data, list) else 'N/A'}")
                    except:
                        pass
                return base_url  # URL funcionando
            else:
                print(f"  ⚠️  {endpoint}: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"  ⏰ {endpoint}: Timeout")
        except requests.exceptions.ConnectionError:
            print(f"  ❌ {endpoint}: Conexão recusada")
        except Exception as e:
            print(f"  ❌ {endpoint}: {str(e)[:50]}")
    
    return None

def main():
    """Testa todas as URLs"""
    print("🔍 TESTANDO CONECTIVIDADE WAHA")
    print("=" * 50)
    
    working_url = None
    
    for url in WAHA_URLS:
        result = test_waha_url(url)
        if result:
            working_url = result
            break
    
    print("\n" + "=" * 50)
    
    if working_url:
        print(f"✅ URL FUNCIONANDO: {working_url}")
        print(f"\n📋 PRÓXIMOS PASSOS:")
        print(f"1. Atualizar WAHA_BASE_URL para: {working_url}")
        print(f"2. Configurar webhook no WAHA")
        print(f"3. Testar envio de mensagens")
    else:
        print("❌ NENHUMA URL DO WAHA FUNCIONANDO")
        print("\n🔧 SOLUÇÕES:")
        print("1. Verificar se WAHA está rodando")
        print("2. Verificar configuração de firewall/proxy")
        print("3. Verificar API key")
        print("4. Contatar suporte do EasyPanel")

if __name__ == "__main__":
    main()
