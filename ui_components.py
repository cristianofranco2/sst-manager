from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from PIL import Image as PILImage, ImageDraw, ImageFont
import streamlit as st


def _gerar_logo_padrao_bytes() -> bytes:
    """Gera um PNG limpo com a marca GLOBEX MULTIMODAL caso o arquivo externo não exista."""
    img = PILImage.new("RGB", (640, 220), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Texto principal GLOBEX MULTIMODAL
    fonte_grande = ImageFont.load_default(size=54)
    fonte_sub = ImageFont.load_default(size=28)

    draw.text((28, 48), "GLOBEX", fill=(11, 57, 84), font=fonte_grande)
    draw.text((135, 118), "MULTIMODAL", fill=(24, 68, 94), font=fonte_sub)

    # Ícone geométrico lateral (azul e vermelho)
    azul = (0, 168, 224)
    vermelho = (206, 24, 54)

    pts_azul = [(475, 65), (525, 38), (575, 65), (575, 135), (525, 162), (475, 135)]
    draw.polygon(pts_azul, outline=azul, width=9)

    pts_vermelho = [(515, 32), (555, 12), (598, 36), (598, 122), (578, 132), (578, 48), (552, 33), (522, 49)]
    draw.polygon(pts_vermelho, fill=vermelho)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def obter_logo_bytes() -> bytes:
    candidatos = [
        Path("assets/logo.png"),
        Path("assets/Logo.png"),
        Path("Logo.png"),
        Path("logo.png"),
        Path("modules/assets/logo.png"),
    ]
    for caminho in candidatos:
        if caminho.exists() and caminho.is_file():
            try:
                return caminho.read_bytes()
            except Exception:
                pass
    return _gerar_logo_padrao_bytes()


def render_logo_sidebar() -> None:
    st.sidebar.image(obter_logo_bytes(), use_container_width=True)
    st.sidebar.caption("Gestor SST • Indaiatuba - SP")
    st.sidebar.markdown("---")


def render_cabecalho_modulo(titulo: str, subtitulo: str = "") -> None:
    col_esq, col_dir = st.columns([4.5, 1.5])
    with col_esq:
        st.title(titulo)
        if subtitulo:
            st.caption(subtitulo)
    with col_dir:
        st.image(obter_logo_bytes(), use_container_width=True)


def gerar_pdf_historico_colaborador(
    colab: dict,
    linhas_epi: list[dict],
    linhas_exame: list[dict],
    linhas_trein: list[dict],
    historico_eventos: list[dict],
) -> tuple[bytes | None, str | None]:
    """Gera um PDF em bytes usando reportlab, incluindo o logo da empresa e datas em dd/mm/aaaa."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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

    logo_bytes = obter_logo_bytes()
    img_stream = BytesIO(logo_bytes)
    img = RLImage(img_stream, width=4.5 * cm, height=1.8 * cm, kind="proportional")

    texto_cab = Paragraph(
        "<b>GLOBEX MULTIMODAL</b><br/>"
        "Relatório de Histórico e Vencimentos SST por Colaborador<br/>"
        f"<font size=8 color='#555555'>Emitido em: {date.today().strftime('%d/%m/%Y')} às {datetime.now().strftime('%H:%M')}</font>",
        estilo_sub,
    )
    tabela_topo = Table([[img, texto_cab]], colWidths=[5.0 * cm, 13.0 * cm])
    tabela_topo.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#0099CC")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elementos.append(tabela_topo)
    elementos.append(Spacer(1, 0.3 * cm))

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

    def _adicionar_tabela(
        titulo_sec: str,
        cabecalhos: list[str],
        linhas: list[list[str]],
        col_widths: list[float],
    ) -> None:
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
