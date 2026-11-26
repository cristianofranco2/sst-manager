from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import streamlit as st


def localizar_logo() -> Path | None:
    candidatos = [
        Path("assets/logo.png"),
        Path("assets/Logo.png"),
        Path("Logo.png"),
        Path("logo.png"),
        Path("modules/assets/logo.png"),
    ]
    for caminho in candidatos:
        if caminho.exists() and caminho.is_file():
            return caminho
    return None


def render_logo_sidebar() -> None:
    logo_path = localizar_logo()
    if logo_path:
        st.sidebar.image(str(logo_path), use_container_width=True)
    else:
        st.sidebar.markdown("### GLOBEX MULTIMODAL")
    st.sidebar.caption("Gestor SST • Indaiatuba - SP")
    st.sidebar.markdown("---")


def render_cabecalho_modulo(titulo: str, subtitulo: str = "") -> None:
    col_esq, col_dir = st.columns([4.5, 1.5])
    with col_esq:
        st.title(titulo)
        if subtitulo:
            st.caption(subtitulo)
    with col_dir:
        logo_path = localizar_logo()
        if logo_path:
            st.image(str(logo_path), use_container_width=True)
        else:
            st.markdown("**GLOBEX MULTIMODAL**")


def gerar_pdf_historico_colaborador(
    colab: dict,
    linhas_epi: list[dict],
    linhas_exame: list[dict],
    linhas_trein: list[dict],
    historico_eventos: list[dict],
) -> tuple[bytes | None, str | None]:
    """
    Gera um PDF em bytes usando reportlab, incluindo o logo da empresa e datas em dd/mm/aaaa.
    Retorna (pdf_bytes, erro).
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return None, "Biblioteca 'reportlab' não instalada. Adicione 'reportlab' ao requirements.txt."

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloRelatorio",
        parent=styles["Heading1"],
        fontSize=15,
        textColor=colors.HexColor("#0B3954"),
        spaceAfter=4,
    )
    estilo_sub = ParagraphStyle(
        "SubRelatorio",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=10,
    )
    estilo_secao = ParagraphStyle(
        "SecaoRelatorio",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#0B3954"),
        spaceBefore=10,
        spaceAfter=4,
    )

    elementos = []

    # Cabeçalho com Logo
    logo_path = localizar_logo()
    texto_cab = Paragraph(
        "<b>GLOBEX MULTIMODAL</b><br/>"
        "Relatório de Histórico e Vencimentos SST por Colaborador<br/>"
        f"<font size=8 color='#555555'>Emitido em: {date.today().strftime('%d/%m/%Y')} às {datetime.now().strftime('%H:%M')}</font>",
        estilo_sub,
    )
    if logo_path:
        img = Image(str(logo_path), width=4.2 * cm, height=1.8 * cm, kind="proportional")
        tabela_topo = Table([[img, texto_cab]], colWidths=[4.8 * cm, 13.2 * cm])
        tabela_topo.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#0099CC")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        elementos.append(tabela_topo)
    else:
        elementos.append(Paragraph("GLOBEX MULTIMODAL — Relatório SST", estilo_titulo))
        elementos.append(texto_cab)

    elementos.append(Spacer(1, 0.3 * cm))

    # Dados do Colaborador
    elementos.append(Paragraph("Dados do Colaborador", estilo_secao))
    dados_colab = [
        ["Nome Completo", str(colab.get("nome_completo") or "—"), "Matrícula", str(colab.get("matricula") or "—")],
        ["Cargo / Função", str(colab.get("cargo") or "—"), "Setor / C.C.", str(colab.get("centro_custo") or "—")],
        ["Status", str(colab.get("status") or "Ativo"), "Admissão", str(colab.get("data_admissao_br") or "—")],
    ]
    t_colab = Table(dados_colab, colWidths=[3.5 * cm, 6.0 * cm, 3.0 * cm, 5.5 * cm])
    t_colab.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF2F7")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EDF2F7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elementos.append(t_colab)

    def _adicionar_tabela(titulo_sec: str, cabecalhos: list[str], linhas: list[list[str]], col_widths: list[float]) -> None:
        elementos.append(Paragraph(titulo_sec, estilo_secao))
        if not linhas:
            elementos.append(Paragraph("Nenhum registro encontrado.", estilo_sub))
            return
        dados_tab = [cabecalhos] + linhas
        tab = Table(dados_tab, colWidths=col_widths, repeatRows=1)
        tab.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3954")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elementos.append(tab)

    _adicionar_tabela(
        "EPIs Vinculados",
        ["EPI", "Vencimento", "Situação / Dias"],
        [[r["EPI"], r["Vencimento"], r["Dias Restantes"]] for r in linhas_epi],
        [9.5 * cm, 3.5 * cm, 5.0 * cm],
    )
    _adicionar_tabela(
        "Exames Vinculados",
        ["Exame", "Vencimento", "Situação / Dias"],
        [[r["Exame"], r["Vencimento"], r["Dias Restantes"]] for r in linhas_exame],
        [9.5 * cm, 3.5 * cm, 5.0 * cm],
    )
    _adicionar_tabela(
        "Treinamentos Vinculados",
        ["Treinamento", "Vencimento", "Situação / Dias"],
        [[r["Treinamento"], r["Vencimento"], r["Dias Restantes"]] for r in linhas_trein],
        [9.5 * cm, 3.5 * cm, 5.0 * cm],
    )
    _adicionar_tabela(
        "Histórico de Trocas e Realizações do Colaborador",
        ["Data", "Tipo", "Item", "Vencimento / Detalhes"],
        [
            [
                ev.get("Data", "—"),
                ev.get("Tipo", "—"),
                ev.get("Item", "—"),
                f"{ev.get('Vencimento', '—')} | {ev.get('Detalhes', '')}",
            ]
            for ev in historico_eventos
        ],
        [2.6 * cm, 3.8 * cm, 5.6 * cm, 6.0 * cm],
    )

    doc.build(elementos)
    return buffer.getvalue(), None
