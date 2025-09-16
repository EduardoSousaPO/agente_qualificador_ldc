#!/usr/bin/env python3
"""
Teste de conectividade com WAHA após correções
"""
import requests
import json
import sys

def test_waha_connection():
    """Testa a conectividade com o WAHA"""
    print("🧪 Testando conectividade com WAHA...")
    
    try:
        # Testar endpoint de teste do WhatsApp
        response = requests.post(
            "https://agente-qualificador-ldc.onrender.com/test-whatsapp",
            timeout=30
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ RESULTADO DO TESTE:")
            print(f"   Status: {data.get('status')}")
            
            waha_conn = data.get('waha_connection', {})
            print(f"   WAHA Success: {waha_conn.get('success')}")
            print(f"   WAHA Response completa: {json.dumps(waha_conn, indent=4)}")
            
            if waha_conn.get('success'):
                print("   🎉 CONEXÃO COM WAHA: SUCESSO!")
                if 'sessions_data' in waha_conn:
                    sessions = waha_conn['sessions_data']
                    print(f"   📱 Sessões encontradas: {len(sessions) if isinstance(sessions, list) else 'N/A'}")
            else:
                print("   ❌ CONEXÃO COM WAHA: FALHOU")
                print(f"   Erro: {waha_conn.get('error', 'Desconhecido')}")
                print(f"   Status Code: {waha_conn.get('status_code', 'N/A')}")
                
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Detalhes: {json.dumps(error_data, indent=2)}")
            except:
                print(f"   Resposta: {response.text}")
                
    except requests.exceptions.Timeout:
        print("⏰ Timeout na requisição (30s)")
    except requests.exceptions.ConnectionError:
        print("🔌 Erro de conexão com o servidor")
    except Exception as e:
        print(f"💥 Erro inesperado: {str(e)}")

def test_health_check():
    """Testa o health check da aplicação"""
    print("\n🏥 Testando health check...")
    
    try:
        response = requests.get(
            "https://agente-qualificador-ldc.onrender.com/health",
            timeout=10
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ HEALTH CHECK: OK")
            print(f"   Status: {data.get('status')}")
            print(f"   Timestamp: {data.get('timestamp')}")
        else:
            print(f"❌ HEALTH CHECK: FALHOU ({response.status_code})")
            
    except Exception as e:
        print(f"💥 Erro no health check: {str(e)}")

if __name__ == "__main__":
    print("🚀 Iniciando testes de conectividade...")
    print("=" * 50)
    
    test_health_check()
    test_waha_connection()
    
    print("\n" + "=" * 50)
    print("✅ Testes concluídos!")
