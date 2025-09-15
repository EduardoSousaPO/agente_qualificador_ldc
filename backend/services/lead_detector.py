"""
Serviço de Detecção de Leads
Monitora planilha Google Sheets e processa novos leads
"""
import os
from typing import Dict, Any, List, Optional
import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json

from backend.models.database_models import Lead, SystemLog

logger = structlog.get_logger()


class LeadDetectorService:
    """Serviço para detectar e processar novos leads da planilha"""
    
    def __init__(self, lead_repo, whatsapp_service, qualification_service):
        self.lead_repo = lead_repo
        self.whatsapp_service = whatsapp_service
        self.qualification_service = qualification_service
        
        # Configurações Google Sheets
        self.spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        self.range_name = os.getenv('GOOGLE_SHEETS_RANGE', 'Sheet1!A:D')
        self.credentials_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
        
        # Scopes necessários
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        
        self.service = None
        self._inicializar_servico()
    
    def _inicializar_servico(self):
        """Inicializa serviço Google Sheets"""
        try:
            creds = None
            token_file = 'token.json'
            
            # Carregar token existente
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, self.scopes)
            
            # Se não há credenciais válidas, fazer login
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_file):
                        logger.error("Arquivo de credenciais não encontrado", 
                                   file=self.credentials_file)
                        return
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.scopes)
                    creds = flow.run_local_server(port=0)
                
                # Salvar credenciais para próxima execução
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
            
            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("Serviço Google Sheets inicializado com sucesso")
            
        except Exception as e:
            logger.error("Erro ao inicializar Google Sheets", error=str(e))
            self.service = None
    
    def detectar_e_processar_novos_leads(self) -> Dict[str, Any]:
        """Detecta novos leads na planilha e inicia qualificação"""
        try:
            if not self.service:
                return {
                    'success': False,
                    'error': 'Serviço Google Sheets não inicializado'
                }
            
            # Ler dados da planilha
            leads_planilha = self._ler_planilha()
            
            if not leads_planilha['success']:
                return leads_planilha
            
            novos_leads = []
            processados = 0
            erros = 0
            detalhes = []
            
            # Processar cada linha da planilha
            for linha in leads_planilha['data']:
                try:
                    resultado = self._processar_linha_planilha(linha)
                    
                    if resultado['success']:
                        if resultado.get('novo_lead'):
                            novos_leads.append(resultado['lead_data'])
                            processados += 1
                        
                        detalhes.append({
                            'telefone': linha.get('telefone', 'N/A'),
                            'status': 'processado' if resultado.get('novo_lead') else 'já_existe',
                            'message': resultado.get('message', '')
                        })
                    else:
                        erros += 1
                        detalhes.append({
                            'telefone': linha.get('telefone', 'N/A'),
                            'status': 'erro',
                            'error': resultado.get('error', '')
                        })
                        
                except Exception as e:
                    erros += 1
                    logger.error("Erro ao processar linha", linha=linha, error=str(e))
                    detalhes.append({
                        'telefone': linha.get('telefone', 'N/A'),
                        'status': 'erro',
                        'error': str(e)
                    })
            
            # Log do resultado
            self._log_resultado_processamento(len(novos_leads), processados, erros)
            
            return {
                'success': True,
                'novos_leads': len(novos_leads),
                'processados': processados,
                'erros': erros,
                'detalhes': detalhes
            }
            
        except Exception as e:
            logger.error("Erro geral no processamento de leads", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _ler_planilha(self) -> Dict[str, Any]:
        """Lê dados da planilha Google Sheets"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return {
                    'success': True,
                    'data': [],
                    'message': 'Planilha vazia'
                }
            
            # Assumir que primeira linha são headers
            headers = values[0] if values else []
            data_rows = values[1:] if len(values) > 1 else []
            
            # Converter para lista de dicionários
            leads_data = []
            for row in data_rows:
                if len(row) >= len(headers):
                    lead_dict = {}
                    for i, header in enumerate(headers):
                        lead_dict[header.lower().strip()] = row[i].strip() if i < len(row) else ''
                    
                    # Validar dados obrigatórios
                    if self._validar_dados_lead(lead_dict):
                        leads_data.append(lead_dict)
            
            logger.info("Planilha lida com sucesso", 
                       total_linhas=len(data_rows),
                       leads_validos=len(leads_data))
            
            return {
                'success': True,
                'data': leads_data
            }
            
        except Exception as e:
            logger.error("Erro ao ler planilha", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validar_dados_lead(self, lead_dict: Dict[str, str]) -> bool:
        """Valida se os dados do lead são válidos"""
        campos_obrigatorios = ['nome', 'telefone', 'canal']
        
        for campo in campos_obrigatorios:
            if not lead_dict.get(campo, '').strip():
                return False
        
        # Validar canal
        canais_validos = ['youtube', 'newsletter', 'ebook', 'meta_ads']
        if lead_dict.get('canal', '').lower() not in canais_validos:
            return False
        
        # Validar telefone (básico)
        telefone = lead_dict.get('telefone', '').strip()
        telefone_numerico = ''.join(filter(str.isdigit, telefone))
        
        if len(telefone_numerico) < 10:
            return False
        
        return True
    
    def _processar_linha_planilha(self, linha: Dict[str, str]) -> Dict[str, Any]:
        """Processa uma linha da planilha"""
        try:
            telefone = self._limpar_telefone(linha['telefone'])
            
            # Verificar se lead já existe
            lead_existente = self.lead_repo.get_lead_by_phone(telefone)
            
            if lead_existente:
                return {
                    'success': True,
                    'novo_lead': False,
                    'message': 'Lead já existe no banco',
                    'lead_data': lead_existente
                }
            
            # Criar novo lead
            novo_lead = Lead(
                nome=linha['nome'].strip(),
                telefone=telefone,
                email=linha.get('email', '').strip() or None,
                canal=linha['canal'].lower().strip(),
                status='novo',
                processado=False
            )
            
            lead_data = self.lead_repo.create_lead(novo_lead)
            
            if not lead_data:
                return {
                    'success': False,
                    'error': 'Erro ao criar lead no banco'
                }
            
            # Iniciar qualificação automaticamente
            resultado_qualificacao = self.qualification_service.iniciar_qualificacao(
                lead_data['id'], 
                telefone, 
                novo_lead.canal
            )
            
            if resultado_qualificacao['success']:
                # Marcar lead como processado
                self.lead_repo.update_lead(lead_data['id'], {
                    'processado': True,
                    'status': 'em_qualificacao'
                })
                
                logger.info("Novo lead processado com sucesso", 
                           lead_id=lead_data['id'],
                           nome=novo_lead.nome,
                           canal=novo_lead.canal)
                
                return {
                    'success': True,
                    'novo_lead': True,
                    'lead_data': lead_data,
                    'qualificacao_iniciada': True,
                    'message': 'Lead criado e qualificação iniciada'
                }
            else:
                logger.warning("Lead criado mas qualificação falhou", 
                              lead_id=lead_data['id'],
                              error=resultado_qualificacao.get('error'))
                
                return {
                    'success': True,
                    'novo_lead': True,
                    'lead_data': lead_data,
                    'qualificacao_iniciada': False,
                    'message': 'Lead criado mas qualificação falhou',
                    'qualificacao_error': resultado_qualificacao.get('error')
                }
                
        except Exception as e:
            logger.error("Erro ao processar linha da planilha", linha=linha, error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _limpar_telefone(self, telefone: str) -> str:
        """Limpa e padroniza número de telefone"""
        # Remove caracteres não numéricos
        telefone_limpo = ''.join(filter(str.isdigit, telefone))
        
        # Adiciona código do país se necessário
        if len(telefone_limpo) == 11 and telefone_limpo.startswith('11'):
            telefone_limpo = '55' + telefone_limpo
        elif len(telefone_limpo) == 10:
            telefone_limpo = '5511' + telefone_limpo
        elif not telefone_limpo.startswith('55'):
            telefone_limpo = '55' + telefone_limpo
        
        return telefone_limpo
    
    def _log_resultado_processamento(self, novos_leads: int, processados: int, erros: int):
        """Log do resultado do processamento"""
        log = SystemLog(
            nivel='INFO',
            evento='processamento_leads_planilha',
            detalhes={
                'novos_leads': novos_leads,
                'processados': processados,
                'erros': erros,
                'timestamp': str(datetime.utcnow())
            }
        )
        
        try:
            # Usar repositório de logs se disponível
            if hasattr(self, 'log_repo'):
                self.log_repo.create_log(log)
        except Exception:
            pass
    
    def testar_conexao_planilha(self) -> Dict[str, Any]:
        """Testa conexão com a planilha"""
        try:
            if not self.service:
                return {
                    'success': False,
                    'error': 'Serviço não inicializado'
                }
            
            if not self.spreadsheet_id:
                return {
                    'success': False,
                    'error': 'GOOGLE_SHEETS_SPREADSHEET_ID não configurado'
                }
            
            # Tentar ler apenas os headers
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A1:Z1'
            ).execute()
            
            headers = result.get('values', [[]])[0] if result.get('values') else []
            
            return {
                'success': True,
                'headers': headers,
                'spreadsheet_id': self.spreadsheet_id,
                'range': self.range_name
            }
            
        except Exception as e:
            logger.error("Erro ao testar conexão com planilha", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def obter_estatisticas_planilha(self) -> Dict[str, Any]:
        """Obtém estatísticas da planilha"""
        try:
            resultado_leitura = self._ler_planilha()
            
            if not resultado_leitura['success']:
                return resultado_leitura
            
            dados = resultado_leitura['data']
            
            # Estatísticas por canal
            canais = {}
            for lead in dados:
                canal = lead.get('canal', 'desconhecido').lower()
                canais[canal] = canais.get(canal, 0) + 1
            
            # Verificar quantos já existem no banco
            leads_existentes = 0
            for lead in dados:
                telefone = self._limpar_telefone(lead.get('telefone', ''))
                if self.lead_repo.get_lead_by_phone(telefone):
                    leads_existentes += 1
            
            return {
                'success': True,
                'total_leads': len(dados),
                'leads_existentes': leads_existentes,
                'leads_novos': len(dados) - leads_existentes,
                'canais': canais
            }
            
        except Exception as e:
            logger.error("Erro ao obter estatísticas da planilha", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }



