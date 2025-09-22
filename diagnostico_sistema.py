#!/usr/bin/env python3
"""
🔍 DIAGNÓSTICO COMPLETO DO SISTEMA
Identifica problemas no agente qualificador de leads
"""

import requests
import json
import sys
from datetime import datetime

def print_status(title, status, details=""):
    """Imprime status formatado"""
    icon = "✅" if status else "❌"
    print(f"{icon} {title}")
    if details:
        print(f"   {details}")

def test_backend_health():
    """Testa saúde do backend"""
    print("🔍 VERIFICANDO BACKEND...")
    
    try:
        response = requests.get("https://agente-qualificador-ldc.onrender.com/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_status("Backend Flask", True, f"Status: {data.get('status')}")
            
            services = data.get('services', {})
            for service, status in services.items():
                print_status(f"  - {service.capitalize()}", status == "connected" or status == "ready", status)
        else:
            print_status("Backend Flask", False, f"HTTP {response.status_code}")
    except Exception as e:
        print_status("Backend Flask", False, str(e))

def test_waha_connection():
    """Testa conexão com WAHA"""
    print("\n📱 VERIFICANDO WAHA...")
    
    headers = {
        "X-API-KEY": "x3TnwERN5YpdSE6hGLJEWJPvPu3vJMjFuQ8ZfOPdulKzlu4pZfGciwYv75uwdBeHPcedm"
    }
    
    # Teste 1: Sessions
    try:
        response = requests.get("https://agenteia-waha.dqhjk.easypanel.host/api/sessions", 
                               headers=headers, timeout=10)
        if response.status_code == 200:
            sessions = response.json()
            print_status("WAHA API", True, f"Sessões encontradas: {len(sessions)}")
            
            for session in sessions:
                name = session.get('name', 'unknown')
                status = session.get('status', 'unknown')
                print_status(f"  - Sessão {name}", status == "WORKING", status)
        else:
            print_status("WAHA API", False, f"HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print_status("WAHA API", False, str(e))
    
    # Teste 2: Webhooks
    try:
        response = requests.get("https://agenteia-waha.dqhjk.easypanel.host/api/webhooks", 
                               headers=headers, timeout=10)
        if response.status_code == 200:
            webhooks = response.json()
            print_status("WAHA Webhooks", len(webhooks) > 0, f"Webhooks configurados: {len(webhooks)}")
            
            for webhook in webhooks:
                url = webhook.get('url', '')
                events = webhook.get('events', [])
                print_status(f"  - Webhook", 'agente-qualificador-ldc' in url, 
                           f"URL: {url}, Events: {events}")
        else:
            print_status("WAHA Webhooks", False, f"HTTP {response.status_code}")
    except Exception as e:
        print_status("WAHA Webhooks", False, str(e))

def test_webhook_endpoint():
    """Testa se webhook está recebendo"""
    print("\n🔗 TESTANDO WEBHOOK...")
    
    test_payload = {
        "event": "message", 
        "payload": {
            "id": "test_diagnostic_123",
            "from": "5511999999999@c.us",
            "fromName": "Teste Diagnóstico",
            "body": "Teste do sistema diagnóstico",
            "fromMe": False,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
    }
    
    try:
        response = requests.post("https://agente-qualificador-ldc.onrender.com/webhook",
                               json=test_payload,
                               headers={"Content-Type": "application/json"},
                               timeout=15)
        
        print_status("Webhook Response", response.status_code == 200, 
                    f"HTTP {response.status_code}: {response.text[:100]}")
    except Exception as e:
        print_status("Webhook Response", False, str(e))

def test_database_connection():
    """Testa conexão com database"""
    print("\n🗄️ VERIFICANDO DATABASE...")
    
    try:
        response = requests.get("https://agente-qualificador-ldc.onrender.com/leads?limit=1", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_status("Database Supabase", True, f"Leads encontrados: {data.get('total', 0)}")
        else:
            print_status("Database Supabase", False, f"HTTP {response.status_code}")
    except Exception as e:
        print_status("Database Supabase", False, str(e))

def check_recent_logs():
    """Verifica logs recentes"""
    print("\n📋 VERIFICANDO LOGS RECENTES...")
    
    try:
        response = requests.get("https://agente-qualificador-ldc.onrender.com/logs?limit=5", timeout=10)
        if response.status_code == 200:
            data = response.json()
            logs = data.get('logs', [])
            print_status("Logs System", True, f"Logs recentes: {len(logs)}")
            
            for log in logs[-3:]:  # Últimos 3 logs
                nivel = log.get('nivel', 'INFO')
                evento = log.get('evento', 'unknown')
                created = log.get('created_at', '')[:19] if log.get('created_at') else ''
                print(f"   📝 {created} [{nivel}] {evento}")
        else:
            print_status("Logs System", False, f"HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print_status("Logs System", False, str(e))

def main():
    """Executa diagnóstico completo"""
    print("🔍 DIAGNÓSTICO COMPLETO DO SISTEMA AGENTE QUALIFICADOR")
    print("=" * 60)
    
    test_backend_health()
    test_waha_connection()
    test_webhook_endpoint()
    test_database_connection()
    check_recent_logs()
    
    print("\n" + "=" * 60)
    print("📊 DIAGNÓSTICO CONCLUÍDO!")
    print("\n💡 PRÓXIMOS PASSOS:")
    print("1. Se WAHA não está conectado: verificar configuração WhatsApp")
    print("2. Se webhook não responde: verificar configuração webhook no WAHA")
    print("3. Se database falha: verificar credenciais Supabase")
    print("4. Verificar logs de erro para mais detalhes")

if __name__ == "__main__":
    main()
