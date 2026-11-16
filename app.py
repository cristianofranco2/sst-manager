import streamlit as st
import os
from dotenv import load_dotenv

# Força a recarga total das variáveis de ambiente a cada execução
load_dotenv(override=True)

# Importação dos módulos funcionais
from modules.colaboradores import render_colaboradores
from modules.epis import render_epis
from modules.exames import render_exames

st.set_page_config(
    page_title="Gestão de SST",
    page_icon="🛡️",
    layout="wide"
)

def main():
    st.sidebar.title("🛡️ SST Manager")
    st.sidebar.markdown("---")
    
    # Opções do menu lateral
    menu = st.sidebar.selectbox(
        "Selecione o Módulo",
        [
            "👥 Colaboradores",
            "🥽 Catálogo de EPIs",
            "🩺 Exames Médicos (ASO)",
            "📚 Treinamentos & Cursos",
            "📦 Gestão de Almoxarifado",
            "⚠️ Alertas & Pendências"
        ]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Sistema Integrado SST • Streamlit + Supabase")

    # Roteamento de páginas
    if menu == "👥 Colaboradores":
        render_colaboradores()
    elif menu == "🥽 Catálogo de EPIs":
        render_epis()
    elif menu == "🩺 Exames Médicos (ASO)":
        render_exames()
    elif menu == "📚 Treinamentos & Cursos":
        st.title("📚 Controle de Treinamentos e NRs")
        st.info("Módulo em desenvolvimento...")
    elif menu == "📦 Gestão de Almoxarifado":
        st.title("📦 Almoxarifado e Movimentação")
        st.info("Módulo em desenvolvimento...")
    elif menu == "⚠️ Alertas & Pendências":
        st.title("⚠️ Painel Geral de Alertas")
        st.info("Módulo em desenvolvimento...")

if __name__ == "__main__":
    main()
