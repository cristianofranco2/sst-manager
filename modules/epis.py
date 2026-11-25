import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_epis() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("epis").select("*").execute()
    return res.data or []


def render_epis() -> None:
    st.title("🥽 Catálogo de EPIs")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["Catálogo Cadastrado", "Cadastrar Novo EPI"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Equipamentos Cadastrados")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_epis", use_container_width=True):
                _buscar_epis.clear()

        try:
            data = _buscar_epis()
            if data:
                df = pd.DataFrame(data)
                colunas = [
                    "codigo_sku",
                    "descricao",
                    "categoria",
                    "numero_ca",
                    "data_validade_ca",
                    "dias_durabilidade_media",
                    "quantidade_estoque",
                ]
                colunas_existentes = [c for c in colunas if c in df.columns]
                st.dataframe(df[colunas_existentes] if colunas_existentes else df, use_container_width=True)
            else:
                st.info("Nenhum EPI cadastrado no catálogo.")
        except Exception as e:
            st.error(f"Erro ao carregar catálogo de EPIs: {e}")

    with tab2:
        st.subheader("Cadastrar Novo EPI")
        with st.form("form_novo_epi", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                codigo_sku = st.text_input("Código SKU / Identificador *")
                descricao = st.text_input("Nome / Descrição do EPI *")
                categoria = st.selectbox("Categoria *", ["Proteção Head", "Proteção Visual", "Proteção Auditiva", "Proteção Respiratória", "Proteção das Mãos", "Calçados", "Proteção Contra Quedas"])
                fabricante = st.text_input("Fabricante")
            with c2:
                ca = st.text_input("Número do CA (Certificado de Aprovação) *")
                validade_ca = st.date_input("Data de Validade do CA *")
                durabilidade = st.number_input("Durabilidade Média (em dias)", min_value=1, value=180)
                qtd_estoque = st.number_input("Quantidade em Estoque", min_value=0, value=0)

            if st.form_submit_button("Salvar EPI"):
                if not codigo_sku or not descricao or not ca:
                    st.warning("Preencha os campos obrigatórios (*).")
                else:
                    try:
                        novo_epi = {
                            "codigo_sku": codigo_sku.strip(),
                            "descricao": descricao.strip(),
                            "categoria": categoria,
                            "fabricante": fabricante.strip(),
                            "numero_ca": ca.strip(),
                            "ca": ca.strip(),
                            "data_validade_ca": str(validade_ca),
                            "validade_ca": str(validade_ca),
                            "dias_durabilidade_media": int(durabilidade),
                            "quantidade_estoque": int(qtd_estoque),
                            "nome_epi": descricao.strip()
                        }
                        supabase.table("epis").insert(novo_epi).execute()
                        _buscar_epis.clear()
                        st.success("EPI cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar EPI: {e}")
