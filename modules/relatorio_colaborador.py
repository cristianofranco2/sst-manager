def _gerar_pdf_auditoria_bytes(resumo_colab: dict, linhas_historico: list[dict]) -> bytes:
    try:
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        agora = datetime.now()
    emitido_em = agora.strftime("%d/%m/%Y às %H:%M")

    page_w = 595.0
    page_h = 842.0
    margin_x = 34.0
    usable_w = page_w - 2 * margin_x

    paginas_cmds: list[list[str]] = []

    def desenhar_logo_globex(cmds: list[str], x_left: float, y_top: float) -> None:
        # Marca textual "GLOBEX" + "MULTIMODAL"
        cmds.append("0.07 0.22 0.45 rg")
        cmds.append(f"BT /F2 14 Tf {x_left:.1f} {y_top - 14:.1f} Td ({_escapar_pdf('GLOBEX')}) Tj ET")
        cmds.append("0.22 0.44 0.72 rg")
        cmds.append(f"BT /F2 7.5 Tf {x_left + 1.0:.1f} {y_top - 24:.1f} Td ({_escapar_pdf('MULTIMODAL')}) Tj ET")

        # Ícone geométrico hexagonal (azul à esquerda/topo e vermelho à direita)
        cx = x_left + 76.0
        cy = y_top - 12.0
        r_outer = 11.5
        r_inner = 6.2
        angles_deg = [-90.0, -30.0, 30.0, 90.0, 150.0, 210.0]

        import math
        pts_out = [
            (cx + r_outer * math.cos(math.radians(a)), cy + r_outer * math.sin(math.radians(a)))
            for a in angles_deg
        ]
        pts_in = [
            (cx + r_inner * math.cos(math.radians(a)), cy + r_inner * math.sin(math.radians(a)))
            for a in angles_deg
        ]

        # Metade esquerda em azul (#1E6BB8)
        cmds.append("0.12 0.42 0.72 rg")
        cmds.append(
            f"{pts_out[3][0]:.2f} {pts_out[3][1]:.2f} m "
            f"{pts_out[4][0]:.2f} {pts_out[4][1]:.2f} l "
            f"{pts_out[5][0]:.2f} {pts_out[5][1]:.2f} l "
            f"{pts_out[0][0]:.2f} {pts_out[0][1]:.2f} l "
            f"{pts_in[0][0]:.2f} {pts_in[0][1]:.2f} l "
            f"{pts_in[5][0]:.2f} {pts_in[5][1]:.2f} l "
            f"{pts_in[4][0]:.2f} {pts_in[4][1]:.2f} l "
            f"{pts_in[3][0]:.2f} {pts_in[3][1]:.2f} l h f"
        )

        # Metade direita em vermelho (#C82333)
        cmds.append("0.78 0.14 0.20 rg")
        cmds.append(
            f"{pts_out[0][0]:.2f} {pts_out[0][1]:.2f} m "
            f"{pts_out[1][0]:.2f} {pts_out[1][1]:.2f} l "
            f"{pts_out[2][0]:.2f} {pts_out[2][1]:.2f} l "
            f"{pts_out[3][0]:.2f} {pts_out[3][1]:.2f} l "
            f"{pts_in[3][0]:.2f} {pts_in[3][1]:.2f} l "
            f"{pts_in[2][0]:.2f} {pts_in[2][1]:.2f} l "
            f"{pts_in[1][0]:.2f} {pts_in[1][1]:.2f} l "
            f"{pts_in[0][0]:.2f} {pts_in[0][1]:.2f} l h f"
        )

    def nova_pagina() -> tuple[list[str], float]:
        cmds: list[str] = []
        top_header_y = page_h - 32.0
        desenhar_logo_globex(cmds, margin_x, top_header_y)

        x_info = margin_x + 112.0
        cmds.append("0.11 0.15 0.21 rg")
        cmds.append(
            f"BT /F2 11.5 Tf {x_info:.1f} {top_header_y - 11:.1f} Td "
            f"({_escapar_pdf('GLOBEX MULTIMODAL')}) Tj ET"
        )

        cmds.append("0.18 0.22 0.28 rg")
        l_sub1 = _quebrar_linhas(
            "Comprovante de Trocas de EPI e Renovações de Exames / Treinamentos (Auditoria / Fiscalização)",
            68,
        )
        y_sub = top_header_y - 23.0
        for idx_s, s_txt in enumerate(l_sub1):
            cmds.append(
                f"BT /F1 9 Tf {x_info:.1f} {y_sub - idx_s * 11.0:.1f} Td ({_escapar_pdf(s_txt)}) Tj ET"
            )

        y_emit = y_sub - len(l_sub1) * 11.0 - 1.0
        cmds.append("0.38 0.42 0.48 rg")
        cmds.append(
            f"BT /F1 8.5 Tf {x_info:.1f} {y_emit:.1f} Td "
            f"({_escapar_pdf(f'Emitido em: {emitido_em}')}) Tj ET"
        )

        y_line = y_emit - 10.0
        cmds.append("0.12 0.42 0.72 RG 1.2 w")
        cmds.append(f"{margin_x:.1f} {y_line:.1f} m {page_w - margin_x:.1f} {y_line:.1f} l S")

        y_cursor = y_line - 22.0

        cmds.append("0.11 0.15 0.21 rg")
        cmds.append(
            f"BT /F2 11 Tf {margin_x:.1f} {y_cursor:.1f} Td ({_escapar_pdf('Dados do Colaborador')}) Tj ET"
        )
        y_cursor -= 10.0

        grid_rows = [
            ("Nome Completo", resumo_colab.get("colaborador", "—"), "Matrícula", resumo_colab.get("matricula", "—")),
            ("Cargo / Função", resumo_colab.get("funcao", "—"), "Setor / C.C.", resumo_colab.get("setor", "—")),
            ("Status", resumo_colab.get("status", "—"), "Admissão", resumo_colab.get("admissao", "—")),
        ]
        col_w = usable_w / 4.0
        row_h = 22.0
        for r_idx, (l1, v1, l2, v2) in enumerate(grid_rows):
            top_y = y_cursor - r_idx * row_h
            bot_y = top_y - row_h

            # Fundo cinza claro nas colunas de rótulo (0 e 2)
            cmds.append("0.94 0.96 0.98 rg")
            cmds.append(f"{margin_x:.1f} {bot_y:.1f} {col_w:.1f} {row_h:.1f} re f")
            cmds.append(f"{margin_x + 2 * col_w:.1f} {bot_y:.1f} {col_w:.1f} {row_h:.1f} re f")

            # Fundo branco nas colunas de valor (1 e 3)
            cmds.append("1.00 1.00 1.00 rg")
            cmds.append(f"{margin_x + col_w:.1f} {bot_y:.1f} {col_w:.1f} {row_h:.1f} re f")
            cmds.append(f"{margin_x + 3 * col_w:.1f} {bot_y:.1f} {col_w:.1f} {row_h:.1f} re f")

            # Bordas da grade
            cmds.append("0.78 0.82 0.87 RG 0.6 w")
            cmds.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {row_h:.1f} re S")
            for c_i in (1, 2, 3):
                x_div = margin_x + c_i * col_w
                cmds.append(f"{x_div:.1f} {bot_y:.1f} m {x_div:.1f} {top_y:.1f} l S")

            cmds.append("0.22 0.26 0.32 rg")
            cmds.append(f"BT /F1 8.5 Tf {margin_x + 6:.1f} {bot_y + 7.5:.1f} Td ({_escapar_pdf(l1)}) Tj ET")
            cmds.append(f"BT /F1 8.5 Tf {margin_x + 2 * col_w + 6:.1f} {bot_y + 7.5:.1f} Td ({_escapar_pdf(l2)}) Tj ET")

            cmds.append("0.11 0.15 0.21 rg")
            cmds.append(
                f"BT /F1 8.5 Tf {margin_x + col_w + 6:.1f} {bot_y + 7.5:.1f} Td "
                f"({_escapar_pdf(_quebrar_linhas(str(v1), 24)[0])}) Tj ET"
            )
            cmds.append(
                f"BT /F1 8.5 Tf {margin_x + 3 * col_w + 6:.1f} {bot_y + 7.5:.1f} Td "
                f"({_escapar_pdf(_quebrar_linhas(str(v2), 24)[0])}) Tj ET"
            )

        y_cursor = y_cursor - len(grid_rows) * row_h - 24.0

        cmds.append("0.11 0.15 0.21 rg")
        cmds.append(
            f"BT /F2 11 Tf {margin_x:.1f} {y_cursor:.1f} Td "
            f"({_escapar_pdf('Registro de Trocas Realizadas e Renovações Efetuadas')}) Tj ET"
        )
        y_cursor -= 12.0
        return cmds, y_cursor

    w_data = 92.0
    w_tipo = 152.0
    w_item = 112.0
    w_det = usable_w - (w_data + w_tipo + w_item)
    col_widths = [w_data, w_tipo, w_item, w_det]
    headers = ["Data Realização", "Tipo de Registro", "Item", "Detalhes / Observações"]

    def desenhar_cabecalho_tabela(cmds: list[str], y_top: float) -> float:
        h_hdr = 22.0
        bot_y = y_top - h_hdr
        # Cabeçalho escuro azul-marinho
        cmds.append("0.04 0.22 0.33 rg")
        cmds.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {h_hdr:.1f} re f")
        cmds.append("0.04 0.22 0.33 RG 0.6 w")
        cmds.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {h_hdr:.1f} re S")

        x_cur = margin_x
        cmds.append("1.00 1.00 1.00 rg")
        for idx_c, h_txt in enumerate(headers):
            cw = col_widths[idx_c]
            if idx_c > 0:
                cmds.append("0.20 0.36 0.46 RG 0.5 w")
                cmds.append(f"{x_cur:.1f} {bot_y:.1f} m {x_cur:.1f} {y_top:.1f} l S")
            cmds.append(f"BT /F2 8.5 Tf {x_cur + 6:.1f} {bot_y + 7.5:.1f} Td ({_escapar_pdf(h_txt)}) Tj ET")
            x_cur += cw
        return bot_y

    cmds_atual, y_cur = nova_pagina()
    y_cur = desenhar_cabecalho_tabela(cmds_atual, y_cur)

    for item in linhas_historico:
        dt_real = str(item.get("Data") or "—").strip()
        tipo_reg = str(item.get("Tipo") or "—").strip()
        nome_item = str(item.get("Item") or "—").strip()
        detalhes = str(item.get("Detalhes") or item.get("Status") or "—").strip()
        for emoji in ("🟢", "🟠", "🟡", "🔴", "⚪"):
            detalhes = detalhes.replace(emoji, "").strip()

        l_data = _quebrar_linhas(dt_real, 15)
        l_tipo = _quebrar_linhas(tipo_reg, 28)
        l_item = _quebrar_linhas(nome_item, 20)
        l_det = _quebrar_linhas(detalhes, 36)

        max_linhas = max(len(l_data), len(l_tipo), len(l_item), len(l_det), 1)
        row_h = max(20.0, max_linhas * 11.5 + 7.0)

        if y_cur - row_h < 45.0:
            paginas_cmds.append(cmds_atual)
            cmds_atual, y_cur = nova_pagina()
            y_cur = desenhar_cabecalho_tabela(cmds_atual, y_cur)

        bot_y = y_cur - row_h
        cmds_atual.append("1.00 1.00 1.00 rg")
        cmds_atual.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {row_h:.1f} re f")

        cmds_atual.append("0.78 0.82 0.87 RG 0.6 w")
        cmds_atual.append(f"{margin_x:.1f} {bot_y:.1f} {usable_w:.1f} {row_h:.1f} re S")

        x_cur = margin_x
        col_linhas = [l_data, l_tipo, l_item, l_det]
        cmds_atual.append("0.15 0.19 0.25 rg")
        for idx_c, linhas_cel in enumerate(col_linhas):
            cw = col_widths[idx_c]
            if idx_c > 0:
                cmds_atual.append(f"{x_cur:.1f} {bot_y:.1f} m {x_cur:.1f} {y_cur:.1f} l S")
            for k_l, txt_l in enumerate(linhas_cel):
                ty = y_cur - 12.5 - k_l * 11.5
                cmds_atual.append(f"BT /F1 8.5 Tf {x_cur + 6:.1f} {ty:.1f} Td ({_escapar_pdf(txt_l)}) Tj ET")
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
