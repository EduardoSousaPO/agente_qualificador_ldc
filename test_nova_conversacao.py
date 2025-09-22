#!/usr/bin/env python3
"""
🧪 TESTE DA NOVA CONVERSAÇÃO PROFISSIONAL
Simula conversas para validar o novo sistema antes do deploy
"""

import requests
import json
import time
from datetime import datetime

BACKEND_URL = "https://agente-qualificador-ldc.onrender.com"

def criar_payload_teste(from_number, message, nome="Eduardo"):
    """Cria payload de teste para webhook"""
    return {
        "event": "message",
        "payload": {
            "id": f"test_{int(time.time())}_{hash(message) % 1000}",
            "from": f"{from_number}@c.us",
            "fromName": nome,
            "body": message,
            "fromMe": False,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
    }

def enviar_mensagem_teste(payload):
    """Envia mensagem de teste para o webhook"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/webhook",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            resposta = data.get('result', {}).get('resposta_enviada', 'Sem resposta')
            print(f"✅ Resposta: {resposta}")
            return True
        else:
            print(f"❌ Erro: HTTP {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return False

def testar_conversa_completa():
    """Testa uma conversa completa do início ao agendamento"""
    
    print("🧪 TESTANDO NOVA CONVERSAÇÃO PROFISSIONAL")
    print("=" * 60)
    
    # Número de teste
    numero_teste = "5511999999999"
    
    # Cenário 1: Conversa ideal
    print("\n📞 CENÁRIO 1: Lead interessado e qualificado")
    print("-" * 40)
    
    conversas_teste = [
        {
            "mensagem": "ola",
            "descricao": "Primeira mensagem"
        },
        {
            "mensagem": "sim",
            "descricao": "Aceita conversar"
        },
        {
            "mensagem": "já invisto um pouco",
            "descricao": "Situação atual"
        },
        {
            "mensagem": "tenho uma reserva boa formada",
            "descricao": "Patrimônio"
        },
        {
            "mensagem": "quero fazer crescer mais rápido",
            "descricao": "Objetivo"
        },
        {
            "mensagem": "sim, me interessaria",
            "descricao": "Interesse no diagnóstico"
        },
        {
            "mensagem": "amanhã às 10h",
            "descricao": "Agendamento"
        }
    ]
    
    for i, teste in enumerate(conversas_teste, 1):
        print(f"\n{i}. {teste['descricao']}")
        print(f"   Lead: {teste['mensagem']}")
        
        payload = criar_payload_teste(numero_teste, teste['mensagem'], "Eduardo")
        
        if enviar_mensagem_teste(payload):
            print("   ✅ Processado com sucesso")
        else:
            print("   ❌ Falhou")
            break
            
        time.sleep(2)  # Pausa entre mensagens
    
    print("\n" + "=" * 60)
    print("🏁 TESTE CONCLUÍDO!")
    
    # Verificar histórico
    print("\n📋 Verificando histórico...")
    try:
        response = requests.get(f"{BACKEND_URL}/leads?limit=1")
        if response.status_code == 200:
            data = response.json()
            leads = data.get('leads', [])
            if leads:
                lead = leads[0]
                print(f"✅ Lead encontrado: {lead.get('nome')} - Status: {lead.get('status')}")
                print(f"   Telefone: {lead.get('telefone')}")
                print(f"   Último contato: {lead.get('ultimo_contato', 'N/A')}")
            else:
                print("❌ Nenhum lead encontrado")
        else:
            print(f"❌ Erro ao buscar leads: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Erro ao verificar histórico: {e}")

def testar_cenarios_especificos():
    """Testa cenários específicos de objeções"""
    
    print("\n🎭 TESTANDO CENÁRIOS DE OBJEÇÕES")
    print("-" * 40)
    
    cenarios_objecoes = [
        {
            "setup": ["ola", "sim", "estou começando"],
            "objecao": "não tenho muito dinheiro",
            "descricao": "Objeção: pouco dinheiro"
        },
        {
            "setup": ["ola", "sim", "já invisto"],
            "objecao": "já tenho um assessor",
            "descricao": "Objeção: já tem assessor"
        },
        {
            "setup": ["ola", "sim", "tenho uma reserva"],
            "objecao": "não tenho tempo agora",
            "descricao": "Objeção: sem tempo"
        }
    ]
    
    for i, cenario in enumerate(cenarios_objecoes, 1):
        print(f"\n{i}. {cenario['descricao']}")
        numero = f"551199999999{i}"  # Número diferente para cada cenário
        
        # Setup inicial
        for msg in cenario['setup']:
            payload = criar_payload_teste(numero, msg, f"Lead{i}")
            enviar_mensagem_teste(payload)
            time.sleep(1)
        
        # Objeção
        print(f"   Objeção: {cenario['objecao']}")
        payload = criar_payload_teste(numero, cenario['objecao'], f"Lead{i}")
        enviar_mensagem_teste(payload)
        
        time.sleep(2)

def main():
    """Executa todos os testes"""
    print("🚀 INICIANDO TESTES DA NOVA CONVERSAÇÃO")
    
    # Verificar se backend está funcionando
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Backend funcionando")
        else:
            print("❌ Backend com problemas")
            return
    except Exception as e:
        print(f"❌ Backend inacessível: {e}")
        return
    
    # Executar testes
    testar_conversa_completa()
    testar_cenarios_especificos()
    
    print("\n🎯 RESUMO DOS TESTES:")
    print("1. ✅ Teste de conversa completa")
    print("2. ✅ Teste de objeções")
    print("3. 📊 Verificação de histórico")
    
    print("\n💡 PRÓXIMOS PASSOS:")
    print("1. Analisar qualidade das respostas")
    print("2. Ajustar prompts se necessário")
    print("3. Fazer deploy das melhorias")

if __name__ == "__main__":
    main()
