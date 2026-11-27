from datetime import date, datetime
import re
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

CHAVE_MSG_COLABORADOR = "msg_feedback_colaborador"
DATA_MINIMA_PERMITIDA = date(1930, 1, 1)
DATA_MAXIMA_PERMITIDA = date(2099, 12, 31)

TABELAS_CARGOS_CANDIDATAS = [
    "cargos",
    "funcoes",
    "funcoes_cargos",
    "cadastro_cargos",
    "cadastro_funcoes",
    "cargo_funcao",
    "cargos_funcoes",
    "roles",
]


@st.cache_data(ttl=10, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


def _buscar_cargos_e_origem() -> tuple[list[dict], str]:
    for tabela in TABELAS_CARGOS_CANDIDATAS:
        dados = _buscar_tabela(tabela)
        if dados:
            return dados, tabela
    return [], ""


def _limpar_cache_colaboradores() -> None:
    st.cache_data.clear()


def _normalizar(valor) -> str:
    return " ".join(str(valor or "").strip().lower().split())


def _para_maiusculo(valor):
    if isinstance(valor, str):
        return " ".join(valor.strip().upper().split())
    if isinstance(valor, list):
        return [_para_maiusculo(item) for item in valor]
    if isinstance(valor, dict):
        return {k: _para_maiusculo(v) for k, v in valor.items()}
    return valor


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


def _garantir_data_valida(dt: date | None, padrao: date) -> date:
    base = dt or padrao
    if base < DATA_MINIMA_PERMITIDA:
        return DATA_MINIMA_PERMITIDA
    if base > DATA_MAXIMA_PERMITIDA:
        return DATA_MAXIMA_PERMITIDA
    return base


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


def _salvar_colaborador_com_fallback(supabase, payload: dict, colab_id: str | None = None):
    dados = _para_maiusculo(dict(payload))
    protegidas = {"matricula", "nome_completo"}

    for _ in range(25):
        try:
            if colab_id:
                return supabase.table("colaboradores").update(dados).eq("id", colab_id).execute()
            return supabase.table("colaboradores").insert(dados).execute()
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida not in protegidas:
                dados.pop(col_invalida)
                continue
            raise

    if colab_id:
        return supabase.table("colaboradores").update(dados).eq("id", colab_id).execute()
    return supabase.table("colaboradores").insert(dados).execute()


def _exibir_mensagem_pendente() -> None:
    msg_info = st.session_state.pop(CHAVE_MSG_COLABORADOR, None)
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


def _nome_cargo_item(c: dict) -> str:
    for k in (
        "nome",
        "nome_cargo",
        "nome_funcao",
        "cargo",
        "funcao",
        "titulo",
        "descricao",
    ):
        v = str(c.get(k) or "").strip()
        if v:
            return " ".join(v.upper().split())
    return ""


def render_formulario_colaborador(supabase, colab_editar: dict | None = None, cargos: list[dict] = []):
    modo_edicao = colab_editar is not None
    colab_id = str(colab_editar.get("id") or "").strip() if modo_edicao else None
    hoje_dt = date.today()

    opcoes_cargos = []
    for idx, c in enumerate(cargos):
        cid = str(c.get("id") or c.get("uuid") or c.get("codigo") or idx).strip()
        nome_c = _nome_cargo_item(c)
        cbo_c = str(c.get("cbo") or c.get("codigo_cbo") or "").strip().upper()
        if nome_c:
            opcoes_cargos.append((cid, nome_c, cbo_c))

    idx_cargo_padrao = 0
    if modo_edicao and opcoes_cargos:
        cid_atual = str(
            colab_editar.get("cargo_id")
            or colab_editar.get("funcao_id")
            or ""
        ).strip()
        nome_atual = _normalizar(colab_editar.get("cargo") or colab_editar.get("funcao"))
        for i, (cid, nome_c, _) in enumerate(opcoes_cargos):
            if (cid and cid == cid_atual) or (nome_atual and _normalizar(nome_c) == nome_atual):
                idx_cargo_padrao = i
                break

    titulo_form = (
        f"EDITANDO COLABORADOR: {str(colab_editar.get('nome_completo') or colab_editar.get('nome') or '').strip().upper()}"
        if modo_edicao
        else "FICHA COMPLETA DE CADASTRO DO COLABORADOR"
    )
    st.subheader(titulo_form)

    val_mat = str(colab_editar.get("matricula") or "").strip().upper() if modo_edicao else ""
    val_cpf = str(colab_editar.get("cpf") or "").strip().upper() if modo_edicao else ""
    val_dt_nasc = _garantir_data_valida(
        _parse_data(colab_editar.get("data_nascimento") or colab_editar.get("data_nasc")) if modo_edicao else None,
        date(1990, 1, 1),
    )
    val_nome = (
        str(colab_editar.get("nome_completo") or colab_editar.get("nome") or "").strip().upper()
        if modo_edicao
        else ""
    )
    val_rg = str(colab_editar.get("rg") or "").strip().upper() if modo_edicao else ""
    val_genero = (
        str(colab_editar.get("genero") or "MASCULINO").strip().upper()
        if modo_edicao
        else "MASCULINO"
    )

    val_num_mat_aloc = (
        str(
            colab_editar.get("numero_matricula")
            or colab_editar.get("matricula")
            or colab_editar.get("numero_registro")
            or colab_editar.get("num_registro")
            or colab_editar.get("registro")
            or ""
        ).strip().upper()
        if modo_edicao
        else ""
    )
    val_dt_adm = _garantir_data_valida(
        _parse_data(colab_editar.get("data_admissao") or colab_editar.get("admissao")) if modo_edicao else None,
        hoje_dt,
    )
    val_setor = (
        str(colab_editar.get("setor") or colab_editar.get("centro_custo") or "OPERAÇÃO").strip().upper()
        if modo_edicao
        else "OPERAÇÃO"
    )
    val_contrato = (
        str(colab_editar.get("tipo_contrato") or colab_editar.get("contrato") or "CLT").strip().upper()
        if modo_edicao
        else "CLT"
    )
    val_status = (
        str(colab_editar.get("status") or "ATIVO").strip().upper()
        if modo_edicao
        else "ATIVO"
    )
    val_gestor = (
        str(colab_editar.get("gestor_direto") or colab_editar.get("gestor") or "").strip().upper()
        if modo_edicao
        else ""
    )

    val_email = (
        str(colab_editar.get("email") or colab_editar.get("e_mail") or "").strip().upper()
        if modo_edicao
        else ""
    )
    val_tel = (
        str(colab_editar.get("telefone") or colab_editar.get("celular") or "").strip().upper()
        if modo_edicao
        else ""
    )
    val_cargo_colab = (
        str(colab_editar.get("cargo") or colab_editar.get("funcao") or "").strip().upper()
        if modo_edicao
        else ""
    )
    val_cbo_colab = (
        str(colab_editar.get("cbo") or "").strip().upper()
        if modo_edicao
        else ""
    )

    with st.form(f"form_colaborador_{colab_id or 'novo'}"):
        st.markdown("##### 📄 Dados Pessoais e Identificação")
        cp1, cp2, cp3 = st.columns(3)
        with cp1:
            matricula = st.text_input("Matrícula *", value=val_mat, placeholder="EX: 123")
        with cp2:
            cpf = st.text_input("CPF * (somente números)", value=val_cpf, placeholder="EX: 00000000000")
        with cp3:
            dt_nasc = st.date_input(
                "Data de Nascimento",
                value=val_dt_nasc,
                min_value=DATA_MINIMA_PERMITIDA,
                max_value=DATA_MAXIMA_PERMITIDA,
                format="DD/MM/YYYY",
            )

        cp4, cp5, cp6 = st.columns(3)
        with cp4:
            nome_completo = st.text_input("Nome Completo *", value=val_nome, placeholder="EX: DANILO SOUSA")
        with cp5:
            rg = st.text_input("RG", value=val_rg, placeholder="EX: 000000000")
        with cp6:
            generos = ["MASCULINO", "FEMININO", "OUTRO", "NÃO INFORMADO"]
            genero = st.selectbox(
                "Gênero",
                options=generos,
                index=generos.index(val_genero) if val_genero in generos else 0,
            )

        st.markdown("---")
        st.markdown("##### 🏢 Dados Profissionais e Alocação")

        cd1, cd2, cd3 = st.columns(3)
        with cd1:
            if opcoes_cargos:
                cargo_sel_id = st.selectbox(
                    "Cargo / Função *",
                    options=[o[0] for o in opcoes_cargos],
                    index=idx_cargo_padrao,
                    format_func=lambda cid: next(
                        (f"{o[1]} (CBO {o[2]})" if o[2] else o[1] for o in opcoes_cargos if o[0] == cid),
                        cid,
                    ),
                )
                sel_tuple = next((o for o in opcoes_cargos if o[0] == cargo_sel_id), ("", "", ""))
                nome_cargo_final = sel_tuple[1]
                cbo_padrao_cargo = sel_tuple[2]
            else:
                cargo_sel_id = None
                nome_cargo_final = st.text_input(
                    "Cargo / Função *",
                    value=val_cargo_colab,
                    placeholder="EX: CONFERENTE, OPERADOR DE EMPILHADEIRA",
                )
                cbo_padrao_cargo = ""
        with cd2:
            cbo_livre = st.text_input(
                "CBO (opcional)",
                value=val_cbo_colab or cbo_padrao_cargo,
                placeholder="EX: 414105",
            )
        with cd3:
            dt_admissao = st.date_input(
                "Data de Admissão",
                value=val_dt_adm,
                min_value=DATA_MINIMA_PERMITIDA,
                max_value=DATA_MAXIMA_PERMITIDA,
                format="DD/MM/YYYY",
            )

        cd4, cd5, cd6 = st.columns(3)
        with cd4:
            num_matricula_aloc = st.text_input(
                "Nº da Matrícula", value=val_num_mat_aloc, placeholder="EX: MAT-998877"
            )
        with cd5:
            setor = st.text_input("Setor / Centro de Custo", value=val_setor, placeholder="EX: OPERAÇÃO")
        with cd6:
            contratos = ["CLT", "PJ", "ESTÁGIO", "TEMPORÁRIO", "TERCEIRIZADO"]
            tipo_contrato = st.selectbox(
                "Tipo de Contrato",
                options=contratos,
                index=contratos.index(val_contrato) if val_contrato in contratos else 0,
            )

        cd7, cd8 = st.columns(2)
        with cd7:
            statuses = ["ATIVO", "INATIVO", "AFASTADO", "DESLIGADO"]
            status_colab = st.selectbox(
                "Status Inicial",
                options=statuses,
                index=statuses.index(val_status) if val_status in statuses else 0,
            )
        with cd8:
            gestor_direto = st.text_input(
                "Gestor Direto / Superior Imediato",
                value=val_gestor,
                placeholder="EX: CARLOS ALBERTO",
            )

        st.markdown("---")
        st.markdown("##### 📞 Contato e Comunicação")
        cc1, cc2 = st.columns(2)
        with cc1:
            email = st.text_input("E-mail", value=val_email, placeholder="COLABORADOR@GLOBEXMULTIMODAL.COM.BR")
        with cc2:
            telefone = st.text_input("Telefone / WhatsApp", value=val_tel, placeholder="(19) 99999-9999")

        btn_rotulo = "💾 Salvar Alterações" if modo_edicao else "💾 Cadastrar Colaborador"
        if st.form_submit_button(btn_rotulo):
            mat_aloc_limpa = num_matricula_aloc.strip().upper()
            mat_limpa = (matricula.strip() or mat_aloc_limpa).upper()
            nome_limpo = " ".join(nome_completo.strip().upper().split())
            cargo_limpo = " ".join(str(nome_cargo_final or "").strip().upper().split())
            cbo_limpo = " ".join(cbo_livre.strip().upper().split())

            if not mat_limpa or not nome_limpo:
                st.warning("Preencha os campos obrigatórios: Matrícula e Nome Completo.")
            elif not cargo_limpo:
                st.warning("Selecione ou informe o Cargo / Função do colaborador.")
            else:
                try:
                    mat_final = mat_aloc_limpa or mat_limpa
                    payload = {
                        "matricula": mat_final,
                        "numero_matricula": mat_aloc_limpa or mat_final,
                        "cpf": cpf.strip().upper(),
                        "data_nascimento": str(dt_nasc),
                        "data_nasc": str(dt_nasc),
                        "nome_completo": nome_limpo,
                        "nome": nome_limpo,
                        "rg": rg.strip().upper(),
                        "genero": genero.strip().upper(),
                        "cargo_id": cargo_sel_id,
                        "funcao_id": cargo_sel_id,
                        "cargo": cargo_limpo,
                        "funcao": cargo_limpo,
                        "cbo": cbo_limpo,
                        "data_admissao": str(dt_admissao),
                        "admissao": str(dt_admissao),
                        "setor": setor.strip().upper(),
                        "centro_custo": setor.strip().upper(),
                        "tipo_contrato": tipo_contrato.strip().upper(),
                        "contrato": tipo_contrato.strip().upper(),
                        "status": status_colab.strip().upper(),
                        "gestor_direto": gestor_direto.strip().upper(),
                        "gestor": gestor_direto.strip().upper(),
                        "email": email.strip().upper(),
                        "e_mail": email.strip().upper(),
                        "telefone": telefone.strip().upper(),
                        "celular": telefone.strip().upper(),
                    }

                    _salvar_colaborador_com_fallback(supabase, payload, colab_id=colab_id)
                    st.session_state[CHAVE_MSG_COLABORADOR] = {
                        "tipo": "success",
                        "texto": f"COLABORADOR '{nome_limpo}' {'ATUALIZADO' if modo_edicao else 'CADASTRADO'} COM SUCESSO!",
                    }
                    if colab_id and f"editar_colab_{colab_id}" in st.session_state:
                        st.session_state[f"editar_colab_{colab_id}"] = False
                    _limpar_cache_colaboradores()
                    st.rerun()
                except Exception as err:
                    st.error(f"Erro ao salvar colaborador no Supabase: {err}")


def render_colaboradores() -> None:
    render_cabecalho_modulo("👥 Cadastro de Colaborador")
    _exibir_mensagem_pendente()

    try:
        supabase = get_supabase()
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return

    cargos, _ = _buscar_cargos_e_origem()
    colaboradores = _buscar_tabela("colaboradores")

    tab1, tab2 = st.tabs([
        "📋 Listar / Gerenciar Colaboradores",
        "➕ Cadastrar Novo Colaborador",
    ])

    with tab1:
        col_t, col_b = st.columns([4, 1])
        with col_t:
            st.subheader("Colaboradores Cadastrados")
        with col_b:
            if st.button("🔄 Atualizar lista", key="btn_atualizar_colabs", use_container_width=True):
                _limpar_cache_colaboradores()
                st.rerun()

        if colaboradores:
            mapa_cargos = {
                str(c.get("id") or c.get("uuid") or c.get("codigo") or idx).strip(): c
                for idx, c in enumerate(cargos)
            }

            for colab in colaboradores:
                cid = str(colab.get("id") or "").strip()
                mat_str = str(colab.get("matricula") or "—").strip().upper()
                nome_str = str(colab.get("nome_completo") or colab.get("nome") or "—").strip().upper()
                cpf_str = str(colab.get("cpf") or "—").strip().upper()

                cargo_id = str(colab.get("cargo_id") or colab.get("funcao_id") or "").strip()
                cargo_info = mapa_cargos.get(cargo_id, {})
                cargo_str = str(
                    _nome_cargo_item(cargo_info)
                    if cargo_info
                    else (colab.get("cargo") or colab.get("funcao") or "—")
                ).strip().upper()
                cbo_str = str(colab.get("cbo") or cargo_info.get("cbo") or "—").strip().upper()

                setor_str = str(colab.get("setor") or colab.get("centro_custo") or "—").strip().upper()
                num_mat_str = str(
                    colab.get("numero_matricula")
                    or colab.get("matricula")
                    or "—"
                ).strip().upper()
                status_str = str(colab.get("status") or "ATIVO").strip().upper()

                with st.container(border=True):
                    c_cols = st.columns([0.8, 2.2, 1.2, 1.2, 1.6, 1.2, 1.2, 1.0, 1.0])
                    c_cols[0].markdown(f"**Matrícula:**  \n{mat_str}")
                    c_cols[1].markdown(f"**Nome:**  \n{nome_str}")
                    c_cols[2].markdown(f"**CPF:**  \n{cpf_str}")
                    c_cols[3].markdown(f"**Nº Matrícula:**  \n{num_mat_str}")
                    c_cols[4].markdown(f"**Cargo / Função:**  \n{cargo_str}")
                    c_cols[5].markdown(f"**CBO:**  \n{cbo_str}")
                    c_cols[6].markdown(f"**Setor:**  \n{setor_str}")
                    c_cols[7].markdown(f"**Status:**  \n{status_str}")

                    chave_edicao = f"editar_colab_{cid}"
                    if c_cols[8].button("✏️ Editar", key=f"btn_{chave_edicao}", use_container_width=True):
                        st.session_state[chave_edicao] = not st.session_state.get(chave_edicao, False)

                    if st.session_state.get(chave_edicao, False):
                        with st.container(border=True):
                            render_formulario_colaborador(supabase, colab_editar=colab, cargos=cargos)
        else:
            st.info("Nenhum colaborador cadastrado.")

    with tab2:
        render_formulario_colaborador(supabase, colab_editar=None, cargos=cargos)


render_colaboradores = render_colaboradores
