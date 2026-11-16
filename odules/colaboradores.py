import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_connection() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Erro: Credenciais SUPABASE_URL ou SUPABASE_KEY não configuradas no arquivo .env!")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

def render_colaboradores():
    st.title("👥 Gestão de Colaboradores")
    
    tab1, tab2 = st.tabs(["Listar / Gerenciar", "Novo Colaborador"])
    
    with tab1:
        st.subheader("Colaboradores Cadastrados")
        try:
            response = supabase.table("colaboradores").select("*").execute()
            data = response.data
            
            if data:
                df = pd.DataFrame(data)
                colunas_exibicao = ['matricula', 'nome_completo', 'cpf', 'cargo', 'centro_custo', 'status']
                df_exib = df[[c for c in colunas_exibicao if c in df.columns]]
                
                st.dataframe(df_exib, use_container_width=True)
                
                st.markdown("### Atualizar Status do Colaborador")
                matricula_sel = st.selectbox("Selecione pela Matrícula", df['matricula'].tolist())
                
                colab_selecionado = df[df['matricula'] == matricula_sel].iloc[0]
                
                with st.form(key="form_update_colab"):
                    novo_status = st.selectbox(
                        "Status do Colaborador",
                        ["Ativo", "Afastado", "Férias", "Desligado"],
                        index=["Ativo", "Afastado", "Férias", "Desligado"].index(colab_selecionado['status']) if colab_selecionado['status'] in ["Ativo", "Afastado", "Férias", "Desligado"] else 0
                    )
                    submit_update = st.form_submit_button("Atualizar Status")
                    
                    if submit_update:
                        supabase.table("colaboradores").update({"status": novo_status}).eq("matricula", matricula_sel).execute()
                        st.success("Status atualizado com sucesso!")
                        st.rerun()
            else:
                st.info("Nenhum colaborador cadastrado ainda.")
        except Exception as e:
            st.error(f"Erro ao conectar com o Supabase: {e}")
            
    with tab2:
        st.subheader("Cadastrar Novo Colaborador")
        
        with st.form("form_novo_colaborador", clear_on_submit=True):
            st.markdown("#### 1. Dados Pessoais")
            col1, col2 = st.columns(2)
            with col1:
                nome_completo = st.text_input("Nome Completo *")
                cpf = st.text_input("CPF * (Ex: 000.000.000-00)")
                rg_numero = st.text_input("Número do RG")
                rg_orgao_emissor = st.text_input("Órgão Emissor")
                rg_data_emissao = st.date_input("Data de Emissão do RG", value=None)
                rg_uf = st.text_input("UF do RG (Ex: SP)", max_chars=2)
                data_nascimento = st.date_input("Data de Nascimento", value=None)
            with col2:
                genero = st.selectbox("Sexo / Gênero", ["Masculino", "Feminino", "Outro", "Não Informar"])
                estado_civil = st.selectbox("Estado Civil", ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "Outro"])
                nacionalidade = st.text_input("Nacionalidade", value="Brasileira")
                naturalidade = st.text_input("Naturalidade (Cidade/UF)")
                nome_mae = st.text_input("Nome da Mãe")
                nome_pai = st.text_input("Nome do Pai")
            
            st.markdown("#### 2. Endereço e Contato")
            col3, col4 = st.columns(2)
            with col3:
                logradouro = st.text_input("Logradouro, Número e Complemento")
                bairro = st.text_input("Bairro")
                cidade = st.text_input("Cidade")
                uf = st.text_input("UF", max_chars=2)
            with col4:
                cep = st.text_input("CEP")
                telefone = st.text_input("Telefone / Celular")
                email_pessoal = st.text_input("E-mail Pessoal")
                
            st.markdown("#### 3. Dados Contratuais e Funcionais")
            col5, col6 = st.columns(2)
            with col5:
                matricula = st.text_input("Matrícula Interna / Código *")
                data_admissao = st.date_input("Data de Admissão", value=None)
                tipo_contrato = st.selectbox("Tipo de Contrato", ["CLT", "Estágio", "PJ", "Aprendiz", "Temporário"])
                cargo = st.text_input("Cargo / Função *")
                cbo = st.text_input("CBO (Classificação Brasileira de Ocupações)")
            with col6:
                centro_custo = st.text_input("Centro de Custo / Departamento / Setor")
                turno = st.text_input("Turno / Escala de Trabalho")
                superior_imediato = st.text_input("Superior Imediato / Gestor")
                status = st.selectbox("Status do Colaborador", ["Ativo", "Afastado", "Férias", "Desligado"])
                
            submitted = st.form_submit_button("Salvar Colaborador")
            
            if submitted:
                if not nome_completo or not cpf or not matricula or not cargo:
                    st.warning("Preencha os campos obrigatórios (*): Nome, CPF, Matrícula e Cargo.")
                else:
                    try:
                        novo_dado = {
                            "nome_completo": nome_completo,
                            "cpf": cpf,
                            "rg_numero": rg_numero if rg_numero else None,
                            "rg_orgao_emissor": rg_orgao_emissor if rg_orgao_emissor else None,
                            "rg_data_emissao": str(rg_data_emissao) if rg_data_emissao else None,
                            "rg_uf": rg_uf if rg_uf else None,
                            "data_nascimento": str(data_nascimento) if data_nascimento else None,
                            "genero": genero,
                            "estado_civil": estado_civil,
                            "nacionalidade": nacionalidade,
                            "naturalidade": naturalidade if naturalidade else None,
                            "nome_mae": nome_mae if nome_mae else None,
                            "nome_pai": nome_pai if nome_pai else None,
                            "logradouro": logradouro if logradouro else None,
                            "bairro": bairro if bairro else None,
                            "cidade": cidade if cidade else None,
                            "uf": uf if uf else None,
                            "cep": cep if cep else None,
                            "telefone": telefone if telefone else None,
                            "email_pessoal": email_pessoal if email_pessoal else None,
                            "matricula": matricula,
                            "data_admissao": str(data_admissao) if data_admissao else None,
                            "tipo_contrato": tipo_contrato,
                            "cargo": cargo,
                            "cbo": cbo if cbo else None,
                            "centro_custo": centro_custo if centro_custo else None,
                            "turno": turno if turno else None,
                            "superior_imediato": superior_imediato if superior_imediato else None,
                            "status": status
                        }
                        supabase.table("colaboradores").insert(novo_dado).execute()
                        st.success("Colaborador cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar no Supabase: {e}")
