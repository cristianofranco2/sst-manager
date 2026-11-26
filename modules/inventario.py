from datetime import date, datetime
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

DATA_MIN_CALENDARIO = date(1900, 1, 1)
DATA_MAX_CALENDARIO = date(2100, 12, 31)


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_epis() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("epis").select("*").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_inventario() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("inventario_epi").select("*").order("data_entrada", desc=True).execute()
        return res.data or []
    except Exception:
        res = supabase.table("inventario_epi").select("*").execute()
        return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_colaboradores() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("colaboradores").select("*").order("nome_completo").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_historico_trocas() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("historico_trocas_epi").select("*").order("data_troca", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def _limpar_cache_inventario() -> None:
    _buscar_epis.clear()
    _buscar_inventario.clear()
    _buscar_colaboradores.clear()
    _buscar_historico_trocas.clear()


def _parse_data(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    texto = str(valor).strip()[:10]
    if not texto:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _formatar_data_br(valor) -> str:
    dt = _parse_data(valor)
    return dt.strftime("%d/%m/%Y") if dt else "—"


def render_inventario() -> None:
    render_cabecalho_modulo("📦 Cadastro de Inventário e Histórico de Trocas")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    epis = _buscar_epis()
    inventario = _buscar_inventario()
    colaboradores = _buscar_colaboradores()
    historico_trocas = _buscar_historico_trocas()

    mapa_epis = {str(e.get("id") or "").strip(): e for e in epis if e.get("id")}
    mapa_colabs = {str(c.get("id") or "").strip(): c for c in colaboradores if c.get("id")}

    tab1, tab2, tab3, tab4 = st.tabs([
        "📦 Estoque / Lotes no Inventário",
        "➕ Entrada no Inventário",
        "🔧 Ajuste de Saldo",
        "🕒 Histórico de Trocas por Colaborador",
    ])

    with tab1:
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.subheader("Lotes Registrados no Inventário")
        with col_b:
            if st.button("🔄 Atualizar", key="btn_att_inv_tab1", use_container_width=True):
                _limpar_cache_inventario()
                st.rerun()

        if inventario:
            linhas_lotes = []
            for item in inventario:
                eid = str(item.get("epi_id") or "").strip()
                epi_ref = mapa_epis.get(eid, {})
                sku = str(epi_ref.get("codigo_sku") or epi_ref.get("sku") or "—").strip()
                nome_epi = str(epi_ref.get("descricao") or epi_ref.get("nome_epi") or "EPI").strip()
                ca = str(
                    item.get("ca")
                    or item.get("numero_ca")
                    or epi_ref.get("ca")
                    or epi_ref.get("numero_ca")
                    or "—"
                ).strip()
                validade = _formatar_data_br(
                    item.get("data_validade")
                    or item.get("data_validade_lote")
                    or epi_ref.get("data_validade_ca")
                    or epi_ref.get("validade_ca")
                )
                linhas_lotes.append({
                    "Lote": str(item.get("codigo_lote") or "—"),
                    "SKU": sku,
                    "EPI": nome_epi,
                    "CA": ca,
                    "Validade": validade,
                    "Entrada": _formatar_data_br(item.get("data_entrada")),
                    "Saldo Disponível": int(item.get("quantidade_disponivel") or 0),
                    "Observações": str(item.get("observacoes") or "—"),
                })
            st.dataframe(pd.DataFrame(linhas_lotes), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum lote registrado no inventário.")

    with tab2:
        st.subheader("Registrar Entrada de EPI no Inventário")

        if not epis:
            st.warning("Nenhum EPI cadastrado. Cadastre um EPI antes de registrar entrada no inventário.")
        else:
            ids_epis = list(mapa_epis.keys())

            def _formatar_epi(eid: str) -> str:
                e = mapa_epis.get(eid, {})
                sku = str(e.get("codigo_sku") or e.get("sku") or eid).strip()
                nome = str(e.get("descricao") or e.get("nome_epi") or "EPI").strip()
                ca = str(e.get("ca") or e.get("numero_ca") or "—").strip()
                val = _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca"))
                return f"{sku} — {nome} | CA {ca} | Val. {val}"

            epi_sel_id = st.selectbox(
                "EPI (identificado por SKU, CA e Validade CA) *",
                options=ids_epis,
                format_func=_formatar_epi,
                key="select_epi_entrada_inv",
            )

            with st.form("form_entrada_inventario", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    quantidade = st.number_input("Quantidade *", min_value=1, value=10, step=1)
                    codigo_lote = st.text_input("Código do Lote", placeholder="Ex: LOTE-2026-11")
                with c2:
                    data_entrada = st.date_input(
                        "Data de Entrada *",
                        value=date.today(),
                        min_value=DATA_MIN_CALENDARIO,
                        max_value=DATA_MAX_CALENDARIO,
                        format="DD/MM/YYYY",
                    )
                with c3:
                    informar_val_lote = st.checkbox("Informar validade específica do lote", value=False)
                    data_validade_lote = st.date_input(
                        "Validade do Lote",
                        value=date.today(),
                        min_value=DATA_MIN_CALENDARIO,
                        max_value=DATA_MAX_CALENDARIO,
                        format="DD/MM/YYYY",
                    )

                observacoes = st.text_area("Observações")
                submitted = st.form_submit_button("💾 Registrar Entrada")

                if submitted:
