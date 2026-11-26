from datetime import date, datetime
import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

DATA_MIN_CALENDARIO = date(1900, 1, 1)
DATA_MAX_CALENDARIO = date(2100, 12, 31)
CHAVE_MSG_INVENTARIO = "msg_feedback_inventario"


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


def _limpar_cache_inventario() -> None:
    st.cache_data.clear()


def _normalizar_texto(valor) -> str:
    return " ".join(str(valor or "").strip().lower().split())


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
    if dt:
        return dt.strftime("%d/%m/%Y")
    texto = str(valor or "").strip()
    return texto if texto else "—"


def _chave_agrupamento_epi(epi: dict) -> tuple[str, str, str]:
    sku = _normalizar_texto(epi.get("codigo_sku") or epi.get("sku") or "")
    ca = _normalizar_texto(epi.get("numero_ca") or epi.get("ca") or epi.get("codigo_ca") or "")
    dt_val = _parse_data(epi.get("data_validade_ca") or epi.get("validade_ca"))
    val_norm = dt_val.strftime("%Y-%m-%d") if dt_val else _normalizar_texto(
        epi.get("data_validade_ca") or epi.get("validade_ca") or ""
    )
    return (sku, ca, val_norm)


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


def _inserir_inventario_com_fallback(supabase, payload: dict):
    dados = dict(payload)
    for _ in range(15):
        try:
            return supabase.table("inventario_epi").insert(dados).execute()
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida != "epi_id":
                dados.pop(col_invalida)
                continue
            raise
    return supabase.table("inventario_epi").insert(dados).execute()


def _exibir_mensagem_pendente() -> None:
    msg_info = st.session_state.pop(CHAVE_MSG_INVENTARIO, None)
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


def render_inventario() -> None:
    render_cabecalho_modulo("📦 Cadastro de Inventário")
    _exibir_mensagem_pendente()

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    epis = _buscar_tabela("epis")
    lotes = _buscar_tabela("inventario_epi")

    mapa_epis = {str(e.get("id") or "").strip(): e for e in epis if e.get("id") is not None}

    saldos_por_epi: dict[str, int] = {}
    qtd_registros_por_epi: dict[str, int] = {}
    for lote in lotes:
        eid = str(lote.get("epi_id") or "").strip()
        if not eid:
            continue
        qtd = int(lote.get("quantidade_disponivel") or 0)
        saldos_por_epi[eid] = saldos_por_epi.get(eid, 0) + qtd
        qtd_registros_por_epi[eid] = qtd_registros_por_epi.get(eid, 0) + 1

    tab1, tab2, tab3 = st.tabs([
        "📦 Estoque / Lotes no Inventário",
        "➕ Entrada no Inventário",
        "🔧 Ajuste de Saldo",
    ])

    with tab1:
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.subheader("📊 Saldo Atual por EPI (Agrupado por SKU, CA e Validade)")
        with col_b:
            if st.button("🔄 Atualizar", key="btn_atualizar_inv", use_container_width=True):
                _limpar_cache_inventario()
                st.rerun()

        if epis:
            agrupados: dict[tuple[str, str, str], dict] = {}
            for e in epis:
                eid = str(e.get("id") or "").strip()
                chave = _chave_agrupamento_epi(e)
                sku_disp = str(e.get("codigo_sku") or e.get("sku") or "—").strip()
                desc_disp = str(e.get("descricao") or e.get("nome_epi") or e.get("nome") or "—").strip()
                ca_disp = str(e.get("numero_ca") or e.get("ca") or e.get("codigo_ca") or "—").strip()
                val_disp = _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca"))
                saldo_epi = saldos_por_epi.get(eid, 0)
                regs_epi = qtd_registros_por_epi.get(eid, 0)

                if chave not in agrupados:
                    agrupados[chave] = {
                        "SKU": sku_disp,
                        "EPI": desc_disp,
                        "CA": ca_disp,
                        "Validade": val_disp,
                        "Saldo Total": saldo_epi,
                        "Qtd. Registros": regs_epi,
                    }
                else:
                    agrupados[chave]["Saldo Total"] += saldo_epi
                    agrupados[chave]["Qtd. Registros"] += regs_epi

            st.dataframe(
                pd.DataFrame(list(agrupados.values())),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhum EPI cadastrado no catálogo.")

        with st.expander("Ver lançamentos individuais (lotes / entradas)"):
            if lotes:
                linhas_lotes = []
                for lote in lotes:
                    eid = str(lote.get("epi_id") or "").strip()
                    ep = mapa_epis.get(eid, {})
                    sku = str(ep.get("codigo_sku") or ep.get("sku") or "—").strip()
                    desc = str(ep.get("descricao") or ep.get("nome_epi") or ep.get("nome") or "—").strip()
                    ca = str(ep.get("numero_ca") or ep.get("ca") or "—").strip()
                    linhas_lotes.append({
                        "SKU": sku,
                        "EPI": desc,
                        "CA": ca,
                        "Lote": str(lote.get("codigo_lote") or "—").strip(),
                        "Quantidade": int(lote.get("quantidade_disponivel") or 0),
                        "Data Entrada": _formatar_data_br(lote.get("data_entrada") or lote.get("created_at")),
                        "Observações": str(lote.get("observacoes") or "—").strip(),
                    })
                st.dataframe(pd.DataFrame(linhas_lotes), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum lançamento individual encontrado no inventário.")

    with tab2:
        st.subheader("➕ Entrada no Inventário")
        if not epis:
            st.info("Cadastre um EPI antes de lançar entradas no inventário.")
        else:
            opcoes_epi = []
            for e in epis:
                eid = str(e.get("id") or "").strip()
                if not eid:
                    continue
                sku = str(e.get("codigo_sku") or e.get("sku") or "—").strip()
                desc = str(e.get("descricao") or e.get("nome_epi") or e.get("nome") or "EPI").strip()
                ca = str(e.get("numero_ca") or e.get("ca") or "—").strip()
                val = _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca"))
                opcoes_epi.append((eid, f"{desc} — SKU {sku} | CA {ca} | Val. {val}"))

            with st.form("form_entrada_inventario", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    epi_sel_id = st.selectbox(
                        "Selecione o EPI *",
                        options=[o[0] for o in opcoes_epi],
                        format_func=lambda eid: dict(opcoes_epi).get(eid, eid),
                    )
                with c2:
                    quantidade_entrada = st.number_input("Quantidade *", min_value=1, value=1, step=1)
                with c3:
                    data_entrada = st.date_input(
                        "Data de Entrada",
                        value=date.today(),
                        min_value=DATA_MIN_CALENDARIO,
                        max_value=DATA_MAX_CALENDARIO,
                        format="DD/MM/YYYY",
                    )

                e1, e2 = st.columns(2)
                with e1:
                    codigo_lote = st.text_input("Código do Lote", placeholder="Ex: LOTE-2026-11")
                with e2:
                    observacoes_entrada = st.text_input("Observações", placeholder="Ex: Nota fiscal / reposição")

                if st.form_submit_button("💾 Registrar Entrada"):
                    try:
                        payload = {
                            "epi_id": epi_sel_id,
                            "codigo_lote": codigo_lote.strip() or f"ENT-{data_entrada.strftime('%Y%m%d')}",
                            "quantidade_disponivel": int(quantidade_entrada),
                            "data_entrada": str(data_entrada),
                            "observacoes": observacoes_entrada.strip(),
                        }
                        _inserir_inventario_com_fallback(supabase, payload)
                        st.session_state[CHAVE_MSG_INVENTARIO] = {
                            "tipo": "success",
                            "texto": f"Entrada de {int(quantidade_entrada)} un. registrada no inventário!",
                        }
                        _limpar_cache_inventario()
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao registrar entrada no inventário: {err}")

    with tab3:
        st.subheader("🔧 Ajuste de Saldo")
        if not lotes:
            st.info("Nenhum lote disponível no inventário para ajuste.")
        else:
            opcoes_lotes = []
            for lote in lotes:
                lid = lote.get("id")
                if lid is None:
                    continue
                eid = str(lote.get("epi_id") or "").strip()
                ep = mapa_epis.get(eid, {})
                desc = str(ep.get("descricao") or ep.get("nome_epi") or ep.get("nome") or "EPI").strip()
                lote_cod = str(lote.get("codigo_lote") or "Lote").strip()
                saldo_atual = int(lote.get("quantidade_disponivel") or 0)
                opcoes_lotes.append((lid, f"{desc} — {lote_cod} (Saldo atual: {saldo_atual})"))

            mapa_lotes = {l["id"]: l for l in lotes if l.get("id") is not None}

            with st.form("form_ajuste_saldo_inventario"):
                a1, a2 = st.columns(2)
                with a1:
                    lote_sel_id = st.selectbox(
                        "Selecione o Lote",
                        options=[o[0] for o in opcoes_lotes],
                        format_func=lambda lid: dict(opcoes_lotes).get(lid, str(lid)),
                    )
                with a2:
                    lote_atual = mapa_lotes.get(lote_sel_id, {})
                    saldo_vigente = max(0, int(lote_atual.get("quantidade_disponivel") or 0))
                    novo_saldo = st.number_input(
                        "Novo Saldo Disponível",
                        min_value=0,
                        value=saldo_vigente,
                        step=1,
                    )

                motivo_ajuste = st.text_input("Motivo do Ajuste", placeholder="Ex: Inventário físico / avaria")

                if st.form_submit_button("✅ Salvar Ajuste"):
                    try:
                        update_payload = {"quantidade_disponivel": int(novo_saldo)}
                        if motivo_ajuste.strip():
                            obs_ant = str(lote_atual.get("observacoes") or "").strip()
                            update_payload["observacoes"] = (
                                f"{obs_ant} | Ajuste: {motivo_ajuste.strip()}" if obs_ant else f"Ajuste: {motivo_ajuste.strip()}"
                            )
                        supabase.table("inventario_epi").update(update_payload).eq("id", lote_sel_id).execute()
                        st.session_state[CHAVE_MSG_INVENTARIO] = {
                            "tipo": "success",
                            "texto": f"Saldo atualizado para {int(novo_saldo)} un.!",
                        }
                        _limpar_cache_inventario()
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao ajustar saldo: {err}")


render_inventario = render_inventario
