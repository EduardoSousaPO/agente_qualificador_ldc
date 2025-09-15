-- Schema do Banco de Dados - Agente Qualificador de Leads
-- Criado automaticamente via Supabase MCP

-- Tabela de Leads com campos otimizados
CREATE TABLE IF NOT EXISTS public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(255) NOT NULL,
    telefone VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(255),
    canal VARCHAR(50) NOT NULL CHECK (canal IN ('youtube', 'newsletter', 'ebook', 'meta_ads')),
    status VARCHAR(50) DEFAULT 'novo' CHECK (status IN ('novo', 'em_qualificacao', 'qualificado', 'nao_qualificado', 'reuniao_agendada', 'finalizado')),
    score INTEGER DEFAULT 0 CHECK (score >= 0 AND score <= 100),
    processado BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de Sessões de Conversa
CREATE TABLE IF NOT EXISTS public.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    estado VARCHAR(50) DEFAULT 'inicio' CHECK (estado IN ('inicio', 'saudacao', 'pergunta_1', 'pergunta_2', 'pergunta_3', 'pergunta_4', 'calculando_score', 'resultado', 'finalizado')),
    contexto JSONB DEFAULT '{}',
    ativa BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de Mensagens
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    conteudo TEXT NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('recebida', 'enviada')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de Qualificações
CREATE TABLE IF NOT EXISTS public.qualificacoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
    
    -- Pergunta 1: Patrimônio (0-30 pontos)
    patrimonio_resposta TEXT,
    patrimonio_pontos INTEGER DEFAULT 0 CHECK (patrimonio_pontos >= 0 AND patrimonio_pontos <= 30),
    
    -- Pergunta 2: Objetivo (0-25 pontos)
    objetivo_resposta TEXT,
    objetivo_pontos INTEGER DEFAULT 0 CHECK (objetivo_pontos >= 0 AND objetivo_pontos <= 25),
    
    -- Pergunta 3: Urgência (0-25 pontos)
    urgencia_resposta TEXT,
    urgencia_pontos INTEGER DEFAULT 0 CHECK (urgencia_pontos >= 0 AND urgencia_pontos <= 25),
    
    -- Pergunta 4: Interesse em especialista (0-20 pontos)
    interesse_resposta TEXT,
    interesse_pontos INTEGER DEFAULT 0 CHECK (interesse_pontos >= 0 AND interesse_pontos <= 20),
    
    -- Score total
    score_total INTEGER GENERATED ALWAYS AS (patrimonio_pontos + objetivo_pontos + urgencia_pontos + interesse_pontos) STORED,
    
    -- Resultado da qualificação
    resultado VARCHAR(50) CHECK (resultado IN ('qualificado', 'nao_qualificado')),
    observacoes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de Reuniões (para leads qualificados)
CREATE TABLE IF NOT EXISTS public.reunioes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    data_agendada TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'agendada' CHECK (status IN ('agendada', 'confirmada', 'realizada', 'cancelada', 'remarcada')),
    link_reuniao TEXT,
    observacoes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de Logs do Sistema
CREATE TABLE IF NOT EXISTS public.system_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES public.leads(id) ON DELETE SET NULL,
    session_id UUID REFERENCES public.sessions(id) ON DELETE SET NULL,
    nivel VARCHAR(20) NOT NULL CHECK (nivel IN ('INFO', 'WARNING', 'ERROR', 'DEBUG')),
    evento VARCHAR(100) NOT NULL,
    detalhes JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para otimizar consultas
CREATE INDEX IF NOT EXISTS idx_leads_telefone ON public.leads(telefone);
CREATE INDEX IF NOT EXISTS idx_leads_canal ON public.leads(canal);
CREATE INDEX IF NOT EXISTS idx_leads_status ON public.leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_processado ON public.leads(processado);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON public.leads(created_at);

CREATE INDEX IF NOT EXISTS idx_sessions_lead_id ON public.sessions(lead_id);
CREATE INDEX IF NOT EXISTS idx_sessions_estado ON public.sessions(estado);
CREATE INDEX IF NOT EXISTS idx_sessions_ativa ON public.sessions(ativa);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON public.messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_lead_id ON public.messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_messages_tipo ON public.messages(tipo);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at);

CREATE INDEX IF NOT EXISTS idx_qualificacoes_lead_id ON public.qualificacoes(lead_id);
CREATE INDEX IF NOT EXISTS idx_qualificacoes_session_id ON public.qualificacoes(session_id);
CREATE INDEX IF NOT EXISTS idx_qualificacoes_score_total ON public.qualificacoes(score_total);
CREATE INDEX IF NOT EXISTS idx_qualificacoes_resultado ON public.qualificacoes(resultado);

CREATE INDEX IF NOT EXISTS idx_reunioes_lead_id ON public.reunioes(lead_id);
CREATE INDEX IF NOT EXISTS idx_reunioes_status ON public.reunioes(status);
CREATE INDEX IF NOT EXISTS idx_reunioes_data_agendada ON public.reunioes(data_agendada);

CREATE INDEX IF NOT EXISTS idx_system_logs_lead_id ON public.system_logs(lead_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_nivel ON public.system_logs(nivel);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON public.system_logs(created_at);

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para atualizar updated_at automaticamente
CREATE TRIGGER IF NOT EXISTS update_leads_updated_at 
    BEFORE UPDATE ON public.leads 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER IF NOT EXISTS update_sessions_updated_at 
    BEFORE UPDATE ON public.sessions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER IF NOT EXISTS update_reunioes_updated_at 
    BEFORE UPDATE ON public.reunioes 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger para atualizar score do lead quando qualificação é criada/atualizada
CREATE OR REPLACE FUNCTION sync_lead_score()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.leads 
    SET score = NEW.score_total,
        status = CASE 
            WHEN NEW.score_total >= 70 THEN 'qualificado'
            ELSE 'nao_qualificado'
        END,
        updated_at = NOW()
    WHERE id = NEW.lead_id;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER IF NOT EXISTS sync_lead_score_trigger
    AFTER INSERT OR UPDATE ON public.qualificacoes
    FOR EACH ROW EXECUTE FUNCTION sync_lead_score();



