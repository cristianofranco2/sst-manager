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

def render_exames():
    st.title("🩺 Gestão de Exames Médicos (ASO)")

    try:
        supabase = init_connection()
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Histórico de Exames", "Registar Novo ASO"])

    colab_map = {}
    colab_dict = {}
    try:
        res_c = supabase.table("colaboradores").select("id, nome_completo, matricula, cargo").execute()
        for c in (res_c.data or []):
            colab_map[c['id']] = c
            colab_dict[f"{c['matricula']} - {c['nome_completo']} ({c['cargo']})"] = c['id']
    except Exception as e:
        st.error(f"Erro ao carregar colaboradores: {e}")

    with tab1:
        st.subheader("ASOs Registados")
        try:
            res_e = supabase.table("exames_medicos").select("*").execute()
            exames_data = res_e.data or []

            if exames_data:
                registos = []
                for item in exames_data:
                    c_info = colab_map.get(item.get('colaborador_id'), {})
                    registos.append({
                        "Matrícula": c_info.get('matricula', '-'),
                        "Colaborador": c_info.get('nome_completo', '-'),
                        "Cargo": c_info.get('cargo', '-'),
                        "Data Realização": item.get('data_realizacao'),
                        "Resultado": item.get('resultado'),
                        "Vencimento": item.get('data_vencimento'),
                        "Médico": item.get('medico_examinador'),
                        "CRM/UF": item.get('crm_uf')
                    })
                st.dataframe(pd.DataFrame(registos), use_container_width=True)
            else:
                st.info("Nenhum exame médico registado.")
        except Exception as e:
            st.error(f"Erro ao listar exames: {e}")

    with tab2:
        st.subheader("Lançamento de ASO / Exame Periódico")

        if not colab_dict:
            st.warning("Cadastre colaboradores antes de registar exames.")
            return

        colab_sel = st.selectbox("Selecione o Colaborador *", list(colab_dict.keys()))
        colaborador_id = colab_dict[colab_sel]

        with st.form("form_novo_aso", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                data_realizacao = st.date_input("Data da Realização *")
                resultado = st.selectbox("Resultado *", ["Apto", "Inapto", "Apto com Restrição"])
                descricao_restricoes = st.text_area("Descrição das Restrições (se houver)")
                data_vencimento = st.date_input("Data de Vencimento *")
            with col2:
                medico_examinador = st.text_input("Médico Examinador *")
                crm_uf = st.text_input("CRM e UF * (ex: 123456/SP)")

            if st.form_submit_button("Salvar Registo"):
                if not medico_examinador or not crm_uf:
                    st.warning("Preencha todos os campos obrigatórios (*).")
                else:
                    try:
                        novo_aso = {
                            "colaborador_id": colaborador_id,
                            "data_realizacao": str(data_realizacao),
                            "resultado": resultado,
                            "descricao_restricoes": descricao_restricoes if resultado == "Apto com Restrição" else None,
                            "data_vencimento": str(data_vencimento),
                            "medico_examinador": medico_examinador,
                            "crm_uf": crm_uf
                        }
                        supabase.table("exames_medicos").insert(novo_aso).execute()
                        st.success("ASO registado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
