from datetime import date, datetime
import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

DATA_MIN_CALENDARIO = date(1900, 1, 1)
DATA_MAX_CALENDARIO = date(2100, 12, 31)
CHAVE_MSG_EPI = "msg_feedback_epi"


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


def _limpar_cache_epis() -> None:
    st.cache_data.clear()


def _para_maiusculo(valor):
    if isinstance(valor, str):
        return valor.strip().upper()
    if isinstance(valor, list):
        return [_para_maiusculo(item) for item in valor]
    if isinstance(valor, dict):
        return {k: _para_maiusculo(v) for k, v in valor.items()}
    return valor


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


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


def _inserir_com_fallback(supabase, tabela: str, payload: dict, protegidas: set[str]):
    dados = _para_maiusculo(dict(payload))
    for _ in range(20):
        try:
            return supabase.table(tabela).insert(dados).execute()
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida not in protegidas:
                dados.pop(col_invalida)
                continue
            raise
    return supabase.table(tabela).insert(dados).execute()


def _exibir_mensagem_pendente() -> None:
    msg_info = st.session_state.pop(CHAVE_MSG_EPI, None)
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


def render_epis() -> None:
    render_cabecalho_modulo("🥽 Cadastro de EPIs")
    _exibir_mensagem_pendente()

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs([
        "EPIs Cadastrados",
        "➕ Cadastrar Novo EPI",
    ])

    with tab1:
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.subheader("EPIs Cadastrados")
        with col_b:
            if st.button("🔄 Atualizar", key="btn_atualizar_epis", use_container_width=True):
                _limpar_cache_epis()
                st.rerun()

        epis = _buscar_tabela("epis")
        if epis:
            linhas = []
            for e in epis:
                dur_val = (
                    e.get("durabilidade_dias")
                    if e.get("durabilidade_dias") is not None
                    else e.get("durabilidade")
                )
                linhas.append({
                    "Código SKU": str(e.get("codigo_sku") or e.get("sku") or "—").strip().upper(),
                    "Descrição do EPI": str(
                        e.get("descricao") or e.get("nome_epi") or e.get("nome") or "—"
                    ).strip().upper(),
                    "Modelo": str(e.get("modelo") or "—").strip().upper(),
                    "CA": str(e.get("numero_ca") or e.get("ca") or "—").strip().upper(),
                    "Validade CA": _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca")),
                    "Durabilidade (dias)": int(dur_val) if dur_val is not None else 180,
                    "Aplicação / Finalidade": str(
                        e.get("aplicacao_finalidade") or e.get("finalidade") or e.get("aplicacao") or "—"
                    ).strip().upper(),
                    "Categoria": str(e.get("categoria") or "—").strip().upper(),
                    "Estoque Mínimo": int(e.get("estoque_minimo") or 0),
                })
            st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum EPI cadastrado.")

    with tab2:
        st.subheader("Cadastrar Novo EPI")
        with st.form("form_novo_epi", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                codigo_sku = st.text_input("Código SKU *", placeholder="EX: EPI-LUVA-001")
            with c2:
                modelo = st.text_input("Modelo", placeholder="EX: NITRÍLICA FORRADA")
            with c3:
                durabilidade_dias = st.number_input(
                    "Durabilidade (dias) *",
                    min_value=1,
                    value=180,
                    step=1,
                )

            c4, c5, c6 = st.columns(3)
            with c4:
                descricao_epi = st.text_input("Descrição do EPI *", placeholder="EX: LUVA DE SEGURANÇA")
            with c5:
                numero_ca = st.text_input("Número do CA *", placeholder="EX: 278")
            with c6:
                quantidade_inicial = st.number_input(
                    "Quantidade Inicial (alimenta Inventário)",
                    min_value=0,
                    value=0,
                    step=1,
                )

            c7, c8, c9 = st.columns(3)
            with c7:
                categoria = st.text_input("Categoria", placeholder="EX: PROTEÇÃO DOS PÉS, MÃOS, OLHOS")
            with c8:
                validade_ca = st.date_input(
                    "Validade do CA *",
                    value=date.today(),
                    min_value=DATA_MIN_CALENDARIO,
                    max_value=DATA_MAX_CALENDARIO,
                    format="DD/MM/YYYY",
                )
            with c9:
                estoque_minimo = st.number_input(
                    "Estoque Mínimo",
                    min_value=0,
                    value=5,
                    step=1,
                )

            aplicacao_finalidade = st.text_input(
                "Aplicação / Finalidade *",
                placeholder="EX: MANUSEIO DE CARGAS E PRODUTOS QUÍMICOS NO ARMAZÉM",
            )

            if st.form_submit_button("💾 Salvar EPI"):
                sku_limpo = codigo_sku.strip().upper()
                desc_limpa = descricao_epi.strip().upper()
                ca_limpo = numero_ca.strip().upper()
                finalidade_limpa = aplicacao_finalidade.strip().upper()

                if not sku_limpo or not desc_limpa or not ca_limpo or not finalidade_limpa:
                    st.warning(
                        "Preencha todos os campos obrigatórios: Código SKU, Descrição do EPI, Número do CA, Validade do CA e Aplicação / Finalidade."
                    )
                else:
                    try:
                        payload_epi = {
                            "codigo_sku": sku_limpo,
                            "sku": sku_limpo,
                            "descricao": desc_limpa,
                            "nome_epi": desc_limpa,
                            "nome": desc_limpa,
                            "modelo": modelo.strip().upper(),
                            "numero_ca": ca_limpo,
                            "ca": ca_limpo,
                            "data_validade_ca": str(validade_ca),
                            "validade_ca": str(validade_ca),
                            "durabilidade_dias": int(durabilidade_dias),
                            "durabilidade": int(durabilidade_dias),
                            "aplicacao_finalidade": finalidade_limpa,
                            "finalidade": finalidade_limpa,
                            "aplicacao": finalidade_limpa,
                            "categoria": categoria.strip().upper(),
                            "estoque_minimo": int(estoque_minimo),
                        }
                        res_epi = _inserir_com_fallback(
                            supabase,
                            "epis",
                            payload_epi,
                            protegidas={"codigo_sku", "descricao", "numero_ca", "durabilidade_dias", "aplicacao_finalidade"},
                        )

                        epi_id = None
                        if res_epi and getattr(res_epi, "data", None):
                            epi_id = res_epi.data[0].get("id")

                        if int(quantidade_inicial) > 0 and epi_id is not None:
                            payload_inv = {
                                "epi_id": epi_id,
                                "codigo_lote": f"INICIAL-{sku_limpo}",
                                "quantidade_disponivel": int(quantidade_inicial),
                                "data_entrada": str(date.today()),
                                "observacoes": f"SALDO INICIAL NO CADASTRO DO EPI - {finalidade_limpa}",
                            }
                            _inserir_com_fallback(
                                supabase,
                                "inventario_epi",
                                payload_inv,
                                protegidas={"epi_id", "quantidade_disponivel"},
                            )

                        st.session_state[CHAVE_MSG_EPI] = {
                            "tipo": "success",
                            "texto": f"EPI '{desc_limpa}' ({sku_limpo}) SALVO COM SUCESSO!",
                        }
                        _limpar_cache_epis()
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao salvar EPI no Supabase: {err}")


render_epis = render_epis
