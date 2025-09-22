"""
🛡️ VALIDADOR DE TELEFONES
Protege contra envios para números não autorizados
"""

import re
import structlog

logger = structlog.get_logger(__name__)

class PhoneValidator:
    """Validador de telefones para evitar envios indevidos"""
    
    def __init__(self):
        # Lista de números autorizados para receber mensagens
        self.numeros_autorizados = {
            # Número do Eduardo (proprietário do sistema)
            '5511987654321',  # Número real do Eduardo
            '5511999999999',  # Número de teste do Eduardo
            
            # Números de teste específicos (apenas para desenvolvimento)
            '5511111111111',  # Teste genérico
            '5511222222222',  # Teste alternativo
        }
        
        # Padrões de números de teste que são permitidos
        self.padroes_teste_permitidos = [
            r'^5511999999\d{3}$',  # 5511999999XXX (testes do Eduardo)
            r'^55119876543\d{2}$', # 551198765432X (variações do número do Eduardo)
        ]
        
        # Padrões suspeitos que devem ser bloqueados
        self.padroes_bloqueados = [
            r'^5511\d{4}4321$',    # Números gerados automaticamente
            r'^5511\d{6}999$',     # Números com padrão suspeito
            r'^55116666\d{4}$',    # Números com sequência repetitiva
        ]
    
    def is_numero_autorizado(self, telefone: str) -> bool:
        """Verifica se um número está autorizado a receber mensagens"""
        
        if not telefone:
            logger.warning("Telefone vazio fornecido para validação")
            return False
        
        # Limpar telefone para comparação
        telefone_limpo = self._limpar_telefone(telefone)
        
        # Verificar lista de autorizados
        if telefone_limpo in self.numeros_autorizados:
            logger.info("✅ Número autorizado encontrado", telefone=telefone_limpo)
            return True
        
        # Verificar padrões de teste permitidos
        for padrao in self.padroes_teste_permitidos:
            if re.match(padrao, telefone_limpo):
                logger.info("✅ Número de teste permitido", telefone=telefone_limpo, padrao=padrao)
                return True
        
        # Verificar padrões bloqueados
        for padrao in self.padroes_bloqueados:
            if re.match(padrao, telefone_limpo):
                logger.warning("🚨 Número com padrão suspeito BLOQUEADO", 
                             telefone=telefone_limpo, padrao=padrao)
                return False
        
        # Se não está na lista e não é padrão de teste, bloquear
        logger.warning("🚨 Número NÃO AUTORIZADO bloqueado", telefone=telefone_limpo)
        return False
    
    def _limpar_telefone(self, telefone: str) -> str:
        """Limpa telefone para validação"""
        # Remove caracteres não numéricos
        telefone_limpo = ''.join(filter(str.isdigit, str(telefone)))
        
        # Adiciona código do país se necessário
        if len(telefone_limpo) == 11 and telefone_limpo.startswith('11'):
            telefone_limpo = '55' + telefone_limpo
        elif len(telefone_limpo) == 10:
            telefone_limpo = '5511' + telefone_limpo
        elif not telefone_limpo.startswith('55'):
            telefone_limpo = '55' + telefone_limpo
        
        return telefone_limpo
    
    def adicionar_numero_autorizado(self, telefone: str, motivo: str = "Adicionado manualmente"):
        """Adiciona um número à lista de autorizados"""
        telefone_limpo = self._limpar_telefone(telefone)
        self.numeros_autorizados.add(telefone_limpo)
        logger.info("✅ Número adicionado à lista de autorizados", 
                   telefone=telefone_limpo, motivo=motivo)
    
    def remover_numero_autorizado(self, telefone: str):
        """Remove um número da lista de autorizados"""
        telefone_limpo = self._limpar_telefone(telefone)
        self.numeros_autorizados.discard(telefone_limpo)
        logger.info("🗑️ Número removido da lista de autorizados", telefone=telefone_limpo)
    
    def get_numeros_autorizados(self) -> list:
        """Retorna lista de números autorizados"""
        return list(self.numeros_autorizados)
    
    def validar_e_log_tentativa(self, telefone: str, contexto: str = "") -> bool:
        """Valida número e registra tentativa de envio"""
        autorizado = self.is_numero_autorizado(telefone)
        
        if autorizado:
            logger.info("✅ Envio AUTORIZADO", telefone=telefone, contexto=contexto)
        else:
            logger.warning("🚨 Envio BLOQUEADO - número não autorizado", 
                         telefone=telefone, contexto=contexto)
        
        return autorizado
