-- =============================================================================
-- EXTENSÕES
-- =============================================================================
create extension if not exists pgcrypto;

-- =============================================================================
-- TABELAS PRINCIPAIS — Conferência de Expedição
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Usuários de operação
-- -----------------------------------------------------------------------------
create table if not exists public.usuarios_operacao (
    id           uuid primary key default gen_random_uuid(),
    empresa_id   uuid null,
    nome         text not null,
    email        text unique null,
    login        text unique not null,
    senha_hash   text not null,
    perfil       text not null default 'CONFERENTE',  -- ADMIN | SUPERVISOR | CONFERENTE
    ativo        boolean default true,
    criado_em    timestamptz default now(),
    atualizado_em timestamptz default now()
);

create index if not exists idx_usuarios_operacao_login
    on public.usuarios_operacao(login);

create index if not exists idx_usuarios_operacao_perfil
    on public.usuarios_operacao(perfil);

create index if not exists idx_usuarios_operacao_ativo
    on public.usuarios_operacao(ativo);

-- -----------------------------------------------------------------------------
-- 2. Conferências de expedição
-- -----------------------------------------------------------------------------
create table if not exists public.conferencias_expedicao (
    id                    uuid primary key default gen_random_uuid(),
    empresa_id            uuid null,
    numero_carga          text not null,
    status                text not null default 'EM_CONFERENCIA',
    total_esperado        integer default 0,
    total_conferido       integer default 0,
    total_faltante        integer default 0,
    total_divergente      integer default 0,
    total_duplicado       integer default 0,
    iniciado_em           timestamptz default now(),
    encerrado_em          timestamptz null,
    criado_por            text null,
    criado_por_id         uuid null references public.usuarios_operacao(id),
    fechado_por           text null,
    fechado_por_id        uuid null references public.usuarios_operacao(id),
    observacao_fechamento text null,
    created_at            timestamptz default now(),
    updated_at            timestamptz default now()
);

create index if not exists idx_conferencias_expedicao_numero_carga
    on public.conferencias_expedicao(numero_carga);

create index if not exists idx_conferencias_expedicao_status
    on public.conferencias_expedicao(status);

create index if not exists idx_conferencias_expedicao_criado_por_id
    on public.conferencias_expedicao(criado_por_id);

-- -----------------------------------------------------------------------------
-- 3. Volumes da conferência
-- -----------------------------------------------------------------------------
create table if not exists public.conferencia_expedicao_volumes (
    id                        uuid primary key default gen_random_uuid(),
    conferencia_id            uuid not null references public.conferencias_expedicao(id) on delete cascade,
    empresa_id                uuid null,
    chave_nfe                 text null,
    nota_fiscal               text null,
    ctrc                      text null,
    numero_rastreamento       text not null,
    seq_ctrc                  text null,
    volume_texto              text null,
    volume_atual              integer null,
    volume_total              integer null,
    unidade_entrega           text null,
    unidade_centralizadora    text null,
    setor_destino             text null,
    data_previsao_entrega     date null,
    remetente                 text null,
    peso                      text null,
    endereco_entrega          text null,
    site                      text null,
    praca                     text null,
    status                    text not null default 'PENDENTE',
    conferido_em              timestamptz null,
    conferido_por             text null,
    conferido_por_id          uuid null references public.usuarios_operacao(id),
    motivo_falta              text null,
    autorizado_por            text null,
    falta_classificada_por_id uuid null references public.usuarios_operacao(id),
    observacao                text null,
    payload_ssw               jsonb null,
    created_at                timestamptz default now(),
    updated_at                timestamptz default now(),
    constraint uq_conferencia_volume_nr unique (conferencia_id, numero_rastreamento)
);

create index if not exists idx_conferencia_volumes_conferencia_id
    on public.conferencia_expedicao_volumes(conferencia_id);

create index if not exists idx_conferencia_volumes_nr
    on public.conferencia_expedicao_volumes(numero_rastreamento);

create index if not exists idx_conferencia_volumes_status
    on public.conferencia_expedicao_volumes(status);

create index if not exists idx_conferencia_volumes_conferido_por_id
    on public.conferencia_expedicao_volumes(conferido_por_id);

-- -----------------------------------------------------------------------------
-- 4. Eventos / auditoria
-- -----------------------------------------------------------------------------
create table if not exists public.conferencia_expedicao_eventos (
    id                       uuid primary key default gen_random_uuid(),
    conferencia_id           uuid not null references public.conferencias_expedicao(id) on delete cascade,
    volume_id                uuid null references public.conferencia_expedicao_volumes(id) on delete set null,
    usuario_id               uuid null references public.usuarios_operacao(id),
    tipo_evento              text not null,
    numero_rastreamento_lido text null,
    mensagem                 text null,
    payload                  jsonb null,
    criado_por               text null,
    created_at               timestamptz default now()
);

create index if not exists idx_conferencia_eventos_conferencia_id
    on public.conferencia_expedicao_eventos(conferencia_id);

create index if not exists idx_conferencia_eventos_usuario_id
    on public.conferencia_expedicao_eventos(usuario_id);

create index if not exists idx_conferencia_eventos_tipo
    on public.conferencia_expedicao_eventos(tipo_evento);

-- =============================================================================
-- SCRIPTS PARA BANCO JÁ EXISTENTE (executar se as tabelas já foram criadas)
-- =============================================================================

-- alter table public.conferencias_expedicao
--     add column if not exists criado_por_id uuid null references public.usuarios_operacao(id),
--     add column if not exists fechado_por_id uuid null references public.usuarios_operacao(id);

-- alter table public.conferencia_expedicao_volumes
--     add column if not exists conferido_por_id          uuid null references public.usuarios_operacao(id),
--     add column if not exists falta_classificada_por_id uuid null references public.usuarios_operacao(id);

-- alter table public.conferencia_expedicao_eventos
--     add column if not exists usuario_id uuid null references public.usuarios_operacao(id);

-- =============================================================================
-- VIEWS ANALÍTICAS
-- =============================================================================

create or replace view public.vw_conferencia_eventos_detalhados as
select
    e.id,
    e.created_at,
    e.tipo_evento,
    e.numero_rastreamento_lido,
    e.mensagem,
    e.payload,
    c.numero_carga,
    c.status                as status_conferencia,
    u.nome                  as usuario_nome,
    u.login                 as usuario_login,
    v.nota_fiscal,
    v.ctrc,
    v.volume_texto,
    v.numero_rastreamento,
    v.status                as status_volume
from public.conferencia_expedicao_eventos e
join public.conferencias_expedicao c
    on c.id = e.conferencia_id
left join public.usuarios_operacao u
    on u.id = e.usuario_id
left join public.conferencia_expedicao_volumes v
    on v.id = e.volume_id;

create or replace view public.vw_desempenho_conferentes as
select
    u.id                                                                       as usuario_id,
    u.nome                                                                     as usuario_nome,
    u.login                                                                    as usuario_login,
    count(*) filter (where e.tipo_evento = 'VOLUME_CONFERIDO')                as volumes_conferidos,
    count(*) filter (where e.tipo_evento = 'VOLUME_DUPLICADO')                as duplicidades,
    count(*) filter (where e.tipo_evento = 'VOLUME_DIVERGENTE')               as divergencias,
    count(*) filter (where e.tipo_evento = 'FALTA_NAO_AUTORIZADA')            as faltas_nao_autorizadas,
    count(*) filter (where e.tipo_evento = 'FALTA_AUTORIZADA')                as faltas_autorizadas,
    count(distinct e.conferencia_id)                                           as conferencias_participadas
from public.usuarios_operacao u
left join public.conferencia_expedicao_eventos e
    on e.usuario_id = u.id
group by u.id, u.nome, u.login;
