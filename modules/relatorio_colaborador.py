from datetime import date, datetime
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
def _buscar_treinamentos() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("treinamentos").select("*").execute()
    return res.data or []


@st.cache_data(ttl=60, show_spinner=False)
def _buscar_tipos_exames() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("tipos_exames").select("*").execute()
    return res.data or []


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


def _somar_meses(data_base: date, meses: int) -> date:
    ano_total = data_base.year + (data_base.month - 1 + meses) // 12
    mes_novo = (data_base.month - 1 + meses) % 12 + 1
    ultimo_dia_mes = pd.Period(f"{ano_total}-{mes_novo:02d}", freq="M").days_in_month
    dia_novo = min(data_base.day, ultimo_dia_mes)
    return date(ano_total, mes_novo, dia_novo)


def _formatar_vencimento_e_dias(data_venc: date | None, hoje: date) -> tuple[str, str]:
    if not data_venc:
        return "—", "Sem data"

    dias = (data_venc - hoje).days
    data_str = data_venc.strftime("%d/%m/%Y")

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
    st.title("📄 Relatório de Pendências e Vencimentos por Colaborador")

    try:
        get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    col_top1, col_top2 = st.columns([4, 1])
    with col_top2:
        if st.button("🔄 Atualizar", key="btn_atualizar_relatorio", use_container_width=True):
            _buscar_colaboradores.clear()
            _buscar_funcoes.clear()
            _buscar_requisitos.clear()
            _buscar_epis.clear()
            _buscar_treinamentos.clear()
            _buscar_tipos_exames.clear()

    colaboradores = _buscar_colaboradores()
    if not colaboradores:
        st.info("Nenhum colaborador cadastrado.")
        return

    mapa_colabs = {str(c["id"]): c for c in colaboradores if c.get("id")}
    ids_colabs = list(mapa_colabs.keys())

    colab_id = st.selectbox(
        "Selecione o Colaborador",
        options=ids_colabs,
        format_func=lambda cid: (
            f"{mapa_colabs[cid].get('nome_completo', 'Sem nome')} "
            f"({mapa_colabs[cid].get('matricula', '')}) — {mapa_colabs[cid].get('cargo', '')}"
        ),
        key="select_colab_relatorio",
    )

    colab = mapa_colabs[colab_id]
    nome_colab = str(colab.get("nome_completo") or "—").strip()
    funcao_colab = str(colab.get("cargo") or "—").strip()
    matricula_colab = str(colab.get("matricula") or "—").strip()
    setor_colab = str(colab.get("centro_custo") or "—").strip()
    data_admissao = _parse_data(colab.get("data_admissao"))

    # CABEÇALHO SIMPLES E OBJETIVO
    with st.container(border=True):
        h1, h2, h3, h4 = st.columns([3, 2, 1.5, 1.5])
        h1.markdown(f"**Colaborador:**  \n{nome_colab}")
        h2.markdown(f"**Função:**  \n{funcao_colab}")
        h3.markdown(f"**Matrícula:**  \n{matricula_colab}")
        h4.markdown(f"**Setor:**  \n{setor_colab}")

    funcoes = _buscar_funcoes()
    requisitos_lista = _buscar_requisitos()
    epis = _buscar_epis()
    treinamentos = _buscar_treinamentos()
    exames = _buscar_tipos_exames()

    # Localiza a função por ID (se houver) ou pelo nome normalizado
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

    mapa_epis = {str(e["id"]).strip(): e for e in epis if e.get("id")}
    mapa_trein = {str(t["id"]).strip(): t for t in treinamentos if t.get("id")}
    mapa_exames = {str(x["id"]).strip(): x for x in exames if x.get("id")}

    # 1. BLOCO EPIs
    st.markdown("### 🥽 EPIs")
    linhas_epi = []
    for eid in epi_ids_req:
        epi = mapa_epis.get(eid)
        if not epi:
            continue
        nome_epi = str(epi.get("descricao") or epi.get("nome_epi") or "EPI").strip()
        qtd = epi_qtds_req.get(eid, 1)
        label_item = f"{nome_epi} (Qtd: {qtd})"

        data_venc_epi = _parse_data(epi.get("data_validade_ca") or epi.get("validade_ca"))
        if not data_venc_epi and data_admissao and epi.get("dias_durabilidade_media"):
            try:
                data_venc_epi = (
                    data_admissao
                    + pd.Timedelta(days=int(epi["dias_durabilidade_media"])).to_pytimedelta().date()
                )
            except Exception:
                data_venc_epi = None

        venc_str, dias_str = _formatar_vencimento_e_dias(data_venc_epi, hoje)
        linhas_epi.append({"EPI": label_item, "Vencimento": venc_str, "Dias Restantes": dias_str})

    if linhas_epi:
        st.dataframe(pd.DataFrame(linhas_epi), use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum EPI vinculado à função deste colaborador.")

    # 2. BLOCO EXAMES
    st.markdown("### 📋 Exames")
    linhas_exame = []
    for ex_id in exame_ids_req:
        ex = mapa_exames.get(ex_id)
        if not ex:
            continue
        nome_ex = str(ex.get("nome_exame") or "Exame").strip()
        validade_meses = ex.get("validade_meses")

        data_venc_ex = None
        if data_admissao and validade_meses:
            try:
                meses_int = int(validade_meses)
                if meses_int > 0:
                    data_venc_ex = _somar_meses(data_admissao, meses_int)
            except Exception:
                data_venc_ex = None

        venc_str, dias_str = _formatar_vencimento_e_dias(data_venc_ex, hoje)
        linhas_exame.append({"Exame": nome_ex, "Vencimento": venc_str, "Dias Restantes": dias_str})

    if linhas_exame:
        st.dataframe(pd.DataFrame(linhas_exame), use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum exame vinculado à função deste colaborador.")

    # 3. BLOCO TREINAMENTOS
    st.markdown("### 🎓 Treinamentos")
    linhas_trein = []

    venc_por_tipo: dict[str, date] = {}
    for tr in treinamentos:
        if str(tr.get("colaborador_id") or "").strip() == str(colab_id).strip():
            tipo_tr = " ".join(str(tr.get("tipo_treinamento") or "").lower().split())
            dt_v = _parse_data(tr.get("data_vencimento"))
            if tipo_tr and dt_v:
                if tipo_tr not in venc_por_tipo or dt_v > venc_por_tipo[tipo_tr]:
                    venc_por_tipo[tipo_tr] = dt_v

    for tid in trein_ids_req:
        tr_base = mapa_trein.get(tid)
        if not tr_base:
            continue
        nome_tr = str(tr_base.get("tipo_treinamento") or "Treinamento").strip()
        chave_tr = " ".join(nome_tr.lower().split())
        data_venc_tr = venc_por_tipo.get(chave_tr) or _parse_data(tr_base.get("data_vencimento"))
        venc_str, dias_str = _formatar_vencimento_e_dias(data_venc_tr, hoje)
        linhas_trein.append({"Treinamento": nome_tr, "Vencimento": venc_str, "Dias Restantes": dias_str})

    if linhas_trein:
        st.dataframe(pd.DataFrame(linhas_trein), use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum treinamento vinculado à função deste colaborador.")
