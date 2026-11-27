from datetime import date, datetime
import re
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

CHAVE_MSG_COLABORADOR = "msg_feedback_colaborador"
DATA_MINIMA_PERMITIDA = date(1930, 1, 1)
DATA_MAXIMA_PERMITIDA = date(2099, 12, 31)


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def _buscar_funcoes_cadastradas() -> list[dict]:
    supabase = get_supabase()
    try:
        res = (
            supabase.table("funcoes")
            .select("id, nome_funcao, cbo, setor_padrao, ativo")
            .order("nome_funcao")
            .execute()
        )
        return res.data or []
    except Exception:
        return _buscar_tabela("funcoes")


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


def _nome_funcao_item(f: dict) -> str:
    v = str(f.get("nome_funcao") or "").strip()
    return " ".join(v.upper().split()) if v else ""


def _cbo_funcao_item(f: dict) -> str:
    v = " ".join(str(f.get("cbo") or "").strip().upper().split())
    if v and v not in ("—", "-", "NONE", "NULL", "N/A"):
        return v
    return ""


def render_formulario_colaborador(supabase, colab_editar: dict | None = None, funcoes: list[dict] = []):
    modo_edicao = colab_editar is not None
    colab_id = str(colab_editar.get("id") or "").strip() if modo_edicao else None
    sufixo_key = colab_id or "novo"
    hoje_dt = date.today()

    funcoes_ativas = [
        f for f in funcoes
        if f.get("ativo", True) is not False and _nome_funcao_item(f)
    ] or [f for f in funcoes if _nome_funcao_item(f)]

    opcoes_funcoes = [
        (
            str(f.get("id") or idx).strip(),
            _nome_funcao_item(f),
            _cbo_funcao_item(f),
        )
        for idx, f in enumerate(funcoes_ativas)
    ]

    idx_funcao_padrao = 0
    if modo_edicao and opcoes_funcoes:
        fid_atual = str(
            colab_editar.get("funcao_id")
            or colab_editar.get("cargo_id")
            or ""
        ).strip()
        nome_atual = _normalizar(colab_editar.get("cargo") or colab_editar.get("funcao"))
        for i, (fid, nome_f, _) in enumerate(opcoes_funcoes):
            if (fid and fid == fid_atual) or (nome_atual and _normalizar(nome_f) == nome_atual):
                idx_funcao_padrao = i
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

    with st.container(border=True):
        st.markdown("##### 📄 Dados Pessoais e Identificação")
        cp1, cp2, cp3 = st.columns(3)
        with cp1:
            matricula = st.text_input(
                "Matrícula *",
                value=val_mat,
                placeholder="EX: 123",
                key=f"mat_{sufixo_key}",
            )
        with cp2:
            cpf = st.text_input(
                "CPF * (somente números)",
                value=val_cpf,
                placeholder="EX: 00000000000",
                key=f"cpf_{sufixo_key}",
            )
        with cp3:
            dt_nasc = st.date_input(
                "Data de Nascimento",
                value=val_dt_nasc,
                min_value=DATA_MINIMA_PERMITIDA,
                max_value=DATA_MAXIMA_PERMITIDA,
                format="DD/MM/YYYY",
                key=f"dt_nasc_{sufixo_key}",
            )

        cp4, cp5, cp6 = st.columns(3)
        with cp4:
            nome_completo = st.text_input(
                "Nome Completo *",
                value=val_nome,
                placeholder="EX: DANILO SOUSA",
                key=f"nome_{sufixo_key}",
            )
        with cp5:
            rg = st.text_input(
                "RG",
                value=val_rg,
                placeholder="EX: 000000000",
                key=f"rg_{sufixo_key}",
            )
        with cp6:
            generos = ["MASCULINO", "FEMININO", "OUTRO", "NÃO INFORMADO"]
            genero = st.selectbox(
                "Gênero",
                options=generos,
                index=generos.index(val_genero) if val_genero in generos else 0,
                key=f"genero_{sufixo_key}",
            )

        st.markdown("---")
        st.markdown("##### 🏢 Dados Profissionais e Alocação")

        cd1, cd2, cd3 = st.columns(3)
        with cd1:
            if opcoes_funcoes:
                funcao_sel_id = st.selectbox(
                    "Cargo / Função *",
                    options=[o[0] for o in opcoes_funcoes],
                    index=idx_funcao_padrao,
                    format_func=lambda fid: next(
                        (f"{o[1]} (CBO {o[2]})" if o[2] else o[1] for o in opcoes_funcoes if o[0] == fid),
                        fid,
                    ),
                    key=f"sel_funcao_{sufixo_key}",
                )
                sel_funcao = next((o for o in opcoes_funcoes if o[0] == funcao_sel_id), ("", "", ""))
                nome_funcao_sel = sel_funcao[1]
                cbo_da_funcao = sel_funcao[2]
            else:
                funcao_sel_id = None
                nome_funcao_sel = st.text_input(
                    "Cargo / Função *",
                    value=(
                        str(colab_editar.get("cargo") or colab_editar.get("funcao") or "").strip().upper()
                        if modo_edicao
                        else ""
                    ),
                    placeholder="EX: ASSISTENTE",
                    key=f"cargo_txt_{sufixo_key}",
                )
                cbo_da_funcao = ""

        chave_cbo_controle = f"_cbo_sync_{sufixo_key}"
        chave_ultimo_cargo = f"_cbo_last_cargo_{sufixo_key}"
        if st.session_state.get(chave_ultimo_cargo) != funcao_sel_id:
            st.session_state[chave_ultimo_cargo] = funcao_sel_id
            st.session_state[chave_cbo_controle] = (
                cbo_da_funcao or (_cbo_funcao_item(colab_editar) if modo_edicao else "")
            )

        with cd2:
            cbo_livre = st.text_input(
                "CBO (opcional)",
                value=st.session_state.get(chave_cbo_controle, ""),
                placeholder="EX: 7822-20",
                key=f"cbo_input_{sufixo_key}_{funcao_sel_id or 'livre'}",
            )
            st.session_state[chave_cbo_controle] = cbo_livre

        with cd3:
            dt_admissao = st.date_input(
                "Data de Admissão",
                value=val_dt_adm,
                min_value=DATA_MINIMA_PERMITIDA,
                max_value=DATA_MAXIMA_PERMITIDA,
                format="DD/MM/YYYY",
                key=f"dt_adm_{sufixo_key}",
            )

        cd4, cd5, cd6 = st.columns(3)
        with cd4:
            num_matricula_aloc = st.text_input(
                "Nº da Matrícula",
                value=val_num_mat_aloc,
                placeholder="EX: MAT-998877",
                key=f"num_mat_{sufixo_key}",
            )
        with cd5:
            setor = st.text_input(
                "Setor / Centro de Custo",
                value=val_setor,
                placeholder="EX: OPERAÇÃO",
                key=f"setor_{sufixo_key}",
            )
        with cd6:
            contratos = ["CLT", "PJ", "ESTÁGIO", "TEMPORÁRIO", "TERCEIRIZADO"]
            tipo_contrato = st.selectbox(
                "Tipo de Contrato",
                options=contratos,
                index=contratos.index(val_contrato) if val_contrato in contratos else 0,
                key=f"contrato_{sufixo_key}",
            )

        cd7, cd8 = st.columns(2)
        with cd7:
            statuses = ["ATIVO", "INATIVO", "AFASTADO", "DESLIGADO"]
            status_colab = st.selectbox(
                "Status Inicial",
                options=statuses,
                index=statuses.index(val_status) if val_status in statuses else 0,
                key=f"status_{sufixo_key}",
            )
        with cd8:
            gestor_direto = st.text_input(
                "Gestor Direto / Superior Imediato",
                value=val_gestor,
                placeholder="EX: CARLOS ALBERTO",
                key=f"gestor_{sufixo_key}",
            )

        st.markdown("---")
        st.markdown("##### 📞 Contato e Comunicação")
        cc1, cc2 = st.columns(2)
        with cc1:
            email = st.text_input(
                "E-mail",
                value=val_email,
                placeholder="COLABORADOR@GLOBEXMULTIMODAL.COM.BR",
                key=f"email_{sufixo_key}",
            )
        with cc2:
            telefone = st.text_input(
                "Telefone / WhatsApp",
                value=val_tel,
                placeholder="(19) 99999-9999",
                key=f"tel_{sufixo_key}",
            )

        btn_rotulo = "💾 Salvar Alterações" if modo_edicao else "💾 Cadastrar Colaborador"
        if st.button(btn_rotulo, key=f"btn_salvar_colab_{sufixo_key}", type="primary"):
            mat_aloc_limpa = num_matricula_aloc.strip().upper()
            mat_limpa = (matricula.strip() or mat_aloc_limpa).upper()
            nome_limpo = " ".join(nome_completo.strip().upper().split())
            funcao_limpa = " ".join(str(nome_funcao_sel or "").strip().upper().split())
            cbo_limpo = _cbo_funcao_item({"cbo": cbo_livre})

            if not mat_limpa or not nome_limpo:
                st.warning("Preencha os campos obrigatórios: Matrícula e Nome Completo.")
            elif not funcao_limpa:
                st.warning("Selecione um Cargo / Função válido.")
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
                        "funcao_id": funcao_sel_id,
                        "cargo_id": funcao_sel_id,
                        "funcao": funcao_limpa,
                        "cargo": funcao_limpa,
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

    funcoes = _buscar_funcoes_cadastradas()
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
            mapa_funcoes = {
                str(f.get("id") or idx).strip(): f
                for idx, f in enumerate(funcoes)
            }

            for colab in colaboradores:
                cid = str(colab.get("id") or "").strip()
                mat_str = str(colab.get("matricula") or "—").strip().upper()
                nome_str = str(colab.get("nome_completo") or colab.get("nome") or "—").strip().upper()
                cpf_str = str(colab.get("cpf") or "—").strip().upper()

                funcao_id = str(colab.get("funcao_id") or colab.get("cargo_id") or "").strip()
                funcao_info = mapa_funcoes.get(funcao_id, {})
                funcao_str = str(
                    _nome_funcao_item(funcao_info)
                    if funcao_info
                    else (colab.get("cargo") or colab.get("funcao") or "—")
                ).strip().upper()
                cbo_str = _cbo_funcao_item(colab) or _cbo_funcao_item(funcao_info) or "—"

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
                    c_cols[4].markdown(f"**Cargo / Função:**  \n{funcao_str}")
                    c_cols[5].markdown(f"**CBO:**  \n{cbo_str}")
                    c_cols[6].markdown(f"**Setor:**  \n{setor_str}")
                    c_cols[7].markdown(f"**Status:**  \n{status_str}")

                    chave_edicao = f"editar_colab_{cid}"
                    if c_cols[8].button("✏️ Editar", key=f"btn_{chave_edicao}", use_container_width=True):
                        st.session_state[chave_edicao] = not st.session_state.get(chave_edicao, False)

                    if st.session_state.get(chave_edicao, False):
                        with st.container(border=True):
                            render_formulario_colaborador(supabase, colab_editar=colab, funcoes=funcoes)
        else:
            st.info("Nenhum colaborador cadastrado.")

    with tab2:
        render_formulario_colaborador(supabase, colab_editar=None, funcoes=funcoes)


render_colaboradores = render_colaboradores
