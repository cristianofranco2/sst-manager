import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv

def get_supabase_client() -> Client:
    load_dotenv(override=True)
    url = os.getenv("SUPABASE_URL", "https://mhrohbalngkhhpldrzsg.supabase.co")
    key = os.getenv("SUPABASE_KEY", "sb_publishable_7aCZMLZVkikSCaktM823rQ_w4mT3e-Z")
    return create_client(url, key)

def render_epis():
    st.title("🥽 Catálogo de Equipamentos de Proteção Individual (EPIs)")
    
    try:
        supabase: Client = get_supabase_client()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Catálogo Cadastrado", "Cadastrar Novo EPI"])
    
    with tab1:
        st.subheader("Equipamentos Cadastrados")
        try:
            response = supabase.table("epis").select("*").execute()
            data = response.data
            
            if data:
                df = pd.DataFrame(data)
                colunas = ['codigo_sku', 'descricao', 'categoria', 'numero_ca', 'data_validade_ca', 'estoque_minimo']
                df_exib = df[[c for c in colunas if c in df.columns]]
                st.dataframe(df_exib, use_container_width=True)
            else:
                st.info("Nenhum EPI cadastrado no catálogo.")
        except Exception as e:
            st.error(f"Erro ao carregar EPIs: {e}")
            
    with tab2:
        st.subheader("Cadastrar Novo EPI")
        
        with st.form("form_novo_epi", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                codigo_sku = st.text_input("Código Interno / SKU *")
                descricao = st.text_input("Descrição do EPI *")
                categoria = st.selectbox(
                    "Categoria / Tipo *",
                    [
                        "Proteção Respiratória",
                        "Proteção das Mãos",
                        "Proteção Auditiva",
                        "Proteção Visual/Facial",
                        "Proteção de Membros Inferiores",
                        "Proteção de Membros Superiores",
                        "Proteção contra Quedas",
                        "Proteção da Cabeça"
                    ]
                )
                modelo = st.text_input("Modelo / Referência")
                numero_ca = st.text_input("Número do CA *")
            
            with col2:
                data_validade_ca = st.date_input("Data de Validade do CA *", value=None)
                descricao_protecao = st.text_area("Descrição da Proteção / Risco Mitigado")
                possui_epc = st.selectbox("Possui EPC Associado?", ["Não", "Sim"])
                vida_util_prevista = st.text_input("Vida Útil Prevista (ex: 6 meses, 180 dias)")
                shelf_life = st.text_input("Validade de Prateleira / Shelf Life (ex: 2 anos)")
                estoque_minimo = st.number_input("Estoque Mínimo para Alerta", min_value=1, value=5)
                
            submitted = st.form_submit_button("Salvar EPI no Catálogo")
            
            if submitted:
                if not codigo_sku or not descricao or not numero_ca or not data_validade_ca:
                    st.warning("Preencha todos os campos obrigatórios (*).")
                else:
                    try:
                        novo_epi = {
                            "codigo_sku": codigo_sku,
                            "descricao": descricao,
                            "categoria": categoria,
                            "modelo": modelo,
                            "numero_ca": numero_ca,
                            "data_validade_ca": str(data_validade_ca),
                            "descricao_protecao": descricao_protecao,
                            "possui_epc": possui_epc,
                            "vida_util_prevista": vida_util_prevista,
                            "shelf_life": shelf_life,
                            "estoque_minimo": estoque_minimo
                        }
                        supabase.table("epis").insert(novo_epi).execute()
                        st.success("EPI cadastrado no catálogo com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar EPI: {e}")
