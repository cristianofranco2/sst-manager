import re
import streamlit as st
from database import get_supabase
from ui_components import render_cabecalho_modulo


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


def _executar_insert_maiusculo(supabase, tabela: str, payload: dict, obrigatorias: set[str]):
    dados = _para_maiusculo(dict(payload))
    for _ in range(20):
        try:
            return supabase.table(tabela).insert(dados).execute()
        except Exception as e:
            col = _extrair_coluna_pgrst204(str(e))
            if col and col in dados and col not in obrigatorias:
                dados.pop(col)
                continue
            raise
    return supabase.table(tabela).insert(dados).execute()


def _converter_exames_existentes_maiusculo(supabase) -> tuple[int, int]:
    atualizados = 0
    erros = 0
    res = supabase.table("tipos_exames").select("*").execute()
    for row in res.data or []:
        rid = row.get("id")
        if rid is None:
            continue
        patch = {}
        for campo in ("nome", "nome_exame", "tipo_exame", "codigo_tuss", "observacoes", "descricao"):
            val = row.get(campo)
            if isinstance(val, str) and val.strip():
                up = " ".join(val.strip().upper().split())
                if up != val:
                    patch[campo] = up
        if patch:
            try:
                supabase.table("tipos_exames").update(patch).eq("id", rid).execute()
                atualizados += 1
            except Exception:
                erros += 1
    return atualizados, erros


def render_tipos_exames() -> None:
    render_cabecalho_modulo("📋 Cadastro de Exames")
    supabase = get_supabase()

    tab_lista, tab_novo = st.tabs(["Exames Cadastrados", "+ Cadastrar Novo Exame"])

    with tab_lista:
        c_top1, c_top2 = st.columns([4, 1.5])
        c_top1.subheader("Tipos de Exames Cadastrados")
        if c_top2.button("🔄 Atualizar lista", key="btn_att_exames", use_container_width=True):
            st.rerun()

        if st.button("🔠 Padronizar cadastrados em MAIÚSCULO", key="btn_up_exames_existentes"):
            ok_q, err_q = _converter_exames_existentes_maiusculo(supabase)
            st.success(
                f"Exames atualizados para MAIÚSCULO: {ok_q}"
                + (f" (erros: {err_q})" if err_q else "")
            )
            st.rerun()

        res = supabase.table("tipos_exames").select("*").execute()
        dados = res.data or []
        if dados:
            st.dataframe(dados, use_container_width=True, hide_index=True)
        else:
            st.info("NENHUM EXAME CADASTRADO.")

    with tab_novo:
        with st.form("form_novo_exame", clear_on_submit=True):
            nome_exame = st.text_input("Nome do Exame *", placeholder="EX: AUDIOMETRIA, SANGUE")
            codigo_tuss = st.text_input("Código TUSS", placeholder="EX: 40101010")
            validade_meses = st.number_input("Validade (meses)", min_value=1, value=12, step=1)
            observacoes = st.text_area("Observações", placeholder="OBSERVAÇÕES DO EXAME")

            submitted = st.form_submit_button("💾 Salvar Exame")
            if submitted:
                if not nome_exame.strip():
                    st.error("Informe o nome do exame.")
                    return

                payload = _para_maiusculo({
                    "nome": nome_exame,
                    "nome_exame": nome_exame,
                    "codigo_tuss": codigo_tuss,
                    "validade_meses": int(validade_meses),
                    "periodicidade_meses": int(validade_meses),
                    "observacoes": observacoes,
                })
                try:
                    _executar_insert_maiusculo(
                        supabase,
                        "tipos_exames",
                        payload,
                        obrigatorias={"nome"},
                    )
                    st.success(f"Exame '{payload['nome']}' cadastrado em MAIÚSCULO!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar exame: {e}")


render_cadastro_exames = render_tipos_exames
render_exames = render_tipos_exames
