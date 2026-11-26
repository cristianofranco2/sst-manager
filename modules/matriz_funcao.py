import pandas as pd
import streamlit as st

from database import get_supabase


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
            "treinamento_ids": [],
            "exame_ids": [],
        }
    elif "epi_quantidades" not in st.session_state["matriz_state"]:
        st.session_state["matriz_state"]["epi_quantidades"] = {}
    return st.session_state["matriz_state"]


def _ir_para_modulo(destino_menu: str) -> None:
    st.session_state["origem_matriz"] = True
    st.session_state["menu_pendente"] = destino_menu


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
    st.title("🧩 Agrupamento por Cargo (EPIs, Treinamentos e Exames)")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    state = _garantir_estado_matriz()

    col_top1, col_top2 = st.columns([4, 1])
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
        nome = str(item.get("nome_funcao") or "Sem nome").strip()
        cbo = str(item.get("cbo") or "").strip()
        setor = str(item.get("setor_padrao") or "").strip()
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
            state["treinamento_ids"] = [str(x) for x in (registro_salvo.get("treinamento_ids") or [])]
            state["exame_ids"] = [str(x) for x in (registro_salvo.get("exame_ids") or [])]
        else:
            state["epi_ids"] = []
            state["epi_quantidades"] = {}
            state["treinamento_ids"] = []
            state["exame_ids"] = []
        state["carregado_para_funcao"] = funcao_selecionada

    epis = _buscar_epis()
    treinamentos = _buscar_treinamentos()
    exames = _buscar_tipos_exames()

    st.markdown("---")

    # BLOCO 1: EPIs + QUANTIDADE (- / +)
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
                nome_epi = str(epi.get("descricao") or epi.get("nome_epi") or "EPI sem descrição").strip()
                ca = str(epi.get("numero_ca") or epi.get("ca") or "").strip()
                sku = str(epi.get("codigo_sku") or "").strip()
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

    # BLOCO 2: TREINAMENTOS
    b2_esq, b2_dir = st.columns([4, 1])
    with b2_esq:
        st.subheader("🎓 3. Treinamentos do Cargo")
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
                nome_tr = str(tr.get("tipo_treinamento") or "Treinamento").strip()
                cap = str(tr.get("tipo_capacitacao") or "").strip()
                ch = tr.get("carga_horaria")
                detalhes = [p for p in [cap, f"{ch}h" if ch else ""] if p]
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

    # BLOCO 3: EXAMES
    b3_esq, b3_dir = st.columns([4, 1])
    with b3_esq:
        st.subheader("📋 4. Exames do Cargo")
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
                nome_ex = str(ex.get("nome_exame") or "Exame").strip()
                tuss = str(ex.get("codigo_tuss") or "").strip()
                meses = ex.get("validade_meses")
                detalhes = [p for p in [f"TUSS {tuss}" if tuss else "", f"Validade {meses}m" if meses else ""] if p]
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

    # RESUMO E SALVAMENTO
    st.subheader("💾 Salvar Agrupamento do Cargo")
    m1, m2, m3 = st.columns(3)
    m1.metric("EPIs Selecionados", len(state["epi_ids"]))
    m2.metric("Treinamentos Selecionados", len(state["treinamento_ids"]))
    m3.metric("Exames Selecionados", len(state["exame_ids"]))

    if st.button("💾 Salvar Requisitos do Cargo", type="primary", key="btn_salvar_matriz"):
        try:
            payload = {
                "funcao_id": funcao_selecionada,
                "epi_ids": state["epi_ids"],
                "epi_quantidades": state["epi_quantidades"],
                "treinamento_ids": state["treinamento_ids"],
                "exame_ids": state["exame_ids"],
            }
            supabase.table("funcao_requisitos").upsert(payload, on_conflict="funcao_id").execute()
            _buscar_requisito_funcao.clear()
            st.success("Requisitos do cargo salvos com sucesso!")
        except Exception as e:
            st.error(f"Erro ao salvar agrupamento do cargo: {e}")

    # TABELA CONSOLIDADA
    requisitos_salvos = _buscar_requisito_funcao(funcao_selecionada)
    if requisitos_salvos:
        mapa_epis = {
            str(e["id"]): str(e.get("descricao") or e.get("nome_epi") or e["id"])
            for e in epis
            if e.get("id")
        }
        mapa_trein = {
            str(t["id"]): str(t.get("tipo_treinamento") or t["id"])
            for t in treinamentos
            if t.get("id")
        }
        mapa_exames = {
            str(x["id"]): str(x.get("nome_exame") or x["id"])
            for x in exames
            if x.get("id")
        }
        qtds_salvas = requisitos_salvos.get("epi_quantidades") or {}

        resumo_linhas = []
        for eid in requisitos_salvos.get("epi_ids") or []:
            eid_str = str(eid)
            qtd_item = qtds_salvas.get(eid
