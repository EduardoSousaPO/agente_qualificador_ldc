#!/usr/bin/env python3
"""
🛡️ TESTE SEGURO - APENAS PARA EDUARDO
Script de teste que usa apenas o número autorizado do Eduardo
"""

import requests
import json
import time
from datetime import datetime

# ⚠️ IMPORTANTE: Apenas o número do Eduardo está autorizado
NUMERO_EDUARDO = "5511987654321"  # Substitua pelo seu número real
BACKEND_URL = "https://agente-qualificador-ldc.onrender.com"

def criar_payload_eduardo(mensagem: str, nome: str = "Eduardo"):
    """Cria payload de teste APENAS para o Eduardo"""
    return {
        "event": "message",
        "payload": {
            "id": f"eduardo_test_{int(time.time())}",
            "from": f"{NUMERO_EDUARDO}@c.us",
            "fromName": nome,
            "body": mensagem,
            "fromMe": False,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
    }

def testar_conversa_eduardo():
    """Testa conversa apenas com o número do Eduardo"""
    
    print("🛡️ TESTE SEGURO - APENAS EDUARDO")
    print("=" * 50)
    print(f"📱 Número autorizado: {NUMERO_EDUARDO}")
    print("⚠️  Apenas este número receberá mensagens")
    print()
    
    # Sequência de teste
    mensagens_teste = [
        "oi, tenho interesse em investimentos",
        "já invisto um pouco",
        "tenho uma reserva boa",
        "quero fazer crescer",
        "sim, me interessaria"
    ]
    
    for i, mensagem in enumerate(mensagens_teste, 1):
        print(f"\n{i}. Enviando: '{mensagem}'")
        
        payload = criar_payload_eduardo(mensagem)
        
        try:
            response = requests.post(
                f"{BACKEND_URL}/webhook",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', {})
                resposta = result.get('resposta_enviada', 'Sem resposta')
                
                print(f"   ✅ Resposta: {resposta[:100]}...")
            else:
                print(f"   ❌ Erro: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        time.sleep(2)  # Pausa entre mensagens
    
    print("\n" + "=" * 50)
    print("✅ Teste concluído com segurança!")

def verificar_numeros_autorizados():
    """Verifica quais números estão autorizados"""
    
    print("\n🔍 VERIFICANDO NÚMEROS AUTORIZADOS...")
    
    try:
        response = requests.get(f"{BACKEND_URL}/numeros-autorizados")
        
        if response.status_code == 200:
            data = response.json()
            numeros = data.get('numeros_autorizados', [])
            
            print(f"✅ {len(numeros)} números autorizados:")
            for numero in numeros:
                print(f"   📱 {numero}")
        else:
            print(f"❌ Erro ao verificar: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

def main():
    """Executa teste seguro"""
    
    print("🛡️ TESTE SEGURO DO SISTEMA AGENTE QUALIFICADOR")
    print("Proteção ativa: Apenas números autorizados recebem mensagens")
    print("=" * 60)
    
    # Verificar números autorizados
    verificar_numeros_autorizados()
    
    # Confirmar se quer prosseguir
    print(f"\n⚠️  ATENÇÃO: O teste enviará mensagens para {NUMERO_EDUARDO}")
    resposta = input("Deseja prosseguir? (s/n): ")
    
    if resposta.lower() in ['s', 'sim', 'y', 'yes']:
        testar_conversa_eduardo()
    else:
        print("❌ Teste cancelado pelo usuário")

if __name__ == "__main__":
    main()
