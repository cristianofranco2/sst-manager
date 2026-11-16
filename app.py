import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Gestão de SST",
    page_icon="🛡️",
    layout="wide"
)

def main():
    st.sidebar.title("🛡️ SST Manager")
    st.sidebar.markdown("---")
    
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

    if menu == "👥 Colaboradores":
        st.title("👥 Gestão de Colaboradores")
        st.info("Módulo em integração...")
    elif menu == "🥽 Catálogo de EPIs":
        st.title("🥽 Catálogo e Controle de EPIs")
        st.info("Módulo em integração...")
    elif menu == "🩺 Exames Médicos (ASO)":
        st.title("🩺 Exames Médicos Ocupacionais")
        st.info("Módulo em integração...")
    elif menu == "📚 Treinamentos & Cursos":
        st.title("📚 Controle de Treinamentos e NRs")
        st.info("Módulo em integração...")
    elif menu == "📦 Gestão de Almoxarifado":
        st.title("📦 Almoxarifado e Movimentação")
        st.info("Módulo em integração...")
    elif menu == "⚠️ Alertas & Pendências":
        st.title("⚠️ Painel Geral de Alertas")
        st.info("Módulo em integração...")

if __name__ == "__main__":
    main()
