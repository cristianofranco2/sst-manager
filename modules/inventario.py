from datetime import date, datetime
import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_epis() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("epis").select("*").order("descricao").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_inventario() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("inventario_epi").select("*").order("data_entrada", desc=True).execute()
        return res.data or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_colaboradores() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("colaboradores").select("id, nome_completo, matricula, cargo").order("nome_completo").execute()
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


def _formatar_data_br(valor) -> str:
    if not valor:
        return "—"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor).strip()[:10]
    if not texto:
        return "—"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return texto


def _label_epi_detalhado(epi: dict) -> str:
    nome = str(epi.get("descricao") or epi.get("nome_epi") or "EPI").strip()
    sku = str(epi.get("codigo_sku") or "").strip()
    ca = str(epi.get("numero_ca") or epi.get("ca") or "").strip()
    val_ca = _formatar_data_br(epi.get("data_validade_ca") or epi.get("validade_ca"))

    partes = []
    if sku:
        partes.append(f"SKU {sku}")
    if ca:
        partes.append(f"CA {ca}")
    if val_ca != "—":
        partes.append(f"Val. CA {val_ca}")

    return f"{nome} — {' | '.join(partes)}" if partes else nome


def render_inventario() -> None:
    st.title("📦 Cadastro de Inventário e Histórico de Trocas")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    epis = _buscar_epis()
    mapa_epis_obj = {str(e["id"]): e for e in epis if e.get("id")}
    mapa_epis = {eid: _label_epi_detalhado(e) for eid, e in mapa_epis_obj.items()}

    colabs = _buscar_colaboradores()
    mapa_colabs = {
        str(c["id"]): f"{c.get('nome_completo') or 'Sem nome'} ({c.get('matricula') or '—'})"
        for c in colabs
        if c.get("id")
    }

    tab1, tab2, tab3, tab4 = st.tabs([
        "📦 Estoque / Lotes no Inventário",
        "➕ Entrada no Inventário",
        "🔧 Ajuste de Saldo",
        "🕒 Histórico de Trocas por Colaborador",
    ])

    with tab1:
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.subheader("Lotes / Quantidades Disponíveis")
        with col_b:
            if st.button("🔄 Atualizar", key="btn_atualizar_inv", use_container_width=True):
                _limpar_cache_inventario()
                st.rerun()

        inv = _buscar_inventario()
        if inv:
            df = pd.DataFrame(inv)
            if "epi_id" in df.columns:
                df["epi_nome"] = df["epi_id"].map(lambda eid: mapa_epis.get(str(eid), str(eid)))
            for col_d in ["data_entrada", "data_validade_lote"]:
                if col_d in df.columns:
                    df[col_d] = df[col_d].map(_formatar_data_br)

            colunas = [
                "epi_nome",
                "codigo_lote",
                "quantidade_disponivel",
                "data_entrada",
                "data_validade_lote",
                "observacoes",
            ]
            existentes = [c for c in colunas if c in df.columns]
            df_exibir = df[existentes].rename(
                columns={
                    "epi_nome": "EPI (SKU / CA / Validade CA)",
                    "codigo_lote": "Lote",
                    "quantidade_disponivel": "Qtd. Disponível",
                    "data_entrada": "Data Entrada",
                    "data_validade_lote": "Validade Lote",
                    "observacoes": "Observações",
                }
            )
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum lote registrado no inventário ainda.")

    with tab2:
        st.subheader("Registrar Entrada de EPI no Inventário")
        ids_epis = list(mapa_epis.keys())
        if not ids_epis:
            st.warning("Cadastre um EPI no **Cadastro de EPIs** antes de lançar no inventário.")
        else:
            with st.form("form_entrada_inventario", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    epi_selecionado = st.selectbox(
                        "EPI (identificado por SKU, CA e Validade CA) *",
                        options=ids_epis,
                        format_func=lambda eid: mapa_epis[eid],
                    )
                    codigo_lote = st.text_input("Código do Lote", placeholder="Ex: LOTE-2026-11")
                with c2:
                    qtd_entrada = st.number_input("Quantidade *", min_value=1, value=10, step=1)
                    data_entrada = st.date_input("Data de Entrada *", value=date.today(), format="DD/MM/YYYY")
                with c3:
                    tem_validade = st.checkbox("Informar validade específica do lote", value=False)
                    data_validade_lote = st.date_input("Validade do Lote", format="DD/MM/YYYY")

                observacoes = st.text_area("Observações")
                submitted = st.form_submit_button("💾 Registrar Entrada")

                if submitted:
                    try:
                        payload = {
                            "epi_id": epi_selecionado,
                            "codigo_lote": codigo_lote.strip(),
                            "quantidade_disponivel": int(qtd_entrada),
                            "data_entrada": str(data_entrada),
                            "data_validade_lote": str(data_validade_lote) if tem_validade else None,
                            "observacoes": observacoes.strip(),
                        }
                        supabase.table("inventario_epi").insert(payload).execute()
                        _limpar_cache_inventario()
                        st.success("Entrada adicionada ao inventário com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar no inventário: {e}")

    with tab3:
        st.subheader("Ajuste Manual de Saldo no Inventário")
        inv_ajuste = _buscar_inventario()
        if not inv_ajuste:
            st.info("Nenhum item no inventário para ajustar saldo.")
        else:
            opcoes_lotes = [str(item["id"]) for item in inv_ajuste if item.get("id")]
            mapa_lotes_aj = {}
            for item in inv_ajuste:
                lid = str(item.get("id") or "")
                if not lid:
                    continue
                epi_txt = mapa_epis.get(str(item.get("epi_id") or ""), str(item.get("epi_id") or "EPI"))
                lote_txt = str(item.get("codigo_lote") or "Sem lote").strip()
                saldo_txt = int(item.get("quantidade_disponivel") or 0)
                dt_ent = _formatar_data_br(item.get("data_entrada"))
                mapa_lotes_aj[lid] = f"{epi_txt} | Lote: {lote_txt} | Entrada: {dt_ent} | Saldo atual: {saldo_txt}"

            lote_escolhido_id = st.selectbox(
                "Selecione o Lote / Item do Inventário *",
                options=opcoes_lotes,
                format_func=lambda lid: mapa_lotes_aj[lid],
                key="sel_lote_ajuste_saldo",
            )
            item_atual = next((x for x in inv_ajuste if str(x.get("id")) == lote_escolhido_id), {})
            saldo_atual = int(item_atual.get("quantidade_disponivel") or 0)

            tipo_ajuste = st.radio(
                "Tipo de Ajuste",
                ["Definir saldo exato", "Somar / Subtrair quantidade"],
                horizontal=True,
                key="tipo_ajuste_saldo",
            )

            if tipo_ajuste == "Definir saldo exato":
                novo_saldo = st.number_input(
                    "Novo Saldo *",
                    min_value=0,
                    max_value=999999,
                    value=saldo_atual,
                    step=1,
                    key="novo_saldo_exato",
                )
            else:
                delta_qtd = st.number_input(
                    "Variação (use positivo para entrada ou negativo para baixa)",
                    min_value=-saldo_atual,
                    max_value=999999,
                    value=0,
                    step=1,
                    key="delta_saldo_qtd",
                )
                novo_saldo = max(0, saldo_atual + int(delta_qtd))
                st.caption(f"Saldo resultante: **{novo_saldo}** (atual: {saldo_atual})")

            motivo_ajuste = st.text_input(
                "Motivo do Ajuste *",
                placeholder="Ex: Inventário físico, avaria, correção de lançamento",
                key="motivo_ajuste_saldo",
            )

            if st.button("💾 Confirmar Ajuste de Saldo", type="primary", key="btn_confirmar_ajuste_saldo"):
                if not motivo_ajuste.strip():
                    st.warning("Informe o motivo do ajuste (*).")
                else:
                    try:
                        obs_antiga = str(item_atual.get("observacoes") or "").strip()
                        registro_obs = (
                            f"[{date.today().strftime('%d/%m/%Y')}] Ajuste de saldo: "
                            f"{saldo_atual} -> {novo_saldo} ({motivo_ajuste.strip()})"
                        )
                        obs_final = f"{obs_antiga} | {registro_obs}" if obs_antiga else registro_obs

                        supabase.table("inventario_epi").update({
                            "quantidade_disponivel": int(novo_saldo),
                            "observacoes": obs_final,
                        }).eq("id", lote_escolhido_id).execute()

                        _limpar_cache_inventario()
                        st.success(f"Saldo atualizado de {saldo_atual} para {novo_saldo}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao ajustar saldo: {e}")

    with tab4:
        st.subheader("Histórico de Trocas e Entregas por Colaborador")
        filtro_colab = st.selectbox(
            "Filtrar por Colaborador",
            options=["TODOS"] + list(mapa_colabs.keys()),
            format_func=lambda cid: "Todos os Colaboradores" if cid == "TODOS" else mapa_colabs[cid],
            key="filtro_hist_trocas_colab",
        )

        hist = _buscar_historico_trocas()
        if filtro_colab != "TODOS":
            hist = [h for h in hist if str(h.get("colaborador_id")) == filtro_colab]

        if hist:
            df_h = pd.DataFrame(hist)
            if "colaborador_id" in df_h.columns:
                df_h["colaborador_nome"] = df_h["colaborador_id"].map(
                    lambda cid: mapa_colabs.get(str(cid), str(cid))
                )
            if "epi_id" in df_h.columns:
                df_h["epi_nome"] = df_h["epi_id"].map(lambda eid: mapa_epis.get(str(eid), str(eid)))

            for col_d in ["data_troca", "data_vencimento_novo"]:
                if col_d in df_h.columns:
                    df_h[col_d] = df_h[col_d].map(_formatar_data_br)

            colunas_h = [
                "data_troca",
                "colaborador_nome",
                "epi_nome",
                "tipo_movimentacao",
                "quantidade",
                "data_vencimento_novo",
                "motivo",
            ]
            existentes_h = [c for c in colunas_h if c in df_h.columns]
            df_h_exibir = df_h[existentes_h].rename(
                columns={
                    "data_troca": "Data Troca",
                    "colaborador_nome": "Colaborador",
                    "epi_nome": "EPI",
                    "tipo_movimentacao": "Tipo",
                    "quantidade": "Qtd.",
                    "data_vencimento_novo": "Novo Vencimento",
                    "motivo": "Motivo",
                }
            )
            st.dataframe(df_h_exibir, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma troca registrada para o filtro selecionado.")
