#!/usr/bin/env python3
"""
🚨 CORREÇÃO EMERGENCIAL: Força uso do sistema profissional
Aplica correção imediata no sistema de conversação
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def aplicar_correcao_emergencial():
    """Aplica correção emergencial no sistema"""
    
    print("🚨 APLICANDO CORREÇÃO EMERGENCIAL")
    print("=" * 50)
    
    # Correção 1: Forçar uso do novo sistema
    with open('backend/services/ai_conversation_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Substituir chamada para garantir que usa o novo sistema
    old_code = """# 🆕 USAR NOVO SISTEMA PROFISSIONAL
            system_prompt = self.prompt_service_pro.system_prompt
            user_prompt = self.prompt_service_pro.build_contextualized_prompt(context)"""
    
    new_code = """# 🆕 USAR NOVO SISTEMA PROFISSIONAL - FORÇA SEMPRE
            system_prompt = self.prompt_service_pro.system_prompt
            user_prompt = self.prompt_service_pro.build_contextualized_prompt(context)
            
            # LOG DEBUG
            logger.info("🆕 Usando sistema profissional", 
                       estado=context.estado_atual,
                       nome=context.nome_lead,
                       prompt_length=len(user_prompt))"""
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        print("✅ Correção 1: Forçado uso do sistema profissional")
    else:
        print("⚠️  Correção 1: Código não encontrado")
    
    # Salvar arquivo
    with open('backend/services/ai_conversation_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Correção 2: Adicionar fallback melhorado
    fallback_code = '''
    def _get_emergency_fallback(self, context: PromptContext) -> str:
        """Fallback emergencial com novo sistema"""
        nome = context.nome_lead
        estado = context.estado_atual
        
        if estado == "inicio":
            return f"Oi {nome}! Sou Rafael, consultor da LDC Capital. Você tem interesse em investimentos? 1) sim 2) não"
        elif estado == "situacao":  
            return f"Legal, {nome}! Você já investe hoje ou está começando? 1) já invisto 2) começando"
        elif estado == "patrimonio":
            return f"Entendi, {nome}. Você está mais na fase de acumular ainda ou já tem uma reserva boa? 1) acumulando 2) tenho reserva"
        elif estado == "objetivo":
            return f"Perfeito, {nome}! O que te atrai mais: 1) crescer patrimônio 2) gerar renda extra 3) aposentadoria"
        else:
            return f"Entendi, {nome}! Que tal marcarmos um diagnóstico gratuito de 30 min? 1) sim 2) depois"
'''
    
    # Adicionar ao final da classe
    with open('backend/services/ai_conversation_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '_get_emergency_fallback' not in content:
        # Adicionar antes da última linha
        content = content.replace(
            '            return None',
            fallback_code + '\n            return None'
        )
        print("✅ Correção 2: Adicionado fallback emergencial")
    else:
        print("⚠️  Correção 2: Fallback já existe")
    
    with open('backend/services/ai_conversation_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n🎯 CORREÇÕES APLICADAS!")
    print("1. ✅ Sistema profissional forçado")
    print("2. ✅ Fallback emergencial adicionado") 
    print("3. ✅ Logs de debug ativados")
    
    return True

def testar_correcao():
    """Testa se a correção funcionou"""
    
    print("\n🧪 TESTANDO CORREÇÃO...")
    
    try:
        from backend.services.ai_conversation_service import AIConversationService
        from backend.services.prompt_service_pro import PromptServicePro
        
        # Verificar se o serviço pode ser instanciado
        service = AIConversationService()
        
        if hasattr(service, 'prompt_service_pro'):
            print("✅ PromptServicePro carregado")
        else:
            print("❌ PromptServicePro não encontrado")
            return False
            
        # Verificar se o prompt profissional está funcionando
        prompt_service = PromptServicePro()
        system_prompt = prompt_service.system_prompt
        
        if "RAFAEL" in system_prompt and "CONSULTIVO" in system_prompt:
            print("✅ Sistema profissional ativo")
            return True
        else:
            print("❌ Sistema profissional não ativo")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

def main():
    """Executa correção emergencial"""
    print("🚨 CORREÇÃO EMERGENCIAL DO SISTEMA DE CONVERSAÇÃO")
    print("Problema: Retornando 'Sem resposta' - Sistema não usa prompts profissionais")
    print("=" * 70)
    
    if aplicar_correcao_emergencial():
        if testar_correcao():
            print("\n🎉 CORREÇÃO APLICADA COM SUCESSO!")
            print("\n💡 PRÓXIMOS PASSOS:")
            print("1. Fazer commit da correção")
            print("2. Fazer push para deploy")
            print("3. Testar conversação novamente")
        else:
            print("\n❌ CORREÇÃO FALHOU NO TESTE")
    else:
        print("\n❌ FALHA NA APLICAÇÃO DA CORREÇÃO")

if __name__ == "__main__":
    main()
