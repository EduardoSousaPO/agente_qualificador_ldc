#!/usr/bin/env python3
"""
Exemplo de Uso das Melhorias do Sistema de IA
Demonstra como utilizar o novo sistema de conversação melhorado
"""
import sys
import os

# Adicionar o diretório backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.models.conversation_models import (
    Estado, Acao, PatrimonioRange, Objetivo, Urgencia, Interesse,
    ContextoConversa, RespostaIA, SessionState, PromptContext
)
from backend.services.prompt_service import PromptService
from backend.services.validation_service import ValidationService
from backend.services.slot_filling_service import SlotFillingService
from backend.services.guardrails_service import GuardrailsService
from backend.services.intention_classifier import IntentionClassifier


def exemplo_fluxo_completo():
    """Demonstra um fluxo completo de conversação"""
    
    print("🤖 EXEMPLO: Sistema de IA Melhorado - Agente LDC")
    print("=" * 60)
    
    # Inicializar serviços
    prompt_service = PromptService()
    validation_service = ValidationService()
    slot_service = SlotFillingService()
    guardrails_service = GuardrailsService()
    intention_classifier = IntentionClassifier()
    
    # Simular sessão de conversa
    session_state = SessionState(
        lead_id="João",
        session_id="exemplo_session",
        estado_atual=Estado.INICIO
    )
    
    print(f"📋 Estado inicial: {session_state.estado_atual.value}")
    print(f"📊 Slots preenchidos: {session_state.slots_preenchidos()}")
    print(f"📝 Slots faltantes: {session_state.slots_faltantes()}")
    print()
    
    # Exemplo 1: Processar mensagem de interesse
    print("1️⃣ EXEMPLO: Processamento de mensagem de interesse")
    print("-" * 50)
    
    mensagem_lead = "Sim, quero saber mais sobre investimentos!"
    
    # Classificar intenção
    intencao = intention_classifier.classificar_intencao_rapida(mensagem_lead)
    print(f"🎯 Intenção classificada: {intencao.intencao}")
    print(f"😊 Sentimento: {intencao.sentimento}")
    print(f"⚡ Urgência: {intencao.urgencia}/10")
    print(f"📈 Score qualificação: {intencao.qualificacao_score}/100")
    print()
    
    # Extrair slots
    session_state.contexto = slot_service.extrair_slots_da_mensagem(
        mensagem_lead, session_state.estado_atual, session_state.contexto
    )
    
    print(f"📦 Slots após extração: {session_state.slots_preenchidos()}")
    print()
    
    # Exemplo 2: Gerar prompt estruturado
    print("2️⃣ EXEMPLO: Geração de prompt estruturado")
    print("-" * 50)
    
    context = PromptContext(
        estado_atual=Estado.SITUACAO,
        slots_preenchidos=session_state.slots_preenchidos(),
        slots_faltantes=session_state.slots_faltantes(),
        nome_lead="João",
        canal="whatsapp",
        ultima_mensagem_lead=mensagem_lead,
        historico_compacto=[]
    )
    
    user_prompt = prompt_service.build_user_prompt(context)
    print("📝 Prompt gerado (primeiras 200 chars):")
    print(user_prompt[:200] + "...")
    print()
    
    # Exemplo 3: Simular resposta da IA
    print("3️⃣ EXEMPLO: Validação de resposta da IA")
    print("-" * 50)
    
    # Simular resposta JSON da IA
    resposta_json = """
    {
        "mensagem": "Oi João! Que bom que você tem interesse! Você já investe hoje ou está começando agora? 1) já invisto 2) estou começando",
        "acao": "continuar",
        "proximo_estado": "patrimonio",
        "contexto": {"ja_investiu": null},
        "score_parcial": 60
    }
    """
    
    # Validar resposta
    validation_result = validation_service.validar_resposta_ia(
        resposta_json, Estado.SITUACAO, "João"
    )
    
    print(f"✅ Resposta válida: {validation_result.valida}")
    if validation_result.resposta_corrigida:
        resposta_ia = validation_result.resposta_corrigida
        print(f"💬 Mensagem: {resposta_ia.mensagem}")
        print(f"🎯 Ação: {resposta_ia.acao}")
        print(f"📍 Próximo estado: {resposta_ia.proximo_estado}")
        print(f"📊 Score parcial: {resposta_ia.score_parcial}")
    print()
    
    # Exemplo 4: Aplicar guardrails
    print("4️⃣ EXEMPLO: Aplicação de guardrails")
    print("-" * 50)
    
    if validation_result.resposta_corrigida:
        passou, erros, corrigida = guardrails_service.aplicar_guardrails(
            validation_result.resposta_corrigida, session_state, "João"
        )
        
        print(f"🛡️ Passou nos guardrails: {passou}")
        if erros:
            print(f"⚠️ Erros encontrados: {len(erros)}")
            for erro in erros[:3]:  # Mostrar apenas os primeiros 3
                print(f"   - {erro}")
        
        if corrigida:
            print(f"🔧 Resposta corrigida: {corrigida.mensagem[:100]}...")
    print()
    
    # Exemplo 5: Simular progressão da conversa
    print("5️⃣ EXEMPLO: Progressão da conversa")
    print("-" * 50)
    
    # Simular respostas do lead para diferentes estados
    respostas_simuladas = [
        ("já invisto", Estado.SITUACAO),
        ("tenho uns 200 mil", Estado.PATRIMONIO),
        ("quero que cresça bastante", Estado.OBJETIVO),
        ("sim, quero agendar!", Estado.INTERESSE)
    ]
    
    for mensagem, estado_esperado in respostas_simuladas:
        print(f"👤 Lead: {mensagem}")
        
        # Extrair slots
        novo_contexto = slot_service.extrair_slots_da_mensagem(
            mensagem, estado_esperado, session_state.contexto
        )
        
        # Atualizar sessão
        session_state.contexto = novo_contexto
        session_state.estado_atual = estado_esperado
        session_state.mensagem_count += 1
        
        # Calcular score
        score = slot_service.calcular_score_parcial(novo_contexto)
        
        print(f"📊 Score atual: {score}/100")
        print(f"📦 Slots: {list(session_state.slots_preenchidos().keys())}")
        print(f"✅ Pode agendar: {session_state.pode_agendar()}")
        print()
    
    # Exemplo 6: Relatório de qualidade
    print("6️⃣ EXEMPLO: Relatório de qualidade da conversa")
    print("-" * 50)
    
    qualidade = guardrails_service.validar_qualidade_conversa(session_state)
    
    print(f"🏆 Score geral: {qualidade['score_geral']}/100")
    print("✅ Pontos positivos:")
    for ponto in qualidade['pontos_positivos']:
        print(f"   + {ponto}")
    
    if qualidade['pontos_negativos']:
        print("⚠️ Pontos negativos:")
        for ponto in qualidade['pontos_negativos']:
            print(f"   - {ponto}")
    
    print("💡 Recomendações:")
    for rec in qualidade['recomendacoes']:
        print(f"   • {rec}")
    print()
    
    print("🎉 EXEMPLO CONCLUÍDO!")
    print("=" * 60)


def exemplo_casos_especiais():
    """Demonstra casos especiais e edge cases"""
    
    print("\n🔧 CASOS ESPECIAIS E EDGE CASES")
    print("=" * 60)
    
    intention_classifier = IntentionClassifier()
    slot_service = SlotFillingService()
    
    # Casos de intenção
    casos_intencao = [
        "Não quero nada agora",
        "Pode marcar para amanhã de manhã?",
        "Não entendi nada do que você falou",
        "Já tenho consultor, obrigado",
        "Me manda mais informações por email"
    ]
    
    print("🎯 CLASSIFICAÇÃO DE INTENÇÕES:")
    print("-" * 40)
    
    for caso in casos_intencao:
        intencao = intention_classifier.classificar_intencao_rapida(caso)
        print(f"📝 '{caso}'")
        print(f"   → {intencao.intencao} | {intencao.sentimento} | Score: {intencao.qualificacao_score}")
        print()
    
    # Casos de slot filling
    casos_slots = [
        ("tenho 50 mil na poupança", Estado.PATRIMONIO),
        ("quero ficar rico", Estado.OBJETIVO),
        ("preciso urgente", Estado.URGENCIA),
        ("não tenho certeza", Estado.INTERESSE)
    ]
    
    print("📦 EXTRAÇÃO DE SLOTS:")
    print("-" * 40)
    
    for mensagem, estado in casos_slots:
        contexto = ContextoConversa()
        contexto_atualizado = slot_service.extrair_slots_da_mensagem(
            mensagem, estado, contexto
        )
        
        print(f"📝 '{mensagem}' ({estado.value})")
        
        # Mostrar mudanças
        mudancas = []
        for attr in ['patrimonio_range', 'objetivo', 'urgencia', 'interesse']:
            valor = getattr(contexto_atualizado, attr)
            if valor:
                mudancas.append(f"{attr}: {valor.value if hasattr(valor, 'value') else valor}")
        
        if mudancas:
            print(f"   → {', '.join(mudancas)}")
        else:
            print("   → Nenhum slot extraído")
        print()


if __name__ == "__main__":
    try:
        exemplo_fluxo_completo()
        exemplo_casos_especiais()
    except Exception as e:
        print(f"❌ Erro ao executar exemplo: {e}")
        import traceback
        traceback.print_exc()
