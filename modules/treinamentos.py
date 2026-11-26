from datetime import date, datetime
import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

CHAVE_MSG_TREINAMENTOS = "msg_feedback_treinamentos"


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


def _limpar_cache_treinamentos() -> None:
    st.cache_data.clear()


def _parse_data(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()[:10]
    if not texto:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _formatar_data_br(valor) -> str:
    dt = _parse_data(valor)
    return dt.strftime("%d/%m/%Y") if dt else "—"


def _somar_meses(data_base: date, meses: int) -> date:
    meses = max(1, int(meses))
    ano = data_base.year + (data_base.month - 1 + meses) // 12
    mes = (data_base.month - 1 + meses) % 12 + 1
    ultimos_dias = [
        31,
        29 if (ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ]
    dia = min(data_base.day, ultimos_dias[mes - 1])
    return date(ano, mes, dia)


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


def _inserir_treinamento_com_fallback(supabase, payload: dict):
    dados = dict(payload)
    for _ in range(15):
        try:
            return supabase.table("treinamentos").insert(dados).execute()
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida != "data_vencimento":
                dados.pop(col_invalida)
                continue
            raise
    return supabase.table("treinamentos").insert(dados).execute()


def _exibir_mensagem_pendente() -> None:
    msg_info = st.session_state.pop(CHAVE_MSG_TREINAMENTOS, None)
    if not msg_info:
        return
    tipo = msg_info.get("tipo", "success")
    texto = msg_info.get("texto", "")
    if not texto:
        return
    if tipo == "warning":
        st.warning(texto)
    elif tipo == "error":
        st.error(texto)
    else:
        st.success(texto)


def render_treinamentos() -> None:
    render_cabecalho_modulo("🎓 Cadastro de Treinamentos")
    _exibir_mensagem_pendente()

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs([
        "Treinamentos Cadastrados",
        "➕ Cadastrar Novo Treinamento",
    ])

    with tab1:
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.subheader("Treinamentos Cadastrados")
        with col_b:
            if st.button("🔄 Atualizar", key="btn_atualizar_trein", use_container_width=True):
                _limpar_cache_treinamentos()
                st.rerun()

        registros = _buscar_tabela("treinamentos")
        if registros:
            linhas = []
            for r in registros:
                linhas.append({
                    "Treinamento": str(
                        r.get("nome_treinamento") or r.get("titulo") or r.get("nome") or "—"
                    ).strip().upper(),
                    "Modalidade": str(r.get("modalidade") or "—").strip().upper(),
                    "Capacitação": str(
                        r.get("tipo_capacitacao") or r.get("capacitacao") or "—"
                    ).strip().upper(),
                    "Carga Horária (h)": r.get("carga_horaria") if r.get("carga_horaria") is not None else "—",
                    "Validade (meses)": r.get("validade_meses") if r.get("validade_meses") is not None else "—",
                    "Vencimento": _formatar_data_br(r.get("data_vencimento")),
                    "Status": str(r.get("status") or "ATIVO").strip().upper(),
                })
            st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum treinamento cadastrado.")

    with tab2:
        st.subheader("Novo Treinamento")
        with st.form("form_novo_treinamento", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                nome_treinamento = st.text_input(
                    "Nome / Tipo do Treinamento *",
                    placeholder="Ex: NR-11 OPERAÇÃO DE EMPILHADEIRA",
                )
            with c2:
                modalidade = st.selectbox(
                    "Modalidade",
                    options=["PRESENCIAL", "EAD / ONLINE", "HÍBRIDO", "PRÁTICO / OPERACIONAL"],
                    index=0,
                )
            with c3:
                validade_meses = st.number_input(
                    "Validade Padrão (meses)",
                    min_value=1,
                    value=12,
                    step=1,
                )

            c4, c5, c6 = st.columns(3)
            with c4:
                tipo_capacitacao = st.text_input(
                    "Tipo de Capacitação",
                    placeholder="Ex: FORMAÇÃO / RECICLAGEM",
                )
            with c5:
                carga_horaria = st.number_input(
                    "Carga Horária (horas)",
                    min_value=1,
                    value=8,
                    step=1,
                )
            with c6:
                status_trein = st.selectbox(
                    "Status",
                    options=["ATIVO", "INATIVO"],
                    index=0,
                )

            if st.form_submit_button("💾 Salvar Treinamento"):
                nome_limpo = nome_treinamento.strip().upper()
                if not nome_limpo:
                    st.warning("Informe o Nome / Tipo do Treinamento.")
                else:
                    try:
                        hoje = date.today()
                        data_venc_calculada = _somar_meses(hoje, int(validade_meses))
                        payload = {
                            "nome_treinamento": nome_limpo,
                            "titulo": nome_limpo,
                            "nome": nome_limpo,
                            "modalidade": modalidade.strip().upper(),
                            "validade_meses": int(validade_meses),
                            "tipo_capacitacao": tipo_capacitacao.strip().upper(),
                            "capacitacao": tipo_capacitacao.strip().upper(),
                            "carga_horaria": int(carga_horaria),
                            "status": status_trein.strip().upper(),
                            "data_vencimento": str(data_venc_calculada),
                            "validade": str(data_venc_calculada),
                        }
                        _inserir_treinamento_com_fallback(supabase, payload)
                        st.session_state[CHAVE_MSG_TREINAMENTOS] = {
                            "tipo": "success",
                            "texto": f"Treinamento '{nome_limpo}' salvo com sucesso em MAIÚSCULO!",
                        }
                        _limpar_cache_treinamentos()
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao salvar treinamento no Supabase: {err}")


render_treinamentos = render_treinamentos
