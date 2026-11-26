from datetime import date, datetime
import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

DATA_MIN_CALENDARIO = date(1900, 1, 1)
DATA_MAX_CALENDARIO = date(2100, 12, 31)
COLUNAS_OBRIGATORIAS_EPI = {"numero_ca"}
CHAVE_MSG_EPI = "msg_feedback_cadastro_epi"


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_epis() -> list[dict]:
    supabase = get_supabase()
    res = supabase.table("epis").select("*").execute()
    return res.data or []


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_saldos_inventario() -> dict[str, int]:
    supabase = get_supabase()
    try:
        res = supabase.table("inventario_epi").select("epi_id, quantidade_disponivel").execute()
        saldos: dict[str, int] = {}
        for row in res.data or []:
            eid = str(row.get("epi_id") or "").strip()
            if not eid:
                continue
            saldos[eid] = saldos.get(eid, 0) + int(row.get("quantidade_disponivel") or 0)
        return saldos
    except Exception:
        return {}


def _limpar_cache_epis() -> None:
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


def _chave_unicidade_epi(sku: str, ca: str, validade: date | str | None) -> tuple[str, str, str]:
    dt_val = _parse_data(validade)
    val_norm = dt_val.strftime("%Y-%m-%d") if dt_val else _normalizar_texto(validade)
    return (
        _normalizar_texto(sku),
        _normalizar_texto(ca),
        val_norm,
    )


def _existe_epi_duplicado(epis_existentes: list[dict], sku: str, ca: str, validade: date) -> dict | None:
    chave_nova = _chave_unicidade_epi(sku, ca, validade)
    for e in epis_existentes:
        sku_e = e.get("codigo_sku") or e.get("sku") or ""
        ca_e = e.get("numero_ca") or e.get("ca") or e.get("codigo_ca") or ""
        val_e = e.get("data_validade_ca") or e.get("validade_ca")
        if _chave_unicidade_epi(sku_e, ca_e, val_e) == chave_nova:
            return e
    return None


def _extrair_id_inserido(res) -> str | None:
    if not res or not getattr(res, "data", None):
        return None
    primeiro = res.data[0]
    if isinstance(primeiro, dict) and primeiro.get("id") is not None:
        return str(primeiro["id"]).strip()
    return None


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


def _inserir_epi_com_fallback(supabase, payload: dict):
    """
    Insere na tabela 'epis' garantindo que colunas obrigatórias (como numero_ca)
    sejam preservadas e removendo colunas inexistentes em caso de PGRST204.
    """
    dados = dict(payload)
    for _ in range(15):
        try:
            return supabase.table("epis").insert(dados).execute()
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida not in COLUNAS_OBRIGATORIAS_EPI:
                dados.pop(col_invalida)
                continue
            raise
    return supabase.table("epis").insert(dados).execute()


def _localizar_epi_id_recem_criado(
    supabase, sku: str, ca: str, validade: date, descricao: str
) -> str | None:
    val_iso = validade.strftime("%Y-%m-%d")
    try:
        res = (
            supabase.table("epis")
            .select("*")
            .eq("codigo_sku", sku)
            .eq("numero_ca", ca)
            .execute()
        )
        linhas = res.data or []
        if linhas:
            for linha in reversed(linhas):
                val_linha = str(linha.get("data_validade_ca") or linha.get("validade_ca") or "")[:10]
                if (
                    val_linha == val_iso
                    and str(linha.get("descricao") or "").strip() == descricao
                    and linha.get("id") is not None
                ):
                    return str(linha["id"]).strip()
            for linha in reversed(linhas):
                val_linha = str(linha.get("data_validade_ca") or linha.get("validade_ca") or "")[:10]
                if val_linha == val_iso and linha.get("id") is not None:
                    return str(linha["id"]).strip()
            if linhas[-1].get("id") is not None:
                return str(linhas[-1]["id"]).strip()
    except Exception:
        pass

    try:
        res_all = supabase.table("epis").select("*").execute()
        for linha in reversed(res_all.data or []):
            val_linha = str(linha.get("data_validade_ca") or linha.get("validade_ca") or "")[:10]
            if (
                str(linha.get("codigo_sku") or "").strip() == sku
                and str(linha.get("numero_ca") or "").strip() == ca
                and val_linha == val_iso
                and linha.get("id") is not None
            ):
                return str(linha["id"]).strip()
    except Exception:
        pass

    return None


def _inserir_entrada_inicial_inventario(
    supabase,
    epi_id: str,
    quantidade: int,
    ca: str,
    validade_ca: date,
    sku: str,
    descricao: str,
) -> tuple[bool, str | None]:
    if quantidade <= 0 or not epi_id:
        return True, None

    obs_partes = []
    if ca.strip():
        obs_partes.append(f"CA: {ca.strip()}")
    if validade_ca:
        obs_partes.append(f"Val. Lote: {validade_ca.strftime('%d/%m/%Y')}")
    obs_partes.append(f"Entrada inicial no cadastro do EPI ({sku.strip()} - {descricao.strip()})")
    observacoes = " | ".join(obs_partes)

    payload = {
        "epi_id": epi_id,
        "codigo_lote": f"INICIAL-{date.today().strftime('%Y%m%d')}",
        "quantidade_disponivel": int(quantidade),
        "data_entrada": str(date.today()),
        "observacoes": observacoes,
    }

    dados = dict(payload)
    for _ in range(15):
        try:
            supabase.table("inventario_epi").insert(dados).execute()
            return True, None
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida != "epi_id":
                dados.pop(col_invalida)
                continue
            return False, msg
    return False, "Não foi possível inserir a entrada inicial no inventário."


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

    tab1, tab2 = st.tabs(["EPIs Cadastrados", "➕ Cadastrar Novo EPI"])

    with tab1:
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.subheader("Catálogo de EPIs")
        with col_b:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_epis", use_container_width=True):
                _limpar_cache_epis()
                st.rerun()

        try:
            epis = _buscar_epis()
            saldos_inv = _buscar_saldos_inventario()

            if epis:
                linhas = []
                for e in epis:
                    eid = str(e.get("id") or "").strip()
                    sku = str(e.get("codigo_sku") or e.get("sku") or "—").strip()
                    descricao = str(e.get("descricao") or e.get("nome_epi") or "—").strip()
                    categoria = str(e.get("categoria") or "—").strip()
                    modelo = str(e.get("modelo") or "—").strip()
                    ca = str(e.get("numero_ca") or e.get("ca") or e.get("codigo_ca") or "—").strip()
                    val_ca = _formatar_data_br(e.get("data_validade_ca") or e.get("validade_ca"))
                    estoque_real = saldos_inv.get(eid, 0)
                    estoque_min = e.get("estoque_minimo")
                    est_min_str = "—" if estoque_min in (None, "") else int(estoque_min)

                    linhas.append({
                        "SKU": sku,
                        "Descrição": descricao,
                        "Categoria": categoria,
                        "Modelo": modelo,
                        "Nº CA": ca,
                        "Validade CA": val_ca,
                        "Estoque": estoque_real,
                        "Estoque Mín.": est_min_str,
                    })

                st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum EPI cadastrado até o momento.")
        except Exception as e:
            st.error(f"Erro ao carregar catálogo de EPIs: {e}")

    with tab2:
        st.subheader("Cadastrar Novo EPI")

        with st.form("form_cadastro_epi", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                codigo_sku = st.text_input("Código SKU *")
                descricao = st.text_input("Descrição do EPI *")
                categoria = st.text_input("Categoria", placeholder="Ex: Proteção dos Pés, Mãos, Olhos")
            with c2:
                modelo = st.text_input("Modelo")
                ca = st.text_input("Número do CA *")
                validade_ca = st.date_input(
                    "Validade do CA *",
                    value=date.today(),
                    min_value=DATA_MIN_CALENDARIO,
                    max_value=DATA_MAX_CALENDARIO,
                    format="DD/MM/YYYY",
                )
            with c3:
                durabilidade_dias = st.number_input("Durabilidade (dias)", min_value=0, value=180, step=1)
                qtd_inicial = st.number_input("Quantidade Inicial (alimenta Inventário)", min_value=0, value=0, step=1)
                estoque_minimo = st.number_input("Estoque Mínimo", min_value=0, value=5, step=1)

            submitted = st.form_submit_button("💾 Salvar EPI")

            if submitted:
                sku_limpo = codigo_sku.strip()
                desc_limpa = descricao.strip()
                ca_limpo = ca.strip()

                if not sku_limpo or not desc_limpa or not ca_limpo:
                    st.warning("Preencha os campos obrigatórios: Código SKU, Descrição do EPI e Número do CA.")
                else:
                    epis_atuais = _buscar_epis()
                    duplicado = _existe_epi_duplicado(epis_atuais, sku_limpo, ca_limpo, validade_ca)

                    if duplicado:
                        desc_dupl = str(duplicado.get("descricao") or duplicado.get("nome_epi") or desc_limpa).strip()
                        st.error(
                            f"Cadastro bloqueado: já existe um EPI cadastrado com SKU '{sku_limpo}', "
                            f"CA '{ca_limpo}' e Validade '{validade_ca.strftime('%d/%m/%Y')}' ({desc_dupl}). "
                            f"Para adicionar novo saldo deste mesmo item, utilize o módulo de Inventário."
                        )
                    else:
                        try:
                            novo_epi = {
                                "codigo_sku": sku_limpo,
                                "descricao": desc_limpa,
                                "categoria": categoria.strip(),
                                "modelo": modelo.strip(),
                                "numero_ca": ca_limpo,
                                "data_validade_ca": str(validade_ca),
                                "estoque_minimo": int(estoque_minimo),
                            }
                            res_epi = _inserir_epi_com_fallback(supabase, novo_epi)
                            epi_id = _extrair_id_inserido(res_epi)

                            if not epi_id:
                                epi_id = _localizar_epi_id_recem_criado(
                                    supabase=supabase,
                                    sku=sku_limpo,
                                    ca=ca_limpo,
                                    validade=validade_ca,
                                    descricao=desc_limpa,
                                )

                            if int(qtd_inicial) > 0:
                                if epi_id:
                                    ok_inv, err_inv = _inserir_entrada_inicial_inventario(
                                        supabase=supabase,
                                        epi_id=epi_id,
                                        quantidade=int(qtd_inicial),
                                        ca=ca_limpo,
                                        validade_ca=validade_ca,
                                        sku=sku_limpo,
                                        descricao=desc_limpa,
                                    )
                                    if ok_inv:
                                        st.session_state[CHAVE_MSG_EPI] = {
                                            "tipo": "success",
                                            "texto": f"EPI '{desc_limpa}' adicionado com sucesso e saldo inicial de {int(qtd_inicial)} un. lançado no Inventário!",
                                        }
                                    else:
                                        st.session_state[CHAVE_MSG_EPI] = {
                                            "tipo": "warning",
                                            "texto": f"EPI '{desc_limpa}' adicionado, mas houve um aviso ao lançar saldo inicial no Inventário: {err_inv}",
                                        }
                                else:
                                    st.session_state[CHAVE_MSG_EPI] = {
                                        "tipo": "warning",
                                        "texto": f"EPI '{desc_limpa}' adicionado, mas não foi possível localizar o ID para lançar o saldo inicial no Inventário.",
                                    }
                            else:
                                st.session_state[CHAVE_MSG_EPI] = {
                                    "tipo": "success",
                                    "texto": f"EPI '{desc_limpa}' adicionado com sucesso!",
                                }

                            _limpar_cache_epis()
                            st.rerun()
                        except Exception as e:
                            msg_err = str(e)
                            if "23505" in msg_err:
                                st.error(
                                    f"Já existe um registro com essa combinação de SKU '{sku_limpo}', "
                                    f"CA '{ca_limpo}' e Validade '{validade_ca.strftime('%d/%m/%Y')}' "
                                    f"(ou restrição única no banco). Se o erro citar 'epis_codigo_sku_key', "
                                    f"rode o SQL para trocar a unicidade para (codigo_sku, numero_ca, data_validade_ca)."
                                )
                            else
