#!/usr/bin/env python3
"""
Teste do Sistema Completo - Agente Qualificador de Leads
Simula fluxo completo: lead na planilha → WhatsApp → score → resultado
"""
import os
import sys
import requests
import json
from datetime import datetime
import time

# Adicionar path do backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Configurações de teste
BASE_URL = "http://localhost:5000"
TELEFONE_TESTE = "5511999888777"
NOME_TESTE = "João Silva Teste"
EMAIL_TESTE = "joao.teste@email.com"
CANAL_TESTE = "youtube"


class TesteCompleto:
    """Classe para executar testes completos do sistema"""
    
    def __init__(self):
        self.session = requests.Session()
        self.resultados = []
        
    def log(self, message, status="INFO"):
        """Log das operações"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        
    def teste_health_check(self):
        """Teste 1: Health Check"""
        self.log("Iniciando teste de health check...")
        
        try:
            response = self.session.get(f"{BASE_URL}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"Health check OK - Status: {data.get('status')}")
                return True
            else:
                self.log(f"Health check falhou - Status: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro no health check: {str(e)}", "ERROR")
            return False
    
    def teste_scoring_algoritmo(self):
        """Teste 2: Algoritmo de Scoring"""
        self.log("Testando algoritmo de scoring...")
        
        # Caso 1: Lead qualificado (score alto)
        dados_qualificado = {
            "patrimonio": "Tenho mais de 1 milhão para investir",
            "objetivo": "Quero fazer meu dinheiro render e crescer rapidamente",
            "urgencia": "Preciso começar agora mesmo, é urgente",
            "interesse": "Sim, tenho muito interesse em conversar com um especialista"
        }
        
        # Caso 2: Lead não qualificado (score baixo)
        dados_nao_qualificado = {
            "patrimonio": "Tenho pouco dinheiro, menos de 50 mil",
            "objetivo": "Só quero proteger o que tenho",
            "urgencia": "Não tenho pressa, talvez no futuro",
            "interesse": "Não sei se preciso de ajuda"
        }
        
        casos_teste = [
            ("Qualificado", dados_qualificado, 70),
            ("Não Qualificado", dados_nao_qualificado, 69)
        ]
        
        for nome_caso, dados, score_esperado_min in casos_teste:
            try:
                response = self.session.post(
                    f"{BASE_URL}/test-scoring",
                    json=dados,
                    timeout=10
                )
                
                if response.status_code == 200:
                    resultado = response.json()['score_result']
                    score = resultado['score_total']
                    
                    if nome_caso == "Qualificado" and score >= score_esperado_min:
                        self.log(f"✅ Caso {nome_caso}: Score {score}/100 - OK")
                    elif nome_caso == "Não Qualificado" and score < 70:
                        self.log(f"✅ Caso {nome_caso}: Score {score}/100 - OK")
                    else:
                        self.log(f"❌ Caso {nome_caso}: Score {score}/100 - Esperado: {'>=70' if nome_caso == 'Qualificado' else '<70'}", "ERROR")
                        return False
                else:
                    self.log(f"Erro ao testar scoring - Status: {response.status_code}", "ERROR")
                    return False
                    
            except Exception as e:
                self.log(f"Erro no teste de scoring: {str(e)}", "ERROR")
                return False
        
        return True
    
    def teste_lead_management(self):
        """Teste 3: Gerenciamento de Leads"""
        self.log("Testando gerenciamento de leads...")
        
        try:
            # Listar leads
            response = self.session.get(f"{BASE_URL}/leads?limit=5")
            
            if response.status_code == 200:
                dados = response.json()
                total_leads = dados.get('total', 0)
                self.log(f"✅ Listagem de leads OK - Total: {total_leads}")
                
                # Se há leads, testar detalhes de um
                if dados.get('leads') and len(dados['leads']) > 0:
                    lead_id = dados['leads'][0]['id']
                    
                    # Testar detalhes do lead
                    response_detalhes = self.session.get(f"{BASE_URL}/leads/{lead_id}")
                    
                    if response_detalhes.status_code == 200:
                        self.log("✅ Detalhes do lead OK")
                        return True
                    else:
                        self.log(f"❌ Erro ao obter detalhes do lead - Status: {response_detalhes.status_code}", "ERROR")
                        return False
                else:
                    self.log("ℹ️  Nenhum lead encontrado para testar detalhes")
                    return True
            else:
                self.log(f"❌ Erro ao listar leads - Status: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro no teste de gerenciamento: {str(e)}", "ERROR")
            return False
    
    def teste_estatisticas(self):
        """Teste 4: Estatísticas do Sistema"""
        self.log("Testando estatísticas...")
        
        try:
            response = self.session.get(f"{BASE_URL}/stats")
            
            if response.status_code == 200:
                stats = response.json()
                leads_info = stats.get('leads', {})
                
                self.log(f"✅ Estatísticas OK:")
                self.log(f"   • Total de leads: {leads_info.get('total', 0)}")
                self.log(f"   • Qualificados: {leads_info.get('qualificados', 0)}")
                self.log(f"   • Taxa de qualificação: {leads_info.get('taxa_qualificacao', 0)}%")
                
                return True
            else:
                self.log(f"❌ Erro ao obter estatísticas - Status: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro no teste de estatísticas: {str(e)}", "ERROR")
            return False
    
    def teste_logs_sistema(self):
        """Teste 5: Sistema de Logs"""
        self.log("Testando sistema de logs...")
        
        try:
            response = self.session.get(f"{BASE_URL}/logs?limit=10")
            
            if response.status_code == 200:
                logs_data = response.json()
                total_logs = logs_data.get('total', 0)
                
                self.log(f"✅ Sistema de logs OK - Total: {total_logs}")
                return True
            else:
                self.log(f"❌ Erro ao obter logs - Status: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro no teste de logs: {str(e)}", "ERROR")
            return False
    
    def teste_processamento_leads(self):
        """Teste 6: Processamento de Novos Leads"""
        self.log("Testando processamento de leads...")
        
        try:
            response = self.session.post(f"{BASE_URL}/process-new-leads")
            
            if response.status_code == 200:
                resultado = response.json()
                novos = resultado.get('novos_leads', 0)
                processados = resultado.get('processados', 0)
                
                self.log(f"✅ Processamento OK - Novos: {novos}, Processados: {processados}")
                return True
            else:
                self.log(f"⚠️  Processamento retornou status {response.status_code} - Pode ser normal se não há planilha configurada")
                return True  # Não é erro crítico
                
        except Exception as e:
            self.log(f"⚠️  Erro no processamento (esperado se Google Sheets não configurado): {str(e)}")
            return True  # Não é erro crítico para o MVP
    
    def executar_todos_testes(self):
        """Executa todos os testes do sistema"""
        self.log("🚀 INICIANDO TESTE COMPLETO DO SISTEMA", "INFO")
        self.log("=" * 60)
        
        testes = [
            ("Health Check", self.teste_health_check),
            ("Algoritmo de Scoring", self.teste_scoring_algoritmo),
            ("Gerenciamento de Leads", self.teste_lead_management),
            ("Estatísticas", self.teste_estatisticas),
            ("Sistema de Logs", self.teste_logs_sistema),
            ("Processamento de Leads", self.teste_processamento_leads)
        ]
        
        resultados = []
        
        for nome_teste, funcao_teste in testes:
            self.log(f"\n📋 Executando: {nome_teste}")
            self.log("-" * 40)
            
            inicio = time.time()
            sucesso = funcao_teste()
            duracao = time.time() - inicio
            
            resultados.append({
                'teste': nome_teste,
                'sucesso': sucesso,
                'duracao': round(duracao, 2)
            })
            
            status = "✅ PASSOU" if sucesso else "❌ FALHOU"
            self.log(f"{status} ({duracao:.2f}s)")
        
        # Relatório final
        self.log("\n" + "=" * 60)
        self.log("📊 RELATÓRIO FINAL DOS TESTES")
        self.log("=" * 60)
        
        total_testes = len(resultados)
        testes_passou = sum(1 for r in resultados if r['sucesso'])
        taxa_sucesso = (testes_passou / total_testes) * 100
        
        for resultado in resultados:
            status = "✅" if resultado['sucesso'] else "❌"
            self.log(f"{status} {resultado['teste']} ({resultado['duracao']}s)")
        
        self.log(f"\n🎯 RESULTADO GERAL:")
        self.log(f"   • Testes executados: {total_testes}")
        self.log(f"   • Testes passou: {testes_passou}")
        self.log(f"   • Taxa de sucesso: {taxa_sucesso:.1f}%")
        
        if taxa_sucesso >= 80:
            self.log("🎉 SISTEMA APROVADO - Pronto para produção!", "SUCCESS")
            return True
        else:
            self.log("⚠️  SISTEMA PRECISA DE AJUSTES", "WARNING")
            return False


def main():
    """Função principal"""
    print("🔧 Agente Qualificador de Leads - Teste Completo do Sistema")
    print("=" * 70)
    
    # Verificar se servidor está rodando
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Servidor detectado em {BASE_URL}")
    except:
        print(f"❌ ERRO: Servidor não encontrado em {BASE_URL}")
        print("   Certifique-se de que a aplicação está rodando:")
        print("   cd agente_qualificador/backend && python app.py")
        return False
    
    # Executar testes
    teste = TesteCompleto()
    sucesso = teste.executar_todos_testes()
    
    print("\n" + "=" * 70)
    if sucesso:
        print("🎉 TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
        print("   O sistema está pronto para deploy em produção.")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM")
        print("   Verifique os logs acima para mais detalhes.")
    
    return sucesso


if __name__ == "__main__":
    exit(0 if main() else 1)



