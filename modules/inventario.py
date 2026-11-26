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


def _normalizar_campo(valor: str) -> str:
    return " ".join(str(valor or "").strip().lower().split())


def _obter_ca(item: dict, epi_ref: dict) -> str:
    return str(
        item.get("ca")
        or item.get("numero_ca")
        or item.get("codigo_ca")
        or epi_ref.get("ca")
        or epi_ref.get("numero_ca")
        or epi_ref.get("codigo_ca")
        or "—"
    ).strip()


def _obter_validade(item: dict, epi_ref: dict) -> date | None:
    dt_val = _parse_data(
        item.get("data_validade")
        or item.get("data_validade_lote")
        or item.get("validade_lote")
        or epi_ref.get("data_validade_ca")
        or epi_ref.get("validade_ca")
        or epi_ref.get("data_validade")
    )
    if not dt_val and item.get("observacoes"):
        obs_str = str(item.get("observacoes"))
        if "Val. Lote:" in obs_str:
            trecho = obs_str.split("Val. Lote:", 1)[1][:10]
            dt_val = _parse_data(trecho)
    return dt_val


def _construir_tabela_saldos(inventario: list[dict], mapa_epis: dict[str, dict]) -> pd.DataFrame:
    """
    Agrupa e soma o saldo apenas quando SKU, CA e Validade forem iguais
    (itens com mesmo SKU mas CA ou Validade diferentes ficam em linhas distintas).
    """
    agrupado: dict[tuple[str, str, str], dict] = {}

    for item in inventario:
        eid = str(item.get("epi_id") or "").strip()
        epi_ref = mapa_epis.get(eid, {})

        sku = str(epi_ref.get("codigo_sku") or epi_ref.get("sku") or eid or "—").strip()
        nome_epi = str(epi_ref.get("descricao") or epi_ref.get("nome_epi") or "EPI").strip()
        ca = _obter_ca(item, epi_ref)

        dt_val = _obter_validade(item, epi_ref)
        validade_str = dt_val.strftime("%d/%m/%Y") if dt_val else "—"

        chave_unica = (
            _normalizar_campo(sku),
            _normalizar_campo(ca),
            validade_str,
        )
        qtd_disp = int(item.get("quantidade_disponivel") or 0)

        if chave_unica not in agrupado:
            agrupado[chave_unica] = {
                "SKU": sku,
                "EPI": nome_epi,
                "CA": ca,
                "Validade": validade_str,
                "Saldo Disponível": 0,
                "Qtd. Lotes": 0,
            }

        agrupado[chave_unica]["Saldo Disponível"] += qtd_disp
        agrupado[chave_unica]["Qtd. Lotes"] += 1

    if not agrupado:
        return pd.DataFrame()

    return pd.DataFrame(list(agrupado.values())).sort_values(
        by=["SKU", "Validade", "CA"], ascending=[True, True, True]
    )


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
            st.subheader("📊 Saldo Consolidado por EPI (SKU, CA e Validade)")
        with col_b:
            if st.button("🔄 Atualizar", key="btn_att_inv_tab1", use_container_width=True):
                _limpar_cache_inventario()
                st.rerun()

        df_saldos_tab1 = _construir_tabela_saldos(inventario, mapa_epis)
        if not df_saldos_tab1.empty:
            st.dataframe(df_saldos_tab1, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum saldo registrado no inventário.")

        st.markdown("---")
        st.subheader("Lotes Registrados no Inventário")
        if inventario:
            linhas_lotes = []
            for item in inventario:
                eid = str(item.get("epi_id") or "").strip()
                epi_ref = mapa_epis.get(eid, {})
                sku = str(epi_ref.get("codigo_sku") or epi_ref.get("sku") or "—").strip()
                nome_epi = str(epi_ref.get("descricao") or epi_ref.get("nome_epi") or "EPI").strip()
                ca = _obter_ca(item, epi_ref)
                validade = _formatar_data_br(_obter_validade(item, epi_ref))
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
                ca = _obter_ca({}, e)
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
                    try:
                        epi_escolhido = mapa_epis.get(epi_sel_id, {})
                        ca_escolhido = _obter_ca({}, epi_escolhido)

                        obs_texto = observacoes.strip()
                        if informar_val_lote:
                            marcador_val = f"Val. Lote: {data_validade_lote.strftime('%d/%m/%Y')}"
                            obs_texto = f"{obs_texto} | {marcador_val}".strip(" |")
                        if ca_escolhido != "—":
                            marcador_ca = f"CA: {ca_escolhido}"
                            if marcador_ca.lower() not in obs_texto.lower():
                                obs_texto = f"{obs_texto} | {marcador_ca}".strip(" |")

                        novo_lote = {
                            "epi_id": epi_sel_id,
                            "codigo_lote": codigo_lote.strip(),
                            "quantidade_disponivel": int(quantidade),
                            "data_entrada": str(data_entrada),
                            "observacoes": obs_texto,
                        }
                        supabase.table("inventario_epi").insert(novo_lote).execute()
                        _limpar_cache_inventario()
                        st.success("Entrada adicionada ao inventário com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao registrar entrada no inventário: {e}")

        st.markdown("---")
        st.subheader("📊 Saldo Atual por EPI (SKU, CA e Validade)")

        df_saldos_tab2 = _construir_tabela_saldos(inventario, mapa_epis)
        if not df_saldos_tab2.empty:
            st.dataframe(df_saldos_tab2, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum saldo registrado no inventário até o momento.")

    with tab3:
        st.subheader("Ajustar Saldo de Lote Existente")
        if not inventario:
            st.info("Nenhum lote disponível para ajuste.")
        else:
            opcoes_lotes = [str(l.get("id")) for l in inventario if l.get("id")]
            mapa_rotulos_lote = {}
            for l in inventario:
                lid = str(l.get("id") or "")
                if not lid:
                    continue
                epi_ref = mapa_epis.get(str(l.get("epi_id") or "").strip(), {})
                sku = str(epi_ref.get("codigo_sku") or epi_ref.get("sku") or "—").strip()
                nome = str(epi_ref.get("descricao") or epi_ref.get("nome_epi") or "EPI").strip()
                ca = _obter_ca(l, epi_ref)
                val = _formatar_data_br(_obter_validade(l, epi_ref))
                mapa_rotulos_lote[lid] = (
                    f"{sku} — {nome} | CA {ca} | Val. {val} | "
                    f"Lote {l.get('codigo_lote') or '—'} | Saldo: {l.get('quantidade_disponivel', 0)}"
                )

            lote_ajuste_id = st.selectbox(
                "Selecione o Lote",
                options=opcoes_lotes,
                format_func=lambda lid: mapa_rotulos_lote.get(lid, lid),
                key="select_lote_ajuste",
            )
            lote_atual = next((l for l in inventario if str(l.get("id")) == lote_ajuste_id), {})
            saldo_atual = int(lote_atual.get("quantidade_disponivel") or 0)

            with st.form("form_ajuste_saldo_lote"):
                novo_saldo = st.number_input(
                    "Novo Saldo Disponível",
                    min_value=0,
                    value=saldo_atual,
                    step=1,
                )
                motivo_ajuste = st.text_input("Motivo do Ajuste", placeholder="Ex: Inventário físico / avaria")
                btn_ajustar = st.form_submit_button("💾 Salvar Ajuste")

                if btn_ajustar:
                    try:
                        obs_antiga = str(lote_atual.get("observacoes") or "").strip()
                        extra_obs = f"Ajuste ({date.today().strftime('%d/%m/%Y')}): {saldo_atual} -> {int(novo_saldo)}"
                        if motivo_ajuste.strip():
                            extra_obs += f" ({motivo_ajuste.strip()})"
                        obs_final = f"{obs_antiga} | {extra_obs}".strip(" |")

                        supabase.table("inventario_epi").update({
                            "quantidade_disponivel": int(novo_saldo),
                            "observacoes": obs_final,
                        }).eq("id", lote_ajuste_id).execute()
                        _limpar_cache_inventario()
                        st.success("Saldo atualizado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar saldo: {e}")

    with tab4:
        st.subheader("Histórico de Trocas de EPI por Colaborador")
        if not historico_trocas:
            st.info("Nenhuma troca de EPI registrada até o momento.")
        else:
            opcoes_colab = ["TODOS"] + list(mapa_colabs.keys())
            colab_filtro = st.selectbox(
                "Filtrar por Colaborador",
                options=opcoes_colab,
                format_func=lambda cid: (
                    "Todos os Colaboradores"
                    if cid == "TODOS"
                    else f"{mapa_colabs[cid].get('nome_completo', '—')} ({mapa_colabs[cid].get('matricula', '')})"
                ),
                key="filtro_colab_hist_trocas_inv",
            )

            linhas_hist = []
            for h in historico_trocas:
                cid = str(h.get("colaborador_id") or "").strip()
                if colab_filtro != "TODOS" and cid != colab_filtro:
                    continue
                c_info = mapa_colabs.get(cid, {})
                e_info = mapa_epis.get(str(h.get("epi_id") or "").strip(), {})
                linhas_hist.append({
                    "Data da Troca": _formatar_data_br(h.get("data_troca")),
                    "Colaborador": c_info.get("nome_completo") or "—",
                    "Matrícula": c_info.get("matricula") or "—",
                    "EPI": e_info.get("descricao") or e_info.get("nome_epi") or "EPI",
                    "Quantidade": int(h.get("quantidade") or 1),
                    "Motivo": str(h.get("motivo") or "—"),
                })

            if linhas_hist:
                st.dataframe(pd.DataFrame(linhas_hist), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma troca encontrada para o colaborador selecionado.")
