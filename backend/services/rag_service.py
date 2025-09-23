import os
import structlog
from dotenv import load_dotenv
from supabase.client import Client, create_client
from openai import OpenAI

load_dotenv()

log = structlog.get_logger()

class RAGService:
    def __init__(self):
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            openai_api_key = os.getenv("OPENAI_API_KEY")

            if not all([supabase_url, supabase_key, openai_api_key]):
                log.error("RAGService: Variáveis de ambiente do Supabase ou OpenAI não encontradas.")
                raise ValueError("Variáveis de ambiente do Supabase ou OpenAI não encontradas.")

            self.supabase: Client = create_client(supabase_url, supabase_key)
            self.openai = OpenAI(api_key=openai_api_key)
            log.info("RAGService inicializado com sucesso.")
        except Exception as e:
            log.error("Falha ao inicializar o RAGService", error=str(e))
            raise

    def _criar_embedding(self, texto: str) -> list[float]:
        """Cria um embedding para um dado texto usando a OpenAI."""
        try:
            response = self.openai.embeddings.create(
                model="text-embedding-3-small",
                input=texto
            )
            return response.data[0].embedding
        except Exception as e:
            log.error("Erro ao criar embedding com a OpenAI", error=str(e))
            return []

    def consultar_base_conhecimento(self, query: str, match_threshold: float = 0.78, match_count: int = 5) -> str:
        """
        Consulta a base de conhecimento para encontrar os documentos mais relevantes para a query.
        Retorna uma string formatada com o conteúdo dos documentos encontrados.
        """
        log.info("Consultando base de conhecimento RAG", query=query)
        try:
            query_embedding = self._criar_embedding(query)
            if not query_embedding:
                log.warning("Não foi possível gerar embedding para a query. RAG não será utilizado.", query=query)
                return ""

            response = self.supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": match_threshold,
                    "match_count": match_count,
                },
            ).execute()

            if response.data:
                contexto = "\n".join([item["content"] for item in response.data])
                log.info("Contexto RAG encontrado", num_documentos=len(response.data))
                return contexto
            else:
                log.info("Nenhum contexto RAG relevante encontrado para a query.", query=query)
                return ""

        except Exception as e:
            log.error("Erro ao consultar a base de conhecimento RAG", error=str(e), query=query)
            return ""
