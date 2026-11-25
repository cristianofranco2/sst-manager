import streamlit as st
import pandas as pd
from database import get_supabase

def render_colaboradores():
    st.title("👥 Gestão de Colaboradores")
    
    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Listar / Gerenciar", "Novo Colaborador"])

    with tab1:
        st.subheader("Colaboradores Cadastrados")
        try:
            res = supabase.table("colaboradores").select("*").execute()
            data = res.data or []
            if data:
                df = pd.DataFrame(data)
                colunas = [c for c in ["matricula", "nome_completo", "cpf", "cargo", "setor", "data_admissao", "status"] if c in df.columns]
                st.dataframe(df[colunas] if colunas else df, use_container_width=True)
            else:
                st.info("Nenhum colaborador encontrado.")
        except Exception as e:
            st.error(f"Erro ao consultar colaboradores: {e}")

    with tab2:
        st.subheader("Cadastrar Colaborador")
        with st.form("form_colab", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                matricula = st.text_input("Matrícula *")
                nome = st.text_input("Nome Completo *")
                cpf = st.text_input("CPF *")
            with c2:
                cargo = st.text_input("Cargo *")
                setor = st.text_input("Setor *")
                data_adm = st.date_input("Data de Admissão *")

            if st.form_submit_button("Salvar"):
                if not matricula or not nome or not cpf or not cargo:
                    st.warning("Preencha os campos obrigatórios (*).")
                else:
                    try:
                        novo = {
                            "matricula": matricula,
                            "nome_completo": nome,
                            "cpf": cpf,
                            "cargo": cargo,
                            "setor": setor,
                            "data_admissao": str(data_adm),
                            "status": "Ativo"
                        }
                        supabase.table("colaboradores").insert(novo).execute()
                        st.success("Colaborador cadastrado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
