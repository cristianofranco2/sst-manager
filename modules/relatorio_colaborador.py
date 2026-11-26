def _escapar_texto_pdf(texto: str) -> str:
    limpo = texto.encode("latin-1", "replace").decode("latin-1")
    return limpo.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _gerar_pdf_nativo_bytes(linhas: list[str]) -> bytes:
    """
    Gera um documento PDF válido (1 página ou múltiplas páginas) em Python puro,
    sem exigir bibliotecas externas.
    """
    linhas_por_pagina = 46
    blocos_paginas = [
        linhas[i : i + linhas_por_pagina]
        for i in range(0, max(1, len(linhas)), linhas_por_pagina)
    ]

    objetos: list[bytes] = []
    # Objeto 1: Catalog
    # Objeto 2: Pages
    # Objeto 3: Font Helvetica
    # A partir do objeto 4: pares de (Page, ContentStream)
    num_paginas = len(blocos_paginas)
    primeiro_page_obj = 4
    page_obj_ids = [primeiro_page_obj + i * 2 for i in range(num_paginas)]
    content_obj_ids = [primeiro_page_obj + i * 2 + 1 for i in range(num_paginas)]

    objetos.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objetos.append(
        f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {num_paginas} >>\nendobj\n".encode("latin-1")
    )
    objetos.append(
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )

    for idx_pag, linhas_pag in enumerate(blocos_paginas):
        page_id = page_obj_ids[idx_pag]
        content_id = content_obj_ids[idx_pag]

        comandos = ["BT", "/F1 10 Tf", "40 760 Td", "15 TL"]
        for i_l, linha in enumerate(linhas_pag):
            escapado = _escapar_texto_pdf(linha[:110])
            if i_l == 0:
                comandos.append(f"({escapado}) Tj")
            else:
                comandos.append(f"T* ({escapado}) Tj")
        comandos.append("ET")
        stream_bytes = ("\n".join(comandos)).encode("latin-1", "replace")

        page_obj = (
            f"{page_id} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>\n"
            f"endobj\n"
        ).encode("latin-1")
        content_obj = (
            f"{content_id} 0 obj\n"
            f"<< /Length {len(stream_bytes)} >>\n"
            f"stream\n"
        ).encode("latin-1") + stream_bytes + b"\nendstream\nendobj\n"

        objetos.append(page_obj)
        objetos.append(content_obj)

    pdf_buffer = io.BytesIO()
    pdf_buffer.write(b"%PDF-1.4\n")
    offsets = [0]

    for obj in objetos:
        offsets.append(pdf_buffer.tell())
        pdf_buffer.write(obj)

    xref_pos = pdf_buffer.tell()
    total_objs = len(objetos) + 1
    pdf_buffer.write(f"xref\n0 {total_objs}\n".encode("latin-1"))
    pdf_buffer.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf_buffer.write(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("latin-1")
    pdf_buffer.write(trailer)
    return pdf_buffer.getvalue()


def _gerar_pdf_bytes(
    titulo: str,
    resumo_colab: dict,
    linhas_historico: list[dict],
) -> bytes:
    linhas_texto = [
        titulo,
        f"Gerado em: {date.today().strftime('%d/%m/%Y')}",
        f"Colaborador: {resumo_colab.get('colaborador', '—')} | Matricula: {resumo_colab.get('matricula', '—')}",
        f"Funcao: {resumo_colab.get('funcao', '—')} | Setor: {resumo_colab.get('setor', '—')} | Status: {resumo_colab.get('status', '—')}",
        "-" * 92,
    ]
    for item in linhas_historico:
        status_limpo = (
            str(item.get("Status") or "—")
            .replace("🟢", "[OK]")
            .replace("🔴", "[VENCIDO]")
            .replace("🟡", "[PENDENTE]")
        )
        linhas_texto.append(
            f"{item.get('Tipo', '')} | {item.get('Item', '')} | "
            f"Data: {item.get('Data', '—')} | Venc.: {item.get('Vencimento', '—')} | "
            f"Status: {status_limpo} | Obs: {item.get('Detalhes', '')}"
        )

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, _escapar_texto_pdf(titulo), ln=True)
        pdf.set_font("Helvetica", size=9)
        for linha in linhas_texto[1:]:
            pdf.multi_cell(0, 5, _escapar_texto_pdf(linha))
        out = pdf.output(dest="S")
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return str(out).encode("latin-1", "replace")
    except Exception:
        return _gerar_pdf_nativo_bytes(linhas_texto)
