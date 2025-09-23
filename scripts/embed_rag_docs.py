"""
Script para Invocação da Edge Function de Ingestão de Documentos RAG
- Lê arquivos da pasta RAG.
- Envia o conteúdo para a Supabase Edge Function 'embed-rag'.
"""
import os
import argparse
import json
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any
import structlog

# Configuração de logging
logger = structlog.get_logger()

# Carregar variáveis de ambiente do arquivo .env na raiz do projeto
load_dotenv()

class RAGInvoker:
    def __init__(self):
        self.supabase_project_id = os.getenv('SUPABASE_PROJECT_ID', 'wsoxukpeyzmpcngjugie')
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not all([self.supabase_project_id, self.supabase_service_key]):
            raise ValueError("Variáveis de ambiente do Supabase são obrigatórias.")
            
        self.edge_function_url = f"https://{self.supabase_project_id}.supabase.co/functions/v1/embed-rag"
        self.headers = {
            "Authorization": f"Bearer {self.supabase_service_key}",
            "Content-Type": "application/json"
        }

    def _read_documents_from_folder(self, folder_path: str) -> List[Dict[str, Any]]:
        """Lê todos os arquivos .md da pasta especificada."""
        documents = []
        log = logger.bind(folder_path=folder_path)
        log.info("Iniciando leitura de documentos locais")
        
        for filename in os.listdir(folder_path):
            if filename.endswith(".md"):
                file_path = os.path.join(folder_path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        documents.append({
                            "content": content,
                            "metadata": {"source": filename}
                        })
                        log.info("Documento lido com sucesso", filename=filename)
                except Exception as e:
                    log.error("Erro ao ler documento", filename=filename, error=str(e))
        
        log.info("Leitura de documentos finalizada", total_docs=len(documents))
        return documents

    def invoke_embedding_function(self, documents: List[Dict[str, Any]]):
        """Invoca a Supabase Edge Function para processar os documentos."""
        log = logger.bind(url=self.edge_function_url)
        log.info("Invocando a Edge Function 'embed-rag'...")
        
        payload = {"documents": documents}
        
        try:
            response = requests.post(self.edge_function_url, headers=self.headers, json=payload, timeout=300)
            response.raise_for_status()
            
            log.info("Edge Function executada com sucesso", response=response.json())
        except requests.exceptions.HTTPError as e:
            log.error("Erro HTTP ao invocar a Edge Function", status_code=e.response.status_code, response_text=e.response.text)
            raise
        except Exception as e:
            log.error("Erro ao invocar a Edge Function", error=str(e))
            raise

    def process_and_invoke(self):
        """Orquestra o processo completo de invocação."""
        logger.info("Iniciando processo de invocação RAG...")
        
        # Constrói o caminho para a pasta RAG relativo à localização do script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        rag_folder_path = os.path.join(base_dir, '..', 'RAG')

        # 1. Ler documentos locais
        documents = self._read_documents_from_folder(rag_folder_path)
        if not documents:
            logger.warning("Nenhum documento encontrado na pasta RAG. Processo encerrado.")
            return
            
        # 2. Invocar a função na nuvem
        self.invoke_embedding_function(documents)
        
        logger.info("Processo de invocação RAG finalizado com sucesso!")

def main():
    invoker = RAGInvoker()
    invoker.process_and_invoke()

if __name__ == "__main__":
    main()
