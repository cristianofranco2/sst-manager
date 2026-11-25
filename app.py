import streamlit as st

from modules.colaboradores import render_colaboradores
from modules.epis import render_epis
from modules.tipos_exames import render_tipos_exames
from modules.treinamentos import render_treinamentos

st.set_page_config(
    page_title="Gestor SST - Globex",
    page_icon="🛡️",
    layout="wide",
)


def main() -> None:
    st.sidebar.title("🛡️ Gestor SST")
    st.sidebar.markdown("---")

    menu = st.sidebar.radio(
        "Selecione o Módulo",
        [
            "👥 Colaboradores",
            "🥽 Catálogo de EPIs",
            "📋 Catálogo de Tipos de Exames",
            "🎓 Treinamentos",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("Sistema Integrado SST • Streamlit + Supabase")

    if menu == "👥 Colaboradores":
        render_colaboradores()
    elif menu == "🥽 Catálogo de EPIs":
        render_epis()
    elif menu == "📋 Catálogo de Tipos de Exames":
        render_tipos_exames()
    elif menu == "🎓 Treinamentos":
        render_treinamentos()


if __name__ == "__main__":
    main()
