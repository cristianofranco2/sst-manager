import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_colaboradores_opcoes() -> list[dict]:
    supabase = get_supabase()
    res = (
        supabase.table("colaboradores")
        .select("id, matricula, nome_completo, cargo, centro_custo, status")
        .order("nome_completo")
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_treinamentos() -> list[dict]:
    supabase = get_supabase()
    res = (
        supabase.table("treinamentos")
        .select(
            "id, colaborador_id, tipo_treinamento, tipo_capacitacao, modalidade, "
            "carga_horaria, data_inicio, data_fim, data_emissao, data_vencimento, "
            "status, created_at"
        )
        .order("data_vencimento", desc=False)
        .execute()
    )
    return res.data or []


def _limpar_cache_treinamentos() -> None:
    _buscar_treinamentos.clear()
    _buscar_colaboradores_opcoes.clear()


def render_treinamentos() -> None:
    st.title("🎓 Controle de Treinamentos e Capacitações (SST)")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    colaboradores = _buscar_colaboradores_opcoes()
    mapa_colaboradores: dict[str, str] = {}
    for c in colaboradores:
        cid = str(c.get("id", "")).strip()
        if cid:
            mat = str(c.get("matricula") or "").strip()
            nome = str(c.get("nome_completo") or "Sem nome").strip()
            cargo = str(c.get("cargo") or "").strip()
            label = f"{nome} ({mat})" if mat else nome
            if cargo:
                label = f"{label} — {cargo}"
            mapa_colaboradores[cid] = label

    tab1, tab2 = st.tabs(["Treinamentos Cadastrados", "➕ Registrar Treinamento"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Histórico e Vencimentos de Treinamentos")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_treinamentos", use_container_width=True):
                _limpar_cache_treinamentos()

        try:
            dados = _buscar_treinamentos()
            if dados:
                df = pd.DataFrame(dados)
                df["Colaborador"] = df["colaborador_id"].astype(str).map(
                    lambda x: mapa_colaboradores.get(x, x)
                )

                colunas_desejadas = [
                    "Colaborador",
                    "tipo_treinamento",
                    "tipo_capacitacao",
                    "modalidade",
                    "carga_horaria",
                    "data_inicio",
                    "data_fim",
                    "data_emissao",
                    "data_vencimento",
                    "status",
                ]
                colunas_existentes = [c for c in colunas_desejadas if c in df.columns]

                df_exibir = df[colunas_existentes].rename(
                    columns={
                        "tipo_treinamento": "Treinamento / NR",
                        "tipo_capacitacao": "Tipo de Capacitação",
                        "modalidade": "Modalidade",
                        "carga_horaria": "Carga Horária (h)",
                        "data_inicio": "Início",
                        "data_fim": "Fim",
                        "data_emissao": "Emissão",
                        "data_vencimento": "Vencimento",
                        "status": "Status",
                    }
                )
                st.dataframe(df_exibir, use_container_width=True)
            else:
                st.info("Nenhum treinamento registrado até o momento.")
        except Exception as e:
            st.error(f"Erro ao carregar treinamentos: {e}")

    with tab2:
        st.subheader("Novo Registro de Treinamento")

        if not mapa_colaboradores:
            st.warning(
                "Nenhum colaborador encontrado na tabela `colaboradores`. "
                "Cadastre um colaborador primeiro para vincular o treinamento."
            )
            return

        ids_ordenados = list(mapa_colaboradores.keys())

        with st.form("form_cadastro_treinamento", clear_on_submit=True):
            st.markdown("##### 👤 Colaborador e Enquadramento")
            c1, c2 = st.columns(2)
            with c1:
                colaborador_id = st.selectbox(
                    "Colaborador *",
                    options=ids_ordenados,
                    format_func=lambda cid: mapa_colaboradores.get(cid, cid),
                )
                tipo_treinamento = st.text_input(
                    "Tipo de Treinamento / Norma *",
                    placeholder="Ex: NR-35 Trabalho em Altura, NR-11 Empilhadeira, NR-12",
                )
            with c2:
                tipo_capacitacao = st.selectbox(
                    "Tipo de Capacitação",
                    ["Inicial", "Periódica", "Reciclagem", "Eventual"],
                )
                modalidade = st.selectbox(
                    "Modalidade",
                    ["Presencial", "Semipresencial", "EAD / Online", "Prática em Campo"],
                )

            st.markdown("---")
            st.markdown("##### 📅 Carga Horária, Datas e Status")
            c3, c4, c5 = st.columns(3)
            with c3:
                carga_horaria = st.number_input("Carga Horária (horas)", min_value=1, max_value=1000, value=8)
                status = st.selectbox("Status", ["Válido", "A Vencer", "Vencido", "Pendente"])
            with c4:
                data_inicio = st.date_input("Data de Início")
                data_fim = st.date_input("Data de Término")
            with c5:
                data_emissao = st.date_input("Data de Emissão do Certificado")
                data_vencimento = st.date_input("Data de Vencimento *")

            submitted = st.form_submit_button("💾 Salvar Treinamento")

            if submitted:
                if not colaborador_id or not tipo_treinamento.strip() or not data_vencimento:
                    st.warning("Preencha todos os campos obrigatórios (*).")
                elif data_fim < data_inicio:
                    st.warning("A data de término não pode ser anterior à data de início.")
                else:
                    try:
                        novo_treinamento = {
                            "colaborador_id": colaborador_id,
                            "tipo_treinamento": tipo_treinamento.strip(),
                            "tipo_capacitacao": tipo_capacitacao,
                            "modalidade": modalidade,
                            "carga_horaria": int(carga_horaria),
                            "data_inicio": str(data_inicio),
                            "data_fim": str(data_fim),
                            "data_emissao": str(data_emissao),
                            "data_vencimento": str(data_vencimento),
                            "status": status,
                        }
                        supabase.table("treinamentos").insert(novo_treinamento).execute()
                        _limpar_cache_treinamentos()
                        st.success("Treinamento registrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar treinamento no Supabase: {e}")
