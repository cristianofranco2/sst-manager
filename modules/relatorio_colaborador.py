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


def _extrair_nome_cargo(colab: dict, cargos: list[dict]) -> tuple[str | None, str]:
    cargo_id = str(colab.get("cargo_id") or colab.get("funcao_id") or "").strip()
    nome_direto = str(
        colab.get("cargo")
        or colab.get("cargo_nome")
        or colab.get("funcao")
        or colab.get("funcao_nome")
        or ""
    ).strip()

    if cargo_id:
        for c in cargos:
            if str(c.get("id") or "").strip() == cargo_id:
                nome_c = str(
                    c.get("nome")
                    or c.get("nome_cargo")
                    or c.get("cargo")
                    or c.get("funcao")
                    or nome_direto
                    or "—"
                ).strip()
                return cargo_id, nome_c

    if nome_direto:
        for c in cargos:
            nome_c = str(c.get("nome") or c.get("nome_cargo") or c.get("cargo") or c.get("funcao") or "").strip()
            if _normalizar(nome_c) == _normalizar(nome_direto):
                cid = str(c.get("id") or "").strip() or None
                return cid, nome_c
        return None, nome_direto

    return None, "—"


def _bate_com_cargo_ou_funcao(registro: dict, cargo_id: str | None, nome_funcao: str) -> bool:
    reg_cargo_id = str(
        registro.get("cargo_id")
        or registro.get("funcao_id")
        or registro.get("id_cargo")
        or ""
    ).strip()
    if cargo_id and reg_cargo_id and reg_cargo_id == cargo_id:
        return True

    if nome_funcao and nome_funcao != "—":
        alvo = _normalizar(nome_funcao)
        for campo in ("funcao", "funcao_nome", "cargo", "cargo_nome", "nome_cargo", "nome_funcao"):
            val = _normalizar(registro.get(campo))
            if val and (val == alvo or alvo in val or val in alvo):
                return True

    return False


def _filtrar_vinculos(
    vinculos: list[dict],
    catalogo: list[dict],
    colab_id: str,
    cargo_id: str | None,
    nome_funcao: str,
    chaves_id_item: tuple[str, ...],
) -> list[dict]:
    mapa_itens = {str(item.get("id") or "").strip(): item for item in catalogo if item.get("id") is not None}
    resultados = []

    for v in vinculos:
        v_colab = str(v.get("colaborador_id") or "").strip()
        bate_colab = bool(colab_id and v_colab and v_colab == colab_id)
        bate_cargo = _bate_com_cargo_ou_funcao(v, cargo_id, nome_funcao)

        if not bate_colab and not bate_cargo:
            continue

        item_ref = {}
        for k in chaves_id_item:
            iid = str(v.get(k) or "").strip()
            if iid and iid in mapa_itens:
                item_ref = mapa_itens[iid]
                break

        resultados.append({**item_ref, **v})

    return resultados


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

    cargos = _buscar_tabela("cargos")
    epis = _buscar_tabela("epis")
    exames = _buscar_tabela("exames")
    treinamentos = _buscar_tabela("treinamentos")

    vinculos_epi = (
        _buscar_tabela("cargo_epis")
        or _buscar_tabela("funcao_epis")
        or _buscar_tabela("epis_cargo")
        or _buscar_tabela("entregas_epi")
        or _buscar_tabela("historico_trocas_epi")
    )
    vinculos_exame = (
        _buscar_tabela("cargo_exames")
        or _buscar_tabela("funcao_exames")
        or _buscar_tabela("exames_cargo")
        or _buscar_tabela("aso_exames")
        or _buscar_tabela("exames_colaborador")
    )
    vinculos_treinamento = (
        _buscar_tabela("cargo_treinamentos")
        or _buscar_tabela("funcao_treinamentos")
        or _buscar_tabela("treinamentos_cargo")
        or _buscar_tabela("treinamentos_colaborador")
    )

    mapa_colabs = {}
    rotulos = []
    for c in colaboradores:
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        mapa_colabs[cid] = c
        _, nome_func = _extrair_nome_cargo(c, cargos)
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
    cargo_id, nome_funcao = _extrair_nome_cargo(colab_atual, cargos)
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

    tab1, tab2, tab3 = st.tabs([
        "👤 Visão por Colaborador",
        "🕒 Histórico do Colaborador (PDF)",
        "📊 Relatório por Período",
    ])

    with tab1:
        st.subheader("🥽 EPIs")
        itens_epi = _filtrar_vinculos(
            vinculos_epi, epis, colab_sel_id, cargo_id, nome_funcao, ("epi_id", "id_epi")
        )
        if itens_epi:
            df_epi = pd.DataFrame([
                {
                    "SKU": str(x.get("codigo_sku") or x.get("sku") or "—"),
                    "EPI": str(x.get("descricao") or x.get("nome_epi") or x.get("nome") or "—"),
                    "CA": str(x.get("numero_ca") or x.get("ca") or "—"),
                    "Validade CA": _formatar_data_br(x.get("data_validade_ca") or x.get("validade_ca")),
                    "Data / Vencimento": _formatar_data_br(x.get("data_vencimento") or x.get("data_entrega") or x.get("data_troca")),
                }
                for x in itens_epi
            ])
            st.dataframe(df_epi, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum EPI vinculado à função deste colaborador.")

        st.subheader("📋 Exames")
        itens_exame = _filtrar_vinculos(
            vinculos_exame, exames, colab_sel_id, cargo_id, nome_funcao, ("exame_id", "id_exame")
        )
        if itens_exame:
            df_ex = pd.DataFrame([
                {
                    "Exame": str(x.get("nome") or x.get("descricao") or x.get("tipo_exame") or "—"),
                    "Periodicidade / Validade": _formatar_data_br(x.get("data_vencimento") or x.get("validade") or x.get("data_realizacao")),
                    "Status": str(x.get("status") or "—"),
                }
                for x in itens_exame
            ])
            st.dataframe(df_ex, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum exame vinculado à função deste colaborador.")

        st.subheader("🎓 Treinamentos")
        itens_trein = _filtrar_vinculos(
            vinculos_treinamento, treinamentos, colab_sel_id, cargo_id, nome_funcao, ("treinamento_id", "id_treinamento")
        )
        if itens_trein:
            df_tr = pd.DataFrame([
                {
                    "Treinamento": str(x.get("nome") or x.get("titulo") or x.get("descricao") or "—"),
                    "NR / Carga": str(x.get("nr") or x.get("codigo_nr") or "—"),
                    "Vencimento": _formatar_data_br(x.get("data_vencimento") or x.get("validade") or x.get("data_realizacao")),
                    "Status": str(x.get("status") or "—"),
                }
                for x in itens_trein
            ])
            st.dataframe(df_tr, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum treinamento vinculado à função deste colaborador.")

    with tab2:
        st.info("Use a aba de exportação em PDF do seu módulo de relatórios para gerar o histórico deste colaborador.")

    with tab3:
        st.info("Filtre vencimentos e pendências por intervalo de datas.")


render_relatorios = render_relatorio_colaborador
