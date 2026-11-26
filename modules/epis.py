from datetime import date, datetime
import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_epis() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("epis").select("*").order("descricao").execute()
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


def render_epis() -> None:
    st.title("🥽 Cadastro de EPIs")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs(["EPIs Cadastrados", "➕ Cadastrar Novo EPI"])

    with tab1:
        col_titulo, col_acao = st.columns([4, 1])
        with col_titulo:
            st.subheader("Catálogo de EPIs")
        with col_acao:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_epis", use_container_width=True):
                _buscar_epis.clear()

        try:
            dados = _buscar_epis()
            if dados:
                df = pd.DataFrame(dados)
                for col_data in ["data_validade_ca", "validade_ca"]:
                    if col_data in df.columns:
                        df[col_data] = df[col_data].map(_formatar_data_br)

                colunas_desejadas = [
                    "codigo_sku",
                    "descricao",
                    "categoria",
                    "modelo",
                    "numero_ca",
                    "data_validade_ca",
                    "dias_durabilidade_media",
                    "quantidade_estoque",
                    "estoque_minimo",
                ]
                colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
                df_exibir = df[colunas_existentes].rename(
                    columns={
                        "codigo_sku": "SKU",
                        "descricao": "Descrição",
                        "categoria": "Categoria",
                        "modelo": "Modelo",
                        "numero_ca": "Nº CA",
                        "data_validade_ca": "Validade CA",
                        "dias_durabilidade_media": "Durabilidade (dias)",
                        "quantidade_estoque": "Estoque",
                        "estoque_minimo": "Estoque Mín.",
                    }
                )
                st.dataframe(df_exibir, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum EPI cadastrado até o momento.")
        except Exception as e:
            st.error(f"Erro ao carregar EPIs: {e}")

    with tab2:
        st.subheader("Novo EPI")
        with st.form("form_cadastro_epi", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                codigo_sku = st.text_input("Código SKU *", placeholder="Ex: EPI-001")
                descricao = st.text_input("Descrição do EPI *", placeholder="Ex: Óculos de Proteção Incolor")
            with c2:
                categoria = st.text_input("Categoria *", placeholder="Ex: Proteção dos Olhos")
                modelo = st.text_input("Modelo", placeholder="Ex: Ampla visão / Lente policarbonato")
            with c3:
                numero_ca = st.text_input("Número do CA *", placeholder="Ex: 15249")
                data_validade_ca = st.date_input("Data de Validade do CA *", format="DD/MM/YYYY")

            c4, c5, c6 = st.columns(3)
            with c4:
                dias_durabilidade = st.number_input("Durabilidade Média (dias)", min_value=0, value=0, step=1)
            with c5:
                quantidade_estoque = st.number_input("Quantidade em Estoque", min_value=0, value=0, step=1)
            with c6:
                estoque_minimo = st.number_input("Estoque Mínimo", min_value=0, value=0, step=1)

            descricao_protecao = st.text_area("Descrição da Proteção / Observações")

            submitted = st.form_submit_button("💾 Salvar EPI")

            if submitted:
                if not codigo_sku.strip() or not descricao.strip() or not categoria.strip() or not numero_ca.strip():
                    st.warning("Preencha os campos obrigatórios (*): SKU, Descrição, Categoria e Nº CA.")
                else:
                    try:
                        novo_epi = {
                            "codigo_sku": codigo_sku.strip(),
                            "descricao": descricao.strip(),
                            "nome_epi": descricao.strip(),
                            "categoria": categoria.strip(),
                            "modelo": modelo.strip(),
                            "numero_ca": numero_ca.strip(),
                            "ca": numero_ca.strip(),
                            "data_validade_ca": str(data_validade_ca),
                            "validade_ca": str(data_validade_ca),
                            "descricao_protecao": descricao_protecao.strip(),
                            "dias_durabilidade_media": int(dias_durabilidade) if dias_durabilidade > 0 else None,
                            "quantidade_estoque": int(quantidade_estoque),
                            "estoque_minimo": int(estoque_minimo),
                        }
                        supabase.table("epis").insert(novo_epi).execute()
                        _buscar_epis.clear()
                        st.success("EPI cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar EPI no Supabase: {e}")
