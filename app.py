import streamlit as st
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv(override=True)

# Importação dos módulos da aplicação
from modules.colaboradores import render_colaboradores
from modules.epis import render_epis
from modules.exames import render_exames

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Gestor SST - Globex",
    page_icon="🛡️",
    layout="wide"
)

def main():
    st.sidebar.title("🛡️ Gestor SST")
    st.sidebar.markdown("---")
    
    menu = st.sidebar.radio(
        "Navegação",
        ["👷 Colaboradores", "🥾 Gestão de EPIs", "🩺 Exames Médicos (ASO)"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("SST Management System v1.0")

    if menu == "👷 Colaboradores":
        render_colaboradores()
    elif menu == "🥾 Gestão de EPIs":
        render_epis()
    elif menu == "🩺 Exames Médicos (ASO)":
        render_exames()

if __name__ == "__main__":
    main()
