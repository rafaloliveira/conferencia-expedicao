import os
import bcrypt
from services.supabase_client import get_supabase

EMPRESA_ID = os.getenv("EMPRESA_ID") or None


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def autenticar_usuario(login: str, senha: str) -> dict | None:
    """
    Valida login/senha. Retorna dict do usuário se autenticado, None caso contrário.
    Levanta ValueError com mensagem amigável para erros esperados.
    """
    sb = get_supabase()
    resp = (
        sb.table("usuarios_operacao")
        .select("*")
        .eq("login", login.strip().lower())
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise ValueError("Usuário não encontrado.")

    usuario = resp.data[0]

    if not usuario.get("ativo"):
        raise ValueError("Usuário inativo. Contate o administrador.")

    if not verificar_senha(senha, usuario["senha_hash"]):
        raise ValueError("Senha incorreta.")

    return usuario


# ---------------------------------------------------------------------------
# Gestão de usuários
# ---------------------------------------------------------------------------

def criar_usuario(
    nome: str,
    login: str,
    senha: str,
    perfil: str = "CONFERENTE",
    email: str | None = None,
) -> dict:
    sb = get_supabase()
    dados = {
        "nome": nome.strip(),
        "login": login.strip().lower(),
        "senha_hash": hash_senha(senha),
        "perfil": perfil,
        "email": email.strip() if email else None,
        "ativo": True,
    }
    if EMPRESA_ID:
        dados["empresa_id"] = EMPRESA_ID

    resp = sb.table("usuarios_operacao").insert(dados).execute()
    return resp.data[0]


def listar_usuarios() -> list[dict]:
    sb = get_supabase()
    resp = (
        sb.table("usuarios_operacao")
        .select("id, nome, login, email, perfil, ativo, criado_em")
        .order("nome")
        .execute()
    )
    return resp.data or []


def ativar_inativar_usuario(usuario_id: str, ativo: bool) -> None:
    from datetime import datetime, timezone
    sb = get_supabase()
    sb.table("usuarios_operacao").update(
        {"ativo": ativo, "atualizado_em": datetime.now(timezone.utc).isoformat()}
    ).eq("id", usuario_id).execute()


def alterar_perfil(usuario_id: str, perfil: str) -> None:
    from datetime import datetime, timezone
    sb = get_supabase()
    sb.table("usuarios_operacao").update(
        {"perfil": perfil, "atualizado_em": datetime.now(timezone.utc).isoformat()}
    ).eq("id", usuario_id).execute()


def resetar_senha(usuario_id: str, nova_senha: str) -> None:
    from datetime import datetime, timezone
    sb = get_supabase()
    sb.table("usuarios_operacao").update(
        {"senha_hash": hash_senha(nova_senha), "atualizado_em": datetime.now(timezone.utc).isoformat()}
    ).eq("id", usuario_id).execute()


def alterar_senha_propria(usuario_id: str, senha_atual: str, nova_senha: str) -> None:
    """Permite que o próprio usuário troque sua senha, validando a senha atual."""
    sb = get_supabase()
    resp = (
        sb.table("usuarios_operacao")
        .select("senha_hash")
        .eq("id", usuario_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise ValueError("Usuário não encontrado.")
    if not verificar_senha(senha_atual, resp.data[0]["senha_hash"]):
        raise ValueError("Senha atual incorreta.")
    resetar_senha(usuario_id, nova_senha)
