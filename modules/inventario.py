from datetime import date, datetime
import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

DATA_MIN_CALENDARIO = date(1900, 1, 1)
DATA_MAX_CALENDARIO = date(2100, 12, 31)
CHAVE_MSG_INVENTARIO = "msg_feedback_inventario"

COLUNAS_QTD_CANDIDATAS = ("quantidade_disponivel", "quantidade", "saldo", "qtd_disponivel", "qtd")


@st.cache_data(ttl=5, show_spinner=False)
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
    if dt:
        return dt.strftime("%d/%m/%Y")
    texto = str(valor or "").strip()
    return texto if texto else "—"


def _obter_qtd_lote(lote: dict) -> int:
    for col in COLUNAS_QTD_CANDIDATAS:
        if col in lote and lote[col] is not None:
            try:
                return int(float(lote[col]))
            except Exception:
                continue
    return 0


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
    dados = _para_maiusculo(dict(payload))
    for _ in range(20):
        try:
            res = supabase.table("inventario_epi").insert(dados).execute()
            return res
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida != "epi_id":
                dados.pop(col_invalida)
                continue
            raise
    return supabase.table("inventario_epi").insert(dados).execute()


def _atualizar_saldo_lote_com_fallback(supabase, lote_id, novo_saldo: int, lote_atual: dict, motivo: str):
    colunas_presentes = [c for c in COLUNAS_QTD_CANDIDATAS if c in lote_atual]
    candidatas_ordenacao = colunas_presentes + [c for c in COLUNAS_QTD_CANDIDATAS if c not in colunas_presentes]

    ultimo_erro = None
    for col_saldo in candidatas_ordenacao:
        payload_update: dict = {col_saldo: int(novo_saldo)}
        if motivo:
            obs_ant = str(lote_atual.get("observacoes") or "").strip().upper()
            novo_obs = f"AJUSTE: {motivo}"
            payload_update["observacoes"] = f"{obs_ant} | {novo_obs}" if obs_ant else novo_obs

        dados = _para_maiusculo(dict(payload_update))
        for _ in range(15):
            try:
                res = supabase.table("inventario_epi").update(dados).eq("id", lote_id).execute()
                linhas_afetadas = getattr(res, "data", None) or []
                if len(linhas_afetadas) > 0:
                    return res
                raise RuntimeError(
                    "O Supabase não retornou nenhuma linha alterada ao executar o UPDATE em 'inventario_epi'. "
                    "Verifique se há política RLS permitindo UPDATE na tabela 'inventario_epi' e se o ID existe."
                )
            except Exception as e:
                ultimo_erro = e
                col_invalida = _extrair_coluna_pgrst204(str(e))
                if col_invalida and col_invalida in dados:
                    if col_invalida == col_saldo:
                        break
                    dados.pop(col_invalida)
                    continue
                raise

    if ultimo_erro:
        raise ultimo_erro
    raise RuntimeError("Não foi possível identificar a coluna de saldo em inventario_epi.")


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
        qtd = _obter_qtd_lote(lote)
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
                sku_disp = str(e.get("codigo_sku") or e.get("sku") or "—").strip().upper()
                desc_disp = str(
                    e.get("descricao") or e.get("nome_epi") or e.get("nome") or "—"
                ).strip().upper()
                ca_disp = str(e.get("numero_ca") or e.get("ca") or e.get("codigo_ca") or "—").strip().upper()
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
                    sku = str(ep.get("codigo_sku") or ep.get("sku") or "—").strip().upper()
                    desc = str(ep.get("descricao") or ep.get("nome_epi") or ep.get("nome") or "—").strip().upper()
                    ca = str(ep.get("numero_ca") or ep.get("ca") or "—").strip().upper()
                    linhas_lotes.append({
                        "SKU": sku,
                        "EPI": desc,
                        "CA": ca,
                        "Lote": str(lote.get("codigo_lote") or "—").strip().upper(),
                        "Quantidade": _obter_qtd_lote(lote),
                        "Data Entrada": _formatar_data_br(lote.get("data_entrada") or lote.get("created_at")),
                        "Observações": str(lote.get("observacoes") or "—").strip().upper(),
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
                sku = str(e.get("codigo_sku") or e.get("sku") or "—").strip().upper()
                desc = str(e.get("descricao") or e.get("nome_epi") or e.get("nome") or "EPI").strip().upper()
                ca = str(e.get("numero_ca") or e.get("ca") or "—").strip().upper()
                val = _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca"))
                opcoes_epi.append((eid, f"{desc} — SKU {sku} | CA {ca} | VAL. {val}"))

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
                    codigo_lote = st.text_input("Código do Lote", placeholder="EX: LOTE-2026-11")
                with e2:
                    observacoes_entrada = st.text_input("Observações", placeholder="EX: NOTA FISCAL / REPOSIÇÃO")

                if st.form_submit_button("💾 Registrar Entrada"):
                    try:
                        payload = {
                            "epi_id": epi_sel_id,
                            "codigo_lote": (codigo_lote.strip() or f"ENT-{data_entrada.strftime('%Y%m%d')}").upper(),
                            "quantidade_disponivel": int(quantidade_entrada),
                            "quantidade": int(quantidade_entrada),
                            "data_entrada": str(data_entrada),
                            "observacoes": observacoes_entrada.strip().upper(),
                        }
                        _inserir_inventario_com_fallback(supabase, payload)
                        st.session_state[CHAVE_MSG_INVENTARIO] = {
                            "tipo": "success",
                            "texto": f"ENTRADA DE {int(quantidade_entrada)} UN. REGISTRADA NO INVENTÁRIO!",
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
            mapa_lotes = {}
            for idx_l, lote in enumerate(lotes):
                lid = lote.get("id")
                if lid is None:
                    continue
                chave_lote = str(lid)
                mapa_lotes[chave_lote] = lote
                eid = str(lote.get("epi_id") or "").strip()
                ep = mapa_epis.get(eid, {})
                desc = str(ep.get("descricao") or ep.get("nome_epi") or ep.get("nome") or "EPI").strip().upper()
                lote_cod = str(lote.get("codigo_lote") or f"LOTE-{idx_l + 1}").strip().upper()
                saldo_atual = _obter_qtd_lote(lote)
                opcoes_lotes.append((chave_lote, f"{desc} — {lote_cod} (SALDO ATUAL: {saldo_atual})"))

            lote_sel_chave = st.selectbox(
                "Selecione o Lote",
                options=[o[0] for o in opcoes_lotes],
                format_func=lambda k: dict(opcoes_lotes).get(k, k),
                key="select_lote_ajuste_saldo",
            )
            lote_atual = mapa_lotes.get(lote_sel_chave, {})
            saldo_vigente = max(0, _obter_qtd_lote(lote_atual))

            with st.form(f"form_ajuste_saldo_inventario_{lote_sel_chave}"):
                novo_saldo = st.number_input(
                    "Novo Saldo Disponível",
                    min_value=0,
                    value=saldo_vigente,
                    step=1,
                    key=f"num_novo_saldo_{lote_sel_chave}",
                )
                motivo_ajuste = st.text_input(
                    "Motivo do Ajuste",
                    placeholder="EX: INVENTÁRIO FÍSICO / AVARIA",
                    key=f"txt_motivo_ajuste_{lote_sel_chave}",
                )

                if st.form_submit_button("✅ Salvar Ajuste"):
                    try:
                        id_real = lote_atual.get("id")
                        _atualizar_saldo_lote_com_fallback(
                            supabase=supabase,
                            lote_id=id_real,
                            novo_saldo=int(novo_saldo),
                            lote_atual=lote_atual,
                            motivo=motivo_ajuste.strip().upper(),
                        )
                        st.session_state[CHAVE_MSG_INVENTARIO] = {
                            "tipo": "success",
                            "texto": f"SALDO DO LOTE ATUALIZADO PARA {int(novo_saldo)} UN.!",
                        }
                        _limpar_cache_inventario()
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao ajustar saldo: {err}")


render_inventario = render_inventario
