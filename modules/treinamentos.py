import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_treinamentos() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("treinamentos").select("*").order("tipo_treinamento").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_colaboradores() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("colaboradores").select("id, nome_completo, matricula").order("nome_completo").execute()
    return res.data or []


def render_treinamentos() -> None:
    st.title("🎓 Cadastro de Treinamentos")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    colaboradores = _buscar_colaboradores()
    mapa_colabs = {
        str(c["id"]): f"{c.get('nome_completo', 'Sem nome')} ({c.get('matricula', '')})"
        for c in colaboradores
        if c.get("id")
    }

    tab1, tab2 = st.tabs(["Treinamentos Cadastrados", "➕ Cadastrar Novo Treinamento"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Treinamentos Registrados")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_trein", use_container_width=True):
                _buscar_treinamentos.clear()
                _buscar_colaboradores.clear()

        try:
            dados = _buscar_treinamentos()
            if dados:
                df = pd.DataFrame(dados)
                if "colaborador_id" in df.columns:
                    df["colaborador"] = df["colaborador_id"].map(
                        lambda cid: mapa_colabs.get(str(cid), str(cid))
                    )

                colunas_desejadas = [
                    "tipo_treinamento",
                    "tipo_capacitacao",
                    "modalidade",
                    "carga_horaria",
                    "colaborador",
                    "data_emissao",
                    "data_vencimento",
                    "status",
                ]
                colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
                df_exibir = df[colunas_existentes].rename(
                    columns={
                        "tipo_treinamento": "Treinamento",
                        "tipo_capacitacao": "Capacitação",
                        "modalidade": "Modalidade",
                        "carga_horaria": "Carga Horária (h)",
                        "colaborador": "Colaborador",
                        "data_emissao": "Emissão",
                        "data_vencimento": "Vencimento",
                        "status": "Status",
                    }
                )
                st.dataframe(df_exibir, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum treinamento cadastrado até o momento.")
        except Exception as e:
            st.error(f"Erro ao carregar treinamentos: {e}")

    with tab2:
        st.subheader("Novo Treinamento")
        ids_colabs = list(mapa_colabs.keys())

        with st.form("form_cadastro_treinamento", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                tipo_treinamento = st.text_input("Nome / Tipo do Treinamento *", placeholder="Ex: NR-11 Operação de Empilhadeira")
                tipo_capacitacao = st.text_input("Tipo de Capacitação", placeholder="Ex: Formação / Reciclagem")
            with c2:
                modalidade = st.selectbox("Modalidade", ["Presencial", "Semipresencial", "EAD"])
                carga_horaria = st.number_input("Carga Horária (horas)", min_value=0, value=8, step=1)
            with c3:
                if ids_colabs:
                    colab_id = st.selectbox(
                        "Colaborador *",
                        options=ids_colabs,
                        format_func=lambda cid: mapa_colabs[cid],
                    )
                else:
                    colab_id = None
                    st.warning("Cadastre um colaborador primeiro.")

                status = st.selectbox("Status", ["Válido", "Vencido", "Em andamento", "Pendente"])

            c4, c5, c6 = st.columns(3)
            with c4:
                data_inicio = st.date_input("Data de Início")
            with c5:
                data_fim = st.date_input("Data de Término")
            with c6:
                data_emissao = st.date_input("Data de Emissão")
                data_vencimento = st.date_input("Data de Vencimento *")

            submitted = st.form_submit_button("💾 Salvar Treinamento")

            if submitted:
                if not tipo_treinamento.strip() or not colab_id:
                    st.warning("Preencha o nome do treinamento (*) e selecione um colaborador.")
                else:
                    try:
                        novo_trein = {
                            "colaborador_id": colab_id,
                            "tipo_treinamento": tipo_treinamento.strip(),
                            "tipo_capacitacao": tipo_capacitacao.strip(),
                            "modalidade": modalidade,
                            "carga_horaria": int(carga_horaria) if carga_horaria > 0 else None,
                            "data_inicio": str(data_inicio),
                            "data_fim": str(data_fim),
                            "data_emissao": str(data_emissao),
                            "data_vencimento": str(data_vencimento),
                            "status": status,
                        }
                        supabase.table("treinamentos").insert(novo_trein).execute()
                        _buscar_treinamentos.clear()
                        st.success("Treinamento cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar treinamento no Supabase: {e}")
