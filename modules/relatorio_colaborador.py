from datetime import date, datetime
import ast
import json
import re
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


def _limpar_cache() -> None:
    st.cache_data.clear()


def _normalizar(valor) -> str:
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


def _executar_insert_fallback(supabase, tabela: str, payload: dict, obrigatorias: set[str]):
    dados = dict(payload)
    for _ in range(15):
        try:
            return supabase.table(tabela).insert(dados).execute()
        except Exception as e:
            col = _extrair_coluna_pgrst204(str(e))
            if col and col in dados and col not in obrigatorias:
                dados.pop(col)
                continue
            raise
    return supabase.table(tabela).insert(dados).execute()


def _converter_para_estrutura(valor):
    if isinstance(valor, (dict, list)):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return None
        if texto.startswith("{") or texto.startswith("["):
            for parser in (json.loads, ast.literal_eval):
                try:
                    return parser(texto)
                except Exception:
                    continue
    return valor


def _extrair_mapa_referencias(valor) -> dict[str, int | None]:
    estrutura = _converter_para_estrutura(valor)
    resultado: dict[str, int | None] = {}
    if estrutura is None:
        return resultado

    if isinstance(estrutura, dict):
        for k, v in estrutura.items():
            chave = str(k or "").strip()
            if not chave:
                continue
            qtd = None
            if isinstance(v, (int, float)):
                qtd = int(v)
            elif isinstance(v, dict):
                q_raw = v.get("quantidade") or v.get("qtd")
                if q_raw is not None:
                    try:
                        qtd = int(q_raw)
                    except Exception:
                        qtd = None
            resultado[chave] = qtd
        return resultado

    if isinstance(estrutura, list):
        for item in estrutura:
            if isinstance(item, dict):
                ref = str(
                    item.get("id")
                    or item.get("epi_id")
                    or item.get("exame_id")
                    or item.get("tipo_exame_id")
                    or item.get("treinamento_id")
                    or item.get("nome")
                    or item.get("descricao")
                    or ""
                ).strip()
                if not ref:
                    continue
                q_raw = item.get("quantidade") or item.get("qtd")
                qtd = None
                if q_raw is not None:
                    try:
                        qtd = int(q_raw)
                    except Exception:
                        qtd = None
                resultado[ref] = qtd
            else:
                ref = str(item or "").strip()
                if ref:
                    resultado[ref] = None
        return resultado

    texto = str(estrutura).strip()
    if not texto:
        return resultado
    if "," in texto:
        for parte in texto.split(","):
            limpo = parte.strip().strip("'\"")
            if limpo:
                resultado[limpo] = None
        return resultado

    resultado[texto.strip("'\"")] = None
    return resultado


def _resolver_funcao_colaborador(colab: dict, funcoes: list[dict]) -> tuple[str | None, str]:
    funcao_id = str(colab.get("funcao_id") or colab.get("cargo_id") or "").strip()
    nome_direto = str(
        colab.get("funcao")
        or colab.get("funcao_nome")
        or colab.get("cargo")
        or colab.get("cargo_nome")
        or ""
    ).strip()

    if funcao_id:
        for f in funcoes:
            if str(f.get("id") or "").strip() == funcao_id:
                nome_f = str(
                    f.get("nome")
                    or f.get("nome_funcao")
                    or f.get("funcao")
                    or f.get("titulo")
                    or nome_direto
                    or "—"
                ).strip()
                return funcao_id, nome_f

    if nome_direto:
        for f in funcoes:
            nome_f = str(
                f.get("nome")
                or f.get("nome_funcao")
                or f.get("funcao")
                or f.get("titulo")
                or ""
            ).strip()
            if _normalizar(nome_f) == _normalizar(nome_direto):
                fid = str(f.get("id") or "").strip() or None
                return fid, nome_f
        return None, nome_direto

    return None, "—"


def _obter_requisito_funcao(
    requisitos: list[dict], funcao_id: str | None, nome_funcao: str
) -> dict | None:
    for req in requisitos:
        rid_func = str(req.get("funcao_id") or req.get("cargo_id") or "").strip()
        if funcao_id and rid_func and rid_func == funcao_id:
            return req
    if nome_funcao and nome_funcao != "—":
        alvo = _normalizar(nome_funcao)
        for req in requisitos:
            for chave in ("funcao", "funcao_nome", "nome_funcao", "cargo", "nome"):
                if _normalizar(req.get(chave)) == alvo:
                    return req
    return None


def _coletar_refs_por_palavra_chave(req_funcao: dict | None, palavras: tuple[str, ...]) -> dict[str, int | None]:
    coletado: dict[str, int | None] = {}
    if not req_funcao:
        return coletado
    for col, val in req_funcao.items():
        col_norm = _normalizar(col)
        if col_norm in ("id", "funcao_id", "cargo_id", "created_at", "updated_at"):
            continue
        if any(p in col_norm for p in palavras):
            for ref, qtd in _extrair_mapa_referencias(val).items():
                if ref not in coletado or coletado[ref] is None:
                    coletado[ref] = qtd
    return coletado


def _resolver_itens_catalogo(
    refs_qtd: dict[str, int | None],
    catalogo: list[dict],
    campos_rotulo: tuple[str, ...],
    manter_nao_encontrados: bool = False,
) -> list[dict]:
    if not refs_qtd:
        return []

    mapa_id = {str(item.get("id") or "").strip(): item for item in catalogo if item.get("id") is not None}
    mapa_rotulo = {}
    for item in catalogo:
        for campo in campos_rotulo:
            val_norm = _normalizar(item.get(campo))
            if val_norm:
                mapa_rotulo[val_norm] = item

    resolvidos: list[dict] = []
    vistos: set[str] = set()

    for ref, qtd in refs_qtd.items():
        item_cat = mapa_id.get(ref) or mapa_rotulo.get(_normalizar(ref))
        if item_cat:
            item_id = str(item_cat.get("id") or _normalizar(ref)).strip()
            if item_id in vistos:
                continue
            vistos.add(item_id)
            combinado = dict(item_cat)
            if qtd is not None:
                combinado["_qtd_requisito"] = qtd
            resolvidos.append(combinado)
        elif manter_nao_encontrados:
            chave = _normalizar(ref)
            if chave and chave not in vistos:
                vistos.add(chave)
                resolvidos.append({"nome": ref, "descricao": ref, "_qtd_requisito": qtd})

    return resolvidos


def _nome_exame(reg: dict) -> str:
    for c in ("nome", "nome_exame", "tipo_exame", "titulo", "descricao"):
        v = str(reg.get(c) or "").strip()
        if v:
            return v
    return "—"


def _nome_treinamento(reg: dict) -> str:
    for c in ("nome", "nome_treinamento", "titulo", "curso", "descricao"):
        v = str(reg.get(c) or "").strip()
        if v:
            return v
    return "—"


def render_relatorio_colaborador() -> None:
    render_cabecalho_modulo("📄 Relatório de Pendências e Vencimentos por Colaborador")

    if "msg_relatorio_colab" in st.session_state:
        msg = st.session_state.pop("msg_relatorio_colab")
        if msg.get("tipo") == "warning":
            st.warning(msg.get("texto", ""))
        else:
            st.success(msg.get("texto", ""))

    col_f, col_btn = st.columns([5, 1])
    with col_btn:
        if st.button("🔄 Atualizar", key="btn_att_relatorio_colab", use_container_width=True):
            _limpar_cache()
            st.rerun()

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    colaboradores = _buscar_tabela("colaboradores")
    if not colaboradores:
        st.info("Nenhum colaborador cadastrado.")
        return

    funcoes = _buscar_tabela("funcoes")
    funcao_requisitos = _buscar_tabela("funcao_requisitos")
    epis = _buscar_tabela("epis")
    inventario = _buscar_tabela("inventario_epi")
    tipos_exames = _buscar_tabela("tipos_exames")
    exames_colab = _buscar_tabela("exames_colaborador")
    treinamentos = _buscar_tabela("treinamentos")

    mapa_colabs = {}
    rotulos = []
    for c in colaboradores:
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        mapa_colabs[cid] = c
        _, nome_func = _resolver_funcao_colaborador(c, funcoes)
        matricula = str(c.get("matricula") or "—").strip()
        status = str(c.get("status") or "Ativo").strip()
        nome_c = str(c.get("nome_completo") or c.get("nome") or "Colaborador").strip()
        rotulos.append((cid, f"{nome_c} ({matricula}) — {nome_func} [{status}]"))

    with col_f:
        colab_sel_id = st.selectbox(
            "Filtrar / Selecionar Colaborador",
            options=[r[0] for r in rotulos],
            format_func=lambda cid: dict(rotulos).get(cid, cid),
            key="select_colab_relatorio",
        )

    colab_atual = mapa_colabs.get(colab_sel_id, {})
    funcao_id, nome_funcao = _resolver_funcao_colaborador(colab_atual, funcoes)
    matricula = str(colab_atual.get("matricula") or "—").strip()
    setor = str(
        colab_atual.get("setor")
        or colab_atual.get("centro_custo")
        or colab_atual.get("departamento")
        or "—"
    ).strip()
    status = str(colab_atual.get("status") or "Ativo").strip()
    nome_colab = str(colab_atual.get("nome_completo") or colab_atual.get("nome") or "—").strip()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f"**Colaborador:**\n\n{nome_colab}")
    c2.markdown(f"**Função:**\n\n{nome_funcao}")
    c3.markdown(f"**Matrícula:**\n\n{matricula}")
    c4.markdown(f"**Setor:**\n\n{setor}")
    c5.markdown(
        f"**Status:**\n\n🟢 {status}" if _normalizar(status) == "ativo" else f"**Status:**\n\n{status}"
    )

    req_funcao = _obter_requisito_funcao(funcao_requisitos, funcao_id, nome_funcao)
    refs_epi = _coletar_refs_por_palavra_chave(req_funcao, ("epi",))
    refs_exame = _coletar_refs_por_palavra_chave(req_funcao, ("exame", "aso"))
    refs_trein = _coletar_refs_por_palavra_chave(req_funcao, ("trein", "curso", "nr"))

    mapa_tipos_ex = {str(tx.get("id") or "").strip(): tx for tx in tipos_exames if tx.get("id") is not None}

    tab1, tab2, tab3 = st.tabs([
        "👤 Visão por Colaborador",
        "🕒 Histórico do Colaborador (PDF)",
        "📊 Relatório por Período",
    ])

    with tab1:
        # ---------------- EPIs ----------------
        st.subheader("🥽 EPIs")
        epis_req = _resolver_itens_catalogo(
            refs_epi, epis, ("descricao", "nome_epi", "codigo_sku", "numero_ca")
        )
        if epis_req:
            for idx, e in enumerate(epis_req):
                eid = str(e.get("id") or idx).strip()
                sku_str = str(e.get("codigo_sku") or e.get("sku") or "—")
                nome_epi_str = str(e.get("descricao") or e.get("nome_epi") or e.get("nome") or "—")
                ca_str = str(e.get("numero_ca") or e.get("ca") or "—")
                val_ca_str = _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca"))
                qtd_req = e.get("_qtd_requisito")

                cols = st.columns([1.2, 2.5, 1.2, 1.5, 1.2, 1.4])
                cols[0].markdown(f"**SKU:** {sku_str}")
                cols[1].markdown(f"**EPI:** {nome_epi_str}")
                cols[2].markdown(f"**CA:** {ca_str}")
                cols[3].markdown(f"**Val. CA:** {val_ca_str}")
                cols[4].markdown(f"**Qtd:** {qtd_req if qtd_req is not None else '—'}")
                chave_acao_epi = f"abrir_troca_epi_{colab_sel_id}_{eid}_{idx}"
                if cols[5].button("🔄 Trocar", key=f"btn_troca_{chave_acao_epi}", use_container_width=True):
                    st.session_state[chave_acao_epi] = not st.session_state.get(chave_acao_epi, False)

                if st.session_state.get(chave_acao_epi, False):
                    with st.container(border=True):
                        with st.form(f"form_troca_{chave_acao_epi}"):
                            f1, f2, f3 = st.columns(3)
                            with f1:
                                qtd_troca = st.number_input("Quantidade", min_value=1, value=max(1, int(qtd_req or 1)), step=1)
                            with f2:
                                data_troca = st.date_input("Data da Troca", value=date.today(), format="DD/MM/YYYY")
                            with f3:
                                motivo_troca = st.text_input("Motivo / Obs.", placeholder="Ex: Troca periódica")
                            if st.form_submit_button("✅ Confirmar Troca"):
                                try:
                                    lote_id = None
                                    qtd_disp_lote = 0
                                    for inv in inventario:
                                        if str(inv.get("epi_id") or "").strip() == str(e.get("id") or "").strip():
                                            disp = int(inv.get("quantidade_disponivel") or 0)
                                            if disp >= int(qtd_troca) and inv.get("id") is not None:
                                                lote_id = inv["id"]
                                                qtd_disp_lote = disp
                                                break

                                    payload_troca = {
                                        "colaborador_id": colab_sel_id,
                                        "epi_id": e.get("id"),
                                        "inventario_id": lote_id,
                                        "quantidade": int(qtd_troca),
                                        "data_troca": str(data_troca),
                                        "data_entrega": str(data_troca),
                                        "motivo": motivo_troca.strip(),
                                        "observacoes": motivo_troca.strip(),
                                    }
                                    _executar_insert_fallback(
                                        supabase,
                                        "historico_trocas_epi",
                                        payload_troca,
                                        obrigatorias={"colaborador_id", "epi_id", "quantidade"},
                                    )
                                    if lote_id is not None:
                                        novo_saldo = max(0, qtd_disp_lote - int(qtd_troca))
                                        try:
                                            supabase.table("inventario_epi").update(
                                                {"quantidade_disponivel": novo_saldo}
                                            ).eq("id", lote_id).execute()
                                        except Exception:
                                            pass

                                    st.session_state[chave_acao_epi] = False
                                    st.session_state["msg_relatorio_colab"] = {
                                        "tipo": "success",
                                        "texto": f"Troca de {nome_epi_str} ({int(qtd_troca)} un.) registrada para {nome_colab}!",
                                    }
                                    _limpar_cache()
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"Erro ao registrar troca: {err}")
        else:
            st.info("Nenhum EPI vinculado à função deste colaborador.")

        # ---------------- EXAMES ----------------
        st.subheader("📋 Exames")
        exames_req = _resolver_itens_catalogo(
            refs_exame, tipos_exames, ("nome", "nome_exame", "tipo_exame", "descricao"), manter_nao_encontrados=True
        )
        exames_do_colab = [
            ex for ex in exames_colab if str(ex.get("colaborador_id") or "").strip() == colab_sel_id
        ]

        linhas_exames_exibir: list[dict] = []
        for ex in exames_do_colab:
            tx_id = str(ex.get("tipo_exame_id") or ex.get("exame_id") or "").strip()
            tx_info = mapa_tipos_ex.get(tx_id, {})
            combinado = {**tx_info, **ex}
            combinado["Exame"] = _nome_exame(combinado)
            linhas_exames_exibir.append(combinado)

        for tx in exames_req:
            tx_id = str(tx.get("id") or "").strip()
            nome_tx = _nome_exame(tx)
            ja_existe = any(
                (tx_id and str(l.get("tipo_exame_id") or l.get("exame_id") or l.get("id") or "").strip() == tx_id)
                or (_normalizar(l.get("Exame")) == _normalizar(nome_tx) and nome_tx != "—")
                for l in linhas_exames_exibir
            )
            if not ja_existe:
                copia = dict(tx)
                copia["Exame"] = nome_tx
                if not copia.get("status"):
                    copia["status"] = "Pendente / Requisito da Função"
                linhas_exames_exibir.append(copia)

        if linhas_exames_exibir:
            for idx, ex_item in enumerate(linhas_exames_exibir):
                ex_id = str(ex_item.get("tipo_exame_id") or ex_item.get("id") or idx).strip()
                nome_ex = str(ex_item.get("Exame") or _nome_exame(ex_item))
                per_val = (
                    ex_item.get("periodicidade_meses")
                    or ex_item.get("validade_meses")
                    or ex_item.get("periodicidade")
                    or "—"
                )
                dt_real_str = _formatar_data_br(
                    ex_item.get("data_realizacao") or ex_item.get("data_exame") or ex_item.get("data_aso")
                )
                dt_venc_str = _formatar_data_br(
                    ex_item.get("data_vencimento") or ex_item.get("proximo_vencimento") or ex_item.get("validade")
                )
                status_ex = str(ex_item.get("status") or ex_item.get("resultado") or "—")

                cols = st.columns([2.4, 1.2, 1.3, 1.3, 1.5, 1.4])
                cols[0].markdown(f"**Exame:** {nome_ex}")
                cols[1].markdown(f"**Period.:** {per_val}")
                cols[2].markdown(f"**Realização:** {dt_real_str}")
                cols[3].markdown(f"**Vencimento:** {dt_venc_str}")
                cols[4].markdown(f"**Status:** {status_ex}")

                chave_ren_ex = f"abrir_ren_exame_{colab_sel_id}_{ex_id}_{idx}"
                if cols[5].button("🔁 Renovar", key=f"btn_{chave_ren_ex}", use_container_width=True):
                    st.session_state[chave_ren_ex] = not st.session_state.get(chave_ren_ex, False)

                if st.session_state.get(chave_ren_ex, False):
                    try:
                        per_padrao = max(1, int(ex_item.get("periodicidade_meses") or ex_item.get("validade_meses") or 12))
                    except Exception:
                        per_padrao = 12

                    with st.container(border=True):
                        with st.form(f"form_{chave_ren_ex}"):
                            r1, r2 = st.columns(2)
                            with r1:
                                data_real_ex = st.date_input("Data de Realização", value=date.today(), format="DD/MM/YYYY")
                            with r2:
                                meses_ex = st.number_input("Validade / Periodicidade (meses)", min_value=1, value=per_padrao, step=1)
                            novo_venc_ex = _somar_meses(data_real_ex, int(meses_ex))
                            st.caption(f"Novo vencimento: **{novo_venc_ex.strftime('%d/%m/%Y')}**")
                            if st.form_submit_button("✅ Confirmar Renovação"):
                                try:
                                    tx_id_alvo = (
                                        ex_item.get("tipo_exame_id")
                                        or (ex_item.get("id") if str(ex_item.get("id") or "").strip() in mapa_tipos_ex else None)
                                    )
                                    payload_ex = {
                                        "colaborador_id": colab_sel_id,
                                        "tipo_exame_id": tx_id_alvo,
                                        "nome": nome_ex,
                                        "data_realizacao": str(data_real_ex),
                                        "data_vencimento": str(novo_venc_ex),
                                        "validade": str(novo_venc_ex),
                                        "status": "Em dia / Renovado",
                                    }
                                    _executar_insert_fallback(
                                        supabase,
                                        "exames_colaborador",
                                        payload_ex,
                                        obrigatorias={"colaborador_id"},
                                    )
                                    st.session_state[chave_ren_ex] = False
                                    st.session_state["msg_relatorio_colab"] = {
                                        "tipo": "success",
                                        "texto": f"Exame '{nome_ex}' renovado até {novo_venc_ex.strftime('%d/%m/%Y')}!",
                                    }
                                    _limpar_cache()
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"Erro ao renovar exame: {err}")
        else:
            st.info("Nenhum exame vinculado à função deste colaborador.")

        # ---------------- TREINAMENTOS ----------------
        st.subheader("🎓 Treinamentos")
        trein_do_colab = [
            tr for tr in treinamentos if str(tr.get("colaborador_id") or "").strip() == colab_sel_id
        ]
        trein_req = _resolver_itens_catalogo(
            refs_trein, treinamentos, ("nome", "nome_treinamento", "titulo", "curso", "descricao"), manter_nao_encontrados=True
        )

        linhas_trein_exibir: list[dict] = []
        for tr in trein_do_colab:
            copia = dict(tr)
            copia["Treinamento"] = _nome_treinamento(copia)
            linhas_trein_exibir.append(copia)

        for tr in trein_req:
            nome_tr = _nome_treinamento(tr)
            ja_existe = any(_normalizar(l.get("Treinamento")) == _normalizar(nome_tr) and nome_tr != "—" for l in linhas_trein_exibir)
            if not ja_existe:
                copia = dict(tr)
                copia["Treinamento"] = nome_tr
                if not copia.get("status"):
                    copia["status"] = "Pendente / Requisito da Função"
                linhas_trein_exibir.append(copia)

        if linhas_trein_exibir:
            for idx, tr_item in enumerate(linhas_trein_exibir):
                tr_id = str(tr_item.get("id") or idx).strip()
                nome_tr = str(tr_item.get("Treinamento") or _nome_treinamento(tr_item))
                nr_tr = str(tr_item.get("nr") or tr_item.get("codigo_nr") or tr_item.get("carga_horaria") or "—")
                real_tr_str = _formatar_data_br(tr_item.get("data_realizacao") or tr_item.get("data_conclusao"))
                venc_tr_str = _formatar_data_br(tr_item.get("data_vencimento") or tr_item.get("validade"))
                status_tr = str(tr_item.get("status") or "—")

                cols = st.columns([2.4, 1.2, 1.3, 1.3, 1.5, 1.4])
                cols[0].markdown(f"**Treinamento:** {nome_tr}")
                cols[1].markdown(f"**NR/Carga:** {nr_tr}")
                cols[2].markdown(f"**Realização:** {real_tr_str}")
                cols[3].markdown(f"**Vencimento:** {venc_tr_str}")
                cols[4].markdown(f"**Status:** {status_tr}")

                chave_ren_tr = f"abrir_ren_trein_{colab_sel_id}_{tr_id}_{idx}"
                if cols[5].button("🔁 Renovar", key=f"btn_{chave_ren_tr}", use_container_width=True):
                    st.session_state[chave_ren_tr] = not st.session_state.get(chave_ren_tr, False)

                if st.session_state.get(chave_ren_tr, False):
                    with st.container(border=True):
                        with st.form(f"form_{chave_ren_tr}"):
                            t1, t2 = st.columns(2)
                            with t1:
                                data_real_tr = st.date_input("Data de Conclusão", value=date.today(), format="DD/MM/YYYY")
                            with t2:
                                meses_tr = st.number_input("Validade (meses)", min_value=1, value=12, step=1)
                            novo_venc_tr = _somar_meses(data_real_tr, int(meses_tr))
                            st.caption(f"Novo vencimento: **{novo_venc_tr.strftime('%d/%m/%Y')}**")
                            if st.form_submit_button("✅ Confirmar Renovação"):
                                try:
                                    payload_tr = {
                                        "colaborador_id": colab_sel_id,
                                        "nome": nome_tr,
                                        "titulo": nome_tr,
                                        "data_realizacao": str(data_real_tr),
                                        "data_conclusao": str(data_real_tr),
                                        "data_vencimento": str(novo_venc_tr),
                                        "validade": str(novo_venc_tr),
                                        "status": "Em dia / Renovado",
                                    }
                                    _executar_insert_fallback(
                                        supabase,
                                        "treinamentos",
                                        payload_tr,
                                        obrigatorias={"colaborador_id"},
                                    )
                                    st.session_state[chave_ren_tr] = False
                                    st.session_state["msg_relatorio_colab"] = {
                                        "tipo": "success",
                                        "texto": f"Treinamento '{nome_tr}' renovado até {novo_venc_tr.strftime('%d/%m/%Y')}!",
                                    }
                                    _limpar_cache()
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"Erro ao renovar treinamento: {err}")
        else:
            st.info("Nenhum treinamento vinculado à função deste colaborador.")

    with tab2:
        st.info("Histórico consolidado do colaborador disponível para consulta e exportação.")

    with tab3:
        st.info("Acompanhamento de vencimentos e renovações por período.")


render_relatorios = render_relatorio_colaborador
