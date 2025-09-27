# Sistema de Métricas e Monitoramento

## Visão Geral

O sistema implementa monitoramento completo com métricas em tempo real para:
- ✅ Envio de mensagens WhatsApp
- ✅ Processo de qualificação de leads
- ✅ Agendamento de reuniões
- ✅ Deduplicação de mensagens

## Endpoints Disponíveis

### 📊 `/metrics` (GET)
Retorna resumo completo das métricas do sistema:

```json
{
  "timestamp": "2025-09-25T21:31:05.453633+00:00",
  "retention_hours": 24,
  "totals": {
    "messages": {
      "total_sent": 150,
      "successful_sent": 145,
      "failed_sent": 5,
      "deduped": 12
    },
    "qualifications": {
      "total_qualifications": 45,
      "qualified": 30,
      "not_qualified": 15
    },
    "meetings": {
      "total_attempts": 25,
      "successful_schedules": 22,
      "failed_schedules": 3
    }
  },
  "last_hour": {
    "messages": { "total": 8, "successful": 7, "failed": 1, "deduped": 2 },
    "qualifications": { "total": 3, "qualified": 2, "not_qualified": 1 },
    "meetings": { "total": 2, "successful": 2, "failed": 0 }
  },
  "rates": {
    "message_success_rate": 96.7,
    "qualification_rate": 66.7,
    "meeting_success_rate": 88.0
  }
}
```

### 📊 `/metrics/detailed` (GET)
Retorna métricas detalhadas com histórico completo de eventos.

### 🏥 `/health` (GET)
Health check com métricas básicas:

```json
{
  "status": "healthy",
  "timestamp": "2025-09-25T18:31:12.488497",
  "metrics": {
    "total_messages": 150,
    "message_success_rate": 96.7,
    "total_qualifications": 45,
    "qualification_rate": 66.7
  }
}
```

## Integração Automática

### MessagingService
- ✅ Registra automaticamente cada mensagem enviada
- ✅ Rastreia sucessos e falhas
- ✅ Monitora deduplicação
- ✅ Calcula taxas de sucesso

### QualificationFlow
- ✅ Registra qualificações aprovadas e rejeitadas
- ✅ Acompanha scores de qualificação
- ✅ Monitora taxa de conversão

### QualificationService
- ✅ Registra reuniões agendadas com sucesso
- ✅ Monitora falhas de agendamento
- ✅ Rastreia slots preferidos

## Logs Estruturados

O sistema gera logs estruturados para todas as métricas:

```
2025-09-25 18:31:46 [info] Mensagem registrada nas métricas 
  success=True telefone=5511999887766 total_sent=150

2025-09-25 18:31:46 [info] Qualificação registrada nas métricas 
  lead_id=lead1 qualified=True score=85 total_qualifications=45

2025-09-25 18:31:46 [info] Agendamento registrado nas métricas 
  lead_id=lead1 slot='Terça 10h' success=True total_attempts=25

2025-09-25 18:31:46 [info] Resumo de Métricas do Sistema
  total_messages_sent=150 message_success_rate=96.7%
  total_qualifications=45 qualification_rate=66.7%
  total_meetings=25 meeting_success_rate=88.0%
```

## Retenção de Dados

- **Período**: 24 horas por padrão
- **Limpeza**: Automática a cada hora
- **Thread-safe**: Suporte completo para concorrência
- **Resumo**: Logado automaticamente a cada hora

## Como Usar

### 1. Via API (Produção)
```bash
curl http://localhost:8000/metrics
curl http://localhost:8000/health
```

### 2. Via Código (Desenvolvimento)
```python
from backend.services.metrics_service import metrics_service

# Registrar métricas manualmente
metrics_service.record_message_sent("5511999887766", True, "Sucesso")
metrics_service.record_qualification_completed("lead1", 85, True)
metrics_service.record_meeting_scheduled("lead1", "Terça 10h", True)

# Obter resumo
summary = metrics_service.get_metrics_summary()
print(f"Taxa de sucesso: {summary['rates']['message_success_rate']:.1f}%")
```

### 3. Demonstração
```bash
python demo_metrics.py
```

## Monitoramento Recomendado

1. **Alertas de Taxa de Sucesso**:
   - Mensagens < 90%
   - Qualificações < 50%
   - Agendamentos < 80%

2. **Métricas de Volume**:
   - Mensagens/hora
   - Qualificações/dia
   - Reuniões/semana

3. **Health Checks**:
   - Verificar `/health` a cada minuto
   - Alertar se status != "healthy"

## Validação de Reuniões

Para validar se reuniões foram realmente criadas na tabela `reunioes`:

```sql
SELECT r.*, l.nome, l.telefone 
FROM reunioes r 
JOIN leads l ON r.lead_id = l.id 
WHERE r.created_at > NOW() - INTERVAL '1 day'
ORDER BY r.created_at DESC;
```

## Testes

Execute a suíte de testes para validar o sistema:

```bash
python -m pytest tests/ -v
```

Todos os 5 testes devem passar:
- ✅ test_leads_watcher_marks_sheet_row_and_triggers_qualification
- ✅ test_messaging_service_deduplicates_same_payload  
- ✅ test_messaging_service_processes_queue_in_order
- ✅ test_flow_collects_answers_and_offers_meeting
- ✅ test_flow_handles_meeting_confirmation

## Próximos Passos

1. **Dashboards**: Integrar com Grafana/Prometheus
2. **Alertas**: Configurar notificações automáticas
3. **Histórico**: Persistir métricas em banco de dados
4. **Analytics**: Análises avançadas de conversão
