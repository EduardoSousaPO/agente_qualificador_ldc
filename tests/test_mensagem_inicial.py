#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste específico para a nova mensagem inicial
"""

import sys
import os
import requests
import json
from datetime import datetime

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def teste_mensagem_inicial_melhorada():
    """Testa se a nova mensagem inicial está sendo enviada corretamente"""
    
    webhook_url = "https://agente-qualificador-ldc.onrender.com/webhook"
    
    # Criar payload de teste com novo número
    telefone_teste = f"5511{datetime.now().strftime('%H%M%S')}999@c.us"
    
    payload = {
        "event": "message",
        "payload": {
            "from": telefone_teste,
            "body": "oi",
            "fromMe": False,
            "fromName": "Teste Mensagem",
            "contact": {"name": "Teste Mensagem"},
            "pushName": "Teste Mensagem",
            "id": f"test_msg_{datetime.now().timestamp()}",
            "timestamp": int(datetime.now().timestamp())
        }
    }
    
    print("🧪 TESTE: Nova Mensagem Inicial")
    print("=" * 40)
    print(f"📱 Telefone de teste: {telefone_teste}")
    print(f"💬 Mensagem enviada: 'oi'")
    print()
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"📊 Status da resposta: {response.status_code}")
        
        if response.status_code == 200:
            try:
                resposta_json = response.json()
                print("✅ Resposta recebida:")
                print(json.dumps(resposta_json, indent=2, ensure_ascii=False))
                
                # Verificar se a resposta contém os elementos esperados
                if 'result' in resposta_json and 'resposta_enviada' in resposta_json['result']:
                    mensagem_enviada = resposta_json['result']['resposta_enviada']
                    
                    # Verificar se contém os elementos da nova mensagem
                    elementos_esperados = [
                        "agente comercial da LDC Capital",
                        "quero te ajudar",
                        "entender suas demandas e objetivos",
                        "melhorar seus investimentos"
                    ]
                    
                    elementos_encontrados = []
                    for elemento in elementos_esperados:
                        if elemento.lower() in mensagem_enviada.lower():
                            elementos_encontrados.append(elemento)
                    
                    print(f"\n🔍 ANÁLISE DA MENSAGEM:")
                    print(f"📝 Mensagem enviada: {mensagem_enviada}")
                    print(f"\n✅ Elementos encontrados ({len(elementos_encontrados)}/{len(elementos_esperados)}):")
                    for elemento in elementos_encontrados:
                        print(f"   ✓ {elemento}")
                    
                    if len(elementos_encontrados) == len(elementos_esperados):
                        print(f"\n🎉 SUCESSO! Nova mensagem inicial está funcionando perfeitamente!")
                        return True
                    else:
                        elementos_faltando = set(elementos_esperados) - set(elementos_encontrados)
                        print(f"\n⚠️ ATENÇÃO! Elementos faltando:")
                        for elemento in elementos_faltando:
                            print(f"   ✗ {elemento}")
                        return False
                else:
                    print("❌ Formato de resposta inesperado")
                    return False
                    
            except json.JSONDecodeError:
                print(f"❌ Erro ao decodificar JSON: {response.text}")
                return False
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            print(f"Resposta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 TESTE DA NOVA MENSAGEM INICIAL")
    print("Verificando se a mensagem comercial melhorada está sendo enviada...")
    print()
    
    sucesso = teste_mensagem_inicial_melhorada()
    
    if sucesso:
        print("\n🎯 RESULTADO: Mensagem inicial melhorada está funcionando!")
        exit(0)
    else:
        print("\n❌ RESULTADO: Mensagem inicial precisa de ajustes")
        exit(1)



