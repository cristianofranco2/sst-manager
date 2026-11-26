import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_tipos_exames() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("tipos_exames").select("*").order("nome_exame").execute()
    return res.data or []


def render_tipos_exames() -> None:
    st.title("📋 Cadastro de Exames")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Exames Cadastrados", "➕ Cadastrar Novo Exame"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Tipos de Exames Cadastrados")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_exames", use_container_width=True):
                _buscar_tipos_exames.clear()

        try:
            dados = _buscar_tipos_exames()
            if dados:
                df = pd.DataFrame(dados)
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
        except Exception as e:
            st.error(f"Erro ao carregar exames: {e}")

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
