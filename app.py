import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from services.auth_service import (
    autenticar_usuario,
    criar_usuario,
    listar_usuarios,
    ativar_inativar_usuario,
    alterar_perfil,
    resetar_senha,
    alterar_senha_propria,
)
from services.conferencia_service import (
    obter_ou_criar_conferencia,
    obter_conferencia,
    adicionar_nfe_na_conferencia,
    listar_volumes,
    listar_ocorrencias,
    registrar_bipagem,
    encerrar_conferencia,
    listar_conferencias_em_andamento,
    excluir_conferencia,
)
from services.relatorio_service import (
    relatorio_por_conferente,
    relatorio_por_carga,
    relatorio_erros,
    listar_usuarios_opcoes,
    listar_cargas_por_conferente,
)
from utils.validators import validar_chave_nfe, validar_nr

STATUS_LABEL = {
    "EM_CONFERENCIA":                 "🟡 Em conferência",
    "CONFERENCIA_COMPLETA":           "🟢 Completa",
    "CONFERENCIA_PARCIAL_AUTORIZADA": "🔵 Parcial autorizada",
    "CONFERENCIA_PARCIAL_COM_FALTA":  "🔴 Parcial com falta",
    "CANCELADA":                      "⚫ Cancelada",
}

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Conferência de Expedição",
    page_icon="📦",
    layout="centered",
)

st.markdown("""
<style>
/* ── Inputs maiores (previne zoom iOS + melhora toque) ── */
input[type="text"], input[type="password"] {
    font-size: 16px !important;
    padding: 0.55rem 0.75rem !important;
    border-radius: 6px !important;
}

/* ── Botões mais altos e com boa área de toque ── */
.stButton > button {
    min-height: 2.8rem !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    width: 100% !important;
}
.stButton > button[kind="primary"] {
    min-height: 3.2rem !important;
    font-size: 1.05rem !important;
}
.stFormSubmitButton > button {
    min-height: 2.8rem !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    width: 100% !important;
}

/* ── Expanders com borda sutil ── */
[data-testid="stExpander"] {
    border: 1px solid #dee2e6 !important;
    border-radius: 8px !important;
    margin-bottom: 6px;
}

/* ── Remover padding excessivo em colunas de cards ── */
[data-testid="column"] {
    padding: 0 4px !important;
}

/* ── Mini cards do resumo da conferência (grade horizontal) ── */
.mini-metric-card {
    background: #111827;
    border: 1px solid #374151;
    border-radius: 10px;
    padding: 8px 4px;
    text-align: center;
    min-height: 64px;
}
.mini-metric-label {
    font-size: 0.68rem;
    color: #d1d5db;
    line-height: 1.1;
    white-space: nowrap;
    margin-bottom: 6px;
}
.mini-metric-value {
    font-size: 1.45rem;
    font-weight: 800;
    color: #ffffff;
    line-height: 1;
}
@media (max-width: 480px) {
    .mini-metric-card {
        padding: 7px 2px;
        min-height: 58px;
        border-radius: 8px;
    }
    .mini-metric-label {
        font-size: 0.58rem;
    }
    .mini-metric-value {
        font-size: 1.25rem;
    }
}

/* ── Força os 5 indicadores do resumo a ficarem sempre em UMA linha,
   mesmo no celular (o Streamlit, por padrão, quebra st.columns para
   layout vertical em telas estreitas) ── */
div[class*="st-key-resumo_conferencia"] div[data-testid="stHorizontalBlock"] {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0.25rem !important;
}
div[class*="st-key-resumo_conferencia"] div[data-testid="stColumn"] {
    flex: 1 1 0 !important;
    width: 0 !important;
    min-width: 0 !important;
    padding: 0 0.15rem !important;
}
</style>
""", unsafe_allow_html=True)


def render_resumo_conferencia(conf: dict):
    """Exibe os 5 indicadores da conferência lado a lado em uma única linha,
    via st.columns(5) + mini cards HTML (evita o empilhamento vertical que
    st.metric causa em telas estreitas)."""
    total_esperado   = conf.get("total_esperado") or 0
    total_conferido  = conf.get("total_conferido") or 0
    total_faltante   = conf.get("total_faltante") or 0
    total_divergente = conf.get("total_divergente") or 0
    total_duplicado  = conf.get("total_duplicado") or 0

    cards = [
        ("📋", "Esper.", total_esperado),
        ("✅", "Conf.",  total_conferido),
        ("⏳", "Pend.",  total_faltante),
        ("⚠️", "Div.",   total_divergente),
        ("🔁", "Repet.", total_duplicado),
    ]

    with st.container(key="resumo_conferencia"):
        cols = st.columns(5)
        for col, (icone, label, valor) in zip(cols, cards):
            with col:
                st.markdown(
                    f"""
                    <div class="mini-metric-card">
                        <div class="mini-metric-label">{icone} {label}</div>
                        <div class="mini-metric-value">{valor}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _autofocus(aria_label_substring: str, attempts: int = 8, delay_ms: int = 150):
    """Foca automaticamente o input com o aria-label informado, para receber a
    leitura do leitor de código de barras sem precisar clicar no campo."""
    safe = aria_label_substring.replace("\\", "\\\\").replace('"', '\\"')
    components.html(
        f"""
        <script>
        (function() {{
            let tries = 0;
            const maxTries = {attempts};
            const tryFocus = () => {{
                tries += 1;
                const doc = window.parent.document;
                const inputs = doc.querySelectorAll('input[aria-label]');
                for (const inp of inputs) {{
                    const label = inp.getAttribute('aria-label') || '';
                    if (label.includes("{safe}")) {{
                        if (doc.activeElement !== inp) {{
                            inp.focus();
                        }}
                        return;
                    }}
                }}
                if (tries < maxTries) setTimeout(tryFocus, {delay_ms});
            }};
            setTimeout(tryFocus, {delay_ms});
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


# ---------------------------------------------------------------------------
# Estado de sessão
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "usuario_id": None,
    "usuario_nome": None,
    "usuario_login": None,
    "usuario_perfil": None,
    "usuario_empresa_id": None,
    "pagina": "conferencia",
    "conferencia_id": None,
    "numero_carga": None,
    "conferencia_cache": None,
    "mensagem_pos_fechamento": None,
    "_vol_all": None,
    "_vol_ocorrencias": None,
    "ultima_bipagem": None,
    "ultima_nr_lido": "",
    "modo_encerramento": False,
    "autorizacoes": {},
    "dialog_conclusao_dismissed": None,
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _usuario_logado() -> bool:
    return bool(st.session_state.usuario_id)


def _perfil() -> str:
    return st.session_state.usuario_perfil or ""


def _pode(perfis: list[str]) -> bool:
    return _perfil() in perfis


# ---------------------------------------------------------------------------
# Tela de login
# ---------------------------------------------------------------------------

def tela_login():
    st.markdown("<br>", unsafe_allow_html=True)
    st.title("📦 Conferência de Expedição")
    st.markdown("---")
    st.subheader("Acesso ao sistema")

    with st.form("form_login"):
        login_input = st.text_input("Login", placeholder="seu.login")
        senha_input = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", use_container_width=True)

    if entrar:
        if not login_input or not senha_input:
            st.error("Informe login e senha.")
            return
        try:
            usuario = autenticar_usuario(login_input, senha_input)
            st.session_state.usuario_id = usuario["id"]
            st.session_state.usuario_nome = usuario["nome"]
            st.session_state.usuario_login = usuario["login"]
            st.session_state.usuario_perfil = usuario["perfil"]
            st.session_state.usuario_empresa_id = usuario.get("empresa_id")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Erro ao acessar o sistema: {exc}")


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

def _sidebar():
    with st.sidebar:
        st.markdown(f"**{st.session_state.usuario_nome}**")
        st.caption(f"`{st.session_state.usuario_login}` · {_perfil()}")
        st.markdown("---")

        if st.button("📦 Conferência", use_container_width=True):
            st.session_state.pagina = "conferencia"
            _reset_conferencia()
            st.rerun()

        if st.button("📜 Minhas Cargas", use_container_width=True):
            st.session_state.pagina = "minhas_cargas"
            _reset_conferencia()
            st.rerun()

        if _pode(["ADMIN", "SUPERVISOR"]):
            if st.button("📊 Relatórios", use_container_width=True):
                st.session_state.pagina = "relatorios"
                _reset_conferencia()
                st.rerun()

        if _pode(["ADMIN", "SUPERVISOR"]):
            if st.button("👤 Usuários", use_container_width=True):
                st.session_state.pagina = "usuarios"
                _reset_conferencia()
                st.rerun()

        if st.button("🔑 Minha Senha", use_container_width=True):
            st.session_state.pagina = "minha_senha"
            _reset_conferencia()
            st.rerun()

        st.markdown("---")
        if st.button("Sair", use_container_width=True):
            for k in list(_DEFAULTS.keys()):
                st.session_state[k] = _DEFAULTS[k]
            st.rerun()


def _reset_conferencia():
    st.session_state.conferencia_id = None
    st.session_state.numero_carga = None
    st.session_state.conferencia_cache = None
    st.session_state["_vol_all"] = None
    st.session_state["_vol_ocorrencias"] = None
    st.session_state.ultima_bipagem = None
    st.session_state.ultima_nr_lido = ""
    st.session_state.modo_encerramento = False
    st.session_state.autorizacoes = {}
    st.session_state.dialog_conclusao_dismissed = None


def _limpar_conferencia_atual():
    """Limpa estado da conferência e volta para tela inicial (pós-encerramento)."""
    st.session_state.conferencia_id = None
    st.session_state.numero_carga = None
    st.session_state.conferencia_cache = None
    st.session_state["_vol_all"] = None
    st.session_state["_vol_ocorrencias"] = None
    st.session_state.ultima_bipagem = None
    st.session_state.ultima_nr_lido = ""
    st.session_state.modo_encerramento = False
    st.session_state.autorizacoes = {}
    st.session_state.dialog_conclusao_dismissed = None


def _reload_conferencia() -> dict | None:
    if not st.session_state.conferencia_id:
        return None
    try:
        conf = obter_conferencia(st.session_state.conferencia_id)
        if conf:
            st.session_state.conferencia_cache = conf
        return conf
    except Exception as exc:
        cached = st.session_state.get("conferencia_cache")
        if cached:
            st.warning("⚠️ Falha temporária ao atualizar a conferência. Exibindo último estado conhecido.")
        else:
            st.error(f"Falha ao carregar conferência: {exc}")
        return cached


# ---------------------------------------------------------------------------
# Tela: Entrada da carga
# ---------------------------------------------------------------------------

def tela_entrada():
    st.title("📦 Conferência de Expedição")

    msg = st.session_state.get("mensagem_pos_fechamento")
    if msg:
        st.success(msg)
        st.session_state["mensagem_pos_fechamento"] = None

    st.markdown(f"Olá, **{st.session_state.usuario_nome}**.")
    st.markdown("---")

    with st.form("form_carga"):
        numero_carga = st.text_input("Número da Carga", placeholder="Ex: 123456")
        submeter = st.form_submit_button("Iniciar / Carregar Conferência", use_container_width=True)

    if submeter:
        numero_carga = numero_carga.strip()
        if not numero_carga:
            st.error("Informe o número da carga.")
            return
        try:
            conferencia = obter_ou_criar_conferencia(
                numero_carga,
                criado_por=st.session_state.usuario_nome,
                usuario_id=st.session_state.usuario_id,
            )
            st.session_state.conferencia_id = conferencia["id"]
            st.session_state.numero_carga = numero_carga
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao iniciar conferência: {exc}")

    _secao_cargas_em_andamento()


def _secao_cargas_em_andamento():
    """Lista cargas EM_CONFERENCIA para retomada (após erro de conexão, etc.)
    ou exclusão (apenas pelo criador ou ADMIN)."""
    st.markdown("---")
    st.subheader("📋 Cargas em andamento")

    pode_ver_todas = _pode(["ADMIN", "SUPERVISOR"])
    try:
        cargas = listar_conferencias_em_andamento(
            usuario_id=st.session_state.usuario_id,
            todas=pode_ver_todas,
        )
    except Exception as exc:
        st.warning(f"Não foi possível carregar cargas em andamento: {exc}")
        return

    if not cargas:
        st.caption("Nenhuma carga em andamento.")
        return

    for c in cargas:
        pode_excluir = _pode(["ADMIN"]) or c.get("criado_por_id") == st.session_state.usuario_id
        confirm_key = f"confirm_del_{c['id']}"

        with st.expander(
            f"📦 Carga {c['numero_carga']}  ·  "
            f"{c.get('total_conferido', 0)}/{c.get('total_esperado', 0)} conferidos  ·  "
            f"por {c.get('criado_por') or '-'}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶ Continuar", key=f"cont_{c['id']}", use_container_width=True):
                    st.session_state.conferencia_id = c["id"]
                    st.session_state.numero_carga = c["numero_carga"]
                    st.rerun()
            with col2:
                if pode_excluir:
                    if not st.session_state.get(confirm_key):
                        if st.button("🗑 Excluir", key=f"del_{c['id']}", use_container_width=True):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    else:
                        if st.button("⚠️ Confirmar exclusão", key=f"del_conf_{c['id']}", use_container_width=True):
                            try:
                                excluir_conferencia(
                                    c["id"],
                                    st.session_state.usuario_id,
                                    st.session_state.usuario_perfil,
                                )
                                st.session_state.pop(confirm_key, None)
                                st.success("Carga excluída.")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                        if st.button("Cancelar", key=f"del_cancel_{c['id']}", use_container_width=True):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()


# ---------------------------------------------------------------------------
# Dialog: Conferência concluída
# ---------------------------------------------------------------------------

@st.dialog("✅ Conferência concluída")
def _dialog_conferencia_concluida(conf: dict):
    st.markdown(
        f"Todos os **{conf.get('total_esperado', 0)}** volumes da carga "
        f"**{conf['numero_carga']}** foram conferidos."
    )
    st.markdown("Deseja encerrar a conferência agora?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Encerrar agora", type="primary", use_container_width=True):
            st.session_state.modo_encerramento = True
            st.session_state.dialog_conclusao_dismissed = conf["id"]
            st.rerun()
    with c2:
        if st.button("Continuar conferindo", use_container_width=True):
            st.session_state.dialog_conclusao_dismissed = conf["id"]
            st.rerun()


# ---------------------------------------------------------------------------
# Tela: Conferência ativa
# ---------------------------------------------------------------------------

def tela_conferencia():
    conf = _reload_conferencia()
    if not conf:
        st.error("Conferência não encontrada.")
        _reset_conferencia()
        st.rerun()
        return

    encerrada = conf["status"] != "EM_CONFERENCIA"

    # ── Cabeçalho ──
    col_h, col_v = st.columns([4, 1])
    with col_h:
        st.markdown(f"### 📦 Carga {conf['numero_carga']}")
        st.caption(
            f"{STATUS_LABEL.get(conf['status'], conf['status'])}  ·  "
            f"{st.session_state.usuario_nome}"
        )
    with col_v:
        if st.button("← Voltar", use_container_width=True):
            _reset_conferencia()
            st.rerun()

    st.markdown("---")

    # ── Cards resumo (grade horizontal, 5 indicadores em uma linha) ──
    render_resumo_conferencia(conf)

    st.markdown("---")

    if encerrada:
        st.info(f"Conferência encerrada: **{conf['status']}**")
        _exibir_volumes_expandidos(conf["id"], auto_load=True)
        return

    tem_volumes = conf.get("total_esperado", 0) > 0

    # ══════════════════════════════════════════════════════════════════
    # ESTADO 1 — Sem volumes: foco em adicionar NF-e
    # ══════════════════════════════════════════════════════════════════
    if not tem_volumes:
        st.info(
            "Nenhuma NF-e adicionada ainda. "
            "Adicione a chave NF-e para carregar os volumes esperados antes de iniciar a conferência."
        )
        st.markdown("---")
        _secao_adicionar_nfe(conf)
        st.markdown(
            "<p style='color:#6c757d;font-size:0.9em;margin-top:8px;'>"
            "Depois de carregar os volumes, a bipagem será liberada.</p>",
            unsafe_allow_html=True,
        )
        return

    # ══════════════════════════════════════════════════════════════════
    # ESTADO 2 — Com volumes: foco na bipagem
    # ══════════════════════════════════════════════════════════════════

    tudo_conferido = conf.get("total_esperado", 0) > 0 and conf.get("total_faltante", 0) == 0
    if (
        tudo_conferido
        and not st.session_state.modo_encerramento
        and st.session_state.dialog_conclusao_dismissed != conf["id"]
    ):
        _dialog_conferencia_concluida(conf)

    # ── Bipagem (foco principal) ──
    _secao_bipagem(conf)

    st.markdown("---")

    # ── Adicionar outra NF-e (recolhido) ──
    with st.expander("📄 Adicionar outra NF-e"):
        _secao_adicionar_nfe(conf)

    st.markdown("---")

    # ── Volumes (recolhidos) ──
    _exibir_volumes_expandidos(conf["id"])

    st.markdown("---")

    # ── Encerramento ──
    if not st.session_state.modo_encerramento:
        if st.button("🔒 Encerrar Conferência", type="primary", use_container_width=True):
            st.session_state.modo_encerramento = True
            st.rerun()
    else:
        _secao_encerramento(conf)


# ---------------------------------------------------------------------------
# Card de feedback da bipagem
# ---------------------------------------------------------------------------

def _feedback_card():
    ultima = st.session_state.ultima_bipagem
    if not ultima:
        return

    status = ultima.get("status", "")
    vol = ultima.get("volume") or {}
    nr = vol.get("numero_rastreamento") or st.session_state.ultima_nr_lido
    nf = vol.get("nota_fiscal") or ""
    vol_txt = vol.get("volume_texto") or ""
    ctrc = vol.get("ctrc") or ""

    cfg = {
        "CONFERIDO":    ("#d1e7dd", "#0a3622", "border-left:5px solid #0a3622", "✅ OK — Volume conferido"),
        "JA_CONFERIDO": ("#fff3cd", "#664d03", "border-left:5px solid #b8860b", "⚠️ Atenção — Etiqueta já conferida"),
        "DUPLICADO":    ("#fff3cd", "#664d03", "border-left:5px solid #664d03", "⚠️ Atenção — Volume já conferido"),
        "DIVERGENTE":   ("#f8d7da", "#58151c", "border-left:5px solid #58151c", "❌ Divergente — Não pertence a esta carga"),
        "ERRO":         ("#f8d7da", "#58151c", "border-left:5px solid #58151c", "❌ Erro"),
    }
    bg, fg, border, titulo = cfg.get(status, ("#e9ecef", "#212529", "", "ℹ️ Info"))

    partes = []
    if nr:      partes.append(f"NR: <b>{nr}</b>")
    if nf:      partes.append(f"NF: <b>{nf}</b>")
    if vol_txt: partes.append(f"Vol: <b>{vol_txt}</b>")
    if ctrc:    partes.append(f"CTRC: <b>{ctrc}</b>")

    detalhe = ""
    if partes:
        detalhe = (
            f'<div style="margin-top:6px;font-size:0.85em;opacity:0.9;">'
            + " &nbsp;|&nbsp; ".join(partes)
            + "</div>"
        )

    st.markdown(
        f'<div style="background:{bg};color:{fg};{border};'
        f'border-radius:10px;padding:14px 16px;margin:8px 0 12px 0;">'
        f'<div style="font-size:1.05em;font-weight:700;">{titulo}</div>'
        f'{detalhe}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Seção: Bipagem (foco mobile)
# ---------------------------------------------------------------------------

def _secao_bipagem(conf: dict):
    st.subheader("🔍 Bipar etiqueta")

    _feedback_card()

    with st.form("form_bipagem", clear_on_submit=True):
        nr = st.text_input(
            "Número de Rastreamento (NR)",
            placeholder="Bipe ou digite o NR da etiqueta",
            label_visibility="collapsed",
        )
        confirmar = st.form_submit_button("✔ Confirmar leitura", use_container_width=True, type="primary")

    _autofocus("Número de Rastreamento")

    if confirmar:
        valido, erro = validar_nr(nr)
        if not valido:
            st.session_state.ultima_bipagem = {"status": "ERRO", "mensagem": erro}
            st.session_state.ultima_nr_lido = nr.strip()
            st.rerun()
            return
        try:
            resultado = registrar_bipagem(
                conf["id"],
                nr.strip(),
                conferido_por=st.session_state.usuario_nome,
                usuario_id=st.session_state.usuario_id,
            )
            st.session_state.ultima_bipagem = resultado
            st.session_state.ultima_nr_lido = nr.strip()
            st.rerun()
        except Exception as exc:
            st.session_state.ultima_bipagem = {"status": "ERRO", "mensagem": str(exc)}
            st.session_state.ultima_nr_lido = nr.strip()
            st.rerun()


# ---------------------------------------------------------------------------
# Seção: Adicionar NF-e (vai dentro de expander)
# ---------------------------------------------------------------------------

def _secao_adicionar_nfe(conf: dict):
    with st.form("form_nfe", clear_on_submit=True):
        chave = st.text_input(
            "Chave NF-e (44 dígitos)",
            placeholder="35260406191751000119550010001840111002349150",
            max_chars=44,
        )
        adicionar = st.form_submit_button("Adicionar NF-e", use_container_width=True)

    _autofocus("Chave NF-e")

    if adicionar:
        valido, erro = validar_chave_nfe(chave)
        if not valido:
            st.error(erro)
            return
        with st.spinner("Consultando SSW e carregando volumes..."):
            try:
                resultado = adicionar_nfe_na_conferencia(
                    conf["id"],
                    chave.strip(),
                    criado_por=st.session_state.usuario_nome,
                    usuario_id=st.session_state.usuario_id,
                )
                if resultado["adicionados"] > 0:
                    st.success(
                        f"✅ {resultado['adicionados']} volume(s) adicionado(s) "
                        f"de {resultado['total_retornados']} retornado(s) pela SSW."
                    )
                if resultado["duplicados"] > 0:
                    st.warning(f"⚠️ {resultado['duplicados']} volume(s) já existiam nesta conferência (ignorados).")
                if resultado["erros"]:
                    st.error("Erros ao inserir alguns volumes:\n" + "\n".join(resultado["erros"]))
                if resultado["total_retornados"] == 0:
                    st.warning(
                        "**Nenhuma etiqueta NR encontrada para esta chave NF-e.**\n\n"
                        "Possíveis causas:\n"
                        "- a chave não possui etiqueta NR gerada;\n"
                        "- a nota já foi baixada, cancelada ou finalizada;\n"
                        "- a nota está agrupada em outro documento;\n"
                        "- a etiqueta foi gerada por outro processo/unidade;\n"
                        "- a chave informada não é a chave NF-e correta."
                    )
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao consultar SSW: {exc}")


# ---------------------------------------------------------------------------
# Volumes em expanders (mobile-first)
# ---------------------------------------------------------------------------

def _exibir_volumes_expandidos(conferencia_id: str, auto_load: bool = False):
    conf_cache = st.session_state.get("conferencia_cache") or {}
    n_pend = conf_cache.get("total_faltante",  0) or 0
    n_conf = conf_cache.get("total_conferido", 0) or 0
    n_div  = conf_cache.get("total_divergente", 0) or 0

    volumes_cache   = st.session_state.get("_vol_all")
    ocorrencias_cache = st.session_state.get("_vol_ocorrencias")

    if auto_load and volumes_cache is None:
        try:
            volumes_cache = listar_volumes(conferencia_id)
            ocorrencias_cache = listar_ocorrencias(conferencia_id)
            st.session_state["_vol_all"] = volumes_cache
            st.session_state["_vol_ocorrencias"] = ocorrencias_cache
        except Exception as exc:
            st.warning(f"Falha temporária ao carregar volumes: {exc}")

    pendentes  = [v for v in (volumes_cache or []) if v["status"] == "PENDENTE"]
    conferidos = [v for v in (volumes_cache or []) if v["status"] == "CONFERIDO"]
    ocorrencias = ocorrencias_cache or []

    def _btn_atualizar(key_suffix: str):
        if st.button("🔄 Atualizar", key=f"btn_upd_{key_suffix}", use_container_width=True):
            try:
                st.session_state["_vol_all"] = listar_volumes(conferencia_id)
                st.session_state["_vol_ocorrencias"] = listar_ocorrencias(conferencia_id)
                st.rerun()
            except Exception as exc:
                st.warning(f"Falha ao atualizar: {exc}")

    # ── Pendentes ──
    with st.expander(f"⏳ Pendentes ({n_pend})", expanded=False):
        _btn_atualizar("pend")
        if volumes_cache is None:
            st.caption("Clique em Atualizar para carregar a lista.")
        elif not pendentes:
            st.info("Nenhum volume pendente.")
        else:
            for v in pendentes:
                st.markdown(
                    f"**NF** {v.get('nota_fiscal') or '-'} &nbsp;·&nbsp; "
                    f"**Vol** {v.get('volume_texto') or '-'} &nbsp;·&nbsp; "
                    f"**NR** `{v.get('numero_rastreamento') or '-'}` &nbsp;·&nbsp; "
                    f"**CTRC** {v.get('ctrc') or '-'}"
                )
                st.divider()

    # ── Conferidos ──
    with st.expander(f"✅ Conferidos ({n_conf})", expanded=False):
        _btn_atualizar("conf")
        if volumes_cache is None:
            st.caption("Clique em Atualizar para carregar a lista.")
        elif not conferidos:
            st.info("Nenhum volume conferido ainda.")
        else:
            for v in conferidos:
                hora = (v.get("conferido_em") or "")[:16].replace("T", " ")
                st.markdown(
                    f"**NF** {v.get('nota_fiscal') or '-'} &nbsp;·&nbsp; "
                    f"**Vol** {v.get('volume_texto') or '-'} &nbsp;·&nbsp; "
                    f"**NR** `{v.get('numero_rastreamento') or '-'}` &nbsp;·&nbsp; "
                    f"**Hora** {hora}"
                )
                st.divider()

    # ── Ocorrências (divergentes + já conferidos) ──
    with st.expander(f"⚠️ Ocorrências ({n_div})", expanded=False):
        _btn_atualizar("ocorr")
        if ocorrencias_cache is None:
            st.caption("Clique em Atualizar para carregar a lista.")
        elif not ocorrencias:
            st.info("Nenhuma ocorrência registrada.")
        else:
            _ICONE_OCORR = {
                "VOLUME_DIVERGENTE":   "🟠",
                "VOLUME_JA_CONFERIDO": "🔁",
                "VOLUME_DUPLICADO":    "🔁",
            }
            for ev in ocorrencias:
                tipo = ev.get("tipo_evento", "")
                icone = _ICONE_OCORR.get(tipo, "⚠️")
                hora = (ev.get("created_at") or "")[:16].replace("T", " ")
                nr_lido = ev.get("numero_rastreamento_lido") or "-"
                msg = ev.get("mensagem") or ""
                st.markdown(
                    f"{icone} **{tipo}** &nbsp;·&nbsp; "
                    f"NR `{nr_lido}` &nbsp;·&nbsp; "
                    f"{hora}"
                )
                if msg:
                    st.caption(msg)
                st.divider()


# ---------------------------------------------------------------------------
# Seção: Encerramento
# ---------------------------------------------------------------------------

def _secao_encerramento(conf: dict):
    st.subheader("🔒 Encerramento da Conferência")

    volumes  = listar_volumes(conf["id"])
    pendentes = [v for v in volumes if v["status"] == "PENDENTE"]

    if not pendentes:
        st.success("Todos os volumes foram conferidos. Será fechada como **CONFERÊNCIA COMPLETA**.")
        obs = st.text_area("Observação (opcional)", key="obs_encerramento")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Confirmar encerramento", type="primary", use_container_width=True):
                _executar_encerramento(conf["id"], [], [], obs)
        with c2:
            if st.button("Cancelar", use_container_width=True):
                st.session_state.modo_encerramento = False
                st.rerun()
        return

    st.warning(f"Existem **{len(pendentes)}** volume(s) pendente(s). Classifique-os antes de encerrar.")

    autorizacoes = st.session_state.autorizacoes

    for vol in pendentes:
        vol_id = vol["id"]
        nr     = vol["numero_rastreamento"]
        nf     = vol.get("nota_fiscal", "")
        ctrc   = vol.get("ctrc", "")

        with st.expander(f"NR: {nr}  ·  NF: {nf}  ·  CTRC: {ctrc}", expanded=True):
            autorizar = st.checkbox(
                "Autorizar esta falta",
                key=f"chk_{vol_id}",
                value=vol_id in autorizacoes,
            )
            if autorizar:
                motivo       = st.text_input("Motivo *",          key=f"motivo_{vol_id}")
                autorizado_por = st.text_input("Autorizado por *", key=f"auth_{vol_id}")
                observacao   = st.text_input("Observação (opcional)", key=f"obs_{vol_id}")
                autorizacoes[vol_id] = {
                    "volume_id": vol_id,
                    "motivo": motivo,
                    "autorizado_por": autorizado_por,
                    "observacao": observacao,
                }
            else:
                autorizacoes.pop(vol_id, None)

    st.session_state.autorizacoes = autorizacoes

    st.markdown("---")
    obs_geral = st.text_area("Observação geral do fechamento", key="obs_geral")

    autorizados_ids    = set(autorizacoes.keys())
    pendentes_ids      = {v["id"] for v in pendentes}
    nao_autorizados_ids = list(pendentes_ids - autorizados_ids)
    autorizados_lista  = list(autorizacoes.values())

    pode_encerrar = all(
        d.get("motivo") and d.get("autorizado_por")
        for d in autorizacoes.values()
    )

    if autorizacoes and not pode_encerrar:
        st.info("Preencha motivo e autorizado por em todas as faltas autorizadas.")

    c1, c2 = st.columns(2)
    with c1:
        btn_encerrar = st.button(
            "🔒 Encerrar conferência",
            type="primary",
            use_container_width=True,
            disabled=not pode_encerrar,
        )
    with c2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.modo_encerramento = False
            st.session_state.autorizacoes = {}
            st.rerun()

    if btn_encerrar and pode_encerrar:
        _executar_encerramento(conf["id"], autorizados_lista, nao_autorizados_ids, obs_geral)


def _executar_encerramento(
    conferencia_id: str,
    autorizados: list[dict],
    nao_autorizados: list[str],
    observacao: str,
):
    with st.spinner("Encerrando conferência..."):
        try:
            resultado = encerrar_conferencia(
                conferencia_id=conferencia_id,
                faltas_autorizadas=autorizados,
                faltas_nao_autorizadas=nao_autorizados,
                observacao=observacao,
                fechado_por=st.session_state.usuario_nome,
                usuario_id=st.session_state.usuario_id,
            )
            status_final = resultado["status_final"]
            msgs_enc = {
                "CONFERENCIA_COMPLETA":           "✅ Conferência encerrada como COMPLETA!",
                "CONFERENCIA_PARCIAL_AUTORIZADA": "🔵 Conferência encerrada como PARCIAL AUTORIZADA.",
                "CONFERENCIA_PARCIAL_COM_FALTA":  "🔴 Conferência encerrada como PARCIAL COM FALTA.",
            }
            st.session_state["mensagem_pos_fechamento"] = msgs_enc.get(
                status_final, f"Conferência encerrada: {status_final}"
            )
            _limpar_conferencia_atual()
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao encerrar conferência: {exc}")


# ---------------------------------------------------------------------------
# Tela: Gestão de Usuários (ADMIN)
# ---------------------------------------------------------------------------

def tela_usuarios():
    st.title("👤 Gestão de Usuários")
    st.markdown("---")

    is_admin = _pode(["ADMIN"])
    is_supervisor_only = _pode(["SUPERVISOR"]) and not is_admin

    tab_lista, tab_novo = st.tabs(["Usuários cadastrados", "Novo usuário"])

    with tab_lista:
        try:
            usuarios = listar_usuarios()
        except Exception as exc:
            st.error(f"Erro ao carregar usuários: {exc}")
            usuarios = None

        if usuarios is not None and is_supervisor_only:
            # Supervisor só pode alterar a senha de conferentes.
            usuarios = [u for u in usuarios if u["perfil"] == "CONFERENTE"]
            st.caption("Como supervisor, você pode apenas redefinir a senha de conferentes.")

        if usuarios is not None and not usuarios:
            st.info("Nenhum usuário cadastrado.")

        for u in (usuarios or []):
            ativo  = u.get("ativo", True)
            icone  = "🟢" if ativo else "🔴"
            with st.expander(f"{icone} {u['nome']}  |  `{u['login']}`  |  {u['perfil']}"):
                if is_admin:
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        novo_perfil = st.selectbox(
                            "Perfil",
                            ["CONFERENTE", "SUPERVISOR", "ADMIN"],
                            index=["CONFERENTE", "SUPERVISOR", "ADMIN"].index(u["perfil"]),
                            key=f"perfil_{u['id']}",
                        )
                        if st.button("Salvar perfil", key=f"btn_perfil_{u['id']}"):
                            try:
                                alterar_perfil(u["id"], novo_perfil)
                                st.success("Perfil atualizado.")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

                    with col2:
                        label_btn = "Inativar" if ativo else "Ativar"
                        if st.button(label_btn, key=f"btn_ativo_{u['id']}"):
                            if u["id"] == st.session_state.usuario_id:
                                st.error("Você não pode inativar seu próprio usuário.")
                            else:
                                try:
                                    ativar_inativar_usuario(u["id"], not ativo)
                                    st.success(f"Usuário {'ativado' if not ativo else 'inativado'}.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))

                    with col3:
                        with st.form(f"reset_senha_{u['id']}"):
                            nova = st.text_input("Nova senha", type="password", key=f"ns_{u['id']}")
                            if st.form_submit_button("Resetar senha"):
                                if len(nova) < 6:
                                    st.error("Senha deve ter ao menos 6 caracteres.")
                                else:
                                    try:
                                        resetar_senha(u["id"], nova)
                                        st.success("Senha resetada.")
                                    except Exception as exc:
                                        st.error(str(exc))
                else:
                    # Supervisor: apenas redefinir senha do conferente.
                    with st.form(f"reset_senha_{u['id']}"):
                        nova = st.text_input("Nova senha", type="password", key=f"ns_{u['id']}")
                        if st.form_submit_button("Resetar senha"):
                            if len(nova) < 6:
                                st.error("Senha deve ter ao menos 6 caracteres.")
                            else:
                                try:
                                    resetar_senha(u["id"], nova)
                                    st.success("Senha resetada.")
                                except Exception as exc:
                                    st.error(str(exc))

    with tab_novo:
        perfis_permitidos = ["CONFERENTE", "SUPERVISOR", "ADMIN"] if is_admin else ["CONFERENTE"]
        if is_supervisor_only:
            st.caption("Como supervisor, você só pode criar usuários com perfil Conferente.")

        with st.form("form_novo_usuario", clear_on_submit=True):
            nome      = st.text_input("Nome completo *")
            login     = st.text_input("Login *")
            email     = st.text_input("E-mail (opcional)")
            perfil    = st.selectbox("Perfil", perfis_permitidos)
            senha     = st.text_input("Senha *", type="password")
            confirmar = st.text_input("Confirmar senha *", type="password")
            criar     = st.form_submit_button("Criar usuário", use_container_width=True)

        if criar:
            erros = []
            if not nome:  erros.append("Nome obrigatório.")
            if not login: erros.append("Login obrigatório.")
            if not senha: erros.append("Senha obrigatória.")
            if senha and len(senha) < 6: erros.append("Senha deve ter ao menos 6 caracteres.")
            if senha != confirmar: erros.append("Senhas não conferem.")
            if perfil not in perfis_permitidos: erros.append("Perfil não permitido para o seu nível de acesso.")
            if erros:
                for e in erros:
                    st.error(e)
            else:
                try:
                    u = criar_usuario(nome=nome, login=login, senha=senha, perfil=perfil, email=email or None)
                    st.success(f"Usuário **{u['nome']}** criado com sucesso.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erro ao criar usuário: {exc}")


# ---------------------------------------------------------------------------
# Tela: Minha Senha (qualquer perfil)
# ---------------------------------------------------------------------------

def tela_minha_senha():
    st.title("🔑 Alterar minha senha")
    st.markdown("---")

    with st.form("form_minha_senha", clear_on_submit=True):
        atual     = st.text_input("Senha atual", type="password")
        nova      = st.text_input("Nova senha", type="password")
        confirmar = st.text_input("Confirmar nova senha", type="password")
        salvar    = st.form_submit_button("Salvar nova senha", use_container_width=True)

    if salvar:
        erros = []
        if not atual: erros.append("Informe a senha atual.")
        if not nova:  erros.append("Informe a nova senha.")
        if nova and len(nova) < 6: erros.append("A nova senha deve ter ao menos 6 caracteres.")
        if nova != confirmar: erros.append("As senhas não conferem.")
        if erros:
            for e in erros:
                st.error(e)
            return
        try:
            alterar_senha_propria(st.session_state.usuario_id, atual, nova)
            st.success("Senha alterada com sucesso.")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Erro ao alterar senha: {exc}")


# ---------------------------------------------------------------------------
# Exibição somente-leitura de cargas/volumes conferidos por um usuário
# (usada em "Minhas Cargas" do conferente e na visão detalhada do supervisor)
# ---------------------------------------------------------------------------

def _exibir_volume_completo(v: dict):
    hora = (v.get("conferido_em") or "")[:16].replace("T", " ")
    st.markdown(
        f"**NF** {v.get('nota_fiscal') or '-'} &nbsp;·&nbsp; "
        f"**Vol** {v.get('volume_texto') or '-'} &nbsp;·&nbsp; "
        f"**NR** `{v.get('numero_rastreamento') or '-'}` &nbsp;·&nbsp; "
        f"**Status** {v.get('status') or '-'}"
        + (f" &nbsp;·&nbsp; **Conferido em** {hora}" if hora else "")
    )
    payload = v.get("payload_ssw") or {}
    if payload:
        st.caption("Todos os dados retornados pela API SSW para esta nota:")
        st.json(payload)
    else:
        st.caption("Sem dados detalhados da API SSW para este volume.")
    st.divider()


def _exibir_cargas_conferente(cargas: list[dict]):
    """Lista cargas (somente leitura) com os volumes e dados completos da API SSW."""
    if not cargas:
        st.info("Nenhuma carga conferida encontrada.")
        return

    for c in cargas:
        with st.expander(
            f"📦 Carga {c.get('numero_carga', '-')}  ·  "
            f"{STATUS_LABEL.get(c.get('status'), c.get('status'))}  ·  "
            f"{c.get('total_conferido', 0)}/{c.get('total_esperado', 0)} conferidos"
        ):
            st.caption(
                f"Criado por: {c.get('criado_por') or '-'}  ·  "
                f"Início: {(c.get('iniciado_em') or '')[:16].replace('T', ' ')}  ·  "
                f"Encerrado: {(c.get('encerrado_em') or '-')[:16].replace('T', ' ') if c.get('encerrado_em') else '-'}"
            )
            try:
                volumes = listar_volumes(c["id"])
            except Exception as exc:
                st.warning(f"Falha ao carregar volumes desta carga: {exc}")
                continue
            if not volumes:
                st.caption("Nenhum volume nesta carga.")
            for v in volumes:
                _exibir_volume_completo(v)


# ---------------------------------------------------------------------------
# Tela: Minhas Cargas (qualquer perfil — somente leitura)
# ---------------------------------------------------------------------------

def tela_minhas_cargas():
    st.title("📜 Minhas Cargas Conferidas")
    st.caption("Somente para visualização — nenhuma alteração é permitida aqui.")
    st.markdown("---")

    try:
        cargas = listar_cargas_por_conferente(st.session_state.usuario_id)
    except Exception as exc:
        st.error(f"Erro ao carregar suas cargas: {exc}")
        return

    _exibir_cargas_conferente(cargas)


# ---------------------------------------------------------------------------
# Tela: Relatórios (ADMIN + SUPERVISOR)
# ---------------------------------------------------------------------------

def tela_relatorios():
    st.title("📊 Relatórios")
    st.markdown("---")

    tab_conf, tab_detalhe, tab_carga, tab_erros = st.tabs(
        ["Por conferente", "Análise por conferente", "Por carga", "Erros de bipagem"]
    )

    usuarios_lista = []
    try:
        usuarios_lista = listar_usuarios_opcoes()
    except Exception:
        pass

    usuarios_map    = {u["id"]: f"{u['nome']} ({u['login']})" for u in usuarios_lista}
    usuarios_opcoes = {"": "Todos"} | usuarios_map

    # ── Por conferente ──
    with tab_conf:
        st.subheader("Desempenho por conferente")
        col1, col2, col3 = st.columns(3)
        with col1:
            data_ini_c = st.date_input("Data inicial", value=None, key="dini_conf")
        with col2:
            data_fim_c = st.date_input("Data final",   value=None, key="dfim_conf")
        with col3:
            uid_sel = st.selectbox(
                "Conferente",
                options=list(usuarios_opcoes.keys()),
                format_func=lambda x: usuarios_opcoes[x],
                key="uid_conf",
            )

        if st.button("Gerar relatório", key="btn_conf"):
            with st.spinner("Carregando..."):
                try:
                    dados = relatorio_por_conferente(
                        data_ini=data_ini_c.isoformat() if data_ini_c else None,
                        data_fim=data_fim_c.isoformat() if data_fim_c else None,
                        usuario_id=uid_sel or None,
                    )
                    if not dados:
                        st.info("Nenhum resultado encontrado.")
                    else:
                        df = pd.DataFrame(dados)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        st.download_button(
                            "Exportar CSV",
                            df.to_csv(index=False).encode("utf-8"),
                            file_name="relatorio_conferentes.csv",
                            mime="text/csv",
                        )
                except Exception as exc:
                    st.error(f"Erro ao gerar relatório: {exc}")

    # ── Análise por conferente (detalhe, somente leitura) ──
    with tab_detalhe:
        st.subheader("Cargas e volumes conferidos por um conferente")
        st.caption("Visão somente leitura, com todos os dados retornados pela API SSW para cada nota.")

        conferentes_lista = []
        try:
            conferentes_lista = listar_usuarios_opcoes(perfil="CONFERENTE")
        except Exception:
            pass
        conferentes_opcoes = {u["id"]: f"{u['nome']} ({u['login']})" for u in conferentes_lista}

        if not conferentes_opcoes:
            st.info("Nenhum conferente cadastrado.")
        else:
            uid_detalhe = st.selectbox(
                "Conferente",
                options=list(conferentes_opcoes.keys()),
                format_func=lambda x: conferentes_opcoes[x],
                key="uid_detalhe",
            )
            if st.button("Carregar cargas", key="btn_detalhe"):
                with st.spinner("Carregando..."):
                    try:
                        cargas = listar_cargas_por_conferente(uid_detalhe)
                        st.session_state["_cargas_detalhe"] = cargas
                    except Exception as exc:
                        st.error(f"Erro ao carregar cargas: {exc}")

            cargas_carregadas = st.session_state.get("_cargas_detalhe")
            if cargas_carregadas is not None:
                _exibir_cargas_conferente(cargas_carregadas)

    # ── Por carga ──
    with tab_carga:
        st.subheader("Relatório por carga")
        col1, col2 = st.columns(2)
        with col1:
            data_ini_ca = st.date_input("Data inicial", value=None, key="dini_carga")
        with col2:
            data_fim_ca = st.date_input("Data final",   value=None, key="dfim_carga")
        col3, col4 = st.columns(2)
        with col3:
            status_sel = st.selectbox(
                "Status",
                ["", "EM_CONFERENCIA", "CONFERENCIA_COMPLETA",
                 "CONFERENCIA_PARCIAL_AUTORIZADA", "CONFERENCIA_PARCIAL_COM_FALTA", "CANCELADA"],
                format_func=lambda x: x or "Todos",
                key="status_carga",
            )
        with col4:
            nr_carga = st.text_input("Nº da carga", placeholder="Parcial ou completo", key="nr_carga")

        if st.button("Gerar relatório", key="btn_carga"):
            with st.spinner("Carregando..."):
                try:
                    dados = relatorio_por_carga(
                        data_ini=data_ini_ca.isoformat() if data_ini_ca else None,
                        data_fim=data_fim_ca.isoformat() if data_fim_ca else None,
                        status=status_sel or None,
                        numero_carga=nr_carga or None,
                    )
                    if not dados:
                        st.info("Nenhuma carga encontrada.")
                    else:
                        df = pd.DataFrame(dados)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        st.download_button(
                            "Exportar CSV",
                            df.to_csv(index=False).encode("utf-8"),
                            file_name="relatorio_cargas.csv",
                            mime="text/csv",
                        )
                except Exception as exc:
                    st.error(f"Erro ao gerar relatório: {exc}")

    # ── Erros ──
    with tab_erros:
        st.subheader("Erros de bipagem e faltas não autorizadas")
        col1, col2 = st.columns(2)
        with col1:
            data_ini_e = st.date_input("Data inicial", value=None, key="dini_erros")
        with col2:
            data_fim_e = st.date_input("Data final",   value=None, key="dfim_erros")
        uid_e = st.selectbox(
            "Conferente",
            options=list(usuarios_opcoes.keys()),
            format_func=lambda x: usuarios_opcoes[x],
            key="uid_erros",
        )
        tipos_sel = st.multiselect(
            "Tipos de evento",
            ["VOLUME_DUPLICADO", "VOLUME_DIVERGENTE", "FALTA_NAO_AUTORIZADA"],
            default=["VOLUME_DUPLICADO", "VOLUME_DIVERGENTE", "FALTA_NAO_AUTORIZADA"],
            key="tipos_erros",
        )

        if st.button("Gerar relatório", key="btn_erros"):
            with st.spinner("Carregando..."):
                try:
                    dados = relatorio_erros(
                        data_ini=data_ini_e.isoformat() if data_ini_e else None,
                        data_fim=data_fim_e.isoformat() if data_fim_e else None,
                        usuario_id=uid_e or None,
                        tipos=tipos_sel or None,
                    )
                    if not dados:
                        st.info("Nenhum erro encontrado no período.")
                    else:
                        df = pd.DataFrame(dados)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        st.download_button(
                            "Exportar CSV",
                            df.to_csv(index=False).encode("utf-8"),
                            file_name="relatorio_erros.csv",
                            mime="text/csv",
                        )
                except Exception as exc:
                    st.error(f"Erro ao gerar relatório: {exc}")


# ---------------------------------------------------------------------------
# Roteador principal
# ---------------------------------------------------------------------------

if not _usuario_logado():
    tela_login()
else:
    _sidebar()
    pagina = st.session_state.pagina

    if pagina == "usuarios":
        if _pode(["ADMIN", "SUPERVISOR"]):
            tela_usuarios()
        else:
            st.error("Acesso restrito a administradores e supervisores.")

    elif pagina == "relatorios":
        if _pode(["ADMIN", "SUPERVISOR"]):
            tela_relatorios()
        else:
            st.error("Acesso restrito a administradores e supervisores.")

    elif pagina == "minha_senha":
        tela_minha_senha()

    elif pagina == "minhas_cargas":
        tela_minhas_cargas()

    else:
        if st.session_state.conferencia_id:
            tela_conferencia()
        else:
            tela_entrada()
