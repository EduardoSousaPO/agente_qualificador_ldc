#!/usr/bin/env python3
"""
🎯 TESTE REAL DA NOVA CONVERSAÇÃO
Simula uma conversa real para validar melhorias
"""

import requests
import json
import time
from datetime import datetime

def teste_conversa_real():
    """Testa conversa real com o novo sistema"""
    
    print("🎯 TESTE REAL DA NOVA CONVERSAÇÃO PROFISSIONAL")
    print("=" * 60)
    
    url = "https://agente-qualificador-ldc.onrender.com/webhook"
    
    # Simular mensagem real
    payload = {
        "event": "message",
        "payload": {
            "id": f"real_test_{int(time.time())}",
            "from": "5511987654321@c.us", 
            "fromName": "Eduardo",
            "body": "oi, tenho interesse em investimentos",
            "fromMe": False,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
    }
    
    print("📱 Enviando mensagem:")
    print(f"   De: Eduardo (5511987654321)")
    print(f"   Mensagem: '{payload['payload']['body']}'")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('result', {})
            
            print(f"\n✅ RESPOSTA RECEBIDA:")
            print(f"   Status: {response.status_code}")
            print(f"   Ação: {result.get('acao', 'N/A')}")
            print(f"   Novo Estado: {result.get('novo_estado', 'N/A')}")
            
            resposta = result.get('resposta_enviada', 'Sem resposta')
            print(f"\n💬 MENSAGEM DO AGENTE:")
            print(f"   \"{resposta}\"")
            
            # Análise da qualidade
            print(f"\n📊 ANÁLISE DA QUALIDADE:")
            
            qualidade_score = 0
            
            # Critérios de qualidade
            if len(resposta) > 50:
                qualidade_score += 20
                print("   ✅ Tamanho adequado (+20)")
            else:
                print("   ❌ Muito curta (-20)")
            
            if "Eduardo" in resposta:
                qualidade_score += 20
                print("   ✅ Usa nome do lead (+20)")
            else:
                print("   ❌ Não usa nome do lead (-20)")
            
            if any(palavra in resposta.lower() for palavra in ["rafael", "consultor", "ldc capital"]):
                qualidade_score += 20
                print("   ✅ Apresentação profissional (+20)")
            else:
                print("   ❌ Sem apresentação profissional (-20)")
            
            if "?" in resposta:
                qualidade_score += 15
                print("   ✅ Faz pergunta (+15)")
            else:
                print("   ❌ Não faz pergunta (-15)")
            
            if any(num in resposta for num in ["1)", "2)", "3)"]):
                qualidade_score += 15
                print("   ✅ Oferece opções (+15)")
            else:
                print("   ❌ Não oferece opções (-15)")
            
            if not any(palavra in resposta.lower() for palavra in ["robô", "chatbot", "sistema", "próxima etapa"]):
                qualidade_score += 10
                print("   ✅ Linguagem natural (+10)")
            else:
                print("   ❌ Linguagem robótica (-10)")
            
            print(f"\n🎯 SCORE FINAL: {qualidade_score}/100")
            
            if qualidade_score >= 80:
                print("   🏆 EXCELENTE! Conversação profissional")
            elif qualidade_score >= 60:
                print("   👍 BOM! Algumas melhorias possíveis")
            elif qualidade_score >= 40:
                print("   ⚠️  REGULAR. Precisa de ajustes")
            else:
                print("   ❌ RUIM. Sistema não está funcionando")
                
        else:
            print(f"❌ ERRO: HTTP {response.status_code}")
            print(f"   Resposta: {response.text}")
            
    except Exception as e:
        print(f"❌ ERRO NA REQUISIÇÃO: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 TESTE CONCLUÍDO!")

if __name__ == "__main__":
    teste_conversa_real()
