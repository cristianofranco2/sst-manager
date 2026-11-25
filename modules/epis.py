import streamlit as st
import pandas as pd
from database import get_supabase

def render_epis():
    st.title("🥽 Catálogo de Equipamentos de Proteção Individual (EPIs)")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Catálogo Cadastrado", "Cadastrar Novo EPI"])

    with tab1:
        st.subheader("Equipamentos Cadastrados")
        try:
            res = supabase.table("epis").select("*").execute()
            data = res.data or []
            if data:
                df = pd.DataFrame(data)
                colunas = [c for c in ["nome_epi", "ca", "fabricante", "validade_ca", "dias_durabilidade_media", "quantidade_estoque"] if c in df.columns]
                st.dataframe(df[colunas] if colunas else df, use_container_width=True)
            else:
                st.info("Nenhum EPI cadastrado no catálogo.")
        except Exception as e:
            st.error(f"Erro ao carregar catálogo de EPIs: {e}")

    with tab2:
        st.subheader("Cadastrar Novo EPI")
        with st.form("form_novo_epi", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nome_epi = st.text_input("Nome / Descrição do EPI *")
                ca = st.text_input("Número do CA (Certificado de Aprovação) *")
                fabricante = st.text_input("Fabricante")
            with c2:
                validade_ca = st.date_input("Data de Validade do CA *")
                durabilidade = st.number_input("Durabilidade Média (em dias)", min_value=1, value=180)
                qtd_estoque = st.number_input("Quantidade em Estoque", min_value=0, value=0)

            if st.form_submit_button("Salvar EPI"):
                if not nome_epi or not ca:
                    st.warning("Preencha os campos obrigatórios (*).")
                else:
                    try:
                        novo_epi = {
                            "nome_epi": nome_epi,
                            "ca": ca,
                            "fabricante": fabricante,
                            "validade_ca": str(validade_ca),
                            "dias_durabilidade_media": durabilidade,
                            "quantidade_estoque": qtd_estoque
                        }
                        supabase.table("epis").insert(novo_epi).execute()
                        st.success("EPI cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar EPI: {e}")
