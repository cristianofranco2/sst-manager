import streamlit as st
import pandas as pd
from database import get_supabase

def render_exames():
    st.title("📋 Catálogo de Tipos de Exames Médicos")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Exames Cadastrados", "Cadastrar Novo Tipo de Exame"])

    with tab1:
        st.subheader("Tipos de Exames do Sistema")
        try:
            res = supabase.table("tipos_exames").select("*").execute()
            data = res.data or []
            if data:
                df = pd.DataFrame(data)
                colunas = [c for c in ["nome_exame", "codigo_tuss", "validade_meses", "observacoes"] if c in df.columns]
                
                # Renomeia colunas para melhor visualização na tabela
                df_exib = df[colunas].rename(columns={
                    "nome_exame": "Nome do Exame",
                    "codigo_tuss": "Código TUSS",
                    "validade_meses": "Periodicidade (Meses)",
                    "observacoes": "Observações"
                })
                st.dataframe(df_exib, use_container_width=True)
            else:
                st.info("Nenhum tipo de exame cadastrado no catálogo.")
        except Exception as e:
            st.error(f"Erro ao carregar tipos de exames: {e}")

    with tab2:
        st.subheader("Cadastrar Novo Tipo de Exame")
        with st.form("form_novo_tipo_exame", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome_exame = st.text_input("Nome do Exame * (ex: Hemograma Completo, Audiometria)")
                codigo_tuss = st.text_input("Código TUSS (opcional)")
            with col2:
                validade_meses = st.number_input("Periodicidade Padrão (em meses) *", min_value=1, max_value=60, value=12)
                observacoes = st.text_area("Observações / Recomendações")

            if st.form_submit_button("Salvar Tipo de Exame"):
                if not nome_exame:
                    st.warning("Preencha o nome do exame (*).")
                else:
                    try:
                        novo_tipo = {
                            "nome_exame": nome_exame,
                            "codigo_tuss": codigo_tuss,
                            "validade_meses": int(validade_meses),
                            "observacoes": observacoes
                        }
                        supabase.table("tipos_exames").insert(novo_tipo).execute()
                        st.success("Tipo de exame cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar tipo de exame: {e}")
