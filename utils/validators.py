import re


def validar_chave_nfe(chave: str) -> tuple[bool, str]:
    """Valida chave NF-e: exatamente 44 dígitos numéricos."""
    if not chave:
        return False, "Chave NF-e não informada."
    chave = chave.strip()
    if not re.fullmatch(r"\d{44}", chave):
        return False, f"Chave NF-e inválida. Deve ter exatamente 44 dígitos numéricos (recebido: {len(chave)} caracteres)."
    return True, ""


def validar_nr(nr: str) -> tuple[bool, str]:
    """Valida número de rastreamento: não vazio e numérico."""
    if not nr:
        return False, "Número de rastreamento não informado."
    nr = nr.strip()
    if not nr.isdigit():
        return False, "Número de rastreamento deve conter apenas dígitos."
    return True, ""
