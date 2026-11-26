from datetime import date, datetime
import re
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

CHAVE_MSG_COLABORADOR = "msg_feedback_colaborador"


@st.cache_data(ttl=15, show_spinner=False)
def _buscar_tabela(nome_tabela: str) -> list[dict]:
    supabase = get_supabase()
    try:
        res = supabase.table(nome_tabela).select("*").execute()
        return res.data or []
    except Exception:
        return []


def _limpar_cache_colaboradores() -> None:
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


def _extrair_coluna_pgrst204(msg: str) -> str | None:
    match = re.search(r"Could not find the '([^']+)' column", msg)
    if match:
        return match.group(1).strip()
    match_alt = re.search(r"column ['\"]([^'\"]+)['\"]", msg)
    if match_alt:
        return match_alt.group(1).strip()
    return None


def _salvar_colaborador_com_fallback(supabase, payload: dict, colab_id: str | None = None):
    dados = dict(payload)
    obrigatorias = {"matricula", "nome_completo", "nome"}
    
    for _ in range(15):
        try:
            if colab_id:
                return supabase.table("colaboradores").update(dados).eq("id", colab_id).execute()
            else:
                return supabase.table("colaboradores").insert(dados).execute()
        except Exception as e:
            msg = str(e)
            col_invalida = _extrair_coluna_pgrst204(msg)
            if col_invalida and col_invalida in dados and col_invalida not in obrigatorias:
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


def render_formulario_colaborador(supabase, colab_editar: dict | None = None, cargos: list[dict] = []):
    modo_edicao = colab_editar is not None
    colab_id = str(colab_editar.get("id") or "").strip() if modo_edicao else None

    opcoes_cargos = []
    for c in cargos:
        cid = str(c.get("id") or "").strip()
        nome_c = str(c.get("nome") or c.get("nome_cargo") or c.get("cargo") or "—").strip().upper()
        cbo_c = str(c.get("cbo") or "—").strip()
        opcoes_cargos.append((cid, f"{nome_c} (CBO {cbo_c})", cbo_c, nome_c))

    idx_cargo_padrao = 0
    if modo_edicao:
        cid_atual = str(colab_editar.get("cargo_id") or colab_editar.get("funcao_id") or "").strip()
        nome_atual = _normalizar(colab_editar.get("cargo") or colab_editar.get("funcao"))
        for i, (cid, label, cbo_c, nome_c) in enumerate(opcoes_cargos):
            if cid == cid_atual or _normalizar(nome_c) == nome_atual:
                idx_cargo_padrao = i
                break

    st.subheader("📝 Ficha Completa de Cadastro do Colaborador" if not modo_edicao else f"✏️ Editando Colaborador: {colab_editar.get('nome_completo') or colab_editar.get('nome')}")

    if opcoes_cargos:
        cargo_sel_id = st.selectbox(
            "Selecione o Cargo Cadastrado",
            options=[o[0] for o in opcoes_cargos],
            index=idx_cargo_padrao,
            format_func=lambda cid: dict([(o[0], o[1]) for o in opcoes_cargos]).get(cid, cid),
            key=f"sel_cargo_colab_{colab_id or 'novo'}",
        )
        cbo_auto = dict([(o[0], o[2]) for o in opcoes_cargos]).get(cargo_sel_id, "—")
        nome_cargo_auto = dict([(o[0], o[3]) for o in opcoes_cargos]).get(cargo_sel_id, "—")
    else:
        cargo_sel_id = None
        cbo_auto = "—"
        nome_cargo_auto = "—"
        st.info("Nenhum cargo pré-cadastrado no sistema. Você pode cadastrar um cargo na aba 'Cadastro de Cargos'.")

    val_mat = str(colab_editar.get("matricula") or "") if modo_edicao else ""
    val_cpf = str(colab_editar.get("cpf") or "") if modo_edicao else ""
    val_dt_nasc = _parse_data(colab_editar.get("data_nascimento") or colab_editar.get("data_nasc")) if modo_edicao else date(1990, 1, 1)
    val_nome = str(colab_editar.get("nome_completo") or colab_editar.get("nome") or "") if modo_edicao else ""
    val_rg = str(colab_editar.get("rg") or "") if modo_edicao else ""
    val_genero = str(colab_editar.get("genero") or "MASCULINO").upper() if modo_edicao else "MASCULINO"
    
    val_num_reg = str(colab_editar.get("numero_registro") or colab_editar.get("num_registro") or colab_editar.get("registro") or "") if modo_edicao else ""
    val_dt_adm = _parse_data(colab_editar.get("data_admissao") or colab_editar.get("admissao")) if modo_edicao else date.today()
    val_setor = str(colab_editar.get("setor") or colab_editar.get("centro_custo") or "OPERAÇÃO").upper() if modo_edicao else "OPERAÇÃO"
    val_contrato = str(colab_editar.get("tipo_contrato") or colab_editar.get("contrato") or "CLT").upper() if modo_edicao else "CLT"
    val_status = str(colab_editar.get("status") or "ATIVO").upper() if modo_edicao else "ATIVO"
    val_gestor = str(colab_editar.get("gestor_direto") or colab_editar.get("gestor") or "") if modo_edicao else ""
    
    val_email = str(colab_editar.get("email") or colab_editar.get("e_mail") or "") if modo_edicao else ""
    val_tel = str(colab_editar.get("telefone") or colab_editar.get("celular") or "") if modo_edicao else ""

    with st.form(f"form_colaborador_{colab_id or 'novo'}"):
        st.markdown("##### 📄 Dados Pessoais e Identificação")
        cp1, cp2, cp3 = st.columns(3)
        with cp1:
            matricula = st.text_input("Matrícula *", value=val_mat, placeholder="Ex: 123")
        with cp2:
            cpf = st.text_input("CPF * (somente números)", value=val_cpf, placeholder="Ex: 00000000000")
        with cp3:
            dt_nasc = st.date_input("Data de Nascimento", value=val_dt_nasc or date(1990, 1, 1), format="DD/MM/YYYY")

        cp4, cp5, cp6 = st.columns(3)
        with cp4:
            nome_completo = st.text_input("Nome Completo *", value=val_nome, placeholder="Ex: DANILO SOUSA")
        with cp5:
            rg = st.text_input("RG", value=val_rg, placeholder="Ex: 000000000")
        with cp6:
            generos = ["MASCULINO", "FEMININO", "OUTRO", "NÃO INFORMADO"]
            genero = st.selectbox("Gênero", options=generos, index=generos.index(val_genero) if val_genero in generos else 0)

        st.markdown("---")
        st.markdown("##### 🏢 Dados Profissionais e Alocação")
        
        cd1, cd2, cd3 = st.columns(3)
        with cd1:
            st.text_input("Cargo Selecionado *", value=nome_cargo_auto, disabled=True)
        with cd2:
            st.text_input("CBO", value=cbo_auto, disabled=True)
        with cd3:
            dt_admissao = st.date_input("Data de Admissão", value=val_dt_adm or date.today(), format="DD/MM/YYYY")

        cd4, cd5, cd6 = st.columns(3)
        with cd4:
            numero_registro = st.text_input("Nº do Registro", value=val_num_reg, placeholder="Ex: REG-998877")
        with cd5:
            setor = st.text_input("Setor / Centro de Custo", value=val_setor, placeholder="Ex: OPERAÇÃO")
        with cd6:
            contratos = ["CLT", "PJ", "ESTÁGIO", "TEMPORÁRIO", "TERCEIRIZADO"]
            tipo_contrato = st.selectbox("Tipo de Contrato", options=contratos, index=contratos.index(val_contrato) if val_contrato in contratos else 0)

        cd7, cd8 = st.columns(2)
        with cd7:
            statuses = ["ATIVO", "INATIVO", "AFASTADO", "DESLIGADO"]
            status_colab = st.selectbox("Status Inicial", options=statuses, index=statuses.index(val_status) if val_status in statuses else 0)
        with cd8:
            gestor_direto = st.text_input("Gestor Direto / Superior Imediato", value=val_gestor, placeholder="Ex: CARLOS ALBERTO")

        st.markdown("---")
        st.markdown("##### 📞 Contato e Comunicação")
        cc1, cc2 = st.columns(2)
        with cc1:
            email = st.text_input("E-mail", value=val_email, placeholder="colaborador@globexmultimodal.com.br")
        with cc2:
            telefone = st.text_input("Telefone / WhatsApp", value=val_tel, placeholder="(19) 99999-9999")

        btn_rotulo = "💾 Salvar Alterações" if modo_edicao else "💾 Cadastrar Colaborador"
        if st.form_submit_button(btn_rotulo):
            mat_limpa = matricula.strip().upper()
            nome_limpo = nome_completo.strip().upper()

            if not mat_limpa or not nome_limpo:
                st.warning("Preencha os campos obrigatórios: Matrícula e Nome Completo.")
            else:
                try:
                    payload = {
                        "matricula": mat_limpa,
                        "cpf": cpf.strip(),
                        "data_nascimento": str(dt_nasc),
                        "data_nasc": str(dt_nasc),
                        "nome_completo": nome_limpo,
                        "nome": nome_limpo,
                        "rg": rg.strip().upper(),
                        "genero": genero.strip().upper(),
                        "cargo_id": cargo_sel_id,
                        "funcao_id": cargo_sel_id,
                        "cargo": nome_cargo_auto.upper(),
                        "funcao": nome_cargo_auto.upper(),
                        "cbo": cbo_auto.upper(),
                        "data_admissao": str(dt_admissao),
                        "admissao": str(dt_admissao),
                        "numero_registro": numero_registro.strip().upper(),
                        "num_registro": numero_registro.strip().upper(),
                        "registro": numero_registro.strip().upper(),
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
                        "texto": f"Colaborador '{nome_limpo}' {'atualizado' if modo_edicao else 'cadastrado'} com sucesso!",
                    }
                    if f"editar_colab_{colab_id}" in st.session_state:
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

    cargos = _buscar_tabela("cargos")
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
            mapa_cargos = {str(c.get("id") or "").strip(): c for c in cargos if c.get("id") is not None}
            
            for colab in colaboradores:
                cid = str(colab.get("id") or "").strip()
                mat_str = str(colab.get("matricula") or "—").strip()
                nome_str = str(colab.get("nome_completo") or colab.get("nome") or "—").strip().upper()
                cpf_str = str(colab.get("cpf") or "—").strip()
                rg_str = str(colab.get("rg") or "—").strip()
                dt_nasc_str = _formatar_data_br(colab.get("data_nascimento") or colab.get("data_nasc"))
                
                cargo_id = str(colab.get("cargo_id") or colab.get("funcao_id") or "").strip()
                cargo_info = mapa_cargos.get(cargo_id, {})
                cargo_str = str(
                    cargo_info.get("nome")
                    or colab.get("cargo")
                    or colab.get("funcao")
                    or "—"
                ).strip().upper()
                cbo_str = str(cargo_info.get("cbo") or colab.get("cbo") or "—").strip()
                
                setor_str = str(colab.get("setor") or colab.get("centro_custo") or "—").strip().upper()
                num_reg_str = str(colab.get("numero_registro") or colab.get("num_registro") or colab.get("registro") or "—").strip().upper()
                contrato_str = str(colab.get("tipo_contrato") or colab.get("contrato") or "—").strip().upper()
                email_str = str(colab.get("email") or colab.get("e_mail") or "—").strip().upper()
                tel_str = str(colab.get("telefone") or colab.get("celular") or "—").strip().upper()
                adm_str = _formatar_data_br(colab.get("data_admissao") or colab.get("admissao"))
                status_str = str(colab.get("status") or "ATIVO").strip().upper()

                with st.container(border=True):
                    c_cols = st.columns([0.8, 2.2, 1.2, 1.2, 1.6, 1.2, 1.2, 1.0, 1.0])
                    c_cols[0].markdown(f"**Matrícula:**  \n{mat_str}")
                    c_cols[1].markdown(f"**Nome:**  \n{nome_str}")
                    c_cols[2].markdown(f"**CPF:**  \n{cpf_str}")
                    c_cols[3].markdown(f"**Nº Reg.:**  \n{num_reg_str}")
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
