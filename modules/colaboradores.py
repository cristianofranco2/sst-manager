import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mhrohbalngkhhpldrzsg.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_7aCZMLZVkikSCaktM823rQ_w4mT3e-Z").strip()

@st.cache_resource(ttl=3600)
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def render_colaboradores():
    st.title("👥 Gestão de Colaboradores")
    
    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Listar / Gerenciar Colaboradores", "➕ Cadastrar Novo Colaborador"])

    with tab1:
        st.subheader("Colaboradores Cadastrados")
        try:
            res = supabase.table("colaboradores").select("*").execute()
            data = res.data or []
            if data:
                df = pd.DataFrame(data)
                
                # Seleção e formatação visual das colunas na tabela
                colunas_desejadas = [
                    "matricula", "nome_completo", "cpf", "rg", "data_nascimento", 
                    "cargo", "setor", "tipo_contrato", "email", "telefone", 
                    "data_admissao", "status"
                ]
                colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
                
                df_exibir = df[colunas_existentes].rename(columns={
                    "matricula": "Matrícula",
                    "nome_completo": "Nome Completo",
                    "cpf": "CPF",
                    "rg": "RG",
                    "data_nascimento": "Data Nasc.",
                    "cargo": "Cargo",
                    "setor": "Setor / Depto",
                    "tipo_contrato": "Contrato",
                    "email": "E-mail",
                    "telefone": "Telefone",
                    "data_admissao": "Admissão",
                    "status": "Status"
                })
                
                st.dataframe(df_exibir, use_container_width=True)
            else:
                st.info("Nenhum colaborador encontrado no banco de dados.")
        except Exception as e:
            st.error(f"Erro ao consultar colaboradores: {e}")

    with tab2:
        st.subheader("Ficha Completa de Cadastro do Colaborador")
        with st.form("form_cadastro_colaborador_completo", clear_on_submit=True):
            
            st.markdown("##### 📄 Dados Pessoais e Identificação")
            c1, c2, c3 = st.columns(3)
            with c1:
                matricula = st.text_input("Matrícula *")
                nome_completo = st.text_input("Nome Completo *")
            with c2:
                cpf = st.text_input("CPF * (somente números)")
                rg = st.text_input("RG")
            with c3:
                data_nascimento = st.date_input("Data de Nascimento")
                sexo = st.selectbox("Gênero", ["Masculino", "Feminino", "Outro", "Não informado"])

            st.markdown("---")
            st.markdown("##### 🏢 Dados Profissionais e Alocação")
            c4, c5, c6 = st.columns(3)
            with c4:
                cargo = st.text_input("Cargo / Função *")
                setor = st.text_input("Setor / Departamento *")
            with c5:
                tipo_contrato = st.selectbox("Tipo de Contrato", ["CLT", "PJ", "Estágio", "Temporário", "Terceirizado"])
                data_admissao = st.date_input("Data de Admissão *")
            with c6:
                status = st.selectbox("Status Inicial", ["Ativo", "Afastado", "Férias", "Desligado"])
                gestor_direto = st.text_input("Gestor Direto / Supervisor")

            st.markdown("---")
            st.markdown("##### 📞 Contato e Observações SST")
            c7, c8 = st.columns(2)
            with c7:
                email = st.text_input("E-mail Corporal / Pessoal")
                telefone = st.text_input("Telefone / WhatsApp")
            with c8:
                observacoes_sst = st.text_area("Observações de SST (Restrições, PCD, etc.)")

            submitted = st.form_submit_button("💾 Salvar Ficha de Colaborador")
            
            if submitted:
                if not matricula or not nome_completo or not cpf or not cargo or not setor:
                    st.warning("Preencha todos os campos obrigatórios assinalados com (*).")
                else:
                    try:
                        novo_colaborador = {
                            "matricula": matricula,
                            "nome_completo": nome_completo,
                            "cpf": cpf,
                            "rg": rg,
                            "data_nascimento": str(data_nascimento),
                            "genero": sexo,
                            "cargo": cargo,
                            "setor": setor,
                            "tipo_contrato": tipo_contrato,
                            "data_admissao": str(data_admissao),
                            "status": status,
                            "gestor_direto": gestor_direto,
                            "email": email,
                            "telefone": telefone,
                            "observacoes_sst": observacoes_sst
                        }
                        
                        supabase.table("colaboradores").insert(novo_colaborador).execute()
                        st.success("Ficha do colaborador cadastrada com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar cadastro no Supabase: {e}")
