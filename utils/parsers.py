from datetime import date


def parse_volume(volume_texto: str) -> dict:
    """Parse '186/187' -> {volume_atual: 186, volume_total: 187, volume_texto: '186/187'}"""
    resultado = {"volume_texto": volume_texto, "volume_atual": None, "volume_total": None}
    if not volume_texto:
        return resultado
    partes = str(volume_texto).strip().split("/")
    if len(partes) == 2:
        try:
            resultado["volume_atual"] = int(partes[0])
            resultado["volume_total"] = int(partes[1])
        except ValueError:
            pass
    return resultado


def parse_data_br(data_str: str) -> str | None:
    """Parse '08/06/2026' -> '2026-06-08'. Retorna None se inválido."""
    if not data_str:
        return None
    try:
        dia, mes, ano = data_str.strip().split("/")
        return date(int(ano), int(mes), int(dia)).isoformat()
    except (ValueError, AttributeError):
        return None
