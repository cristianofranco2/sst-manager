import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo


def _para_maiusculo(texto: str | None) -> str:
    return " ".join(str(texto or "").strip().upper().split())


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_funcoes() -> list[dict]:
    supabase = get_supabase()
    res = (
        supabase.table("funcoes")
        .select(
            "id, nome_funcao, cbo, setor_padrao, descricao_atividades, "
            "riscos_principais, ativo, created_at"
        )
        .order("nome_funcao")
        .execute()
    )
    return res.data or []


def render_funcoes() -> None:
    render_cabecalho_modulo("💼 Cadastro de Cargos")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Cargos Cadastrados", "➕ Cadastrar Novo Cargo"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Cargos da Empresa")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_funcoes", use_container_width=True):
                _buscar_funcoes.clear()
                st.rerun()

        try:
            dados = _buscar_funcoes()
            if dados:
                df = pd.DataFrame(dados)
                if "ativo" in df.columns:
                    df["ativo"] = df["ativo"].map(lambda v: "ATIVO" if bool(v) else "INATIVO")

                colunas_desejadas = [
                    "nome_funcao",
                    "cbo",
                    "setor_padrao",
                    "descricao_atividades",
                    "riscos_principais",
                    "ativo",
                ]
                colunas_existentes = [c for c in colunas_desejadas if c in df.columns]

                for col in colunas_existentes:
                    if col != "ativo":
                        df[col] = df[col].map(lambda v: _para_maiusculo(v) if v is not None else "")

                df_exibir = df[colunas_existentes].rename(
                    columns={
                        "nome_funcao": "Cargo / Função",
                        "cbo": "CBO",
                        "setor_padrao": "Setor Padrão",
                        "descricao_atividades": "Descrição das Atividades",
                        "riscos_principais": "Riscos Principais",
                        "ativo": "Status",
                    }
                )
                st.dataframe(df_exibir, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum cargo cadastrado até o momento.")
        except Exception as e:
            st.error(f"Erro ao carregar cargos: {e}")

    with tab2:
        st.subheader("Novo Cargo")
        with st.form("form_cadastro_funcao", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                nome_funcao = st.text_input(
                    "Nome do Cargo / Função *",
                    placeholder="Ex: Gerente, Operador de Empilhadeira",
                )
            with c2:
                cbo = st.text_input(
                    "Código CBO",
                    placeholder="Ex: 7822-20",
                )
            with c3:
                setor_padrao = st.text_input(
                    "Setor / Área Padrão",
                    placeholder="Ex: Armazém / Expedição / Gestão",
                )

            c4, c5 = st.columns(2)
            with c4:
                descricao_atividades = st.text_area(
                    "Descrição das Atividades",
                    placeholder="Principais rotinas e responsabilidades do cargo...",
                )
            with c5:
                riscos_principais = st.text_area(
                    "Riscos Ocupacionais Principais",
                    placeholder="Ex: Ruído, movimentação de cargas, atropelamento/colisão...",
                )

            ativo = st.checkbox("Cargo ativo", value=True)
            submitted = st.form_submit_button("💾 Salvar Cargo")

            if submitted:
                if not nome_funcao.strip():
                    st.warning("Informe o nome do cargo (*).")
                else:
                    try:
                        nova_funcao = {
                            "nome_funcao": _para_maiusculo(nome_funcao),
                            "cbo": _para_maiusculo(cbo),
                            "setor_padrao": _para_maiusculo(setor_padrao),
                            "descricao_atividades": _para_maiusculo(descricao_atividades),
                            "riscos_principais": _para_maiusculo(riscos_principais),
                            "ativo": bool(ativo),
                        }
                        supabase.table("funcoes").insert(nova_funcao).execute()
                        _buscar_funcoes.clear()
                        st.success("Cargo cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar cargo no Supabase: {e}")


render_funcoes = render_funcoes
