from datetime import date, datetime
import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_tipos_exames() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("tipos_exames").select("*").order("nome_exame").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_colaboradores() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("colaboradores").select("id, nome_completo, matricula").order("nome_completo").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_exames_colaborador() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("exames_colaborador").select("*").order("data_realizacao", desc=True).execute()
        return res.data or []
    except Exception:
        return []


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


def _somar_meses(data_base: date, meses: int) -> date:
    ano_total = data_base.year + (data_base.month - 1 + meses) // 12
    mes_novo = (data_base.month - 1 + meses) % 12 + 1
    ultimo_dia_mes = pd.Period(f"{ano_total}-{mes_novo:02d}", freq="M").days_in_month
    dia_novo = min(data_base.day, ultimo_dia_mes)
    return date(ano_total, mes_novo, dia_novo)


def render_tipos_exames() -> None:
    st.title("📋 Cadastro de Exames")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    exames = _buscar_tipos_exames()
    colabs = _buscar_colaboradores()
    mapa_exames = {str(x["id"]): x for x in exames if x.get("id")}
    mapa_colabs = {
        str(c["id"]): f"{c.get('nome_completo') or 'Sem nome'} ({c.get('matricula') or '—'})"
        for c in colabs
        if c.get("id")
    }

    tab1, tab2, tab3 = st.tabs([
        "Exames Cadastrados",
        "➕ Cadastrar Tipo de Exame",
        "🗓️ Lançar Realização / Renovação",
    ])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Tipos de Exames Cadastrados")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_exames", use_container_width=True):
                _buscar_tipos_exames.clear()

        if exames:
            df = pd.DataFrame(exames)
            colunas_desejadas = ["nome_exame", "codigo_tuss", "validade_meses", "observacoes"]
            colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
            df_exibir = df[colunas_existentes].rename(
                columns={
                    "nome_exame": "Nome do Exame",
                    "codigo_tuss": "Código TUSS",
                    "validade_meses": "Validade (meses)",
                    "observacoes": "Observações",
                }
            )
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum exame cadastrado até o momento.")

    with tab2:
        st.subheader("Novo Tipo de Exame")
        with st.form("form_cadastro_exame", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                nome_exame = st.text_input("Nome do Exame *", placeholder="Ex: Audiometria Ocupacional")
            with c2:
                codigo_tuss = st.text_input("Código TUSS", placeholder="Ex: 40101010")
            with c3:
                validade_meses = st.number_input("Validade (meses)", min_value=0, value=12, step=1)

            observacoes = st.text_area("Observações")
            submitted = st.form_submit_button("💾 Salvar Exame")

            if submitted:
                if not nome_exame.strip():
                    st.warning("Informe o nome do exame (*).")
                else:
                    try:
                        novo_exame = {
                            "nome_exame": nome_exame.strip(),
                            "codigo_tuss": codigo_tuss.strip(),
                            "validade_meses": int(validade_meses) if validade_meses > 0 else None,
                            "observacoes": observacoes.strip(),
                        }
                        supabase.table("tipos_exames").insert(novo_exame).execute()
                        _buscar_tipos_exames.clear()
                        st.success("Exame cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar exame no Supabase: {e}")

    with tab3:
        st.subheader("Registrar Realização de Exame por Colaborador")
        ids_colabs = list(mapa_colabs.keys())
        ids_exames = list(mapa_exames.keys())

        if not ids_colabs or not ids_exames:
            st.info("Cadastre colaboradores e tipos de exames para registrar realizações.")
        else:
            sel_colab = st.selectbox(
                "Colaborador *",
                options=ids_colabs,
                format_func=lambda cid: mapa_colabs[cid],
                key="ex_real_colab",
            )
            sel_exame = st.selectbox(
                "Tipo de Exame *",
                options=ids_exames,
                format_func=lambda eid: str(mapa_exames[eid].get("nome_exame") or "Exame"),
                key="ex_real_tipo",
            )
            data_realizacao = st.date_input(
                "Data de Realização *",
                value=date.today(),
                format="DD/MM/YYYY",
                key="ex_real_data",
            )

            validade_m = int(mapa_exames[sel_exame].get("validade_meses") or 12)
            prox_venc = _somar_meses(data_realizacao, validade_m)
            dias_ciclo = (prox_venc - date.today()).days

            m1, m2, m3 = st.columns(3)
            m1.metric("Validade do Exame", f"{validade_m} meses")
            m2.metric("Próximo Vencimento", prox_venc.strftime("%d/%m/%Y"))
            m3.metric("Dias até Vencer", f"{dias_ciclo} dias")

            obs_ex = st.text_input("Observações", key="ex_real_obs")

            if st.button("💾 Salvar Realização do Exame", type="primary", key="btn_salvar_real_exame"):
                try:
                    payload = {
                        "colaborador_id": sel_colab,
                        "tipo_exame_id": sel_exame,
                        "data_realizacao": str(data_realizacao),
                        "data_vencimento": str(prox_venc),
                        "status": "Válido",
                        "observacoes": obs_ex.strip(),
                    }
                    supabase.table("exames_colaborador").insert(payload).execute()
                    _buscar_exames_colaborador.clear()
                    st.success(f"Exame registrado! Novo vencimento em {prox_venc.strftime('%d/%m/%Y')}.")
                except Exception as e:
                    st.error(f"Erro ao salvar realização do exame: {e}")

        hist_ex = _buscar_exames_colaborador()
        if hist_ex:
            st.markdown("##### Histórico de Realizações de Exames")
            df_e = pd.DataFrame(hist_ex)
            if "colaborador_id" in df_e.columns:
                df_e["colaborador"] = df_e["colaborador_id"].map(lambda c: mapa_colabs.get(str(c), str(c)))
            if "tipo_exame_id" in df_e.columns:
                df_e["exame"] = df_e["tipo_exame_id"].map(
                    lambda x: str(mapa_exames.get(str(x), {}).get("nome_exame") or x)
                )
            for col_d in ["data_realizacao", "data_vencimento"]:
                if col_d in df_e.columns:
                    df_e[col_d] = df_e[col_d].map(_formatar_data_br)

            cols_e = [c for c in ["colaborador", "exame", "data_realizacao", "data_vencimento", "status"] if c in df_e.columns]
            st.dataframe(
                df_e[cols_e].rename(
                    columns={
                        "colaborador": "Colaborador",
                        "exame": "Exame",
                        "data_realizacao": "Realização",
                        "data_vencimento": "Vencimento",
                        "status": "Status",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
