import os
import requests
from dotenv import load_dotenv
from utils.parsers import parse_volume, parse_data_br

load_dotenv(override=True)

SSW_BASE_URL = "https://ssw.inf.br/api"


def _get_env(nome: str) -> str:
    valor = os.getenv(nome, "")
    return str(valor).strip()


def _validar_config_ssw():
    obrigatorias = [
        "SSW_DOMAIN",
        "SSW_USERNAME",
        "SSW_PASSWORD",
        "SSW_CNPJ_EDI",
    ]

    faltando = []

    for nome in obrigatorias:
        if not _get_env(nome):
            faltando.append(nome)

    if faltando:
        raise RuntimeError(
            "Variáveis SSW ausentes no .env: " + ", ".join(faltando)
        )


def gerar_token_ssw() -> str:
    """
    Gera e retorna token SSW.
    Não usa raise_for_status antes de ler o JSON, porque a SSW pode retornar
    HTTP 401 com uma mensagem útil no corpo.
    """

    _validar_config_ssw()

    payload = {
        "domain": _get_env("SSW_DOMAIN"),
        "username": _get_env("SSW_USERNAME"),
        "password": _get_env("SSW_PASSWORD"),
        "cnpj_edi": _get_env("SSW_CNPJ_EDI"),
        "force": True,
    }

    try:
        resp = requests.post(
            f"{SSW_BASE_URL}/generateToken",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Erro de conexão ao gerar token SSW: {exc}") from exc

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(
            f"Resposta inválida ao gerar token SSW. "
            f"HTTP {resp.status_code}: {resp.text}"
        )

    if not data.get("sucess"):
        msg = data.get("message", "Resposta inesperada da API SSW ao gerar token.")
        raise RuntimeError(
            f"Falha ao gerar token SSW. "
            f"HTTP {resp.status_code}. "
            f"Mensagem SSW: {msg}. "
            f"Domínio: {payload['domain']}. "
            f"Usuário: {payload['username']}. "
            f"CNPJ EDI: {payload['cnpj_edi']}."
        )

    token = data.get("token")

    if not token:
        raise RuntimeError("SSW retornou sucesso, mas não retornou token.")

    return token


def consultar_nr_por_chave(chave_nfe: str) -> list[dict]:
    """
    Consulta API SSW consultaNr pela chave NF-e.
    Retorna lista de volumes normalizados prontos para inserção no Supabase.
    """

    token = gerar_token_ssw()

    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(
            f"{SSW_BASE_URL}/consultaNr",
            params={"chave_nfe": chave_nfe.strip()},
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Erro de conexão ao consultar NF-e na SSW: {exc}") from exc

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(
            f"Resposta inválida ao consultar NF-e na SSW. "
            f"HTTP {resp.status_code}: {resp.text}"
        )

    if data.get("success") is False:
        msg = data.get("message", "Resposta inesperada da API SSW ao consultar NF-e.")
        raise RuntimeError(
            f"SSW retornou erro. "
            f"HTTP {resp.status_code}. "
            f"Mensagem SSW: {msg}"
        )

    # success=true sem etiquetas é resultado válido (NF sem NR gerado, chave ainda não disponível etc.)
    etiquetas = data.get("etiquetas") or []

    if not etiquetas:
        return []

    return [_normalizar_etiqueta(e, chave_nfe.strip()) for e in etiquetas]


def _normalizar_etiqueta(etiqueta: dict, chave_nfe: str) -> dict:
    """Transforma a etiqueta SSW no formato esperado pelo banco."""

    vol_info = parse_volume(etiqueta.get("volume", ""))
    qr = etiqueta.get("qrCode") or {}

    nr = (
        etiqueta.get("numeroRastreamento")
        or qr.get("numeroRastreamento")
        or ""
    )

    return {
        "chave_nfe": chave_nfe,
        "nota_fiscal": etiqueta.get("notaFiscal"),
        "ctrc": etiqueta.get("ctrc"),
        "numero_rastreamento": str(nr).strip(),
        "seq_ctrc": qr.get("seqCtrc"),
        "volume_texto": vol_info["volume_texto"],
        "volume_atual": vol_info["volume_atual"],
        "volume_total": vol_info["volume_total"],
        "unidade_entrega": etiqueta.get("unidadeEntrega"),
        "unidade_centralizadora": etiqueta.get("unidadeCentralizadora"),
        "setor_destino": etiqueta.get("setorDestino"),
        "data_previsao_entrega": parse_data_br(etiqueta.get("dataPrevisaoEntrega")),
        "remetente": etiqueta.get("remetente"),
        "peso": etiqueta.get("peso"),
        "endereco_entrega": etiqueta.get("entrega"),
        "site": etiqueta.get("site"),
        "praca": etiqueta.get("praca"),
        "payload_ssw": etiqueta,
    }