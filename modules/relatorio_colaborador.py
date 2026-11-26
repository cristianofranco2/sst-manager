from datetime import date, datetime, timedelta
import ast
import io
import json
import re
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from database import get_supabase
from ui_components import render_cabecalho_modulo

COLUNAS_QTD_INVENTARIO = ("quantidade_disponivel", "quantidade", "saldo", "qtd_disponivel", "qtd")


@st.cache_data(ttl=10, show_spinner=False)
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


def _para_maiusculo(valor):
    if isinstance(valor, str):
        return valor.strip().upper()
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


def _formatar_data_br(valor) -> str:
    dt = _parse_data(valor)
    return dt.strftime("%d/%m/%Y") if dt else "—"


def _obter_qtd_lote(lote: dict) -> int:
    for col in COLUNAS_QTD_INVENTARIO:
        if col in lote and lote[col] is not None:
            try:
                return int(float(lote[col]))
            except Exception:
                continue
    return 0


def _indicador_vencimento(data_venc_raw, hoje: date | None = None) -> tuple[str, str]:
    """
    Regras de alertas por bolinhas:
    - 🔴 VENCIDO: dt_venc < hoje
    - 🟠 VENCE EM ATÉ 10 DIAS: 0 <= (dt_venc - hoje).days <= 10
    - 🟡 VENCE EM ATÉ 30 DIAS: 10 < (dt_venc - hoje).days <= 30
    - 🟢 EM DIA: (dt_venc - hoje).days > 30
    """
    ref_hoje = hoje or date.today()
    dt_venc = _parse_data(data_venc_raw)
    if dt_venc is None:
        return "🔴", "VENCIDO"

    dias_restantes = (dt_venc - ref_hoje).days
    if dias_restantes < 0:
        return "🔴", f"VENCIDO ({abs(dias_restantes)} DIAS)"
    if dias_restantes <= 10:
        return "🟠", f"VENCE EM {dias_restantes} DIAS"
    if dias_restantes <= 30:
        return "🟡", f"VENCE EM {dias_restantes} DIAS"
    return "🟢", "EM DIA"


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


def _consumir_inventario_epi(supabase, inventario: list[dict], epi_id, qtd_consumir: int) -> tuple[bool, str, int | None]:
    """
    Consome qtd_consumir do saldo de inventario_epi para o epi_id informado.
    Retorna (sucesso, mensagem, lote_id_usado).
    """
    eid_alvo = str(epi_id or "").strip()
    if not eid_alvo:
        return False, "EPI SEM ID VÁLIDO NO CATÁLOGO.", None

    lotes_epi = [
        inv for inv in inventario
        if str(inv.get("epi_id") or "").strip() == eid_alvo and inv.get("id") is not None
    ]
    saldo_total = sum(max(0, _obter_qtd_lote(inv)) for inv in lotes_epi)
    if saldo_total < int(qtd_consumir):
        return (
            False,
            f"SALDO INSUFICIENTE NO INVENTÁRIO (DISPONÍVEL: {saldo_total} UN. | SOLICITADO: {int(qtd_consumir)} UN.).",
            None,
        )

    restante = int(qtd_consumir)
    lote_principal_id = None

    for inv in lotes_epi:
        if restante <= 0:
            break
        lid = inv.get("id")
        disp_atual = max(0, _obter_qtd_lote(inv))
        if disp_atual <= 0:
            continue
        baixa = min(disp_atual, restante)
        novo_saldo = disp_atual - baixa
        restante -= baixa
        if lote_principal_id is None:
            lote_principal_id = lid

        cols_presentes = [c for c in COLUNAS_QTD_INVENTARIO if c in inv]
        candidatas = cols_presentes + [c for c in COLUNAS_QTD_INVENTARIO if c not in cols_presentes]
        atualizado = False

        for col_q in candidatas:
            try:
                res = supabase.table("inventario_epi").update({col_q: int(novo_saldo)}).eq("id", lid).execute()
                if getattr(res, "data", None):
                    atualizado = True
                    break
            except Exception as e:
                if _extrair_coluna_pgrst204(str(e)) == col_q:
                    continue
                raise

        if not atualizado:
            return (
                False,
                "NÃO FOI POSSÍVEL ATUALIZAR O SALDO EM 'inventario_epi' (VERIFIQUE PERMISSÕES / RLS NO SUPABASE).",
                lote_principal_id,
            )

    return True, f"SALDO DO INVENTÁRIO ATUALIZADO (-{int(qtd_consumir)} UN.).", lote_principal_id


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
                    or item.get("nome_treinamento")
                    or item.get("titulo")
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


def _resolver_funcao_colaborador(
    colab: dict, funcoes: list[dict], cargos: list[dict]
) -> tuple[str | None, str]:
    funcao_id = str(colab.get("funcao_id") or colab.get("cargo_id") or "").strip()
    nome_direto = str(
        colab.get("funcao")
        or colab.get("funcao_nome")
        or colab.get("cargo")
        or colab.get("cargo_nome")
        or ""
    ).strip()

    origens_cargo = list(funcoes) + list(cargos)

    if funcao_id:
        for f in origens_cargo:
            if str(f.get("id") or "").strip() == funcao_id:
                nome_f = str(
                    f.get("nome")
                    or f.get("nome_funcao")
                    or f.get("nome_cargo")
                    or f.get("funcao")
                    or f.get("cargo")
                    or f.get("titulo")
                    or nome_direto
                    or "—"
                ).strip().upper()
                return funcao_id, nome_f

    if nome_direto:
        for f in origens_cargo:
            nome_f = str(
                f.get("nome")
                or f.get("nome_funcao")
                or f.get("nome_cargo")
                or f.get("funcao")
                or f.get("cargo")
                or f.get("titulo")
                or ""
            ).strip()
            if _normalizar(nome_f) == _normalizar(nome_direto):
                fid = str(f.get("id") or "").strip() or None
                return fid, nome_f.upper()
        return None, nome_direto.upper()

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
            for chave in ("funcao", "funcao_nome", "nome_funcao", "cargo", "nome_cargo", "nome"):
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
                resolvidos.append({"nome": ref.upper(), "descricao": ref.upper(), "_qtd_requisito": qtd})

    return resolvidos


def _nome_exame(reg: dict) -> str:
    for c in ("nome", "nome_exame", "tipo_exame", "titulo", "descricao"):
        v = str(reg.get(c) or "").strip()
        if v:
            return v.upper()
    return "—"


def _nome_treinamento(reg: dict) -> str:
    for c in ("nome_treinamento", "nome", "titulo", "curso", "tipo_treinamento", "descricao"):
        v = str(reg.get(c) or "").strip()
        if v:
            return v.upper()
    return "—"


def _durabilidade_dias_epi(epi: dict) -> int:
    for campo in ("durabilidade_dias", "durabilidade", "validade_dias", "dias_durabilidade"):
        val = epi.get(campo)
        if val is not None and str(val).strip() != "":
            try:
                dias = int(float(val))
                if dias > 0:
                    return dias
            except Exception:
                continue
    return 180


def _formatar_periodo_meses(val) -> str:
    if val is None or str(val).strip() == "" or str(val).strip() == "—":
        return "—"
    txt = str(val).strip().upper()
    if any(u in txt for u in ("MES", "MÊS", "DIA", "ANO")):
        return txt
    try:
        num = int(float(txt))
        return f"{num} {'MÊS' if num == 1 else 'MESES'}"
    except Exception:
        return txt


def _latin1(texto: str) -> str:
    return str(texto or "").encode("latin-1", "replace").decode("latin-1")


def _escapar_pdf(texto: str) -> str:
    limpo = _latin1(texto)
    return limpo.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _quebrar_linhas(texto: str, max_chars: int) -> list[str]:
    palavras = _latin1(texto).split()
    if not palavras:
        return [""]
    linhas: list[str] = []
    atual = palavras[0]
    for p in palavras[1:]:
        if len(atual) + 1 + len(p) <= max_chars:
            atual += " " + p
        else:
            linhas.append(atual)
            atual = p
    linhas.append(atual)
    return linhas


def _gerar_pdf_auditoria_bytes(resumo_colab: dict, linhas_historico: list[dict]) -> bytes:
    try:
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        agora = datetime.now()
    emitido_em = agora.strftime("%d/%m/%Y às %H:%M")

    page_w = 595.0
    page_h = 842.0
    margin_x = 36.0
    usable_w = page_w - 2 * margin_x

    paginas_cmds: list[list[str]] = []

    def nova_pagina() -> tuple[list[str], float]:
        cmds: list[str] = []
        cmds.append("0.07 0.22 0.45 rg")
        cmds.append(f"BT /F2 13 Tf {margin_x:.1f} {page_h - 46:.1f} Td ({_escapar_pdf('GLOBEX')}) Tj ET")
        cmds.append("0.20 0.45 0.75 rg")
        cmds.append(f"BT /F2 8 Tf {margin_x:.1f} {page_h - 57:.1f} Td ({_escapar_pdf('MULTIMODAL')}) Tj ET")

        cmds.append("0.10 0.14 0.20 rg")
        cmds.append(
            f"BT /F2 12 Tf {margin_x:.1f} {page_h - 80:.1f} Td "
            f"({_escapar_pdf('Comprovante de Trocas de EPI e Renovações de Exames / Treinamentos')}) Tj ET"
        )
        cmds.append(
            f"BT /F2 12 Tf {margin_x:.1f} {page_h - 95:.1f} Td "
            f"({_escapar_pdf('(Auditoria / Fiscalização)')}) Tj ET"
        )

        cmds.append("0.40 0.44 0.50 rg")
        cmds.append(
            f"BT /F1 8.5 Tf {margin_x:.1f} {page_h - 112:.1f} Td "
            f"({_escapar_pdf(f'Emitido em: {emitido_em}')}) Tj ET"
        )

        cmds.append("0.78 0.82 0.87 RG 0.8 w")
        cmds.append(f"{margin_x:.1f} {page_h - 120:.1f} m {page_w - margin_x:.1f} {page_h - 120:.1f} l S")

        y_cursor = page_h - 140.0

        cmds.append("0.10 0.14 0.20 rg")
        cmds.append(
            f"BT /F2 10 Tf {margin_x:.1f} {y_cursor:.1f} Td ({_escapar_pdf('Dados do Colaborador')}) Tj ET"
        )
        y_cursor -= 10.0

        grid_rows = [
            ("Nome Completo", resumo_colab.get("colaborador", "—"), "Matrícula", resumo_colab.get("matricula", "—")),
            ("Cargo / Função", resumo_colab.get("funcao", "—"), "Setor / C.C.", resumo_colab.get("setor", "—")),
            ("Status", resumo_colab.get("status", "—"), "Admissão", resumo_colab.get("admissao", "—")),
        ]
        col_w = usable_w / 4.0
        row_h = 20.0
        for r_idx, (l1, v1, l2, v2) in enumerate(grid_rows):
            top_y = y_cursor - r_idx * row_h
            bot_y = top_y - row_h
            cmds.append("0.95 0.96 0.98 rg")
            cmds.append(f"{margin_x:.1f} {bot_y:.1f} {col_w:.1f} {row_h:.1f} re f")
            cmds.append(f"{margin_x + 2*col_w:.1f} {bot_y:.1f} {col_w:.1f} {row_h:.1f} re f")

            cmds.append("0.80 0.83 0.88 RG 0.6 w")
            cmds.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {row_h:.1f} re S")
            for c_i in (1, 2, 3):
                x_div = margin_x + c_i * col_w
                cmds.append(f"{x_div:.1f} {bot_y:.1f} m {x_div:.1f} {top_y:.1f} l S")

            cmds.append("0.25 0.29 0.35 rg")
            cmds.append(f"BT /F2 8 Tf {margin_x + 5:.1f} {bot_y + 7:.1f} Td ({_escapar_pdf(l1)}) Tj ET")
            cmds.append(f"BT /F2 8 Tf {margin_x + 2*col_w + 5:.1f} {bot_y + 7:.1f} Td ({_escapar_pdf(l2)}) Tj ET")

            cmds.append("0.10 0.14 0.20 rg")
            cmds.append(f"BT /F1 8.5 Tf {margin_x + col_w + 5:.1f} {bot_y + 7:.1f} Td ({_escapar_pdf(_quebrar_linhas(str(v1), 24)[0])}) Tj ET")
            cmds.append(f"BT /F1 8.5 Tf {margin_x + 3*col_w + 5:.1f} {bot_y + 7:.1f} Td ({_escapar_pdf(_quebrar_linhas(str(v2), 24)[0])}) Tj ET")

        y_cursor = y_cursor - len(grid_rows) * row_h - 22.0

        cmds.append("0.10 0.14 0.20 rg")
        cmds.append(
            f"BT /F2 10 Tf {margin_x:.1f} {y_cursor:.1f} Td "
            f"({_escapar_pdf('Registro de Trocas Realizadas e Renovações Efetuadas')}) Tj ET"
        )
        y_cursor -= 12.0
        return cmds, y_cursor

    w_data = 82.0
    w_tipo = 135.0
    w_item = 130.0
    w_det = usable_w - (w_data + w_tipo + w_item)
    col_widths = [w_data, w_tipo, w_item, w_det]
    headers = ["Data Realização", "Tipo de Registro", "Item", "Detalhes / Observações"]

    def desenhar_cabecalho_tabela(cmds: list[str], y_top: float) -> float:
        h_hdr = 20.0
        bot_y = y_top - h_hdr
        cmds.append("0.92 0.94 0.97 rg")
        cmds.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {h_hdr:.1f} re f")
        cmds.append("0.75 0.79 0.85 RG 0.7 w")
        cmds.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {h_hdr:.1f} re S")

        x_cur = margin_x
        cmds.append("0.15 0.20 0.28 rg")
        for idx_c, h_txt in enumerate(headers):
            cw = col_widths[idx_c]
            if idx_c > 0:
                cmds.append(f"{x_cur:.1f} {bot_y:.1f} m {x_cur:.1f} {y_top:.1f} l S")
            cmds.append(f"BT /F2 8.5 Tf {x_cur + 5:.1f} {bot_y + 6.5:.1f} Td ({_escapar_pdf(h_txt)}) Tj ET")
            x_cur += cw
        return bot_y

    cmds_atual, y_cur = nova_pagina()
    y_cur = desenhar_cabecalho_tabela(cmds_atual, y_cur)

    for item in linhas_historico:
        dt_real = str(item.get("Data") or "—").strip().upper()
        tipo_reg = str(item.get("Tipo") or "—").strip().upper()
        nome_item = str(item.get("Item") or "—").strip().upper()
        detalhes = str(item.get("Detalhes") or item.get("Status") or "—").strip().upper()
        for emoji in ("🟢", "🟠", "🟡", "🔴", "⚪"):
            detalhes = detalhes.replace(emoji, "").strip()

        l_data = _quebrar_linhas(dt_real, 13)
        l_tipo = _quebrar_linhas(tipo_reg, 24)
        l_item = _quebrar_linhas(nome_item, 22)
        l_det = _quebrar_linhas(detalhes, 30)

        max_linhas = max(len(l_data), len(l_tipo), len(l_item), len(l_det), 1)
        row_h = max(18.0, max_linhas * 11.0 + 6.0)

        if y_cur - row_h < 45.0:
            paginas_cmds.append(cmds_atual)
            cmds_atual, y_cur = nova_pagina()
            y_cur = desenhar_cabecalho_tabela(cmds_atual, y_cur)

        bot_y = y_cur - row_h
        cmds_atual.append("0.82 0.85 0.90 RG 0.6 w")
        cmds_atual.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {row_h:.1f} re S")

        x_cur = margin_x
        col_linhas = [l_data, l_tipo, l_item, l_det]
        cmds_atual.append("0.12 0.16 0.22 rg")
        for idx_c, linhas_cel in enumerate(col_linhas):
            cw = col_widths[idx_c]
            if idx_c > 0:
                cmds_atual.append(f"{x_cur:.1f} {bot_y:.1f} m {x_cur:.1f} {y_cur:.1f} l S")
            for k_l, txt_l in enumerate(linhas_cel):
                ty = y_cur - 11.5 - k_l * 11.0
                cmds_atual.append(f"BT /F1 8 Tf {x_cur + 5:.1f} {ty:.1f} Td ({_escapar_pdf(txt_l)}) Tj ET")
            x_cur += cw

        y_cur = bot_y

    paginas_cmds.append(cmds_atual)

    objetos: list[bytes] = []
    num_pag = len(paginas_cmds)
    page_ids = [5 + i * 2 for i in range(num_pag)]
    content_ids = [5 + i * 2 + 1 for i in range(num_pag)]

    objetos.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objetos.append(f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {num_pag} >>\nendobj\n".encode("latin-1"))
    objetos.append(b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objetos.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")

    for i_p, cmds_p in enumerate(paginas_cmds):
        pid = page_ids[i_p]
        cid = content_ids[i_p]
        stream_bytes = ("\n".join(cmds_p)).encode("latin-1", "replace")
        page_obj = (
            f"{pid} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {int(page_w)} {int(page_h)}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {cid} 0 R >>\n"
            f"endobj\n"
        ).encode("latin-1")
        content_obj = (
            f"{cid} 0 obj\n"
            f"<< /Length {len(stream_bytes)} >>\n"
            f"stream\n"
        ).encode("latin-1") + stream_bytes + b"\nendstream\nendobj\n"
        objetos.append(page_obj)
        objetos.append(content_obj)

    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objetos:
        offsets.append(buf.tell())
        buf.write(obj)

    xref_pos = buf.tell()
    total_objs = len(objetos) + 1
    buf.write(f"xref\n0 {total_objs}\n".encode("latin-1"))
    buf.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.write(f"{off:010d} 00000 n \n".encode("latin-1"))

    buf.write(
        f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return buf.getvalue()


def _conteudo_dialog_troca_epi(
    supabase, inventario: list[dict], colab_sel_id: str, nome_colab: str, e: dict, qtd_req, dur_dias: int, fechar_cb
) -> None:
    nome_epi_str = str(e.get("descricao") or e.get("nome_epi") or e.get("nome") or "EPI").strip().upper()
    sku_str = str(e.get("codigo_sku") or e.get("sku") or "—").strip().upper()
    eid_alvo = str(e.get("id") or "").strip()

    saldo_disp_epi = sum(
        max(0, _obter_qtd_lote(inv))
        for inv in inventario
        if str(inv.get("epi_id") or "").strip() == eid_alvo
    )
    st.caption(f"EPI: **{nome_epi_str}** (SKU: {sku_str}) — Saldo disponível no inventário: **{saldo_disp_epi} UN.**")

    qtd_troca = st.number_input(
        "Quantidade", min_value=1, value=max(1, int(qtd_req or 1)), step=1, key=f"q_troca_{colab_sel_id}_{eid_alvo}"
    )
    data_troca = st.date_input(
        "Data da Entrega / Troca", value=date.today(), format="DD/MM/YYYY", key=f"d_troca_{colab_sel_id}_{eid_alvo}"
    )
    motivo_troca = st.text_input(
        "Motivo / Obs.", placeholder="EX: TROCA PERIÓDICA", key=f"m_troca_{colab_sel_id}_{eid_alvo}"
    )
    novo_venc_prev = data_troca + timedelta(days=dur_dias)
    st.caption(
        f"Durabilidade: **{dur_dias} DIAS** — Vencimento calculado pela entrega: **{novo_venc_prev.strftime('%d/%m/%Y')}**"
    )

    b1, b2 = st.columns(2)
    if b1.button("✅ Confirmar Troca", key=f"ok_troca_{colab_sel_id}_{eid_alvo}", use_container_width=True):
        try:
            ok_inv, msg_inv, lote_id = _consumir_inventario_epi(supabase, inventario, e.get("id"), int(qtd_troca))
            if not ok_inv:
                st.error(msg_inv)
                return

            payload_troca = {
                "colaborador_id": colab_sel_id,
                "epi_id": e.get("id"),
                "inventario_id": lote_id,
                "quantidade": int(qtd_troca),
                "data_troca": str(data_troca),
                "data_entrega": str(data_troca),
                "data_vencimento": str(novo_venc_prev),
                "motivo": motivo_troca.strip().upper(),
                "observacoes": motivo_troca.strip().upper(),
            }
            _executar_insert_fallback(
                supabase,
                "historico_trocas_epi",
                payload_troca,
                obrigatorias={"colaborador_id", "epi_id", "quantidade"},
            )
            fechar_cb()
            st.session_state["msg_relatorio_colab"] = {
                "tipo": "success",
                "texto": f"TROCA DE {nome_epi_str} ({int(qtd_troca)} UN.) REGISTRADA PARA {nome_colab}! {msg_inv}",
            }
            _limpar_cache()
            st.rerun()
        except Exception as err:
            st.error(f"Erro ao registrar troca: {err}")

    if b2.button("❌ Cancelar", key=f"canc_troca_{colab_sel_id}_{eid_alvo}", use_container_width=True):
        fechar_cb()
        st.rerun()


def _conteudo_dialog_renovar(
    supabase,
    tipo_label: str,
    tabela_destino: str,
    colab_sel_id: str,
    nome_colab: str,
    item_dict: dict,
    nome_item: str,
    per_padrao: int,
    fechar_cb,
) -> None:
    chave_base = f"{tabela_destino}_{colab_sel_id}_{re.sub(r'[^a-zA-Z0-9]', '_', nome_item)}"
    st.caption(f"{tipo_label}: **{nome_item}**")

    data_real = st.date_input(
        "Data de Realização / Conclusão", value=date.today(), format="DD/MM/YYYY", key=f"d_ren_{chave_base}"
    )
    meses_val = st.number_input(
        "Validade / Período (MESES)", min_value=1, value=per_padrao, step=1, key=f"m_ren_{chave_base}"
    )
    novo_venc = _somar_meses(data_real, int(meses_val))
    st.caption(f"Período: **{int(meses_val)} MESES** — Novo vencimento: **{novo_venc.strftime('%d/%m/%Y')}**")

    b1, b2 = st.columns(2)
    if b1.button("✅ Confirmar Renovação", key=f"ok_ren_{chave_base}", use_container_width=True):
        try:
            if tabela_destino == "exames_colaborador":
                payload = {
                    "colaborador_id": colab_sel_id,
                    "tipo_exame_id": item_dict.get("tipo_exame_id") or item_dict.get("id"),
                    "nome": nome_item.upper(),
                    "data_realizacao": str(data_real),
                    "data_vencimento": str(novo_venc),
                    "validade": str(novo_venc),
                    "status": "EM DIA",
                }
            else:
                payload = {
                    "colaborador_id": colab_sel_id,
                    "nome_treinamento": nome_item.upper(),
                    "tipo_treinamento": str(item_dict.get("tipo_treinamento") or nome_item).upper(),
                    "nome": nome_item.upper(),
                    "titulo": nome_item.upper(),
                    "data_realizacao": str(data_real),
                    "data_conclusao": str(data_real),
                    "data_vencimento": str(novo_venc),
                    "validade": str(novo_venc),
                    "status": "EM DIA",
                }
            _executar_insert_fallback(
                supabase,
                tabela_destino,
                payload,
                obrigatorias={"colaborador_id"},
            )
            fechar_cb()
            st.session_state["msg_relatorio_colab"] = {
                "tipo": "success",
                "texto": f"{tipo_label.upper()} '{nome_item}' RENOVADO ATÉ {novo_venc.strftime('%d/%m/%Y')}!",
            }
            _limpar_cache()
            st.rerun()
        except Exception as err:
            st.error(f"Erro ao renovar: {err}")

    if b2.button("❌ Cancelar", key=f"canc_ren_{chave_base}", use_container_width=True):
        fechar_cb()
        st.rerun()


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
        st.info("NENHUM COLABORADOR CADASTRADO.")
        return

    funcoes = _buscar_tabela("funcoes")
    cargos = _buscar_tabela("cargos")
    funcao_requisitos = _buscar_tabela("funcao_requisitos")
    epis = _buscar_tabela("epis")
    inventario = _buscar_tabela("inventario_epi")
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
        _, nome_func = _resolver_funcao_colaborador(c, funcoes, cargos)
        matricula = str(c.get("matricula") or "—").strip().upper()
        status = str(c.get("status") or "ATIVO").strip().upper()
        nome_c = str(c.get("nome_completo") or c.get("nome") or "COLABORADOR").strip().upper()
        rotulos.append((cid, f"{nome_c} ({matricula}) — {nome_func} [{status}]"))

    with col_f:
        colab_sel_id = st.selectbox(
            "Filtrar / Selecionar Colaborador",
            options=[r[0] for r in rotulos],
            format_func=lambda cid: dict(rotulos).get(cid, cid),
            key="select_colab_relatorio",
        )

    colab_atual = mapa_colabs.get(colab_sel_id, {})
    funcao_id, nome_funcao = _resolver_funcao_colaborador(colab_atual, funcoes, cargos)
    matricula = str(colab_atual.get("matricula") or "—").strip().upper()
    setor = str(
        colab_atual.get("setor")
        or colab_atual.get("centro_custo")
        or colab_atual.get("departamento")
        or "—"
    ).strip().upper()
    status = str(colab_atual.get("status") or "ATIVO").strip().upper()
    nome_colab = str(colab_atual.get("nome_completo") or colab_atual.get("nome") or "—").strip().upper()
    admissao_str = _formatar_data_br(
        colab_atual.get("data_admissao") or colab_atual.get("admissao") or colab_atual.get("created_at")
    )

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f"**Colaborador:**  \n{nome_colab}")
        c2.markdown(f"**Função:**  \n{nome_funcao}")
        c3.markdown(f"**Matrícula:**  \n{matricula}")
        c4.markdown(f"**Setor:**  \n{setor}")
        c5.markdown(
            f"**Status:**  \n🟢 {status}" if _normalizar(status) == "ativo" else f"**Status:**  \n{status}"
        )

    req_funcao = _obter_requisito_funcao(funcao_requisitos, funcao_id, nome_funcao)
    refs_epi = _coletar_refs_por_palavra_chave(req_funcao, ("epi",))
    refs_exame = _coletar_refs_por_palavra_chave(req_funcao, ("exame", "aso"))
    refs_trein = _coletar_refs_por_palavra_chave(req_funcao, ("trein", "curso", "nr"))

    mapa_epis = {str(e.get("id") or "").strip(): e for e in epis if e.get("id") is not None}
    mapa_tipos_ex = {str(tx.get("id") or "").strip(): tx for tx in tipos_exames if tx.get("id") is not None}

    historico_itens: list[dict] = []

    trocas_do_colab = [
        t for t in historico_trocas if str(t.get("colaborador_id") or "").strip() == colab_sel_id
    ]
    for t in trocas_do_colab:
        ep = mapa_epis.get(str(t.get("epi_id") or "").strip(), {})
        nome_e = str(ep.get("descricao") or ep.get("nome_epi") or ep.get("nome") or "EPI").strip().upper()
        dt_entrega_raw = t.get("data_entrega") or t.get("data_troca") or t.get("created_at")
        dt_entrega = _parse_data(dt_entrega_raw)
        dur_dias = _durabilidade_dias_epi(ep)
        dt_venc_epi = (dt_entrega + timedelta(days=dur_dias)) if dt_entrega else None
        bol_epi, rot_epi = _indicador_vencimento(dt_venc_epi)
        obs_t = str(t.get("motivo") or t.get("observacoes") or "").strip().upper()
        det_t = f"QTD: {t.get('quantidade') or 1} | DUR.: {dur_dias} DIAS" + (f" — {obs_t}" if obs_t else "")
        historico_itens.append({
            "Tipo": "TROCA DE EPI",
            "Item": nome_e,
            "Data": _formatar_data_br(dt_entrega),
            "Vencimento": _formatar_data_br(dt_venc_epi),
            "Status": f"{bol_epi} {rot_epi}",
            "Detalhes": det_t,
        })

    exames_do_colab = [
        ex for ex in exames_colab if str(ex.get("colaborador_id") or "").strip() == colab_sel_id
    ]
    for ex in exames_do_colab:
        tx_id = str(ex.get("tipo_exame_id") or ex.get("exame_id") or "").strip()
        tx_info = mapa_tipos_ex.get(tx_id, {})
        nome_ex = _nome_exame({**tx_info, **ex})
        venc_raw = ex.get("data_vencimento") or ex.get("proximo_vencimento") or ex.get("validade")
        bol, rot = _indicador_vencimento(venc_raw)
        det_ex = str(ex.get("observacoes") or ex.get("resultado") or "").strip().upper()
        if not det_ex:
            det_ex = f"EXAME REALIZADO / RENOVADO (VENC.: {_formatar_data_br(venc_raw)})"
        historico_itens.append({
            "Tipo": "RENOVAÇÃO DE EXAME",
            "Item": nome_ex,
            "Data": _formatar_data_br(ex.get("data_realizacao") or ex.get("data_exame") or ex.get("created_at")),
            "Vencimento": _formatar_data_br(venc_raw),
            "Status": f"{bol} {rot}",
            "Detalhes": det_ex,
        })

    trein_do_colab = [
        tr for tr in treinamentos if str(tr.get("colaborador_id") or "").strip() == colab_sel_id
    ]
    for tr in trein_do_colab:
        nome_tr = _nome_treinamento(tr)
        venc_raw = tr.get("data_vencimento") or tr.get("validade")
        bol, rot = _indicador_vencimento(venc_raw)
        det_tr = str(tr.get("observacoes") or tr.get("carga_horaria") or "").strip().upper()
        if not det_tr:
            det_tr = f"TREINAMENTO REALIZADO / RENOVADO (VENC.: {_formatar_data_br(venc_raw)})"
        historico_itens.append({
            "Tipo": "RENOVAÇÃO DE TREINAMENTO",
            "Item": nome_tr,
            "Data": _formatar_data_br(tr.get("data_realizacao") or tr.get("data_conclusao") or tr.get("created_at")),
            "Vencimento": _formatar_data_br(venc_raw),
            "Status": f"{bol} {rot}",
            "Detalhes": det_tr,
        })

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
                nome_epi_str = str(e.get("descricao") or e.get("nome_epi") or e.get("nome") or "—").strip().upper()
                dur_dias = _durabilidade_dias_epi(e)
                dur_str = f"{dur_dias} {'DIA' if dur_dias == 1 else 'DIAS'}"

                trocas_deste_epi = []
                for t in trocas_do_colab:
                    if str(t.get("epi_id") or "").strip() == str(e.get("id") or "").strip():
                        dt_e = _parse_data(t.get("data_entrega") or t.get("data_troca") or t.get("created_at"))
                        if dt_e:
                            trocas_deste_epi.append((dt_e, t))
                trocas_deste_epi.sort(key=lambda par: par[0], reverse=True)

                if trocas_deste_epi:
                    dt_entrega_ref, _ = trocas_deste_epi[0]
                    dt_venc_epi = dt_entrega_ref + timedelta(days=dur_dias)
                    bol_epi, rot_epi = _indicador_vencimento(dt_venc_epi)
                    texto_entrega_epi = _formatar_data_br(dt_entrega_ref)
                    texto_venc_epi = f"{bol_epi} {_formatar_data_br(dt_venc_epi)}"
                    texto_status_epi = f"{bol_epi} {rot_epi}"
                else:
                    texto_entrega_epi = "—"
                    texto_venc_epi = "🔴 —"
                    texto_status_epi = "🔴 VENCIDO (SEM ENTREGA)"

                qtd_req = e.get("_qtd_requisito")
                chave_modal_epi = f"abrir_troca_epi_{colab_sel_id}_{eid}_{idx}"

                def _fechar_epi(k=chave_modal_epi):
                    st.session_state[k] = False

                with st.container(border=True):
                    cols = st.columns([2.1, 1.1, 1.2, 1.9, 1.6, 1.3])
                    cols[0].markdown(f"**EPI:**  \n{nome_epi_str}")
                    cols[1].markdown(f"**Durabilidade:**  \n{dur_str}")
                    cols[2].markdown(f"**Entrega:**  \n{texto_entrega_epi}")
                    cols[3].markdown(f"**Vencimento:**  \n{texto_venc_epi}")
                    cols[4].markdown(f"**Status:**  \n{texto_status_epi}")

                    if cols[5].button("🔄 Trocar", key=f"btn_{chave_modal_epi}", use_container_width=True):
                        st.session_state[chave_modal_epi] = True

                    if st.session_state.get(chave_modal_epi, False):
                        if hasattr(st, "dialog"):
                            @st.dialog(f"🔄 Trocar EPI — {nome_epi_str}")
                            def _dlg_epi(
                                _e=e, _q=qtd_req, _d=dur_dias, _cb=_fechar_epi
                            ):
                                _conteudo_dialog_troca_epi(
                                    supabase, inventario, colab_sel_id, nome_colab, _e, _q, _d, _cb
                                )
                            _dlg_epi()
                        else:
                            with st.container(border=True):
                                _conteudo_dialog_troca_epi(
                                    supabase, inventario, colab_sel_id, nome_colab, e, qtd_req, dur_dias, _fechar_epi
                                )
        else:
            st.info("NENHUM EPI VINCULADO À FUNÇÃO DESTE COLABORADOR.")

        # ---------------- EXAMES ----------------
        st.subheader("📋 Exames")
        exames_req = _resolver_itens_catalogo(
            refs_exame,
            tipos_exames,
            ("nome", "nome_exame", "tipo_exame", "descricao"),
            manter_nao_encontrados=True,
        )

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
                    copia["status"] = "PENDENTE / REQUISITO DA FUNÇÃO"
                linhas_exames_exibir.append(copia)

        if linhas_exames_exibir:
            for idx, ex_item in enumerate(linhas_exames_exibir):
                ex_id = str(ex_item.get("tipo_exame_id") or ex_item.get("id") or idx).strip()
                nome_ex = str(ex_item.get("Exame") or _nome_exame(ex_item)).upper()
                per_raw = (
                    ex_item.get("periodicidade_meses")
                    or ex_item.get("validade_meses")
                    or ex_item.get("periodicidade")
                )
                per_str = _formatar_periodo_meses(per_raw)
                dt_real_str = _formatar_data_br(
                    ex_item.get("data_realizacao") or ex_item.get("data_exame") or ex_item.get("data_aso")
                )
                venc_raw = ex_item.get("data_vencimento") or ex_item.get("proximo_vencimento") or ex_item.get("validade")
                dt_venc_str = _formatar_data_br(venc_raw)
                bol_ex, rot_ex = _indicador_vencimento(venc_raw)
                status_ex = str(ex_item.get("status") or ex_item.get("resultado") or rot_ex).upper()

                chave_modal_ex = f"abrir_ren_exame_{colab_sel_id}_{ex_id}_{idx}"

                def _fechar_ex(k=chave_modal_ex):
                    st.session_state[k] = False

                try:
                    per_padrao = max(1, int(float(per_raw))) if per_raw is not None else 12
                except Exception:
                    per_padrao = 12

                with st.container(border=True):
                    cols = st.columns([2.1, 1.1, 1.2, 1.9, 1.6, 1.3])
                    cols[0].markdown(f"**Exame:**  \n{nome_ex}")
                    cols[1].markdown(f"**Período:**  \n{per_str}")
                    cols[2].markdown(f"**Realização:**  \n{dt_real_str}")
                    cols[3].markdown(f"**Vencimento:**  \n{bol_ex} {dt_venc_str}")
                    cols[4].markdown(f"**Status:**  \n{bol_ex} {status_ex}")

                    if cols[5].button("🔁 Renovar", key=f"btn_{chave_modal_ex}", use_container_width=True):
                        st.session_state[chave_modal_ex] = True

                    if st.session_state.get(chave_modal_ex, False):
                        if hasattr(st, "dialog"):
                            @st.dialog(f"🔁 Renovar Exame — {nome_ex}")
                            def _dlg_ex(
                                _item=ex_item, _n=nome_ex, _p=per_padrao, _cb=_fechar_ex
                            ):
                                _conteudo_dialog_renovar(
                                    supabase, "Exame", "exames_colaborador", colab_sel_id, nome_colab, _item, _n, _p, _cb
                                )
                            _dlg_ex()
                        else:
                            with st.container(border=True):
                                _conteudo_dialog_renovar(
                                    supabase, "Exame", "exames_colaborador", colab_sel_id, nome_colab, ex_item, nome_ex, per_padrao, _fechar_ex
                                )
        else:
            st.info("NENHUM EXAME VINCULADO À FUNÇÃO DESTE COLABORADOR.")

        # ---------------- TREINAMENTOS ----------------
        st.subheader("🎓 Treinamentos")

        trein_vinculados_colab = [
            tr for tr in treinamentos
            if str(tr.get("colaborador_id") or "").strip() == colab_sel_id
        ]
        trein_vinculados_funcao = []
        for tr in treinamentos:
            if str(tr.get("colaborador_id") or "").strip():
                continue
            tr_fid = str(tr.get("funcao_id") or tr.get("cargo_id") or "").strip()
            tr_fnome = _normalizar(tr.get("funcao") or tr.get("cargo") or tr.get("nome_funcao") or tr.get("nome_cargo"))
            if (funcao_id and tr_fid and tr_fid == funcao_id) or (
                nome_funcao and nome_funcao != "—" and tr_fnome and tr_fnome == _normalizar(nome_funcao)
            ):
                trein_vinculados_funcao.append(tr)

        trein_req = _resolver_itens_catalogo(
            refs_trein,
            treinamentos,
            ("nome_treinamento", "nome", "titulo", "curso", "tipo_treinamento", "
