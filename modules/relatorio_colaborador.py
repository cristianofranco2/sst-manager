from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st

from database import get_supabase


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_colaboradores() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("colaboradores").select("*").order("nome_completo").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_funcoes() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("funcoes").select("*").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_requisitos() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("funcao_requisitos").select("*").execute()
        return res.data or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_epis() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("epis").select("*").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_inventario() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("inventario_epi").select("*").execute()
        return res.data or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_historico_trocas() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("historico_trocas_epi").select("*").order("data_troca", desc=True).execute()
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
def _buscar_exames_colaborador() -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table("exames_colaborador").select("*").order("data_realizacao", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def _limpar_todo_cache_relatorio() -> None:
    _buscar_colaboradores.clear()
    _buscar_funcoes.clear()
    _buscar_requisitos.clear()
    _buscar_epis.clear()
    _buscar_inventario.clear()
    _buscar_historico_trocas.clear()
    _buscar_treinamentos.clear()
    _buscar_tipos_exames.clear()
    _buscar_exames_colaborador.clear()


def _parse_data(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
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
    ano_total = data_base.year + (data_base.month - 1 + meses) // 12
    mes_novo = (data_base.month - 1 + meses) % 12 + 1
    ultimo_dia_mes = pd.Period(f"{ano_total}-{mes_novo:02d}", freq="M").days_in_month
    dia_novo = min(data_base.day, ultimo_dia_mes)
    return date(ano_total, mes_novo, dia_novo)


def _formatar_vencimento_e_dias(data_venc: date | None, hoje: date, is_desligado: bool = False) -> tuple[str, str]:
    if not data_venc:
        return "—", "Sem data"

    data_str = data_venc.strftime("%d/%m/%Y")
    if is_desligado:
        return data_str, "⏹️ Desligado (Histórico)"

    dias = (data_venc - hoje).days
    if dias < 0:
        return data_str, f"🔴 Vencido ({abs(dias)}d)"
    if dias == 0:
        return data_str, "🟡 Vence hoje (0d)"
    if dias <= 30:
        return data_str, f"🟡 {dias} dias"
    return data_str, f"🟢 {dias} dias"


def _normalizar_lista_ids(valor) -> list[str]:
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(x).strip() for x in valor if x is not None and str(x).strip()]
    return []


def render_relatorio_colaborador() -> None:
    st.title("📄 Relatório de SST e Auditoria de Vencimentos")

    try:
        get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab1, tab2 = st.tabs([
        "👤 Visão por Colaborador",
        "📊 Relatório por Período (Trocas, Exames e Treinamentos)",
    ])

    colaboradores = _buscar_colaboradores()
    mapa_colabs = {str(c["id"]): c for c in colaboradores if c.get("id")}
    ids_colabs = list(mapa_colabs.keys())

    funcoes = _buscar_funcoes()
    requisitos_lista = _buscar_requisitos()
    epis = _buscar_epis()
    inventario = _buscar_inventario()
    historico_trocas = _buscar_historico_trocas()
    treinamentos = _buscar_treinamentos()
    exames = _buscar_tipos_exames()
    exames_colab = _buscar_exames_colaborador()

    mapa_epis = {str(e["id"]).strip(): e for e in epis if e.get("id")}
    mapa_trein = {str(t["id"]).strip(): t for t in treinamentos if t.get("id")}
    mapa_exames = {str(x["id"]).strip(): x for x in exames if x.get("id")}

    with tab1:
        col_top1, col_top2 = st.columns([5, 1])
        with col_top2:
            if st.button("🔄 Atualizar", key="btn_atualizar_relatorio_tab1", use_container_width=True):
                _limpar_todo_cache_relatorio()
                st.rerun()

        if not colaboradores:
            st.info("Nenhum colaborador cadastrado.")
            return

        colab_id = st.selectbox(
            "Selecione o Colaborador",
            options=ids_colabs,
            format_func=lambda cid: (
                f"{mapa_colabs[cid].get('nome_completo', 'Sem nome')} "
                f"({mapa_colabs[cid].get('matricula', '')}) — {mapa_colabs[cid].get('cargo', '')} "
                f"[{mapa_colabs[cid].get('status', 'Ativo')}]"
            ),
            key="select_colab_relatorio",
        )

        colab = mapa_colabs[colab_id]
        nome_colab = str(colab.get("nome_completo") or "—").strip()
        funcao_colab = str(colab.get("cargo") or "—").strip()
        matricula_colab = str(colab.get("matricula") or "—").strip()
        setor_colab = str(colab.get("centro_custo") or "—").strip()
        status_colab = str(colab.get("status") or "Ativo").strip()
        data_admissao = _parse_data(colab.get("data_admissao"))

        is_desligado = status_colab.lower() in ["desligado", "inativo"]

        with st.container(border=True):
            h1, h2, h3, h4, h5 = st.columns([3, 2, 1.5, 1.5, 1.5])
            h1.markdown(f"**Colaborador:**  \n{nome_colab}")
            h2.markdown(f"**Função:**  \n{funcao_colab}")
            h3.markdown(f"**Matrícula:**  \n{matricula_colab}")
            h4.markdown(f"**Setor:**  \n{setor_colab}")
            h5.markdown(f"**Status:**  \n{'🔴 ' + status_colab if is_desligado else '🟢 ' + status_colab}")

        if is_desligado:
            st.warning("⚠️ **Colaborador Desligado:** Os contadores de vencimento e alertas foram desativados para este colaborador. Os registros são mantidos exclusivamente para consulta histórica.")

        funcao_id_encontrado = None
        if colab.get("funcao_id"):
            funcao_id_encontrado = str(colab.get("funcao_id")).strip()

        if not funcao_id_encontrado:
            alvo = " ".join(funcao_colab.lower().split())
            for f in funcoes:
                nome_f = " ".join(str(f.get("nome_funcao") or "").lower().split())
                if nome_f and nome_f == alvo:
                    funcao_id_encontrado = str(f.get("id")).strip()
                    break

        req_funcao = {}
        if funcao_id_encontrado:
            for r in requisitos_lista:
                if str(r.get("funcao_id") or "").strip() == funcao_id_encontrado:
                    req_funcao = r
                    break

        hoje = date.today()
        epi_ids_req = _normalizar_lista_ids(req_funcao.get("epi_ids"))
        epi_qtds_req = req_funcao.get("epi_quantidades") or {}
        trein_ids_req = _normalizar_lista_ids(req_funcao.get("treinamento_ids"))
        exame_ids_req = _normalizar_lista_ids(req_funcao.get("exame_ids"))

        # 1. BLOCO EPIs
        st.markdown("### 🥽 EPIs")
        ultima_troca_epi: dict[str, dict] = {}
        for h in historico_trocas:
            if str(h.get("colaborador_id") or "").strip() == str(colab_id).strip():
                eid_h = str(h.get("epi_id") or "").strip()
                if eid_h and eid_h not in ultima_troca_epi:
                    ultima_troca_epi[eid_h] = h

        linhas_epi_exibicao = []
        for eid in epi_ids_req:
            epi = mapa_epis.get(eid)
            if not epi:
                continue
            nome_epi = str(epi.get("descricao") or epi.get("nome_epi") or "EPI").strip()
            qtd = int(epi_qtds_req.get(eid, 1) or 1)
            label_item = f"{nome_epi} (Qtd: {qtd})"

            troca_info = ultima_troca_epi.get(eid)
            data_venc_epi = _parse_data(troca_info.get("data_vencimento_novo")) if troca_info else None
            if not data_venc_epi:
                data_venc_epi = _parse_data(epi.get("data_validade_ca") or epi.get("validade_ca"))
            if not data_venc_epi and data_admissao and epi.get("dias_durabilidade_media"):
                try:
                    data_venc_epi = data_admissao + timedelta(days=int(epi["dias_durabilidade_media"]))
                except Exception:
                    data_venc_epi = None

            venc_str, dias_str = _formatar_vencimento_e_dias(data_venc_epi, hoje, is_desligado=is_desligado)
            linhas_epi_exibicao.append((eid, epi, nome_epi, qtd, label_item, venc_str, dias_str))

        if linhas_epi_exibicao:
            for eid, epi, nome_epi, qtd, label_item, venc_str, dias_str in linhas_epi_exibicao:
                c_item, c_venc, c_dias, c_acao = st.columns([4.5, 1.8, 2.2, 0.9])
                c_item.write(label_item)
                c_venc.write(venc_str)
                c_dias.write(dias_str)

                with c_acao:
                    if is_desligado:
                        st.caption("⏹️ Desligado")
                    else:
                        lotes_epi = [
                            item for item in inventario
                            if str(item.get("epi_id") or "").strip() == eid and int(item.get("quantidade_disponivel") or 0) > 0
                        ]
                        with st.popover("🔄", help=f"Trocar {nome_epi}"):
                            if not lotes_epi:
                                st.warning("Sem saldo disponível no inventário para este EPI.")
                            else:
                                opcoes_lotes = [str(l["id"]) for l in lotes_epi if l.get("id")]
                                mapa_lotes = {
                                    str(l["id"]): (
                                        f"Lote {l.get('codigo_lote') or '—'} | "
                                        f"Saldo: {l.get('quantidade_disponivel')} | "
                                        f"Entrada: {_formatar_data_br(l.get('data_entrada'))}"
                                    )
                                    for l in lotes_epi if l.get("id")
                                }
                                lote_sel_id = st.selectbox(
                                    "Item do Inventário",
                                    options=opcoes_lotes,
                                    format_func=lambda lid: mapa_lotes[lid],
                                    key=f"sel_lote_troca_{colab_id}_{eid}",
                                )
                                lote_sel = next((l for l in lotes_epi if str(l.get("id")) == lote_sel_id), {})
                                saldo_disp = int(lote_sel.get("quantidade_disponivel") or 1)

                                qtd_troca = st.number_input(
                                    "Quantidade",
                                    min_value=1,
                                    max_value=max(1, saldo_disp),
                                    value=min(qtd, max(1, saldo_disp)),
                                    step=1,
                                    key=f"qtd_troca_{colab_id}_{eid}",
                                )
                                data_troca = st.date_input(
                                    "Data da troca",
                                    value=hoje,
                                    format="DD/MM/YYYY",
                                    key=f"dt_troca_{colab_id}_{eid}",
                                )
                                motivo_troca = st.text_input(
                                    "Motivo",
                                    value="Troca / Renovação",
                                    key=f"mot_troca_{colab_id}_{eid}",
                                )

                                dur_dias = int(epi.get("dias_durabilidade_media") or 0)
                                novo_venc_epi = (
                                    data_troca + timedelta(days=dur_dias)
                                    if dur_dias > 0
                                    else (_parse_data(epi.get("data_validade_ca") or epi.get("validade_ca")) or (data_troca + timedelta(days=365)))
                                )
                                st.caption(f"Novo vencimento: **{novo_venc_epi.strftime('%d/%m/%Y')}**")

                                if st.button("Confirmar Troca", key=f"btn_conf_troca_{colab_id}_{eid}"):
                                    try:
                                        novo_saldo = max(0, saldo_disp - int(qtd_troca))
                                        supabase.table("inventario_epi").update(
                                            {"quantidade_disponivel": novo_saldo}
                                        ).eq("id", lote_sel_id).execute()

                                        supabase.table("historico_trocas_epi").insert({
                                            "colaborador_id": colab_id,
                                            "epi_id": eid,
                                            "inventario_id": lote_sel_id,
                                            "tipo_movimentacao": "Troca",
                                            "quantidade": int(qtd_troca),
                                            "data_troca": str(data_troca),
                                            "data_vencimento_novo": str(novo_venc_epi),
                                            "motivo": motivo_troca.strip(),
                                        }).execute()

                                        _limpar_todo_cache_relatorio()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao registrar troca: {e}")
        else:
            st.caption("Nenhum EPI vinculado à função deste colaborador.")

        # 2. BLOCO EXAMES
        st.markdown("### 📋 Exames")
        ultimos_exames_colab: dict[str, date] = {}
        for ec in exames_colab:
            if str(ec.get("colaborador_id") or "").strip() == str(colab_id).strip():
                ex_id_c = str(ec.get("tipo_exame_id") or "").strip()
                dt_v = _parse_data(ec.get("data_vencimento"))
                if ex_id_c and dt_v:
                    if ex_id_c not in ultimos_exames_colab or dt_v > ultimos_exames_colab[ex_id_c]:
                        ultimos_exames_colab[ex_id_c] = dt_v

        linhas_exame_exibicao = []
        for ex_id in exame_ids_req:
            ex = mapa_exames.get(ex_id)
            if not ex:
                continue
            nome_ex = str(ex.get("nome_exame") or "Exame").strip()
            validade_meses = int(ex.get("validade_meses") or 12)

            data_venc_ex = ultimos_exames_colab.get(ex_id)
            if not data_venc_ex and data_admissao:
                data_venc_ex = _somar_meses(data_admissao, validade_meses)

            venc_str, dias_str = _formatar_vencimento_e_dias(data_venc_ex, hoje, is_desligado=is_desligado)
            linhas_exame_exibicao.append((ex_id, nome_ex, validade_meses, venc_str, dias_str))

        if linhas_exame_exibicao:
            for ex_id, nome_ex, validade_meses, venc_str, dias_str in linhas_exame_exibicao:
                c_item, c_venc, c_dias, c_acao = st.columns([4.5, 1.8, 2.2, 0.9])
                c_item.write(nome_ex)
                c_venc.write(venc_str)
                c_dias.write(dias_str)

                with c_acao:
                    if is_desligado:
                        st.caption("⏹️ Desligado")
                    else:
                        with st.popover("🔁", help=f"Lançar realização / renovar {nome_ex}"):
                            dt_real_ex = st.date_input(
                                "Data de realização",
                                value=hoje,
                                format="DD/MM/YYYY",
                                key=f"dt_real_ex_{colab_id}_{ex_id}",
                            )
                            novo_venc_ex = _somar_meses(dt_real_ex, validade_meses)
                            st.caption(f"Próximo vencimento ({validade_meses}m): **{novo_venc_ex.strftime('%d/%m/%Y')}**")
                            obs_ex = st.text_input("Observação", key=f"obs_ex_{colab_id}_{ex_id}")

                            if st.button("Salvar Realização", key=f"btn_ren_ex_{colab_id}_{ex_id}"):
                                try:
                                    supabase.table("exames_colaborador").insert({
                                        "colaborador_id": colab_id,
                                        "tipo_exame_id": ex_id,
                                        "data_realizacao": str(dt_real_ex),
                                        "data_vencimento": str(novo_venc_ex),
                                        "status": "Válido",
                                        "observacoes": obs_ex.strip(),
                                    }).execute()
                                    _limpar_todo_cache_relatorio()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar realização do exame: {e}")
        else:
            st.caption("Nenhum exame vinculado à função deste colaborador.")

        # 3. BLOCO TREINAMENTOS
        st.markdown("### 🎓 Treinamentos")
        venc_por_tipo: dict[str, date] = {}
        for tr in treinamentos:
            if str(tr.get("colaborador_id") or "").strip() == str(colab_id).strip():
                tipo_tr = " ".join(str(tr.get("tipo_treinamento") or "").lower().split())
                dt_v = _parse_data(tr.get("data_vencimento"))
                if tipo_tr and dt_v:
                    if tipo_tr not in venc_por_tipo or dt_v > venc_por_tipo[tipo_tr]:
                        venc_por_tipo[tipo_tr] = dt_v

        linhas_trein_exibicao = []
        for tid in trein_ids_req:
            tr_base = mapa_trein.get(tid)
            if not tr_base:
                continue
            nome_tr = str(tr_base.get("tipo_treinamento") or "Treinamento").strip()
            chave_tr = " ".join(nome_tr.lower().split())
            data_venc_tr = venc_por_tipo.get(chave_tr) or _parse_data(tr_base.get("data_vencimento"))
            venc_str, dias_str = _formatar_vencimento_e_dias(data_venc_tr, hoje, is_desligado=is_desligado)
            linhas_trein_exibicao.append((tid, tr_base, nome_tr, venc_str, dias_str))

        if linhas_trein_exibicao:
            for tid, tr_base, nome_tr, venc_str, dias_str in linhas_trein_exibicao:
                c_item, c_venc, c_dias, c_acao = st.columns([4.5, 1.8, 2.2, 0.9])
                c_item.write(nome_tr)
                c_venc.write(venc_str)
                c_dias.write(dias_str)

                with c_acao:
                    if is_desligado:
                        st.caption("⏹️ Desligado")
                    else:
                        with st.popover("🔁", help=f"Lançar realização / renovar {nome_tr}"):
                            dt_real_tr = st.date_input(
                                "Data de realização",
                                value=hoje,
                                format="DD/MM/YYYY",
                                key=f"dt_real_tr_{colab_id}_{tid}",
                            )
                            meses_tr = int(tr_base.get("validade_meses") or 12)
                            novo_venc_tr = _somar_meses(dt_real_tr, meses_tr)
                            st.caption(f"Próximo vencimento ({meses_tr}m): **{novo_venc_tr.strftime('%d/%m/%Y')}**")

                            if st.button("Salvar Realização", key=f"btn_ren_tr_{colab_id}_{tid}"):
                                try:
                                    supabase.table("treinamentos").insert({
                                        "colaborador_id": colab_id,
                                        "tipo_treinamento": nome_tr,
                                        "tipo_capacitacao": tr_base.get("tipo_capacitacao") or "Reciclagem",
                                        "modalidade": tr_base.get("modalidade") or "Presencial",
                                        "carga_horaria": tr_base.get("carga_horaria"),
                                        "data_inicio": str(dt_real_tr),
                                        "data_fim": str(dt_real_tr),
                                        "data_emissao": str(dt_real_tr),
                                        "data_realizacao": str(dt_real_tr),
                                        "validade_meses": meses_tr,
                                        "data_vencimento": str(novo_venc_tr),
                                        "status": "Válido",
                                    }).execute()
                                    _limpar_todo_cache_relatorio()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar realização do treinamento: {e}")
        else:
            st.caption("Nenhum treinamento vinculado à função deste colaborador.")

    # ABA 2: RELATÓRIO CONSOLIDADO POR PERÍODO
    with tab2:
        st.subheader("🗓️ Consulta Geral de Movimentações por Período")
        p1, p2, p3 = st.columns([2, 2, 2])
        with p1:
            dt_inicio = st.date_input("Data Inicial", value=date.today() - timedelta(days=30), format="DD/MM/YYYY")
        with p2:
            dt_fim = st.date_input("Data Final", value=date.today(), format="DD/MM/YYYY")
        with p3:
            tipo_filtro = st.selectbox("Categoria", ["TODOS", "Trocas de EPI", "Exames Realizados", "Treinamentos Realizados"])

        registros_periodo = []

        # 1. Trocas de EPI
        if tipo_filtro in ["TODOS", "Trocas de EPI"]:
            for h in historico_trocas:
                dt_evt = _parse_data(h.get("data_troca"))
                if dt_evt and dt_inicio <= dt_evt <= dt_fim:
                    cid = str(h.get("colaborador_id") or "")
                    col_info = mapa_colabs.get(cid, {})
                    eid = str(h.get("epi_id") or "")
                    epi_info = mapa_epis.get(eid, {})
                    registros_periodo.append({
                        "Data": dt_evt.strftime("%d/%m/%Y"),
                        "Categoria": "🥽 Troca de EPI",
                        "Colaborador": col_info.get("nome_completo") or "—",
                        "Matrícula": col_info.get("matricula") or "—",
                        "Status Colab.": col_info.get("status") or "Ativo",
                        "Item / Evento": epi_info.get("descricao") or "EPI",
                        "Detalhes / Qtd": f"Qtd: {h.get('quantidade', 1)} | Motivo: {h.get('motivo', '—')}",
                        "Novo Vencimento": _formatar_data_br(h.get("data_vencimento_novo")),
                    })

        # 2. Exames Realizados
        if tipo_filtro in ["TODOS", "Exames Realizados"]:
            for ec in exames_colab:
                dt_evt = _parse_data(ec.get("data_realizacao"))
                if dt_evt and dt_inicio <= dt_evt <= dt_fim:
                    cid = str(ec.get("colaborador_id") or "")
                    col_info = mapa_colabs.get(cid, {})
                    xid = str(ec.get("tipo_exame_id") or "")
                    ex_info = mapa_exames.get(xid, {})
                    registros_periodo.append({
                        "Data": dt_evt.strftime("%d/%m/%Y"),
                        "Categoria": "📋 Realização de Exame",
                        "Colaborador": col_info.get("nome_completo") or "—",
                        "Matrícula": col_info.get("matricula") or "—",
                        "Status Colab.": col_info.get("status") or "Ativo",
                        "Item / Evento": ex_info.get("nome_exame") or "Exame",
                        "Detalhes / Qtd": ec.get("observacoes") or "Realização cadastrada",
                        "Novo Vencimento": _formatar_data_br(ec.get("data_vencimento")),
                    })

        # 3. Treinamentos Realizados
        if tipo_filtro in ["TODOS", "Treinamentos Realizados"]:
            for tr in treinamentos:
                dt_evt = _parse_data(tr.get("data_realizacao") or tr.get("data_emissao"))
                if dt_evt and dt_inicio <= dt_evt <= dt_fim:
                    cid = str(tr.get("colaborador_id") or "")
                    col_info = mapa_colabs.get(cid, {})
                    registros_periodo.append({
                        "Data": dt_evt.strftime("%d/%m/%Y"),
                        "Categoria": "🎓 Realização de Treinamento",
                        "Colaborador": col_info.get("nome_completo") or "—",
                        "Matrícula": col_info.get("matricula") or "—",
                        "Status Colab.": col_info.get("status") or "Ativo",
                        "Item / Evento": tr.get("tipo_treinamento") or "Treinamento",
                        "Detalhes / Qtd": f"{tr.get('tipo_capacitacao', '')} ({tr.get('carga_horaria', '')}h)",
                        "Novo Vencimento": _formatar_data_br(tr.get("data_vencimento")),
                    })

        if registros_periodo:
            df_rep = pd.DataFrame(registros_periodo)
            df_rep = df_rep.sort_values(by="Data", ascending=False)
            st.markdown(f"##### Total de eventos no período ({dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}): **{len(df_rep)}**")
            st.dataframe(df_rep, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma movimentação ou realização encontrada no período selecionado.")
