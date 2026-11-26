from datetime import date, datetime
import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_treinamentos() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("treinamentos").select("*").order("tipo_treinamento").execute()
    return res.data or []


def _formatar_data_br(valor) -> str:
    if not valor:
        return "—"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor).strip()[:10]
    if not texto:
        return "—"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return texto


def render_treinamentos() -> None:
    st.title("🎓 Cadastro de Treinamentos")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Treinamentos Cadastrados", "➕ Cadastrar Novo Treinamento"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Catálogo de Treinamentos")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_trein", use_container_width=True):
                _buscar_treinamentos.clear()

        dados = _buscar_treinamentos()
        if dados:
            df = pd.DataFrame(dados)
            for col_d in ["data_inicio", "data_fim", "data_emissao", "data_realizacao", "data_vencimento"]:
                if col_d in df.columns:
                    df[col_d] = df[col_d].map(_formatar_data_br)

            colunas_desejadas = [
                "tipo_treinamento",
                "tipo_capacitacao",
                "modalidade",
                "carga_horaria",
                "validade_meses",
                "status",
            ]
            colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
            df_exibir = df[colunas_existentes].rename(
                columns={
                    "tipo_treinamento": "Treinamento",
                    "tipo_capacitacao": "Capacitação",
                    "modalidade": "Modalidade",
                    "carga_horaria": "Carga Horária (h)",
                    "validade_meses": "Validade (meses)",
                    "status": "Status",
                }
            )
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum treinamento cadastrado até o momento.")

    with tab2:
        st.subheader("Novo Treinamento")
        with st.form("form_cadastro_treinamento", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                tipo_treinamento = st.text_input(
                    "Nome / Tipo do Treinamento *",
                    placeholder="Ex: NR-11 Operação de Empilhadeira",
                )
                tipo_capacitacao = st.text_input(
                    "Tipo de Capacitação",
                    placeholder="Ex: Formação / Reciclagem",
                )
            with c2:
                modalidade = st.selectbox("Modalidade", ["Presencial", "Semipresencial", "EAD"])
                carga_horaria = st.number_input("Carga Horária (horas)", min_value=0, value=8, step=1)
            with c3:
                validade_meses = st.number_input(
                    "Validade Padrão (meses)",
                    min_value=1,
                    max_value=120,
                    value=12,
                    step=1,
                )
                status = st.selectbox("Status", ["Ativo", "Em revisão", "Inativo"])

            submitted = st.form_submit_button("💾 Salvar Treinamento")

            if submitted:
                if not tipo_treinamento.strip():
                    st.warning("Informe o nome do treinamento (*).")
                else:
                    try:
                        novo_trein = {
                            "tipo_treinamento": tipo_treinamento.strip(),
                            "tipo_capacitacao": tipo_capacitacao.strip(),
                            "modalidade": modalidade,
                            "carga_horaria": int(carga_horaria) if carga_horaria > 0 else None,
                            "validade_meses": int(validade_meses),
                            "status": status,
                        }
                        supabase.table("treinamentos").insert(novo_trein).execute()
                        _buscar_treinamentos.clear()
                        st.success("Treinamento cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar treinamento no Supabase: {e}")
