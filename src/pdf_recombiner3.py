import fitz  # PyMuPDF
from PIL import Image
import os
from typing import List, Dict, Any

Component = Dict[str, Any]
LogicalUnit = List[Component]

def recombine_pdf(
    output_pdf_path: str,
    logical_units_to_place: List[LogicalUnit],
    cfg: Dict[str, Any]
):
    """
    논리적 단위에 따라 컴포넌트 이미지들을 새 PDF 페이지에 재조합합니다.
    - 모든 페이지 상단에 머리글(가로선)을 그림
    - 2단 레이아웃 지원
    - question_block 하단에 attachments(예: figure) 자동 배치
    """
    doc = fitz.open()
    page = doc.new_page(width=cfg['page_size'][0], height=cfg['page_size'][1])

    page_width, page_height = cfg['page_size']
    margin = cfg['margin']
    spacing = cfg['spacing_between_components']

    header_y = cfg.get('header_y_position', 70)
    header_line_width = cfg.get('header_line_width', 0.5)
    content_start_y = header_y + spacing

    two_column_layout = cfg.get('two_column_layout', False)
    column_line_width = cfg.get('column_line_width', 0)

    def draw_header(p: fitz.Page):
        p.draw_line(
            fitz.Point(margin, header_y),
            fitz.Point(page_width - margin, header_y),
            color=(0, 0, 0),
            width=header_line_width
        )

    draw_header(page)

    if two_column_layout:
        column_width = (page_width - 3 * margin) / 2
        column_x_pos = [margin, margin + column_width + margin]
        y_cursors = [content_start_y, content_start_y]
    else:
        column_width = page_width - 2 * margin
        column_x_pos = [float(margin)]
        y_cursors = [content_start_y]

    current_column = 0
    current_question_num = cfg.get('start_question_number', 1)

    def get_scaled_dimensions(img_w, img_h):
        # scale to fit column width
        max_allowed_width = column_width
        if img_w > max_allowed_width:
            scale = max_allowed_width / img_w
            return int(img_w * scale), int(img_h * scale)
        return int(img_w), int(img_h)

    def ensure_space(h_needed):
        nonlocal page, current_column, y_cursors
        if y_cursors[current_column] + h_needed > page_height - margin:
            if two_column_layout and current_column == 0:
                current_column = 1
            else:
                page = doc.new_page(width=page_width, height=page_height)
                draw_header(page)
                y_cursors = [content_start_y, content_start_y] if two_column_layout else [content_start_y]
                current_column = 0

    for unit in logical_units_to_place:
        for i, component in enumerate(unit):
            image_path = component['image_path']
            if not os.path.exists(image_path):
                print(f"경고: 이미지를 찾을 수 없습니다. 건너뜁니다 -> {image_path}")
                continue

            with Image.open(image_path) as img:
                w0, h0 = img.size
            w, h = get_scaled_dimensions(w0, h0)

            is_header_followed_by_passage = (
                component['label'] == 'header' and (i + 1) < len(unit) and unit[i + 1]['label'] == 'passage'
            )
            required_height = h
            if is_header_followed_by_passage:
                next_comp = unit[i + 1]
                if os.path.exists(next_comp['image_path']):
                    with Image.open(next_comp['image_path']) as nimg:
                        nw, nh = get_scaled_dimensions(*nimg.size)
                    required_height += spacing + nh

            # also include attachments height if any (for space check)
            attachments = component.get('attachments', [])
            for att in attachments:
                if os.path.exists(att['image_path']):
                    with Image.open(att['image_path']) as aimg:
                        aw, ah = get_scaled_dimensions(*aimg.size)
                    required_height += spacing + ah

            ensure_space(required_height)

            x_pos = column_x_pos[current_column]
            y_pos = y_cursors[current_column]

            # place main image
            rect = fitz.Rect(x_pos, y_pos, x_pos + w, y_pos + h)
            page.insert_image(rect, filename=image_path)

            if component['label'] == "question_block":
                q_num_text = f"{current_question_num}."
                text_pos = fitz.Point(
                    x_pos + cfg.get('question_number_offset_x', 10),
                    y_pos + cfg.get('question_number_offset_y', 12)
                )
                page.insert_text(
                    text_pos, q_num_text,
                    fontsize=cfg.get('question_number_font_size', 12), color=(0, 0, 0)
                )
                current_question_num += 1

            y_cursors[current_column] += h + spacing

            # place attachments directly below
            for att in attachments:
                apath = att['image_path']
                if not os.path.exists(apath):
                    continue
                with Image.open(apath) as aimg:
                    aw0, ah0 = aimg.size
                aw, ah = get_scaled_dimensions(aw0, ah0)
                ensure_space(ah)
                rect_att = fitz.Rect(x_pos, y_cursors[current_column], x_pos + aw, y_cursors[current_column] + ah)
                page.insert_image(rect_att, filename=apath)
                y_cursors[current_column] += ah + spacing

    # draw vertical divider for two-column layout
    if two_column_layout and column_line_width > 0:
        for p in doc:
            center_x = page_width / 2
            p.draw_line(fitz.Point(center_x, content_start_y),
                        fitz.Point(center_x, page_height - margin),
                        color=(0, 0, 0), width=column_line_width)

    doc.save(output_pdf_path)
    doc.close()
    print(f"\nPDF 재조합 완료: {output_pdf_path}")