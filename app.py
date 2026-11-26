import streamlit as st

from modules.colaboradores import render_colaboradores
from modules.epis import render_epis
from modules.funcoes import render_funcoes
from modules.inventario import render_inventario
from modules.matriz_funcao import render_matriz_funcao, render_voltar_matriz_se_necessario
from modules.relatorio_colaborador import render_relatorio_colaborador
from modules.tipos_exames import render_tipos_exames
from modules.treinamentos import render_treinamentos

st.set_page_config(
    page_title="Gestor SST - Globex",
    page_icon="🛡️",
    layout="wide",
)

OPCOES_MENU = [
    "📄 Relatório por Colaborador",
    "🧩 Agrupamento por Cargo",
    "💼 Cadastro de Cargos",
    "👥 Cadastro de Colaborador",
    "🥽 Cadastro de EPIs",
    "📦 Cadastro de Inventário",
    "📋 Cadastro de Exames",
    "🎓 Cadastro de Treinamentos",
]


def main() -> None:
    if "menu_selecionado" not in st.session_state:
        st.session_state["menu_selecionado"] = OPCOES_MENU[0]

    # Aplica navegação pendente ANTES de instanciar o widget st.radio
    if "menu_pendente" in st.session_state and st.session_state["menu_pendente"]:
        destino = st.session_state.pop("menu_pendente")
        if destino in OPCOES_MENU:
            st.session_state["menu_selecionado"] = destino
            st.session_state["radio_menu_SST"] = destino

    if "radio_menu_SST" not in st.session_state:
        st.session_state["radio_menu_SST"] = st.session_state["menu_selecionado"]

    st.sidebar.title("🛡️ Gestor SST")
    st.sidebar.markdown("---")

    menu = st.sidebar.radio(
        "Selecione o Módulo",
        OPCOES_MENU,
        key="radio_menu_SST",
    )
    st.session_state["menu_selecionado"] = menu

    st.sidebar.markdown("---")
    st.sidebar.caption("Sistema Integrado SST • Streamlit + Supabase")

    if menu == "📄 Relatório por Colaborador":
        render_relatorio_colaborador()
    elif menu == "🧩 Agrupamento por Cargo":
        render_matriz_funcao()
    elif menu == "💼 Cadastro de Cargos":
        render_voltar_matriz_se_necessario()
        render_funcoes()
    elif menu == "👥 Cadastro de Colaborador":
        render_voltar_matriz_se_necessario()
        render_colaboradores()
    elif menu == "🥽 Cadastro de EPIs":
        render_voltar_matriz_se_necessario()
        render_epis()
    elif menu == "📦 Cadastro de Inventário":
        render_voltar_matriz_se_necessario()
        render_inventario()
    elif menu == "📋 Cadastro de Exames":
        render_voltar_matriz_se_necessario()
        render_tipos_exames()
    elif menu == "🎓 Cadastro de Treinamentos":
        render_voltar_matriz_se_necessario()
        render_treinamentos()


if __name__ == "__main__":
    main()
