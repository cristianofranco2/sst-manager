import os
import streamlit as st
from supabase import create_client, Client


def _get_config(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return os.getenv(key, default).strip()


@st.cache_resource(ttl=3600)
def get_supabase() -> Client:
    url = _get_config("SUPABASE_URL", "https://mhrohbalngkhhpldrzsg.supabase.co")
    key = _get_config("SUPABASE_KEY", "sb_publishable_7aCZMLZVkikSCaktM823rQ_w4mT3e-Z")
    if not url or not key:
        raise ValueError("Credenciais do Supabase não configuradas.")
    return create_client(url, key)
