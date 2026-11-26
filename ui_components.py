from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import base64
import math
from PIL import Image as PILImage, ImageDraw, ImageFont
import streamlit as st


def _carregar_fonte(tamanho: int, negrito: bool = False):
    candidatas_fontes = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if negrito
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if negrito
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if negrito else "DejaVuSans.ttf",
    ]
    for caminho_fonte in candidatas_fontes:
        if Path(caminho_fonte).exists():
            try:
                return ImageFont.truetype(caminho_fonte, size=tamanho)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


def _vertices_hexagono(cx: float, cy: float, raio: float) -> list[tuple[float, float]]:
    """Retorna os 6 vértices de um hexágono com topo/base planos (flat-top)."""
    pts = []
    for i in range(6):
        ang = math.radians(60 * i)
        pts.append((cx + raio * math.cos(ang), cy + raio * math.sin(ang)))
    return pts


def _gerar_logo_padrao_bytes() -> bytes:
    """
    Gera um PNG fiel à identidade visual GLOBEX MULTIMODAL caso o ficheiro
    de imagem não esteja presente no ambiente de execução.
    """
    largura, altura = 1200, 420
    img = PILImage.new("RGBA", (largura, altura), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    cor_texto = (10, 58, 78, 255)      # Azul-petróleo escuro
    cor_azul = (0, 169, 224, 255)      # Ciano / azul vibrante do hexágono
    cor_vermelho = (204, 20, 56, 255)  # Vermelho da faixa lateral

    fonte_globex = _carregar_fonte(tamanho=118, negrito=True)
    fonte_sub = _carregar_fonte(tamanho=56, negrito=False)

    x_texto = 95
    y_globex = 115
    draw.text((x_texto, y_globex), "GLOBEX", fill=cor_texto, font=fonte_globex)

    bbox_globex = draw.textbbox((x_texto, y_globex), "GLOBEX", font=fonte_globex)
    bbox_sub = draw.textbbox((0, 0), "MULTIMODAL", font=fonte_sub)
    larg_sub = bbox_sub[2] - bbox_sub[0]
    x_sub = bbox_globex[2] - larg_sub - 6
    y_sub = bbox_globex[3] + 18
    draw.text((x_sub, y_sub), "MULTIMODAL", fill=cor_texto, font=fonte_sub)

    cx_hex = 915.0
    cy_hex = 210.0
    raio_ext = 118.0
    raio_int = 84.0

    hex_ext = _vertices_hexagono(cx_hex, cy_hex, raio_ext)
    hex_int = _vertices_hexagono(cx_hex, cy_hex, raio_int)

    mascara = PILImage.new("L", (largura, altura), 0)
    draw_mask = ImageDraw.Draw(mascara)
    draw_mask.polygon(hex_ext, fill=255)
    draw_mask.polygon(hex_int, fill=0)

    camada_azul = PILImage.new("RGBA", (largura, altura), cor_azul)
    img = PILImage.alpha_composite(
        img,
        PILImage.composite(
            camada_azul,
            PILImage.new("RGBA", (largura, altura), (0, 0, 0, 0)),
            mascara,
        ),
    )

    dx = 54.0
    dy = -26.0
    esp = 28.0
    p_top_r = (hex_ext[5][0] + dx, hex_ext[5][1] + dy)
    p_right = (hex_ext[0][0] + dx, hex_ext[0][1] + dy)
    p_bot_r = (hex_ext[1][0] + dx, hex_ext[1][1] + dy)

    faixa_vermelha = [
        (p_top_r[0] - esp * 0.4, p_top_r[1] - esp * 0.7),
        (p_right[0] + esp * 0.85, p_right[1] - esp * 0.3),
        (p_bot_r[0] - esp * 0.4, p_bot_r[1] + esp * 0.7),
        (p_bot_r[0] - esp * 1.35, p_bot_r[1] - esp * 0.2),
        (p_right[0] - esp * 0.35, p_right[1]),
        (p_top_r[0] - esp * 1.35, p_top_r[1] + esp * 0.2),
    ]
    draw = ImageDraw.Draw(img, "RGBA")
    draw.polygon(faixa_vermelha, fill=cor_vermelho)

    bbox = img.getbbox()
    if bbox:
        pad = 24
        img = img.crop(
            (
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(largura, bbox[2] + pad),
                min(altura, bbox[3] + pad),
            )
        )

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def obter_logo_bytes() -> bytes:
    """
    Busca o ficheiro de logótipo oficial no repositório antes de recorrer ao desenho padrão.
    """
    base_dir = Path(__file__).resolve().parent
    candidatos = [
        Path("Logo_2.png"),
        Path("logo_2.png"),
        Path("assets/Logo_2.png"),
        Path("assets/logo_2.png"),
        Path("assets/logo.png"),
        Path("assets/Logo.png"),
        Path("Logo.png"),
        Path("logo.png"),
        Path("modules/assets/logo.png"),
        base_dir / "Logo_2.png",
        base_dir / "logo_2.png",
        base_dir / "assets" / "logo.png",
        base_dir / "logo.png",
    ]
    for caminho in candidatos:
        if caminho.exists() and caminho.is_file():
            try:
                return caminho.read_bytes()
            except Exception:
                pass
    return _gerar_logo_padrao_bytes()


def render_logo_sidebar() -> None:
    st.sidebar.caption("Gestor SST • Indaiatuba - SP")
    st.sidebar.markdown("---")


def render_cabecalho_modulo(titulo: str, subtitulo: str = "") -> None:
    logo_b64 = base64.b64encode(obter_logo_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <div style="display: flex; justify-content: center; align-items: center; width: 100%; margin-bottom: 10px;">
            <img src="data:image/png;base64,{logo_b64}" alt="GLOBEX MULTIMODAL" style="max-height: 155px; max-width: 420px; width: auto; object-fit: contain;" />
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.title(titulo)
    if subtitulo:
        st.caption(subtitulo)


def gerar_pdf_historico_colaborador(
    colab: dict,
    movimentacoes_realizadas: list[dict],
) -> tuple[bytes | None, str | None]:
    """
    Gera um PDF de auditoria/fiscalização com as datas em que as trocas de EPI
    foram realizadas e as datas em que exames e treinamentos foram renovados,
    incluindo o logótipo da empresa e datas no formato dd/mm/aaaa.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image as RLImage,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        return (
            None,
            "Biblioteca 'reportlab' não instalada. Adicione 'reportlab' ao requirements.txt e faça reboot na app.",
        )

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
        spaceBefore=12,
        spaceAfter=6,
    )

    elementos = []

    logo_bytes = obter_logo_bytes()
    img = RLImage(BytesIO(logo_bytes), width=4.8 * cm, height=1.7 * cm, kind="proportional")

    texto_cab = Paragraph(
        "<b>GLOBEX MULTIMODAL</b><br/>"
        "Comprovante de Trocas de EPI e Renovações de Exames / Treinamentos (Auditoria / Fiscalização)<br/>"
        f"<font size=8 color='#555555'>Emitido em: {date.today().strftime('%d/%m/%Y')} às {datetime.now().strftime('%H:%M')}</font>",
        estilo_sub,
    )
    tabela_topo = Table([[img, texto_cab]], colWidths=[5.2 * cm, 12.8 * cm])
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
        [
            "Nome Completo",
            str(colab.get("nome_completo") or "—"),
            "Matrícula",
            str(colab.get("matricula") or "—"),
        ],
        [
            "Cargo / Função",
            str(colab.get("cargo") or "—"),
            "Setor / C.C.",
            str(colab.get("centro_custo") or "—"),
        ],
        [
            "Status",
            str(colab.get("status") or "Ativo"),
            "Admissão",
            str(colab.get("data_admissao_br") or "—"),
        ],
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

    elementos.append(Paragraph("Registro de Trocas Realizadas e Renovações Efetuadas", estilo_secao))
    if not movimentacoes_realizadas:
        elementos.append(
            Paragraph("Nenhuma troca de EPI ou renovação registrada para este colaborador.", estilo_sub)
        )
    else:
        cabecalhos = ["Data Realização", "Tipo de Registro", "Item", "Detalhes / Observações"]
        linhas = [
            [
                str(m.get("Data Realização") or "—"),
                str(m.get("Tipo de Registro") or "—"),
                str(m.get("Item") or "—"),
                str(m.get("Detalhes / Observações") or "—"),
            ]
            for m in movimentacoes_realizadas
        ]
        tab_mov = Table(
            [cabecalhos] + linhas,
            colWidths=[2.8 * cm, 4.2 * cm, 5.5 * cm, 5.5 * cm],
            repeatRows=1,
        )
        tab_mov.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3954")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("PADDING", (0, 0), (-1, -1), 5),
            ])
        )
        elementos.append(tab_mov)

    doc.build(elementos)
    return buffer.getvalue(), None
