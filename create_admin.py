"""Script para criar o primeiro usuário ADMIN no sistema."""
import sys
import getpass
from dotenv import load_dotenv

load_dotenv()

from services.auth_service import criar_usuario


def main():
    print("=== Criar usuário ADMIN ===\n")
    nome = input("Nome completo: ").strip()
    if not nome:
        print("Nome obrigatório.")
        sys.exit(1)

    login = input("Login: ").strip().lower()
    if not login:
        print("Login obrigatório.")
        sys.exit(1)

    email = input("E-mail (opcional, Enter para pular): ").strip() or None

    senha = getpass.getpass("Senha: ")
    if len(senha) < 6:
        print("Senha deve ter pelo menos 6 caracteres.")
        sys.exit(1)

    confirmacao = getpass.getpass("Confirmar senha: ")
    if senha != confirmacao:
        print("Senhas não conferem.")
        sys.exit(1)

    try:
        usuario = criar_usuario(nome=nome, login=login, senha=senha, perfil="ADMIN", email=email)
        print(f"\nAdministrador criado com sucesso!")
        print(f"  ID:    {usuario['id']}")
        print(f"  Nome:  {usuario['nome']}")
        print(f"  Login: {usuario['login']}")
        print(f"  Perfil: {usuario['perfil']}")
    except Exception as exc:
        print(f"\nErro ao criar administrador: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
