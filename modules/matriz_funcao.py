import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo


def _para_maiusculo(texto: str | None) -> str:
    return " ".join(str(texto or "").strip().upper().split())


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_funcoes() -> list[dict]:
    supabase = get_supabase()
    res = (
        supabase.table("funcoes")
        .select("id, nome_funcao, cbo, setor_padrao, ativo")
        .order("nome_funcao")
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_epis() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("epis").select("*").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_uniformes() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("uniformes").select("*").execute()
        return res.data or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_treinamentos() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("treinamentos").select("*").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_tipos_exames() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("tipos_exames").select("*").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_requisito_funcao(funcao_id: str) -> dict | None:
    supabase = get_supabase()
    try:
        res = (
            supabase.table("funcao_requisitos")
            .select("*")
            .eq("funcao_id", funcao_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception:
        return None
    return None


def _limpar_cache_matriz() -> None:
    _buscar_funcoes.clear()
    _buscar_epis.clear()
    _buscar_uniformes.clear()
    _buscar_treinamentos.clear()
    _buscar_tipos_exames.clear()
    _buscar_requisito_funcao.clear()


def _garantir_estado_matriz() -> dict:
    if "matriz_state" not in st.session_state:
        st.session_state["matriz_state"] = {
            "funcao_id": None,
            "carregado_para_funcao": None,
            "epi_ids": [],
            "epi_quantidades": {},
            "uniforme_ids": [],
            "uniforme_quantidades": {},
            "treinamento_ids": [],
            "exame_ids": [],
        }
    else:
        st.session_state["matriz_state"].setdefault("epi_quantidades", {})
        st.session_state["matriz_state"].setdefault("uniforme_ids", [])
        st.session_state["matriz_state"].setdefault("uniforme_quantidades", {})
    return st.session_state["matriz_state"]


def _ir_para_modulo(destino_menu: str) -> None:
    st.session_state["origem_matriz"] = True
    st.session_state["menu_pendente"] = destino_menu


def _salvar_requisito_com_fallback(supabase, payload: dict) -> None:
    dados = dict(payload)
    for _ in range(15):
        try:
            supabase.table("funcao_requisitos").upsert(dados, on_conflict="funcao_id").execute()
            return
        except Exception as e:
            col = _extrair_coluna_pgrst204(str(e))
            if col and col in dados and col != "funcao_id":
                dados.pop(col)
                continue
            raise
    supabase.table("funcao_requisitos").upsert(dados, on_conflict="funcao_id").execute()


def render_voltar_matriz_se_necessario() -> None:
    if st.session_state.get("origem_matriz"):
        col_aviso, col_btn = st.columns([3, 1])
        with col_aviso:
            st.info(
                "Você abriu este cadastro a partir do **Agrupamento por Cargo**. "
                "Seu rascunho está preservado."
            )
        with col_btn:
            if st.button("↩️ Voltar para o Agrupamento", key="btn_voltar_matriz", use_container_width=True):
                st.session_state["origem_matriz"] = False
                _limpar_cache_matriz()
                st.session_state["menu_pendente"] = "🧩 Agrupamento por Cargo"
                st.rerun()


def render_matriz_funcao() -> None:
    render_cabecalho_modulo("🧩 Agrupamento por Cargo (EPIs, Uniformes, Treinamentos e Exames)")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    state = _garantir_estado_matriz()

    _, col_top2 = st.columns([4, 1])
    with col_top2:
        if st.button("🔄 Atualizar dados", key="btn_atualizar_matriz", use_container_width=True):
            _limpar_cache_matriz()
            state["carregado_para_funcao"] = None

    funcoes = _buscar_funcoes()
    if not funcoes:
        st.warning("Nenhum cargo cadastrado ainda. Cadastre um cargo no **Cadastro de Cargos** para começar.")
        if st.button("➕ Ir para Cadastro de Cargos", key="btn_ir_funcoes"):
            _ir_para_modulo("💼 Cadastro de Cargos")
            st.rerun()
        return

    mapa_funcoes = {str(f["id"]): f for f in funcoes if f.get("id")}
    ids_funcoes = list(mapa_funcoes.keys())

    funcao_atual = state.get("funcao_id") if state.get("funcao_id") in ids_funcoes else ids_funcoes[0]

    def _format_funcao(fid: str) -> str:
        item = mapa_funcoes[fid]
        nome = _para_maiusculo(item.get("nome_funcao")) or "SEM NOME"
        cbo = _para_maiusculo(item.get("cbo"))
        setor = _para_maiusculo(item.get("setor_padrao"))
        extra = [p for p in [f"CBO {cbo}" if cbo else "", setor] if p]
        return f"{nome} ({' • '.join(extra)})" if extra else nome

    funcao_selecionada = st.selectbox(
        "1. Selecione o Cargo / Função *",
        options=ids_funcoes,
        index=ids_funcoes.index(funcao_atual),
        format_func=_format_funcao,
        key="selectbox_funcao_matriz",
    )
    state["funcao_id"] = funcao_selecionada

    if state.get("carregado_para_funcao") != funcao_selecionada:
        registro_salvo = _buscar_requisito_funcao(funcao_selecionada)
        if registro_salvo:
            state["epi_ids"] = [str(x) for x in (registro_salvo.get("epi_ids") or [])]
            qtd_raw = registro_salvo.get("epi_quantidades") or {}
            state["epi_quantidades"] = {
                str(k): max(1, int(v)) for k, v in qtd_raw.items() if v is not None
            }
            state["uniforme_ids"] = [str(x) for x in (registro_salvo.get("uniforme_ids") or [])]
            uni_qtd_raw = registro_salvo.get("uniforme_quantidades") or {}
            state["uniforme_quantidades"] = {
                str(k): max(1, int(v)) for k, v in uni_qtd_raw.items() if v is not None
            }
            state["treinamento_ids"] = [str(x) for x in (registro_salvo.get("treinamento_ids") or [])]
            state["exame_ids"] = [str(x) for x in (registro_salvo.get("exame_ids") or [])]
        else:
            state["epi_ids"] = []
            state["epi_quantidades"] = {}
            state["uniforme_ids"] = []
            state["uniforme_quantidades"] = {}
            state["treinamento_ids"] = []
            state["exame_ids"] = []
        state["carregado_para_funcao"] = funcao_selecionada

    epis = _buscar_epis()
    uniformes = _buscar_uniformes()
    treinamentos = _buscar_treinamentos()
    exames = _buscar_tipos_exames()

    st.markdown("---")

    b1_esq, b1_dir = st.columns([4, 1])
    with b1_esq:
        st.subheader("🥽 2. EPIs do Cargo e Quantidade")
    with b1_dir:
        if st.button("➕ Cadastrar EPI", key="btn_add_epi_matriz", use_container_width=True):
            _ir_para_modulo("🥽 Cadastro de EPIs")
            st.rerun()

    epi_ids_selecionados = set(state["epi_ids"])
    qtds_atuais = dict(state.get("epi_quantidades") or {})
    novos_epi_ids: list[str] = []
    novas_epi_qtds: dict[str, int] = {}

    if epis:
        with st.container(border=True):
            for epi in epis:
                eid = str(epi.get("id", "")).strip()
                if not eid:
                    continue
                nome_epi = _para_maiusculo(epi.get("descricao") or epi.get("nome_epi")) or "EPI SEM DESCRIÇÃO"
                ca = _para_maiusculo(epi.get("numero_ca") or epi.get("ca"))
                sku = _para_maiusculo(epi.get("codigo_sku"))
                detalhes = [p for p in [f"SKU {sku}" if sku else "", f"CA {ca}" if ca else ""] if p]
                label_epi = f"{nome_epi} — {' | '.join(detalhes)}" if detalhes else nome_epi

                col_chk, col_qtd = st.columns([4, 1])
                with col_chk:
                    marcado = st.checkbox(
                        label_epi,
                        value=eid in epi_ids_selecionados,
                        key=f"chk_epi_{funcao_selecionada}_{eid}",
                    )
                with col_qtd:
                    if marcado:
                        qtd_padrao = max(1, int(qtds_atuais.get(eid, 1)))
                        qtd_val = st.number_input(
                            "Qtd.",
                            min_value=1,
                            max_value=999,
                            value=qtd_padrao,
                            step=1,
                            label_visibility="collapsed",
                            key=f"qtd_epi_{funcao_selecionada}_{eid}",
                        )
                    else:
                        qtd_val = max(1, int(qtds_atuais.get(eid, 1)))

                if marcado:
                    novos_epi_ids.append(eid)
                    novas_epi_qtds[eid] = int(qtd_val)
    else:
        st.info("Nenhum EPI cadastrado ainda. Use o botão **➕ Cadastrar EPI** ao lado para cadastrar.")

    state["epi_ids"] = novos_epi_ids
    state["epi_quantidades"] = novas_epi_qtds

    st.markdown("---")

    bu_esq, bu_dir = st.columns([4, 1])
    with bu_esq:
        st.subheader("👕 3. Uniformes do Cargo e Quantidade")
    with bu_dir:
        if st.button("➕ Cadastrar Uniforme", key="btn_add_uni_matriz", use_container_width=True):
            _ir_para_modulo("👕 Cadastro de Uniformes")
            st.rerun()

    uni_ids_selecionados = set(state.get("uniforme_ids") or [])
    uni_qtds_atuais = dict(state.get("uniforme_quantidades") or {})
    novos_uni_ids: list[str] = []
    novas_uni_qtds: dict[str, int] = {}

    if uniformes:
        with st.container(border=True):
            for uni in uniformes:
                uid = str(uni.get("id", "")).strip()
                if not uid:
                    continue
                nome_uni = _para_maiusculo(uni.get("nome") or uni.get("descricao")) or "UNIFORME SEM NOME"
                tipo_u = _para_maiusculo(uni.get("tipo"))
                tam_u = _para_maiusculo(uni.get("tamanho"))
                cor_u = _para_maiusculo(uni.get("cor"))
                setor_u = _para_maiusculo(uni.get("setor"))
                detalhes_u = [p for p in [tipo_u, f"TAM {tam_u}" if tam_u else "", cor_u, setor_u] if p]
                label_uni = f"{nome_uni} — {' | '.join(detalhes_u)}" if detalhes_u else nome_uni

                col_chk_u, col_qtd_u = st.columns([4, 1])
                with col_chk_u:
                    marcado_u = st.checkbox(
                        label_uni,
                        value=uid in uni_ids_selecionados,
                        key=f"chk_uni_{funcao_selecionada}_{uid}",
                    )
                with col_qtd_u:
                    if marcado_u:
                        qtd_padrao_u = max(1, int(uni_qtds_atuais.get(uid, 1)))
                        qtd_val_u = st.number_input(
                            "Qtd.",
                            min_value=1,
                            max_value=999,
                            value=qtd_padrao_u,
                            step=1,
                            label_visibility="collapsed",
                            key=f"qtd_uni_{funcao_selecionada}_{uid}",
                        )
                    else:
                        qtd_val_u = max(1, int(uni_qtds_atuais.get(uid, 1)))

                if marcado_u:
                    novos_uni_ids.append(uid)
                    novas_uni_qtds[uid] = int(qtd_val_u)
    else:
        st.info("Nenhum uniforme cadastrado ainda. Use o botão **➕ Cadastrar Uniforme** ao lado para cadastrar.")

    state["uniforme_ids"] = novos_uni_ids
    state["uniforme_quantidades"] = novas_uni_qtds

    st.markdown("---")

    b2_esq, b2_dir = st.columns([4, 1])
    with b2_esq:
        st.subheader("🎓 4. Treinamentos do Cargo")
    with b2_dir:
        if st.button("➕ Cadastrar Treinamento", key="btn_add_trein_matriz", use_container_width=True):
            _ir_para_modulo("🎓 Cadastro de Treinamentos")
            st.rerun()

    trein_ids_selecionados = set(state["treinamento_ids"])
    novos_trein_ids: list[str] = []

    if treinamentos:
        with st.container(border=True):
            for tr in treinamentos:
                tid = str(tr.get("id", "")).strip()
                if not tid:
                    continue
                nome_tr = _para_maiusculo(tr.get("tipo_treinamento") or tr.get("nome")) or "TREINAMENTO"
                cap = _para_maiusculo(tr.get("tipo_capacitacao"))
                ch = tr.get("carga_horaria")
                detalhes = [p for p in [cap, f"{ch}H" if ch else ""] if p]
                label_tr = f"{nome_tr} — {' | '.join(detalhes)}" if detalhes else nome_tr

                marcado = st.checkbox(
                    label_tr,
                    value=tid in trein_ids_selecionados,
                    key=f"chk_trein_{funcao_selecionada}_{tid}",
                )
                if marcado:
                    novos_trein_ids.append(tid)
    else:
        st.info("Nenhum treinamento cadastrado ainda. Use o botão **➕ Cadastrar Treinamento** ao lado para cadastrar.")

    state["treinamento_ids"] = novos_trein_ids

    st.markdown("---")

    b3_esq, b3_dir = st.columns([4, 1])
    with b3_esq:
        st.subheader("📋 5. Exames do Cargo")
    with b3_dir:
        if st.button("➕ Cadastrar Exame", key="btn_add_exame_matriz", use_container_width=True):
            _ir_para_modulo("📋 Cadastro de Exames")
            st.rerun()

    exame_ids_selecionados = set(state["exame_ids"])
    novos_exame_ids: list[str] = []

    if exames:
        with st.container(border=True):
            for ex in exames:
                ex_id = str(ex.get("id", "")).strip()
                if not ex_id:
                    continue
                nome_ex = _para_maiusculo(ex.get("nome_exame") or ex.get("nome")) or "EXAME"
                tuss = _para_maiusculo(ex.get("codigo_tuss"))
                meses = ex.get("validade_meses")
                detalhes = [p for p in [f"TUSS {tuss}" if tuss else "", f"VALIDADE {meses}M" if meses else ""] if p]
                label_ex = f"{nome_ex} — {' | '.join(detalhes)}" if detalhes else nome_ex

                marcado = st.checkbox(
                    label_ex,
                    value=ex_id in exame_ids_selecionados,
                    key=f"chk_exame_{funcao_selecionada}_{ex_id}",
                )
                if marcado:
                    novos_exame_ids.append(ex_id)
    else:
        st.info("Nenhum tipo de exame cadastrado ainda. Use o botão **➕ Cadastrar Exame** ao lado para cadastrar.")

    state["exame_ids"] = novos_exame_ids

    st.markdown("---")

    st.subheader("💾 Salvar Agrupamento do Cargo")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("EPIs Selecionados", len(state["epi_ids"]))
    m2.metric("Uniformes Selecionados", len(state["uniforme_ids"]))
    m3.metric("Treinamentos Selecionados", len(state["treinamento_ids"]))
    m4.metric("Exames Selecionados", len(state["exame_ids"]))

    if st.button("💾 Salvar Requisitos do Cargo", type="primary", key="btn_salvar_matriz"):
        try:
            payload = {
                "funcao_id": funcao_selecionada,
                "epi_ids": state["epi_ids"],
                "epi_quantidades": state["epi_quantidades"],
                "uniforme_ids": state["uniforme_ids"],
                "uniforme_quantidades": state["uniforme_quantidades"],
                "treinamento_ids": state["treinamento_ids"],
                "exame_ids": state["exame_ids"],
            }
            _salvar_requisito_com_fallback(supabase, payload)
            _buscar_requisito_funcao.clear()
            st.success("Requisitos do cargo salvos com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar agrupamento do cargo: {e}")

    requisitos_salvos = _buscar_requisito_funcao(funcao_selecionada) or {}
    mapa_epis = {
        str(e["id"]): _para_maiusculo(e.get("descricao") or e.get("nome_epi")) or str(e["id"])
        for e in epis
        if e.get("id")
    }
    mapa_uniformes = {
        str(u["id"]): _para_maiusculo(u.get("nome") or u.get("descricao")) or str(u["id"])
        for u in uniformes
        if u.get("id")
    }
    mapa_trein = {
        str(t["id"]): _para_maiusculo(t.get("tipo_treinamento") or t.get("nome")) or str(t["id"])
        for t in treinamentos
        if t.get("id")
    }
    mapa_exames = {
        str(x["id"]): _para_maiusculo(x.get("nome_exame") or x.get("nome")) or str(x["id"])
        for x in exames
        if x.get("id")
    }

    lista_epi_ids = requisitos_salvos.get("epi_ids") or state.get("epi_ids") or []
    lista_uni_ids = requisitos_salvos.get("uniforme_ids") or state.get("uniforme_ids") or []
    lista_trein_ids = requisitos_salvos.get("treinamento_ids") or state.get("treinamento_ids") or []
    lista_exame_ids = requisitos_salvos.get("exame_ids") or state.get("exame_ids") or []

    qtds_salvas = requisitos_salvos.get("epi_quantidades") or state.get("epi_quantidades") or {}
    uni_qtds_salvas = requisitos_salvos.get("uniforme_quantidades") or state.get("uniforme_quantidades") or {}

    resumo_linhas = []
    for eid in lista_epi_ids:
        eid_str = str(eid)
        resumo_linhas.append({
            "Categoria": "EPI",
            "Item": mapa_epis.get(eid_str, eid_str),
            "Quantidade": qtds_salvas.get(eid_str, 1),
        })
    for uid in lista_uni_ids:
        uid_str = str(uid)
        resumo_linhas.append({
            "Categoria": "UNIFORME",
            "Item": mapa_uniformes.get(uid_str, uid_str),
            "Quantidade": uni_qtds_salvas.get(uid_str, 1),
        })
    for tid in lista_trein_ids:
        tid_str = str(tid)
        resumo_linhas.append({
            "Categoria": "TREINAMENTO",
            "Item": mapa_trein.get(tid_str, tid_str),
            "Quantidade": "-",
        })
    for xid in lista_exame_ids:
        xid_str = str(xid)
        resumo_linhas.append({
            "Categoria": "EXAME",
            "Item": mapa_exames.get(xid_str, xid_str),
            "Quantidade": "-",
        })

    if resumo_linhas:
        st.markdown("##### Itens Atualmente Vinculados a Este Cargo no Banco")
        st.dataframe(pd.DataFrame(resumo_linhas), use_container_width=True, hide_index=True)
