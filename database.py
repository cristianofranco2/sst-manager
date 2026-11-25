import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mhrohbalngkhhpldrzsg.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_7aCZMLZVkikSCaktM823rQ_w4mT3e-Z").strip()

@st.cache_resource(ttl=3600)
def get_supabase() -> Client:
    """Conexão centralizada com cache para evitar erros de DNS."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)
