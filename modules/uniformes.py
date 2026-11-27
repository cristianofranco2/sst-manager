import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

COLUNAS_OCULTAS_TABELA = {"id", "created_at", "updated_at", "deleted_at"}
TIPOS_UNIFORME_PADRAO = [
    "CAMISA",
    "CALÇA",
    "BERMUDA",
    "JAQUETA / FRIO",
    "CALÇADO",
    "COLETE",
    "AVENTAL",
    "OUTRO",
]
TAMANHOS_UNIFORME_PADRAO = [
    "PP",
    "P",
    "M",
    "G",
    "GG",
    "XGG",
    "36",
    "38",
    "40",
    "42",
    "44",
    "46",
    "48",
    "ÚNICO",
]
SETORES_UNIFORME_PADRAO = [
    "OPERAÇÃO",
    "ADMINISTRATIVO",
    "LOGÍSTICA",
    "EXPEDIÇÃO",
    "MANUTENÇÃO",
    "QUALIDADE",
    "GERAL",
]


def _para_maiusculo(valor):
    if isinstance(valor, str):
        return " ".join(valor.strip().upper().split())
    if isinstance(valor, list):
        return [_para_maiusculo(item) for item in valor]
    if isinstance(valor, dict):
        return {k: _para_maiusculo(v) for k, v in valor.items()}
    return valor


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


def _limpar_cache_uniformes() -> None:
    st.cache_data.clear()


def _executar_insert_fallback(supabase, tabela: str, payload: dict, obrigatorias: set[str]):
    dados = _para_maiusculo(dict(payload))
    for _ in range(25):
        try:
            return supabase.table(tabela).insert(dados).execute()
        except Exception as e:
            col = _extrair_coluna_pgrst204(str(e))
            if col and col in dados and col not in obrigatorias:
                dados.pop(col)
                continue
            raise
    return supabase.table(tabela).insert(dados).execute()


def _filtrar_colunas_exibicao(registros: list[dict]) -> list[dict]:
    filtrados: list[dict] = []
    for reg in registros:
        if not isinstance(reg, dict):
            continue
        item = {
            k: v
            for k, v in reg.items()
            if str(k).strip().lower() not in COLUNAS_OCULTAS_TABELA
        }
        filtrados.append(item)
    return filtrados


def _registrar_estoque_inicial_uniforme(
    supabase, uniforme_id, quantidade: int, estoque_minimo: int, localizacao: str
) -> None:
    if uniforme_id is None or quantidade <= 0:
        return
    payload_inv = {
        "uniforme_id": uniforme_id,
        "quantidade_disponivel": int(quantidade),
        "quantidade": int(quantidade),
        "saldo": int(quantidade),
        "estoque_minimo": int(estoque_minimo),
        "localizacao": _para_maiusculo(localizacao),
    }
    try:
        _executar_insert_fallback(
            supabase,
            "inventario_uniforme",
            payload_inv,
            obrigatorias={"uniforme_id"},
        )
    except Exception:
        pass


def render_uniformes() -> None:
    render_cabecalho_modulo("👕 Cadastro de Uniformes")

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    tab_lista, tab_novo = st.tabs([
        "📋 Uniformes Cadastrados",
        "➕ Cadastrar Novo Uniforme",
    ])

    with tab_lista:
        c_top1, c_top2 = st.columns([4, 1.5])
        with c_top1:
            st.subheader("Uniformes Cadastrados")
        with c_top2:
            if st.button("🔄 Atualizar lista", key="btn_att_uniformes", use_container_width=True):
                _limpar_cache_uniformes()
                st.rerun()

        dados = _buscar_tabela("uniformes")
        if dados:
            dados_limpos = _filtrar_colunas_exibicao(dados)
            df = pd.DataFrame(dados_limpos)
            for col in df.columns:
                if col not in ("durabilidade_dias", "validade_meses", "periodicidade_meses", "ativo"):
                    df[col] = df[col].map(lambda v: _para_maiusculo(v) if isinstance(v, str) else v)
            if "ativo" in df.columns:
                df["ativo"] = df["ativo"].map(lambda v: "ATIVO" if bool(v) else "INATIVO")

            mapa_colunas = {
                "nome": "Uniforme",
                "descricao": "Descrição",
                "tipo": "Tipo",
                "tamanho": "Tamanho",
                "cor": "Cor",
                "modelo": "Modelo",
                "setor": "Setor",
                "durabilidade_dias": "Durabilidade (Dias)",
                "validade_meses": "Validade (Meses)",
                "codigo_sku": "SKU",
                "ativo": "Status",
            }
            df_exibir = df.rename(columns={k: v for k, v in mapa_colunas.items() if k in df.columns})
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
        else:
            st.info("NENHUM UNIFORME CADASTRADO ATÉ O MOMENTO.")

    with tab_novo:
        st.subheader("Novo Uniforme")
        with st.form("form_cadastro_uniforme", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                nome_uniforme = st.text_input(
                    "Nome / Descrição do Uniforme *",
                    placeholder="EX: CAMISA POLO OPERACIONAL, CALÇA BRIM",
                )
            with c2:
                tipo_sel = st.selectbox(
                    "Tipo *",
                    options=TIPOS_UNIFORME_PADRAO,
                )
                tipo_custom = st.text_input(
                    "Ou informe outro Tipo",
                    placeholder="EX: JALECO, MACACÃO",
                )
            with c3:
                tamanho_sel = st.selectbox(
                    "Tamanho *",
                    options=TAMANHOS_UNIFORME_PADRAO,
                    index=2,
                )
                tamanho_custom = st.text_input(
                    "Ou informe outro Tamanho",
                    placeholder="EX: 50, G1",
                )

            c4, c5, c6 = st.columns(3)
            with c4:
                cor = st.text_input(
                    "Cor *",
                    placeholder="EX: AZUL MARINHO, CINZA, PRETO",
                )
            with c5:
                modelo = st.text_input(
                    "Modelo *",
                    placeholder="EX: MANGA CURTA, REFORÇADO, TRADICIONAL",
                )
            with c6:
                setor_sel = st.selectbox(
                    "Setor *",
                    options=SETORES_UNIFORME_PADRAO,
                )
                setor_custom = st.text_input(
                    "Ou informe outro Setor",
                    placeholder="EX: RECEBIMENTO, PORTARIA",
                )

            c7, c8, c9 = st.columns(3)
            with c7:
                durabilidade_dias = st.number_input(
                    "Período de Troca / Durabilidade (dias) *",
                    min_value=1,
                    value=180,
                    step=1,
                )
            with c8:
                validade_meses = st.number_input(
                    "Validade Referência (meses)",
                    min_value=1,
                    value=6,
                    step=1,
                )
            with c9:
                codigo_sku = st.text_input(
                    "Código SKU / Referência",
                    placeholder="EX: UNI-CAM-M-01",
                )

            st.markdown("---")
            st.markdown("##### 📦 Estoque Inicial (Opcional)")
            e1, e2, e3 = st.columns(3)
            with e1:
                qtd_inicial = st.number_input(
                    "Quantidade Inicial",
                    min_value=0,
                    value=0,
                    step=1,
                )
            with e2:
                estoque_minimo = st.number_input(
                    "Estoque Mínimo",
                    min_value=0,
                    value=5,
                    step=1,
                )
            with e3:
                localizacao = st.text_input(
                    "Localização no Almoxarifado",
                    placeholder="EX: PRATELEIRA U-01",
                )

            ativo = st.checkbox("Uniforme ativo", value=True)
            submitted = st.form_submit_button("💾 Salvar Uniforme")

            if submitted:
                nome_limpo = _para_maiusculo(nome_uniforme)
                tipo_limpo = _para_maiusculo(tipo_custom or tipo_sel)
                tamanho_limpo = _para_maiusculo(tamanho_custom or tamanho_sel)
                cor_limpa = _para_maiusculo(cor)
                modelo_limpo = _para_maiusculo(modelo)
                setor_limpo = _para_maiusculo(setor_custom or setor_sel)

                if not nome_limpo or not tipo_limpo or not tamanho_limpo:
                    st.warning("Preencha os campos obrigatórios: Nome do Uniforme, Tipo e Tamanho.")
                else:
                    try:
                        payload = {
                            "nome": nome_limpo,
                            "descricao": nome_limpo,
                            "tipo": tipo_limpo,
                            "tamanho": tamanho_limpo,
                            "cor": cor_limpa,
                            "modelo": modelo_limpo,
                            "setor": setor_limpo,
                            "durabilidade_dias": int(durabilidade_dias),
                            "validade_meses": int(validade_meses),
                            "periodicidade_meses": int(validade_meses),
                            "codigo_sku": _para_maiusculo(codigo_sku),
                            "ativo": bool(ativo),
                        }
                        res = _executar_insert_fallback(
                            supabase,
                            "uniformes",
                            payload,
                            obrigatorias={"nome"},
                        )
                        inserido = (res.data or [{}])[0] if getattr(res, "data", None) else {}
                        if int(qtd_inicial) > 0 and inserido.get("id") is not None:
                            _registrar_estoque_inicial_uniforme(
                                supabase,
                                inserido.get("id"),
                                int(qtd_inicial),
                                int(estoque_minimo),
                                localizacao,
                            )
                        _limpar_cache_uniformes()
                        st.success(
                            f"Uniforme '{nome_limpo}' ({tipo_limpo} • {tamanho_limpo} • {setor_limpo}) cadastrado em MAIÚSCULO!"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar uniforme no Supabase: {e}")


render_cadastro_uniformes = render_uniformes
