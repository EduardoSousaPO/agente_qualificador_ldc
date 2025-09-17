"""
Modelos de dados para o Agente Qualificador de Leads
Integração com Supabase via Python
"""
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import json
from supabase import create_client, Client
from dataclasses import dataclass, asdict


class DatabaseConnection:
    """Gerenciador de conexão com Supabase"""
    
    def __init__(self):
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórios")
        
        self.client: Client = create_client(self.url, self.key)
    
    def get_client(self) -> Client:
        return self.client


@dataclass
class Lead:
    """Modelo do Lead"""
    nome: str
    telefone: str
    email: Optional[str] = None
    canal: str = 'youtube'  # youtube, newsletter, ebook, meta_ads
    status: str = 'novo'
    score: int = 0
    processado: bool = False
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para inserção no banco"""
        data = asdict(self)
        # Remove campos None e de controle
        data = {k: v for k, v in data.items() if v is not None and k not in ['id', 'created_at', 'updated_at']}
        return data


@dataclass 
class Session:
    """Modelo da Sessão de Conversa"""
    lead_id: str
    estado: str = 'inicio'
    contexto: Dict[str, Any] = None
    ativa: bool = True
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.contexto is None:
            self.contexto = {}
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data = {k: v for k, v in data.items() if v is not None and k not in ['id', 'created_at', 'updated_at']}
        return data


@dataclass
class Message:
    """Modelo da Mensagem"""
    session_id: str
    lead_id: str
    conteudo: str
    tipo: str  # 'recebida' ou 'enviada'
    metadata: Dict[str, Any] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data = {k: v for k, v in data.items() if v is not None and k not in ['id', 'created_at']}
        return data


@dataclass
class Qualificacao:
    """Modelo da Qualificação"""
    lead_id: str
    session_id: str
    patrimonio_resposta: Optional[str] = None
    patrimonio_pontos: int = 0
    objetivo_resposta: Optional[str] = None
    objetivo_pontos: int = 0
    urgencia_resposta: Optional[str] = None
    urgencia_pontos: int = 0
    interesse_resposta: Optional[str] = None
    interesse_pontos: int = 0
    resultado: Optional[str] = None
    observacoes: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @property
    def score_total(self) -> int:
        """Calcula score total automaticamente"""
        return self.patrimonio_pontos + self.objetivo_pontos + self.urgencia_pontos + self.interesse_pontos
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data = {k: v for k, v in data.items() if v is not None and k not in ['id', 'created_at']}
        return data


@dataclass
class SystemLog:
    """Modelo do Log do Sistema"""
    nivel: str  # INFO, WARNING, ERROR, DEBUG
    evento: str
    detalhes: Dict[str, Any] = None
    lead_id: Optional[str] = None
    session_id: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.detalhes is None:
            self.detalhes = {}
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data = {k: v for k, v in data.items() if v is not None and k not in ['id', 'created_at']}
        return data


class LeadRepository:
    """Repository para operações com Leads"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db.get_client()
    
    def create_lead(self, lead: Lead) -> Optional[Dict[str, Any]]:
        """Cria um novo lead"""
        try:
            result = self.db.table('leads').insert(lead.to_dict()).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao criar lead: {str(e)}", {'lead_data': lead.to_dict()})
            return None
    
    def get_lead_by_phone(self, telefone: str) -> Optional[Dict[str, Any]]:
        """Busca lead por telefone"""
        try:
            result = self.db.table('leads').select('*').eq('telefone', telefone).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao buscar lead por telefone: {str(e)}", {'telefone': telefone})
            return None
    
    def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """Atualiza um lead"""
        try:
            result = self.db.table('leads').update(updates).eq('id', lead_id).execute()
            return len(result.data) > 0
        except Exception as e:
            self.log_error(f"Erro ao atualizar lead: {str(e)}", {'lead_id': lead_id, 'updates': updates})
            return False
    
    def get_unprocessed_leads(self) -> List[Dict[str, Any]]:
        """Busca leads não processados"""
        try:
            result = self.db.table('leads').select('*').eq('processado', False).execute()
            return result.data or []
        except Exception as e:
            self.log_error(f"Erro ao buscar leads não processados: {str(e)}")
            return []
    
    def log_error(self, evento: str, detalhes: Dict[str, Any] = None):
        """Log de erro interno"""
        try:
            log = SystemLog(
                nivel='ERROR',
                evento=evento,
                detalhes=detalhes or {}
            )
            self.db.table('system_logs').insert(log.to_dict()).execute()
        except:
            pass  # Evita loop infinito de erros


class SessionRepository:
    """Repository para operações com Sessions"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db.get_client()
    
    def create_session(self, session: Session) -> Optional[Dict[str, Any]]:
        """Cria uma nova sessão"""
        try:
            result = self.db.table('sessions').insert(session.to_dict()).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao criar sessão: {str(e)}", {'session_data': session.to_dict()})
            return None
    
    def get_active_session(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Busca sessão ativa do lead"""
        try:
            result = self.db.table('sessions').select('*').eq('lead_id', lead_id).eq('ativa', True).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao buscar sessão ativa: {str(e)}", {'lead_id': lead_id})
            return None
    
    def get_recent_session(self, lead_id: str, seconds: int = 30) -> Optional[Dict[str, Any]]:
        """Busca sessão criada recentemente para o lead (nos últimos X segundos)"""
        try:
            from datetime import datetime, timedelta
            
            # Calcular timestamp limite (30 segundos atrás)
            time_limit = datetime.now() - timedelta(seconds=seconds)
            time_limit_str = time_limit.isoformat()
            
            result = self.db.table('sessions').select('*').eq('lead_id', lead_id).gte('created_at', time_limit_str).order('created_at', desc=True).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao buscar sessão recente: {str(e)}", {'lead_id': lead_id})
            return None
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Busca uma sessão pelo ID"""
        try:
            result = self.db.table('sessions').select('*').eq('id', session_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao buscar sessão: {str(e)}", {'session_id': session_id})
            return None

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Atualiza uma sessão"""
        try:
            result = self.db.table('sessions').update(updates).eq('id', session_id).execute()
            return len(result.data) > 0
        except Exception as e:
            self.log_error(f"Erro ao atualizar sessão: {str(e)}", {'session_id': session_id, 'updates': updates})
            return False
    
    def log_error(self, evento: str, detalhes: Dict[str, Any] = None):
        """Log de erro interno"""
        try:
            log = SystemLog(
                nivel='ERROR',
                evento=evento,
                detalhes=detalhes or {}
            )
            self.db.table('system_logs').insert(log.to_dict()).execute()
        except:
            pass


class MessageRepository:
    """Repository para operações com Messages"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db.get_client()
    
    def create_message(self, message: Message) -> Optional[Dict[str, Any]]:
        """Cria uma nova mensagem"""
        try:
            result = self.db.table('messages').insert(message.to_dict()).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao criar mensagem: {str(e)}", {'message_data': message.to_dict()})
            return None
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Busca uma sessão pelo ID"""
        try:
            result = self.db.table('sessions').select('*').eq('id', session_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao buscar sessão: {str(e)}", {'session_id': session_id})
            return None

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Busca mensagens de uma sessão"""
        try:
            result = self.db.table('messages').select('*').eq('session_id', session_id).order('created_at').execute()
            return result.data or []
        except Exception as e:
            self.log_error(f"Erro ao buscar mensagens da sessão: {str(e)}", {'session_id': session_id})
            return []
    
    def get_messages_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Busca mensagens por sessão (alias para get_session_messages)"""
        return self.get_session_messages(session_id)
    
    def log_error(self, evento: str, detalhes: Dict[str, Any] = None):
        """Log de erro interno"""
        try:
            log = SystemLog(
                nivel='ERROR',
                evento=evento,
                detalhes=detalhes or {}
            )
            self.db.table('system_logs').insert(log.to_dict()).execute()
        except:
            pass


class QualificacaoRepository:
    """Repository para operações com Qualificações"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db.get_client()
    
    def create_qualificacao(self, qualificacao: Qualificacao) -> Optional[Dict[str, Any]]:
        """Cria uma nova qualificação"""
        try:
            result = self.db.table('qualificacoes').insert(qualificacao.to_dict()).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao criar qualificação: {str(e)}", {'qualificacao_data': qualificacao.to_dict()})
            return None
    
    def update_qualificacao(self, qualificacao_id: str, updates: Dict[str, Any]) -> bool:
        """Atualiza uma qualificação"""
        try:
            result = self.db.table('qualificacoes').update(updates).eq('id', qualificacao_id).execute()
            return len(result.data) > 0
        except Exception as e:
            self.log_error(f"Erro ao atualizar qualificação: {str(e)}", {'qualificacao_id': qualificacao_id, 'updates': updates})
            return False
    
    def get_lead_qualificacao(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Busca qualificação de um lead"""
        try:
            result = self.db.table('qualificacoes').select('*').eq('lead_id', lead_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.log_error(f"Erro ao buscar qualificação do lead: {str(e)}", {'lead_id': lead_id})
            return None
    
    def log_error(self, evento: str, detalhes: Dict[str, Any] = None):
        """Log de erro interno"""
        try:
            log = SystemLog(
                nivel='ERROR',
                evento=evento,
                detalhes=detalhes or {}
            )
            self.db.table('system_logs').insert(log.to_dict()).execute()
        except:
            pass


class SystemLogRepository:
    """Repository para operações com System Logs"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db.get_client()
    
    def create_log(self, log: SystemLog) -> Optional[Dict[str, Any]]:
        """Cria um novo log"""
        try:
            result = self.db.table('system_logs').insert(log.to_dict()).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None  # Evita loop infinito
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Busca logs recentes"""
        try:
            result = self.db.table('system_logs').select('*').order('created_at', desc=True).limit(limit).execute()
            return result.data or []
        except Exception:
            return []
    
    def get_error_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Busca logs de erro"""
        try:
            result = self.db.table('system_logs').select('*').eq('nivel', 'ERROR').order('created_at', desc=True).limit(limit).execute()
            return result.data or []
        except Exception:
            return []


class QualificacaoRepository:
    """Repository para operações com Qualificações"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db.get_client()
    
    def create_qualificacao(self, qualificacao: Qualificacao) -> Optional[Dict[str, Any]]:
        """Cria uma nova qualificação"""
        try:
            result = self.db.table('qualificacoes').insert(qualificacao.to_dict()).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            return None
    
    def get_by_lead_id(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Busca qualificação por lead_id"""
        try:
            result = self.db.table('qualificacoes').select('*').eq('lead_id', lead_id).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None


class SystemLogRepository:
    """Repository para logs do sistema"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db.get_client()
    
    def create_log(self, log: SystemLog) -> bool:
        """Cria um log"""
        try:
            self.db.table('system_logs').insert(log.to_dict()).execute()
            return True
        except Exception:
            return False


