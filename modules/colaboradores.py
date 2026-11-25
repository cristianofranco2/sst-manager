import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mhrohbalngkhhpldrzsg.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_7aCZMLZVkikSCaktM823rQ_w4mT3e-Z").strip()

@st.cache_resource
def init_connection() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def render_colaboradores():
    st.title("👷 Gestão de Colaboradores")
    
    try:
        supabase = init_connection()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Lista de Colaboradores", "Cadastrar Novo Colaborador"])

    with tab1:
        st.subheader("Colaboradores Ativos")
        try:
            res = supabase.table("colaboradores").select("*").execute()
            data = res.data or []
            if data:
                df = pd.DataFrame(data)
                # Seleciona e renomeia colunas relevantes se existirem
                colunas_exibir = [c for c in ["matricula", "nome_completo", "cpf", "cargo", "setor", "data_admissao", "status"] if c in df.columns]
                st.dataframe(df[colunas_exibir] if colunas_exibir else df, use_container_width=True)
            else:
                st.info("Nenhum colaborador cadastrado.")
        except Exception as e:
            st.error(f"Erro ao carregar colaboradores: {e}")

    with tab2:
        st.subheader("Formulário de Cadastro")
        with st.form("form_novo_colaborador", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                matricula = st.text_input("Matrícula *")
                nome_completo = st.text_input("Nome Completo *")
                cpf = st.text_input("CPF *")
            with col2:
                cargo = st.text_input("Cargo *")
                setor = st.text_input("Setor / Departamento *")
                data_admissao = st.date_input("Data de Admissão *")

            submitted = st.form_submit_button("Salvar Colaborador")
            if submitted:
                if not matricula or not nome_completo or not cpf or not cargo:
                    st.warning("Preencha todos os campos obrigatórios (*).")
                else:
                    try:
                        novo_c = {
                            "matricula": matricula,
                            "nome_completo": nome_completo,
                            "cpf": cpf,
                            "cargo": cargo,
                            "setor": setor,
                            "data_admissao": str(data_admissao),
                            "status": "Ativo"
                        }
                        supabase.table("colaboradores").insert(novo_c).execute()
                        st.success("Colaborador cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar colaborador: {e}")
