from datetime import date, datetime
import pandas as pd
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


def _extrair_valores_lista_ou_campo(valor) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, list):
        out = []
        for item in valor:
            if isinstance(item, dict):
                v = item.get("id") or item.get("nome") or item.get("descricao")
                if v is not None and str(v).strip():
                    out.append(str(v).strip())
            elif str(item).strip():
                out.append(str(item).strip())
        return out
    texto = str(valor).strip()
    if not texto:
        return []
    if "," in texto:
        return [p.strip() for p in texto.split(",") if p.strip()]
    return [texto]


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


def _mapear_itens_por_referencia(
    referencias: list[str], catalogo: list[dict], campos_rotulo: tuple[str, ...]
) -> list[dict]:
    if not referencias:
        return []
    mapa_id = {str(item.get("id") or "").strip(): item for item in catalogo if item.get("id") is not None}
    mapa_rotulo = {}
    for item in catalogo:
        for c in campos_rotulo:
            val = _normalizar(item.get(c))
            if val:
                mapa_rotulo[val] = item

    encontrados = []
    vistos = set()
    for ref in referencias:
        item = mapa_id.get(ref) or mapa_rotulo.get(_normalizar(ref))
        if item:
            iid = str(item.get("id") or _normalizar(ref))
            if iid not in vistos:
                vistos.add(iid)
                encontrados.append(item)
        else:
            chave = _normalizar(ref)
            if chave not in vistos:
                vistos.add(chave)
                encontrados.append({"nome": ref, "descricao": ref})
    return encontrados


def render_relatorio_colaborador() -> None:
    render_cabecalho_modulo("📄 Relatório de Pendências e Vencimentos por Colaborador")

    col_f, col_btn = st.columns([5, 1])
    with col_btn:
        if st.button("🔄 Atualizar", key="btn_att_relatorio_colab", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    colaboradores = _buscar_tabela("colaboradores")
    if not colaboradores:
        st.info("Nenhum colaborador cadastrado.")
        return

    funcoes = _buscar_tabela("funcoes")
    funcao_requisitos = _buscar_tabela("funcao_requisitos")
    epis = _buscar_tabela("epis")
    historico_trocas = _buscar_tabela("historico_trocas_epi")
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
    setor = str(colab_atual.get("setor") or colab_atual.get("departamento") or "—").strip()
    status = str(colab_atual.get("status") or "Ativo").strip()
    nome_colab = str(colab_atual.get("nome_completo") or colab_atual.get("nome") or "—").strip()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f"**Colaborador:**\n\n{nome_colab}")
    c2.markdown(f"**Função:**\n\n{nome_funcao}")
    c3.markdown(f"**Matrícula:**\n\n{matricula}")
    c4.markdown(f"**Setor:**\n\n{setor}")
    c5.markdown(f"**Status:**\n\n🟢 {status}" if _normalizar(status) == "ativo" else f"**Status:**\n\n{status}")

    req_funcao = _obter_requisito_funcao(funcao_requisitos, funcao_id, nome_funcao)

    refs_epi = []
    refs_exame = []
    refs_trein = []
    if req_funcao:
        for k, v in req_funcao.items():
            kl = k.lower()
            if "epi" in kl and k not in ("id", "funcao_id", "cargo_id"):
                refs_epi.extend(_extrair_valores_lista_ou_campo(v))
            elif "exame" in kl:
                refs_exame.extend(_extrair_valores_lista_ou_campo(v))
            elif "trein" in kl:
                refs_trein.extend(_extrair_valores_lista_ou_campo(v))

    tab1, tab2, tab3 = st.tabs([
        "👤 Visão por Colaborador",
        "🕒 Histórico do Colaborador (PDF)",
        "📊 Relatório por Período",
    ])

    with tab1:
        st.subheader("🥽 EPIs")
        epis_req = _mapear_itens_por_referencia(
            refs_epi, epis, ("descricao", "nome_epi", "codigo_sku", "numero_ca")
        )
        trocas_colab = [
            t for t in historico_trocas if str(t.get("colaborador_id") or "").strip() == colab_sel_id
        ]
        mapa_epis = {str(e.get("id") or "").strip(): e for e in epis if e.get("id") is not None}

        if epis_req:
            st.dataframe(
                pd.DataFrame([
                    {
                        "SKU": str(e.get("codigo_sku") or e.get("sku") or "—"),
                        "EPI": str(e.get("descricao") or e.get("nome_epi") or e.get("nome") or "—"),
                        "Nº CA": str(e.get("numero_ca") or e.get("ca") or "—"),
                        "Validade CA": _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca")),
                    }
                    for e in epis_req
                ]),
                use_container_width=True,
                hide_index=True,
            )
        elif trocas_colab:
            st.dataframe(
                pd.DataFrame([
                    {
                        "EPI": str(
                            (mapa_epis.get(str(t.get("epi_id") or "").strip()) or {}).get("descricao")
                            or (mapa_epis.get(str(t.get("epi_id") or "").strip()) or {}).get("nome_epi")
                            or "—"
                        ),
                        "Quantidade": t.get("quantidade") or "—",
                        "Data": _formatar_data_br(t.get("data_entrega") or t.get("data_troca") or t.get("created_at")),
                    }
                    for t in trocas_colab
                ]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhum EPI vinculado à função deste colaborador.")

        st.subheader("📋 Exames")
        exames_req = _mapear_itens_por_referencia(
            refs_exame, tipos_exames, ("nome", "descricao", "tipo_exame")
        )
        exames_do_colab = [
            ex for ex in exames_colab if str(ex.get("colaborador_id") or "").strip() == colab_sel_id
        ]
        mapa_tipos_ex = {str(tx.get("id") or "").strip(): tx for tx in tipos_exames if tx.get("id") is not None}

        if exames_do_colab:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Exame": str(
                            (mapa_tipos_ex.get(str(ex.get("tipo_exame_id") or "").strip()) or {}).get("nome")
                            or (mapa_tipos_ex.get(str(ex.get("tipo_exame_id") or "").strip()) or {}).get("descricao")
                            or ex.get("nome")
                            or "—"
                        ),
                        "Vencimento": _formatar_data_br(ex.get("data_vencimento") or ex.get("validade")),
                        "Status": str(ex.get("status") or "—"),
                    }
                    for ex in exames_do_colab
                ]),
                use_container_width=True,
                hide_index=True,
            )
        elif exames_req:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Exame": str(tx.get("nome") or tx.get("descricao") or "—"),
                        "Periodicidade": str(tx.get("periodicidade_meses") or tx.get("periodicidade") or "—"),
                    }
                    for tx in exames_req
                ]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhum exame vinculado à função deste colaborador.")

        st.subheader("🎓 Treinamentos")
        trein_do_colab = [
            tr for tr in treinamentos if str(tr.get("colaborador_id") or "").strip() == colab_sel_id
        ]
        trein_req = _mapear_itens_por_referencia(
            refs_trein, treinamentos, ("nome", "titulo", "descricao")
        )

        if trein_do_colab:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Treinamento": str(tr.get("nome") or tr.get("titulo") or tr.get("descricao") or "—"),
                        "Vencimento": _formatar_data_br(tr.get("data_vencimento") or tr.get("validade")),
                        "Status": str(tr.get("status") or "—"),
                    }
                    for tr in trein_do_colab
                ]),
                use_container_width=True,
                hide_index=True,
            )
        elif trein_req:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Treinamento": str(tr.get("nome") or tr.get("titulo") or tr.get("descricao") or "—"),
                        "Vencimento": _formatar_data_br(tr.get("data_vencimento") or tr.get("validade")),
                    }
                    for tr in trein_req
                ]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhum treinamento vinculado à função deste colaborador.")

    with tab2:
        st.info("Histórico em PDF disponível para o colaborador selecionado.")

    with tab3:
        st.info("Visão por período disponível para acompanhamento de vencimentos.")


render_relatorios = render_relatorio_colaborador
