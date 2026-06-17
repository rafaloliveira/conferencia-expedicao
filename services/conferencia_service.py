import os
from datetime import datetime, timezone
from services.supabase_client import get_supabase
from services.ssw_api import consultar_nr_por_chave
from utils.retry import executar_com_retry


def _exec(qb):
    """Executa um query builder Supabase com retry em falhas de transporte."""
    return executar_com_retry(lambda: qb.execute())

EMPRESA_ID = os.getenv("EMPRESA_ID") or None

# ---------------------------------------------------------------------------
# Conferência
# ---------------------------------------------------------------------------

def obter_ou_criar_conferencia(
    numero_carga: str,
    criado_por: str = "",
    usuario_id: str | None = None,
) -> dict:
    """
    Retorna conferência ativa (EM_CONFERENCIA) para a carga.
    Cria uma nova se não existir.
    """
    sb = get_supabase()
    resp = (
        sb.table("conferencias_expedicao")
        .select("*")
        .eq("numero_carga", numero_carga)
        .eq("status", "EM_CONFERENCIA")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]

    nova = {
        "numero_carga": numero_carga,
        "status": "EM_CONFERENCIA",
        "criado_por": criado_por or None,
        "criado_por_id": usuario_id or None,
    }
    if EMPRESA_ID:
        nova["empresa_id"] = EMPRESA_ID

    insert = sb.table("conferencias_expedicao").insert(nova).execute()
    conferencia = insert.data[0]

    registrar_evento(
        conferencia_id=conferencia["id"],
        tipo_evento="CONFERENCIA_CRIADA",
        mensagem=f"Conferência criada para carga {numero_carga}.",
        criado_por=criado_por,
        usuario_id=usuario_id,
    )
    return conferencia


def obter_conferencia(conferencia_id: str) -> dict | None:
    sb = get_supabase()
    resp = _exec(
        sb.table("conferencias_expedicao")
        .select("*")
        .eq("id", conferencia_id)
        .single()
    )
    return resp.data


def listar_conferencias_em_andamento(
    usuario_id: str | None = None,
    todas: bool = False,
) -> list[dict]:
    """
    Lista cargas com status EM_CONFERENCIA, para retomada após queda de conexão.
    Se todas=False, retorna apenas as criadas pelo usuário informado.
    """
    sb = get_supabase()
    qb = (
        sb.table("conferencias_expedicao")
        .select("*")
        .eq("status", "EM_CONFERENCIA")
        .order("created_at", desc=True)
    )
    if not todas and usuario_id:
        qb = qb.eq("criado_por_id", usuario_id)
    resp = _exec(qb)
    return resp.data or []


def excluir_conferencia(conferencia_id: str, usuario_id: str | None, perfil: str | None) -> None:
    """
    Exclui uma carga em conferência. Apenas o usuário que a criou ou um ADMIN podem excluir.
    """
    conf = obter_conferencia(conferencia_id)
    if not conf:
        raise ValueError("Conferência não encontrada.")
    if perfil != "ADMIN" and conf.get("criado_por_id") != usuario_id:
        raise PermissionError(
            "Apenas o usuário que criou esta carga ou um administrador pode excluí-la."
        )
    sb = get_supabase()
    sb.table("conferencias_expedicao").delete().eq("id", conferencia_id).execute()


# ---------------------------------------------------------------------------
# NF-e / Volumes
# ---------------------------------------------------------------------------

def adicionar_nfe_na_conferencia(
    conferencia_id: str,
    chave_nfe: str,
    criado_por: str = "",
    usuario_id: str | None = None,
) -> dict:
    """
    Consulta SSW para a chave_nfe, insere volumes no banco e retorna resumo.
    Retorna: {adicionados, duplicados, total_retornados, erros}
    """
    etiquetas = consultar_nr_por_chave(chave_nfe)

    if not etiquetas:
        return {"adicionados": 0, "duplicados": 0, "total_retornados": 0, "erros": []}

    sb = get_supabase()
    adicionados = 0
    duplicados = 0
    erros = []

    for etiqueta in etiquetas:
        nr = etiqueta.get("numero_rastreamento", "")
        if not nr:
            erros.append("Volume sem número de rastreamento ignorado.")
            continue

        volume_data = {
            "conferencia_id": conferencia_id,
            "status": "PENDENTE",
            **etiqueta,
        }
        if EMPRESA_ID:
            volume_data["empresa_id"] = EMPRESA_ID

        try:
            sb.table("conferencia_expedicao_volumes").insert(volume_data).execute()
            adicionados += 1
            registrar_evento(
                conferencia_id=conferencia_id,
                tipo_evento="NFE_ADICIONADA",
                numero_rastreamento_lido=nr,
                mensagem=f"Volume {nr} adicionado via NF-e {chave_nfe}.",
                payload={"chave_nfe": chave_nfe, "numero_rastreamento": nr},
                criado_por=criado_por,
                usuario_id=usuario_id,
            )
        except Exception as exc:
            msg = str(exc)
            if "uq_conferencia_volume_nr" in msg or "duplicate" in msg.lower():
                duplicados += 1
            else:
                erros.append(f"NR {nr}: {msg}")

    recalcular_totais(conferencia_id)
    return {
        "adicionados": adicionados,
        "duplicados": duplicados,
        "total_retornados": len(etiquetas),
        "erros": erros,
    }


def listar_ocorrencias(conferencia_id: str) -> list[dict]:
    """Retorna eventos de divergência e duplicidade para exibição na tela de conferência."""
    sb = get_supabase()
    resp = (
        sb.table("conferencia_expedicao_eventos")
        .select("tipo_evento, numero_rastreamento_lido, mensagem, created_at")
        .eq("conferencia_id", conferencia_id)
        .in_("tipo_evento", ["VOLUME_DIVERGENTE", "VOLUME_DUPLICADO", "VOLUME_JA_CONFERIDO"])
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def listar_volumes(conferencia_id: str) -> list[dict]:
    sb = get_supabase()
    resp = _exec(
        sb.table("conferencia_expedicao_volumes")
        .select("*")
        .eq("conferencia_id", conferencia_id)
        .order("created_at")
    )
    return resp.data or []


# ---------------------------------------------------------------------------
# Bipagem
# ---------------------------------------------------------------------------

def registrar_bipagem(
    conferencia_id: str,
    numero_rastreamento: str,
    conferido_por: str = "",
    usuario_id: str | None = None,
) -> dict:
    """
    Processa a leitura de um NR.
    Retorna: {status: 'CONFERIDO'|'DUPLICADO'|'DIVERGENTE', mensagem: str, volume: dict|None}
    """
    sb = get_supabase()
    nr = numero_rastreamento.strip()

    resp = (
        sb.table("conferencia_expedicao_volumes")
        .select("*")
        .eq("conferencia_id", conferencia_id)
        .eq("numero_rastreamento", nr)
        .limit(1)
        .execute()
    )

    if not resp.data:
        registrar_evento(
            conferencia_id=conferencia_id,
            tipo_evento="VOLUME_DIVERGENTE",
            numero_rastreamento_lido=nr,
            mensagem=f"Volume {nr} não pertence a esta conferência.",
            criado_por=conferido_por,
            usuario_id=usuario_id,
        )
        _incrementar_divergente(conferencia_id)
        recalcular_totais(conferencia_id)
        return {
            "status": "DIVERGENTE",
            "mensagem": f"Atenção — Volume {nr} não pertence a esta carga/conferência.",
            "volume": None,
        }

    volume = resp.data[0]

    if volume["status"] == "CONFERIDO":
        registrar_evento(
            conferencia_id=conferencia_id,
            volume_id=volume["id"],
            tipo_evento="VOLUME_JA_CONFERIDO",
            numero_rastreamento_lido=nr,
            mensagem=f"Volume {nr} já havia sido conferido anteriormente (releitura).",
            criado_por=conferido_por,
            usuario_id=usuario_id,
        )
        return {
            "status": "JA_CONFERIDO",
            "mensagem": f"Atenção — Etiqueta já conferida.",
            "volume": volume,
        }

    agora = datetime.now(timezone.utc).isoformat()
    sb.table("conferencia_expedicao_volumes").update({
        "status": "CONFERIDO",
        "conferido_em": agora,
        "conferido_por": conferido_por or None,
        "conferido_por_id": usuario_id or None,
        "updated_at": agora,
    }).eq("id", volume["id"]).execute()

    registrar_evento(
        conferencia_id=conferencia_id,
        volume_id=volume["id"],
        tipo_evento="VOLUME_CONFERIDO",
        numero_rastreamento_lido=nr,
        mensagem=f"Volume {nr} conferido com sucesso.",
        criado_por=conferido_por,
        usuario_id=usuario_id,
    )
    recalcular_totais(conferencia_id)
    return {
        "status": "CONFERIDO",
        "mensagem": f"OK — Volume {nr} conferido.",
        "volume": volume,
    }


def _incrementar_duplicado(conferencia_id: str) -> None:
    sb = get_supabase()
    conf = obter_conferencia(conferencia_id)
    if conf:
        agora = datetime.now(timezone.utc).isoformat()
        sb.table("conferencias_expedicao").update(
            {"total_duplicado": (conf.get("total_duplicado") or 0) + 1, "updated_at": agora}
        ).eq("id", conferencia_id).execute()


def _incrementar_divergente(conferencia_id: str) -> None:
    sb = get_supabase()
    conf = obter_conferencia(conferencia_id)
    if conf:
        agora = datetime.now(timezone.utc).isoformat()
        sb.table("conferencias_expedicao").update(
            {"total_divergente": (conf.get("total_divergente") or 0) + 1, "updated_at": agora}
        ).eq("id", conferencia_id).execute()


# ---------------------------------------------------------------------------
# Totais
# ---------------------------------------------------------------------------

def recalcular_totais(conferencia_id: str) -> None:
    sb = get_supabase()
    volumes = listar_volumes(conferencia_id)

    total_esperado = len(volumes)
    total_conferido = sum(1 for v in volumes if v["status"] == "CONFERIDO")
    total_faltante = sum(
        1 for v in volumes
        if v["status"] in ("PENDENTE", "FALTANTE_AUTORIZADO", "FALTANTE_NAO_AUTORIZADO")
    )

    # Divergentes e duplicados são rastreados por incremento direto (não criam registro de volume),
    # portanto preservamos os contadores atuais da conferência.
    conf = obter_conferencia(conferencia_id)
    total_divergente = (conf or {}).get("total_divergente", 0) or 0
    total_duplicado = (conf or {}).get("total_duplicado", 0) or 0

    agora = datetime.now(timezone.utc).isoformat()
    sb.table("conferencias_expedicao").update({
        "total_esperado": total_esperado,
        "total_conferido": total_conferido,
        "total_faltante": total_faltante,
        "total_divergente": total_divergente,
        "total_duplicado": total_duplicado,
        "updated_at": agora,
    }).eq("id", conferencia_id).execute()


# ---------------------------------------------------------------------------
# Fechamento
# ---------------------------------------------------------------------------

def encerrar_conferencia(
    conferencia_id: str,
    faltas_autorizadas: list[dict],
    faltas_nao_autorizadas: list[str],
    observacao: str = "",
    fechado_por: str = "",
    usuario_id: str | None = None,
) -> dict:
    """
    Encerra a conferência.
    faltas_autorizadas: lista de dicts {volume_id, motivo, autorizado_por, observacao}
    faltas_nao_autorizadas: lista de volume_ids
    """
    sb = get_supabase()
    agora = datetime.now(timezone.utc).isoformat()

    for falta in faltas_autorizadas:
        sb.table("conferencia_expedicao_volumes").update({
            "status": "FALTANTE_AUTORIZADO",
            "motivo_falta": falta.get("motivo"),
            "autorizado_por": falta.get("autorizado_por"),
            "falta_classificada_por_id": usuario_id or None,
            "observacao": falta.get("observacao"),
            "updated_at": agora,
        }).eq("id", falta["volume_id"]).execute()

        registrar_evento(
            conferencia_id=conferencia_id,
            volume_id=falta["volume_id"],
            tipo_evento="FALTA_AUTORIZADA",
            mensagem=f"Falta autorizada por {falta.get('autorizado_por')}. Motivo: {falta.get('motivo')}",
            criado_por=fechado_por,
            usuario_id=usuario_id,
        )

    for vol_id in faltas_nao_autorizadas:
        sb.table("conferencia_expedicao_volumes").update({
            "status": "FALTANTE_NAO_AUTORIZADO",
            "falta_classificada_por_id": usuario_id or None,
            "updated_at": agora,
        }).eq("id", vol_id).execute()

        registrar_evento(
            conferencia_id=conferencia_id,
            volume_id=vol_id,
            tipo_evento="FALTA_NAO_AUTORIZADA",
            mensagem="Volume marcado como faltante não autorizado.",
            criado_por=fechado_por,
            usuario_id=usuario_id,
        )

    volumes = listar_volumes(conferencia_id)
    pendentes_restantes = [v for v in volumes if v["status"] == "PENDENTE"]

    if not pendentes_restantes and not faltas_nao_autorizadas:
        status_final = "CONFERENCIA_PARCIAL_AUTORIZADA" if faltas_autorizadas else "CONFERENCIA_COMPLETA"
    elif faltas_nao_autorizadas:
        status_final = "CONFERENCIA_PARCIAL_COM_FALTA"
    else:
        status_final = "CONFERENCIA_COMPLETA"

    sb.table("conferencias_expedicao").update({
        "status": status_final,
        "encerrado_em": agora,
        "fechado_por": fechado_por or None,
        "fechado_por_id": usuario_id or None,
        "observacao_fechamento": observacao or None,
        "updated_at": agora,
    }).eq("id", conferencia_id).execute()

    recalcular_totais(conferencia_id)

    registrar_evento(
        conferencia_id=conferencia_id,
        tipo_evento="CONFERENCIA_ENCERRADA",
        mensagem=f"Conferência encerrada com status: {status_final}.",
        payload={"status_final": status_final},
        criado_por=fechado_por,
        usuario_id=usuario_id,
    )

    return {"status_final": status_final}


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------

def registrar_evento(
    conferencia_id: str,
    tipo_evento: str,
    volume_id: str | None = None,
    numero_rastreamento_lido: str | None = None,
    mensagem: str | None = None,
    payload: dict | None = None,
    criado_por: str = "",
    usuario_id: str | None = None,
) -> None:
    sb = get_supabase()
    sb.table("conferencia_expedicao_eventos").insert({
        "conferencia_id": conferencia_id,
        "tipo_evento": tipo_evento,
        "volume_id": volume_id,
        "usuario_id": usuario_id or None,
        "numero_rastreamento_lido": numero_rastreamento_lido,
        "mensagem": mensagem,
        "payload": payload,
        "criado_por": criado_por or None,
    }).execute()
