from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Relatório por conferente (baseado em eventos)
# ---------------------------------------------------------------------------

def relatorio_por_conferente(
    data_ini: str | None = None,
    data_fim: str | None = None,
    usuario_id: str | None = None,
) -> list[dict]:
    """
    Retorna um registro por usuário com contadores de eventos, agregados em Python.
    Filtros de join em tabelas relacionadas não são suportados pelo PostgREST via .eq(),
    por isso os filtros são apenas sobre colunas diretas da tabela de eventos.
    """
    sb = get_supabase()

    query = (
        sb.table("conferencia_expedicao_eventos")
        .select(
            "tipo_evento, usuario_id, conferencia_id, "
            "created_at, "
            "usuarios_operacao(nome, login), "
            "conferencias_expedicao(numero_carga, status)"
        )
    )

    if data_ini:
        query = query.gte("created_at", f"{data_ini}T00:00:00+00:00")
    if data_fim:
        query = query.lte("created_at", f"{data_fim}T23:59:59+00:00")
    if usuario_id:
        query = query.eq("usuario_id", usuario_id)

    resp = query.execute()
    eventos = resp.data or []

    agregados: dict[str, dict] = {}
    for ev in eventos:
        uid = ev.get("usuario_id") or "_sem_usuario"
        usuario_info = ev.get("usuarios_operacao") or {}
        nome = usuario_info.get("nome", "Desconhecido")
        login = usuario_info.get("login", "-")

        if uid not in agregados:
            agregados[uid] = {
                "usuario_id": uid,
                "usuario_nome": nome,
                "usuario_login": login,
                "volumes_conferidos": 0,
                "duplicidades": 0,
                "divergencias": 0,
                "faltas_nao_autorizadas": 0,
                "faltas_autorizadas": 0,
                "conferencias_encerradas": 0,
                "conferencias_participadas": set(),
            }

        tipo = ev.get("tipo_evento", "")
        agg = agregados[uid]
        agg["conferencias_participadas"].add(ev.get("conferencia_id"))

        if tipo == "VOLUME_CONFERIDO":
            agg["volumes_conferidos"] += 1
        elif tipo == "VOLUME_DUPLICADO":
            agg["duplicidades"] += 1
        elif tipo == "VOLUME_DIVERGENTE":
            agg["divergencias"] += 1
        elif tipo == "FALTA_NAO_AUTORIZADA":
            agg["faltas_nao_autorizadas"] += 1
        elif tipo == "FALTA_AUTORIZADA":
            agg["faltas_autorizadas"] += 1
        elif tipo == "CONFERENCIA_ENCERRADA":
            agg["conferencias_encerradas"] += 1

    resultado = []
    for agg in agregados.values():
        conf_part = len(agg["conferencias_participadas"])
        vc = agg["volumes_conferidos"]
        erros = agg["duplicidades"] + agg["divergencias"] + agg["faltas_nao_autorizadas"]
        total = vc + erros
        acerto = round((vc / total * 100), 1) if total > 0 else 100.0

        resultado.append({
            "Usuario": agg["usuario_nome"],
            "Login": agg["usuario_login"],
            "Vol. Conferidos": vc,
            "Duplicidades": agg["duplicidades"],
            "Divergencias": agg["divergencias"],
            "Faltas Aut.": agg["faltas_autorizadas"],
            "Faltas N.Aut.": agg["faltas_nao_autorizadas"],
            "Confs. Encerradas": agg["conferencias_encerradas"],
            "Confs. Participadas": conf_part,
            "% Acerto": acerto,
        })

    return sorted(resultado, key=lambda x: x["Usuario"])


# ---------------------------------------------------------------------------
# Relatório por carga
# ---------------------------------------------------------------------------

def relatorio_por_carga(
    data_ini: str | None = None,
    data_fim: str | None = None,
    status: str | None = None,
    numero_carga: str | None = None,
) -> list[dict]:
    sb = get_supabase()

    query = (
        sb.table("conferencias_expedicao")
        .select(
            "numero_carga, status, total_esperado, total_conferido, "
            "total_faltante, total_divergente, total_duplicado, "
            "iniciado_em, encerrado_em, criado_por, fechado_por, "
            "criado_por_id, fechado_por_id"
        )
        .order("iniciado_em", desc=True)
    )

    if data_ini:
        query = query.gte("iniciado_em", f"{data_ini}T00:00:00+00:00")
    if data_fim:
        query = query.lte("iniciado_em", f"{data_fim}T23:59:59+00:00")
    if status:
        query = query.eq("status", status)
    if numero_carga:
        query = query.ilike("numero_carga", f"%{numero_carga}%")

    resp = query.execute()
    return resp.data or []


# ---------------------------------------------------------------------------
# Relatório de erros (eventos de erro detalhados)
# ---------------------------------------------------------------------------

def relatorio_erros(
    data_ini: str | None = None,
    data_fim: str | None = None,
    usuario_id: str | None = None,
    tipos: list[str] | None = None,
) -> list[dict]:
    """Retorna eventos de erro: VOLUME_DUPLICADO, VOLUME_DIVERGENTE, FALTA_NAO_AUTORIZADA."""
    sb = get_supabase()

    if tipos is None:
        tipos = ["VOLUME_DUPLICADO", "VOLUME_DIVERGENTE", "FALTA_NAO_AUTORIZADA"]

    query = (
        sb.table("conferencia_expedicao_eventos")
        .select(
            "created_at, tipo_evento, numero_rastreamento_lido, mensagem, "
            "usuarios_operacao(nome, login), "
            "conferencias_expedicao(numero_carga), "
            "conferencia_expedicao_volumes(nota_fiscal, ctrc, volume_texto, numero_rastreamento)"
        )
        .in_("tipo_evento", tipos)
        .order("created_at", desc=True)
    )

    if data_ini:
        query = query.gte("created_at", f"{data_ini}T00:00:00+00:00")
    if data_fim:
        query = query.lte("created_at", f"{data_fim}T23:59:59+00:00")
    if usuario_id:
        query = query.eq("usuario_id", usuario_id)

    resp = query.execute()
    eventos = resp.data or []

    linhas = []
    for ev in eventos:
        u = ev.get("usuarios_operacao") or {}
        c = ev.get("conferencias_expedicao") or {}
        v = ev.get("conferencia_expedicao_volumes") or {}
        linhas.append({
            "Data/Hora": ev.get("created_at", ""),
            "Tipo": ev.get("tipo_evento", ""),
            "Usuario": u.get("nome", "-"),
            "Login": u.get("login", "-"),
            "Carga": c.get("numero_carga", "-"),
            "NR Lido": ev.get("numero_rastreamento_lido", ""),
            "NR Volume": v.get("numero_rastreamento", ""),
            "NF": v.get("nota_fiscal", ""),
            "CTRC": v.get("ctrc", ""),
            "Volume": v.get("volume_texto", ""),
            "Mensagem": ev.get("mensagem", ""),
        })
    return linhas


# ---------------------------------------------------------------------------
# Cargas conferidas por um conferente específico (visão detalhada/somente leitura)
# ---------------------------------------------------------------------------

def listar_cargas_por_conferente(usuario_id: str) -> list[dict]:
    """Lista as cargas (conferências) em que o usuário bipou ao menos um volume."""
    sb = get_supabase()
    resp = (
        sb.table("conferencia_expedicao_eventos")
        .select(
            "conferencia_id, created_at, "
            "conferencias_expedicao(id, numero_carga, status, total_esperado, "
            "total_conferido, total_faltante, total_divergente, total_duplicado, "
            "iniciado_em, encerrado_em, criado_por)"
        )
        .eq("usuario_id", usuario_id)
        .eq("tipo_evento", "VOLUME_CONFERIDO")
        .order("created_at", desc=True)
        .execute()
    )
    eventos = resp.data or []

    cargas: dict[str, dict] = {}
    for ev in eventos:
        c = ev.get("conferencias_expedicao") or {}
        cid = c.get("id") or ev.get("conferencia_id")
        if not cid or cid in cargas:
            continue
        cargas[cid] = c

    return sorted(cargas.values(), key=lambda x: x.get("iniciado_em") or "", reverse=True)


# ---------------------------------------------------------------------------
# Listar usuários para filtros
# ---------------------------------------------------------------------------

def listar_usuarios_opcoes(perfil: str | None = None) -> list[dict]:
    sb = get_supabase()
    query = (
        sb.table("usuarios_operacao")
        .select("id, nome, login, perfil")
        .eq("ativo", True)
        .order("nome")
    )
    if perfil:
        query = query.eq("perfil", perfil)
    resp = query.execute()
    return resp.data or []
