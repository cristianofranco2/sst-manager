import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_colaboradores() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("colaboradores").select("*").execute()
    return res.data or []


def render_colaboradores() -> None:
    st.title("👥 Gestão de Colaboradores")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Listar / Gerenciar Colaboradores", "➕ Cadastrar Novo Colaborador"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Colaboradores Cadastrados")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_colabs", use_container_width=True):
                _buscar_colaboradores.clear()

        try:
            data = _buscar_colaboradores()
            if data:
                df = pd.DataFrame(data)
                colunas_desejadas = [
                    "matricula",
                    "nome_completo",
                    "cpf",
                    "rg",
                    "data_nascimento",
                    "cargo",
                    "setor",
                    "tipo_contrato",
                    "email",
                    "telefone",
                    "data_admissao",
                    "status",
                ]
                colunas_existentes = [c for c in colunas_desejadas if c in df.columns]

                df_exibir = df[colunas_existentes].rename(
                    columns={
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
                        "status": "Status",
                    }
                )
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
                tipo_contrato = st.selectbox(
                    "Tipo de Contrato", ["CLT", "PJ", "Estágio", "Temporário", "Terceirizado"]
                )
                data_admissao = st.date_input("Data de Admissão *")
            with c6:
                status = st.selectbox("Status Inicial", ["Ativo", "Afastado", "Férias", "Desligado"])
                gestor_direto = st.text_input("Gestor Direto / Supervisor")

            st.markdown("---")
            st.markdown("##### 📞 Contato e Observações SST")
            c7, c8 = st.columns(2)
            with c7:
                email = st.text_input("E-mail Corporativo / Pessoal")
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
                            "matricula": matricula.strip(),
                            "nome_completo": nome_completo.strip(),
                            "cpf": cpf.strip(),
                            "rg": rg.strip(),
                            "data_nascimento": str(data_nascimento),
                            "genero": sexo,
                            "cargo": cargo.strip(),
                            "setor": setor.strip(),
                            "tipo_contrato": tipo_contrato,
                            "data_admissao": str(data_admissao),
                            "status": status,
                            "gestor_direto": gestor_direto.strip(),
                            "email": email.strip(),
                            "telefone": telefone.strip(),
                            "observacoes_sst": observacoes_sst.strip(),
                        }
                        supabase.table("colaboradores").insert(novo_colaborador).execute()
                        _buscar_colaboradores.clear()
                        st.success("Ficha do colaborador cadastrada com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar cadastro no Supabase: {e}")
