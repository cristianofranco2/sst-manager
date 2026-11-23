import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mhrohbalngkhhpldrzsg.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_7aCZMLZVkikSCaktM823rQ_w4mT3e-Z").strip()

@st.cache_resource
def init_connection() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Erro: Credenciais SUPABASE_URL ou SUPABASE_KEY não configuradas no arquivo .env!")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Instancia a conexão global no módulo
supabase = init_connection()

def render_exames():
    st.title("🩺 Gestão de Exames Médicos (ASO)")
    
    tab1, tab2 = st.tabs(["Histórico de Exames", "Registar Novo ASO"])
    
    # 1. Carrega o mapa de colaboradores (evita JOIN via PostgREST/DNS)
    colab_map = {}
    colab_dict = {}
    try:
        res_colabs = supabase.table("colaboradores").select("id, nome_completo, matricula, cargo").execute()
        colabs_data = res_colabs.data or []
        for c in colabs_data:
            colab_map[c['id']] = c
            colab_dict[f"{c['matricula']} - {c['nome_completo']} ({c['cargo']})"] = c['id']
    except Exception as e:
        st.error(f"Não foi possível buscar a lista de colaboradores: {e}")

    with tab1:
        st.subheader("ASOs Registados")
        try:
            # Consulta simples na tabela de exames
            res_exames = supabase.table("exames_medicos").select("*").execute()
            exames_data = res_exames.data or []
            
            if exames_data:
                registos = []
                for item in exames_data:
                    c_id = item.get('colaborador_id')
                    c_info = colab_map.get(c_id, {})
                    
                    registos.append({
                        "Matrícula": c_info.get('matricula', '-'),
                        "Colaborador": c_info.get('nome_completo', '-'),
                        "Cargo": c_info.get('cargo', '-'),
                        "Data Realização": item.get('data_realizacao'),
                        "Resultado": item.get('resultado'),
                        "Próximo Exame (Vencimento)": item.get('data_vencimento'),
                        "Médico": item.get('medico_examinador'),
                        "CRM/UF": item.get('crm_uf')
                    })
                df_exib = pd.DataFrame(registos)
                st.dataframe(df_exib, use_container_width=True)
            else:
                st.info("Nenhum exame médico registado até ao momento.")
        except Exception as e:
            st.error(f"Erro ao carregar exames: {e}")

    with tab2:
        st.subheader("Lançamento de ASO / Exame Periódico")
        
        if not colab_dict:
            st.warning("Cadastre colaboradores antes de registar exames médicos.")
            return
            
        colab_sel_label = st.selectbox("Selecione o Colaborador *", list(colab_dict.keys()))
        colaborador_id = colab_dict[colab_sel_label]
        
        with st.form("form_novo_aso", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                data_realizacao = st.date_input("Data da Realização do ASO *")
                resultado = st.selectbox("Resultado do Exame *", ["Apto", "Inapto", "Apto com Restrição"])
                descricao_restricoes = st.text_area("Descrição das Restrições (se houver)")
                data_vencimento = st.date_input("Data de Vencimento / Próximo Exame *")
                
            with col2:
                medico_examinador = st.text_input("Nome do Médico Examinador *")
                crm_uf = st.text_input("CRM e UF do Médico (ex: 123456/SP) *")
                
                st.markdown("##### Exames Complementares Realizados")
                nome_tuss = st.text_input("Nome do Exame / Código TUSS (ex: Hemograma)")
                data_comp = st.date_input("Data do Complementar", value=None)
                res_comp = st.selectbox("Resultado Complementar", ["Normal", "Alterado"])

            submitted = st.form_submit_button("Salvar Registo de Exame")
            
            if submitted:
                if not data_realizacao or not data_vencimento or not medico_examinador:
                    st.warning("Preencha todos os campos obrigatórios (*).")
                else:
                    try:
                        exames_comp_json = []
                        if nome_tuss:
                            exames_comp_json.append({
                                "exame": nome_tuss,
                                "data": str(data_comp) if data_comp else str(data_realizacao),
                                "resultado": res_comp
                            })
                            
                        novo_aso = {
                            "colaborador_id": colaborador_id,
                            "data_realizacao": str(data_realizacao),
                            "resultado": resultado,
                            "descricao_restricoes": descricao_restricoes if resultado == "Apto com Restrição" else None,
                            "data_vencimento": str(data_vencimento),
                            "medico_examinador": medico_examinador,
                            "crm_uf": crm_uf,
                            "exames_complementares": exames_comp_json
                        }
                        
                        supabase.table("exames_medicos").insert(novo_aso).execute()
                        st.success("Exame médico ASO registado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar ASO: {e}")
