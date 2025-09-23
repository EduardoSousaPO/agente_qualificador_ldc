"""
Serviço para integração completa com Google Sheets
- Entrada: Detectar novos leads
- Saída: Enviar resultados para CRM
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    """Serviço completo para Google Sheets - Entrada e Saída"""
    
    def __init__(self):
        self.service = None
        self.credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', '/app/credentials.json')
        
        # Configurações de entrada (leads)
        self.input_sheets_id = os.getenv('GOOGLE_SHEETS_ID')
        self.input_range = os.getenv('GOOGLE_SHEETS_RANGE', 'Sheet1!A:E')
        
        # Configurações de saída (CRM)
        self.crm_sheets_id = os.getenv('GOOGLE_CRM_SHEETS_ID')
        self.crm_range = os.getenv('GOOGLE_CRM_SHEETS_RANGE', 'Sheet1!A:L')
        
        self._inicializar_servico()
    
    def _inicializar_servico(self):
        """Inicializa serviço Google Sheets"""
        try:
            if not GOOGLE_AVAILABLE:
                logger.warning("Bibliotecas Google não disponíveis")
                return
            
            if not os.path.exists(self.credentials_path):
                if os.getenv('FLASK_ENV') == 'production':
                    logger.info("Google Sheets desabilitado - credentials.json não encontrado")
                    return
                else:
                    logger.error("credentials.json não encontrado")
                    return
            
            # Carregar credenciais
            with open(self.credentials_path, 'r') as f:
                credentials_info = json.load(f)
            
            credentials = Credentials.from_service_account_info(
                credentials_info,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets service inicializado com sucesso")
            
        except Exception as e:
            logger.error("Erro ao inicializar Google Sheets", error=str(e))
            self.service = None
    
    # ========== ENTRADA DE LEADS ==========
    
    def detectar_novos_leads(self) -> Dict[str, Any]:
        """Detecta novos leads na planilha de entrada"""
        try:
            if not self.service or not self.input_sheets_id:
                return {
                    'success': True,
                    'message': 'Google Sheets não configurado',
                    'novos_leads': 0,
                    'processados': 0,
                    'erros': 0
                }
            
            # Ler dados da planilha
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.input_sheets_id,
                range=self.input_range
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return {
                    'success': True,
                    'message': 'Nenhum dado encontrado na planilha',
                    'novos_leads': 0,
                    'processados': 0,
                    'erros': 0
                }
            
            # Primeira linha são os cabeçalhos
            headers = values[0] if values else []
            leads_data = values[1:] if len(values) > 1 else []
            
            novos_leads = 0
            processados = 0
            erros = 0
            detalhes = []
            
            for i, row in enumerate(leads_data, start=2):  # Linha 2 em diante
                try:
                    # Preencher campos faltantes
                    while len(row) < len(headers):
                        row.append('')
                    
                    lead_data = dict(zip(headers, row))
                    
                    # Verificar se já foi processado
                    if lead_data.get('processado', '').lower() in ['true', 'sim', 'x', '1']:
                        continue
                    
                    # Validar dados obrigatórios
                    if not lead_data.get('nome') or not lead_data.get('telefone'):
                        detalhes.append(f"Linha {i}: Nome ou telefone em branco")
                        erros += 1
                        continue
                    
                    # Processar lead
                    resultado = self._processar_lead_entrada(lead_data)
                    
                    if resultado['success']:
                        # Marcar como processado na planilha
                        self._marcar_lead_processado(i, len(headers))
                        processados += 1
                        detalhes.append(f"Lead {lead_data['nome']} processado com sucesso")
                    else:
                        erros += 1
                        detalhes.append(f"Erro ao processar {lead_data['nome']}: {resultado.get('error')}")
                    
                    novos_leads += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao processar linha {i}", error=str(e))
                    erros += 1
                    detalhes.append(f"Linha {i}: Erro - {str(e)}")
            
            return {
                'success': True,
                'message': f'Processamento concluído',
                'novos_leads': novos_leads,
                'processados': processados,
                'erros': erros,
                'detalhes': detalhes
            }
            
        except Exception as e:
            logger.error("Erro ao detectar novos leads", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'novos_leads': 0,
                'processados': 0,
                'erros': 1
            }
    
    def _processar_lead_entrada(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa um lead da planilha de entrada"""
        try:
            from backend.models.database_models import DatabaseConnection, LeadRepository
            from backend.services.qualification_service import QualificationService
            from backend.services.whatsapp_service import WhatsAppService
            from backend.models.database_models import (
                SessionRepository, MessageRepository, QualificacaoRepository
            )
            from backend.services.scoring_service import ScoringService
            
            # Inicializar repositórios
            db_conn = DatabaseConnection()
            lead_repo = LeadRepository(db_conn)
            session_repo = SessionRepository(db_conn)
            message_repo = MessageRepository(db_conn)
            qualificacao_repo = QualificacaoRepository(db_conn)
            
            # Inicializar serviços
            whatsapp_service = WhatsAppService()
            scoring_service = ScoringService()
            qualification_service = QualificationService(
                session_repo, message_repo, qualificacao_repo, 
                scoring_service, whatsapp_service
            )
            
            # Verificar se lead já existe
            existing_lead = lead_repo.get_lead_by_phone(lead_data['telefone'])
            if existing_lead:
                return {
                    'success': False,
                    'error': 'Lead já existe no sistema'
                }
            
            # Criar lead
            lead_id = lead_repo.create_lead(
                nome=lead_data['nome'],
                telefone=lead_data['telefone'],
                email=lead_data.get('email', ''),
                canal=lead_data.get('canal', 'planilha')
            )
            
            if not lead_id:
                return {
                    'success': False,
                    'error': 'Erro ao criar lead no banco'
                }
            
            # Iniciar qualificação via WhatsApp
            resultado = qualification_service.iniciar_qualificacao(
                lead_id=lead_id,
                telefone=lead_data['telefone'],
                canal=lead_data.get('canal', 'planilha')
            )
            
            return resultado
            
        except Exception as e:
            logger.error("Erro ao processar lead de entrada", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _marcar_lead_processado(self, linha: int, num_colunas: int):
        """Marca lead como processado na planilha"""
        try:
            # Coluna E (índice 4) para marcar como processado
            coluna_processado = chr(ord('A') + min(4, num_colunas - 1))
            range_update = f"{coluna_processado}{linha}"
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.input_sheets_id,
                range=range_update,
                valueInputOption='RAW',
                body={'values': [['TRUE']]}
            ).execute()
            
        except Exception as e:
            logger.error(f"Erro ao marcar linha {linha} como processada", error=str(e))
    
    # ========== SAÍDA PARA CRM ==========
    
    def enviar_resultado_crm(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Envia resultado da qualificação para planilha CRM"""
        try:
            if not self.service or not self.crm_sheets_id:
                logger.warning("CRM Sheets não configurado")
                return {'success': False, 'error': 'CRM Sheets não configurado'}
            
            # Preparar dados para CRM
            crm_row = [
                lead_data.get('nome', ''),
                lead_data.get('telefone', ''),
                lead_data.get('email', ''),
                lead_data.get('canal', ''),
                lead_data.get('status', ''),
                str(lead_data.get('score', 0)),
                lead_data.get('patrimonio_faixa', ''),
                lead_data.get('objetivo', ''),
                lead_data.get('prazo', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                lead_data.get('resumo_conversa', ''),
                lead_data.get('proximo_passo', '')
            ]
            
            # Adicionar à planilha
            self.service.spreadsheets().values().append(
                spreadsheetId=self.crm_sheets_id,
                range=self.crm_range,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [crm_row]}
            ).execute()
            
            logger.info("Resultado enviado para CRM", nome_lead=lead_data.get('nome'))
            return {'success': True, 'message': 'Enviado para CRM com sucesso'}
            
        except Exception as e:
            logger.error("Erro ao enviar resultado para CRM", error=str(e))
            return {'success': False, 'error': str(e)}
    
    def gerar_resumo_conversa(self, lead_id: str) -> str:
        """Gera resumo da conversa para o CRM"""
        try:
            from backend.models.database_models import DatabaseConnection, MessageRepository
            
            db_conn = DatabaseConnection()
            message_repo = MessageRepository(db_conn)
            
            # Buscar mensagens da sessão
            mensagens = message_repo.get_messages_by_lead(lead_id)
            
            if not mensagens:
                return "Nenhuma conversa registrada"
            
            resumo_parts = []
            for msg in mensagens[-10:]:  # Últimas 10 mensagens
                tipo = "Lead" if msg['tipo'] == 'recebida' else "Agente"
                conteudo = msg['conteudo'][:100]  # Primeiros 100 chars
                resumo_parts.append(f"{tipo}: {conteudo}")
            
            return " | ".join(resumo_parts)
            
        except Exception as e:
            logger.error("Erro ao gerar resumo da conversa", error=str(e))
            return "Erro ao gerar resumo"
    
    def definir_proximo_passo(self, status: str, score: int) -> str:
        """Define próximo passo baseado no status e score"""
        if status == 'reuniao_agendada':
            return "Reunião de diagnóstico agendada - Aguardar contato do consultor"
        elif score >= 70:
            return "Lead qualificado - Agendar reunião de diagnóstico"
        elif score >= 50:
            return "Lead em aquecimento - Continuar nutrição com conteúdo"
        else:
            return "Lead não qualificado - Incluir em campanha de nutrição"

    # ========== UTILITÁRIOS ==========
    
    def testar_conexao(self) -> Dict[str, Any]:
        """Testa conexão com Google Sheets"""
        try:
            if not self.service:
                return {'success': False, 'error': 'Serviço não inicializado'}
            
            # Testar planilha de entrada
            if self.input_sheets_id:
                result = self.service.spreadsheets().get(
                    spreadsheetId=self.input_sheets_id
                ).execute()
                entrada_ok = True
                entrada_nome = result.get('properties', {}).get('title', 'Desconhecido')
            else:
                entrada_ok = False
                entrada_nome = 'Não configurado'
            
            # Testar planilha CRM
            if self.crm_sheets_id:
                result = self.service.spreadsheets().get(
                    spreadsheetId=self.crm_sheets_id
                ).execute()
                crm_ok = True
                crm_nome = result.get('properties', {}).get('title', 'Desconhecido')
            else:
                crm_ok = False
                crm_nome = 'Não configurado'
            
            return {
                'success': True,
                'entrada': {
                    'configurado': entrada_ok,
                    'nome': entrada_nome,
                    'id': self.input_sheets_id
                },
                'crm': {
                    'configurado': crm_ok,
                    'nome': crm_nome,
                    'id': self.crm_sheets_id
                }
            }
            
        except Exception as e:
            logger.error("Erro ao testar conexão Google Sheets", error=str(e))
            return {'success': False, 'error': str(e)}

