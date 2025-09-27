"""
Serviço de Monitoramento e Métricas do Sistema
"""

import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Deque
import structlog

logger = structlog.get_logger(__name__)

class MetricsService:
    """Serviço centralizado de coleta e exposição de métricas"""
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.retention_seconds = retention_hours * 3600
        
        # Métricas de mensagens
        self.message_metrics: Deque[Dict[str, Any]] = deque()
        self.message_counters = defaultdict(int)
        
        # Métricas de qualificação
        self.qualification_metrics: Deque[Dict[str, Any]] = deque()
        self.qualification_counters = defaultdict(int)
        
        # Métricas de agendamentos
        self.meeting_metrics: Deque[Dict[str, Any]] = deque()
        self.meeting_counters = defaultdict(int)
        
        # Lock para thread safety
        self._lock = threading.RLock()
        
        # Iniciar limpeza periódica
        self._start_cleanup_thread()
    
    def record_message_sent(self, telefone: str, success: bool, details: Optional[str] = None):
        """Registra envio de mensagem"""
        with self._lock:
            timestamp = datetime.now(timezone.utc)
            
            metric = {
                'timestamp': timestamp,
                'type': 'message_sent',
                'telefone': telefone,
                'success': success,
                'details': details
            }
            
            self.message_metrics.append(metric)
            self.message_counters['total_sent'] += 1
            
            if success:
                self.message_counters['successful_sent'] += 1
            else:
                self.message_counters['failed_sent'] += 1
            
            logger.info(
                "Mensagem registrada nas métricas",
                telefone=telefone,
                success=success,
                total_sent=self.message_counters['total_sent']
            )
    
    def record_message_deduped(self, telefone: str, reason: str = "duplicate"):
        """Registra mensagem dedupada"""
        with self._lock:
            timestamp = datetime.now(timezone.utc)
            
            metric = {
                'timestamp': timestamp,
                'type': 'message_deduped',
                'telefone': telefone,
                'reason': reason
            }
            
            self.message_metrics.append(metric)
            self.message_counters['deduped'] += 1
            
            logger.info(
                "Mensagem dedupada registrada",
                telefone=telefone,
                reason=reason,
                total_deduped=self.message_counters['deduped']
            )
    
    def record_qualification_completed(self, lead_id: str, score: int, qualified: bool):
        """Registra qualificação completada"""
        with self._lock:
            timestamp = datetime.now(timezone.utc)
            
            metric = {
                'timestamp': timestamp,
                'type': 'qualification_completed',
                'lead_id': lead_id,
                'score': score,
                'qualified': qualified
            }
            
            self.qualification_metrics.append(metric)
            self.qualification_counters['total_qualifications'] += 1
            
            if qualified:
                self.qualification_counters['qualified'] += 1
            else:
                self.qualification_counters['not_qualified'] += 1
            
            logger.info(
                "Qualificação registrada nas métricas",
                lead_id=lead_id,
                score=score,
                qualified=qualified,
                total_qualifications=self.qualification_counters['total_qualifications']
            )
    
    def record_meeting_scheduled(self, lead_id: str, slot: str, success: bool):
        """Registra agendamento de reunião"""
        with self._lock:
            timestamp = datetime.now(timezone.utc)
            
            metric = {
                'timestamp': timestamp,
                'type': 'meeting_scheduled',
                'lead_id': lead_id,
                'slot': slot,
                'success': success
            }
            
            self.meeting_metrics.append(metric)
            self.meeting_counters['total_attempts'] += 1
            
            if success:
                self.meeting_counters['successful_schedules'] += 1
            else:
                self.meeting_counters['failed_schedules'] += 1
            
            logger.info(
                "Agendamento registrado nas métricas",
                lead_id=lead_id,
                slot=slot,
                success=success,
                total_attempts=self.meeting_counters['total_attempts']
            )
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorna resumo das métricas"""
        with self._lock:
            self._cleanup_old_metrics()
            
            now = datetime.now(timezone.utc)
            one_hour_ago = now - timedelta(hours=1)
            
            # Métricas da última hora
            recent_messages = [m for m in self.message_metrics if m['timestamp'] > one_hour_ago]
            recent_qualifications = [m for m in self.qualification_metrics if m['timestamp'] > one_hour_ago]
            recent_meetings = [m for m in self.meeting_metrics if m['timestamp'] > one_hour_ago]
            
            return {
                'timestamp': now.isoformat(),
                'retention_hours': self.retention_hours,
                'totals': {
                    'messages': dict(self.message_counters),
                    'qualifications': dict(self.qualification_counters),
                    'meetings': dict(self.meeting_counters)
                },
                'last_hour': {
                    'messages': {
                        'total': len(recent_messages),
                        'successful': len([m for m in recent_messages if m.get('success')]),
                        'failed': len([m for m in recent_messages if not m.get('success')]),
                        'deduped': len([m for m in recent_messages if m['type'] == 'message_deduped'])
                    },
                    'qualifications': {
                        'total': len(recent_qualifications),
                        'qualified': len([m for m in recent_qualifications if m.get('qualified')]),
                        'not_qualified': len([m for m in recent_qualifications if not m.get('qualified')])
                    },
                    'meetings': {
                        'total': len(recent_meetings),
                        'successful': len([m for m in recent_meetings if m.get('success')]),
                        'failed': len([m for m in recent_meetings if not m.get('success')])
                    }
                },
                'rates': {
                    'message_success_rate': self._calculate_success_rate(
                        self.message_counters['successful_sent'],
                        self.message_counters['total_sent']
                    ),
                    'qualification_rate': self._calculate_success_rate(
                        self.qualification_counters['qualified'],
                        self.qualification_counters['total_qualifications']
                    ),
                    'meeting_success_rate': self._calculate_success_rate(
                        self.meeting_counters['successful_schedules'],
                        self.meeting_counters['total_attempts']
                    )
                }
            }
    
    def get_detailed_metrics(self) -> Dict[str, Any]:
        """Retorna métricas detalhadas com histórico"""
        with self._lock:
            self._cleanup_old_metrics()
            
            return {
                'messages': [dict(m) for m in self.message_metrics],
                'qualifications': [dict(m) for m in self.qualification_metrics],
                'meetings': [dict(m) for m in self.meeting_metrics],
                'summary': self.get_metrics_summary()
            }
    
    def log_metrics_summary(self):
        """Loga um resumo das métricas"""
        summary = self.get_metrics_summary()
        
        logger.info(
            "Resumo de Métricas do Sistema",
            **{
                'total_messages_sent': summary['totals']['messages'].get('total_sent', 0),
                'message_success_rate': f"{summary['rates']['message_success_rate']:.1f}%",
                'total_qualifications': summary['totals']['qualifications'].get('total_qualifications', 0),
                'qualification_rate': f"{summary['rates']['qualification_rate']:.1f}%",
                'total_meetings': summary['totals']['meetings'].get('total_attempts', 0),
                'meeting_success_rate': f"{summary['rates']['meeting_success_rate']:.1f}%",
                'last_hour_messages': summary['last_hour']['messages']['total'],
                'last_hour_qualifications': summary['last_hour']['qualifications']['total'],
                'last_hour_meetings': summary['last_hour']['meetings']['total']
            }
        )
    
    def _calculate_success_rate(self, successful: int, total: int) -> float:
        """Calcula taxa de sucesso em percentual"""
        if total == 0:
            return 0.0
        return (successful / total) * 100.0
    
    def _cleanup_old_metrics(self):
        """Remove métricas antigas"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.retention_seconds)
        
        # Limpar métricas de mensagens
        while self.message_metrics and self.message_metrics[0]['timestamp'] < cutoff:
            self.message_metrics.popleft()
        
        # Limpar métricas de qualificação
        while self.qualification_metrics and self.qualification_metrics[0]['timestamp'] < cutoff:
            self.qualification_metrics.popleft()
        
        # Limpar métricas de reuniões
        while self.meeting_metrics and self.meeting_metrics[0]['timestamp'] < cutoff:
            self.meeting_metrics.popleft()
    
    def _start_cleanup_thread(self):
        """Inicia thread de limpeza periódica"""
        def cleanup_worker():
            while True:
                time.sleep(3600)  # Limpar a cada hora
                with self._lock:
                    self._cleanup_old_metrics()
                    self.log_metrics_summary()
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

# Instância global do serviço de métricas
metrics_service = MetricsService()
