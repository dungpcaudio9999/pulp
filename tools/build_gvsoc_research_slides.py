#!/usr/bin/env python3
"""Build the GVSoC/RTL research presentation from template_edabk.pptx.

The script intentionally keeps all diagrams editable PowerPoint shapes.  Places
that require a real GUI capture are represented by orange dashed placeholders
that include the exact command and requested crop.
"""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

DEPS = Path("/tmp/gvsoc_pptx_deps")
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(
    "/home/dungpc/ndmoney4porche/projects/doc/for-report/template_edabk.pptx"
)
OUTPUT = ROOT / "report" / "Bao_cao_GVSoC_RTL_PULP_2026-10-03.pptx"
ARCH = ROOT / "report" / "gvsoc_manual_run" / "step2" / "architecture.png"

NAVY = "000572"
DEEP_BLUE = "123A70"
BLUE = "1769AA"
CYAN = "00A6C8"
SKY = "DDF3FA"
GREEN = "27845C"
PALE_GREEN = "E7F5EE"
ORANGE = "F2A63B"
PALE_ORANGE = "FFF3DF"
RED = "B63A3A"
PALE_RED = "FBE9E9"
INK = "1F2D3D"
GRAY = "5E6B78"
MID_GRAY = "AAB5C0"
LIGHT_GRAY = "E8EDF3"
PAPER = "F8FAFD"
WHITE = "FFFFFF"
BLACK = "000000"


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def iter_shapes(shapes):
    for shape in shapes:
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(shape.shapes)


def set_shape_text(shape, text: str, size: float | None = None, color: str | None = None):
    shape.text = text
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            if size is not None:
                run.font.size = Pt(size)
            if color is not None:
                run.font.color.rgb = rgb(color)


def remove_slide(prs: Presentation, slide):
    slide_id = slide.slide_id
    slide_id_list = prs.slides._sldIdLst
    for slide_id_element in list(slide_id_list):
        if int(slide_id_element.id) == slide_id:
            rel_id = slide_id_element.rId
            slide_id_list.remove(slide_id_element)
            prs.part.drop_rel(rel_id)
            break


def add_text(
    slide,
    text,
    x,
    y,
    w,
    h,
    *,
    size=18,
    color=INK,
    bold=False,
    font="Arial",
    align=PP_ALIGN.LEFT,
    valign=MSO_ANCHOR.TOP,
    margin=0.08,
    fill=None,
    line=None,
    radius=False,
    italic=False,
    autosize=False,
):
    if fill is not None or line is not None:
        shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
        shape = slide.shapes.add_shape(
            shape_type, Inches(x), Inches(y), Inches(w), Inches(h)
        )
        if fill is None:
            shape.fill.background()
        else:
            shape.fill.solid()
            shape.fill.fore_color.rgb = rgb(fill)
        if line is None:
            shape.line.fill.background()
        else:
            shape.line.color.rgb = rgb(line)
            shape.line.width = Pt(1)
        tf = shape.text_frame
    else:
        shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = shape.text_frame
    tf.clear()
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    if autosize:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    p = tf.paragraphs[0]
    p.alignment = align
    p.space_after = Pt(0)
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = rgb(color)
    return shape


def add_rich_text(slide, runs, x, y, w, h, *, size=16, color=INK, valign=MSO_ANCHOR.TOP):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    for item in runs:
        text, bold, item_color, font = item
        r = p.add_run()
        r.text = text
        r.font.name = font or "Arial"
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = rgb(item_color or color)
    return shape


def add_bullets(
    slide,
    items,
    x,
    y,
    w,
    h,
    *,
    size=17,
    color=INK,
    accent=BLUE,
    gap=7,
):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.margin_left = Inches(0.03)
    tf.margin_right = Inches(0.03)
    tf.margin_top = Inches(0.03)
    tf.margin_bottom = Inches(0.03)
    for idx, item in enumerate(items):
        if isinstance(item, tuple):
            head, rest = item
        else:
            head, rest = "", item
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.level = 0
        p.text = ""
        bullet = p.add_run()
        bullet.text = "●  "
        bullet.font.name = "Arial"
        bullet.font.size = Pt(max(size - 3, 10))
        bullet.font.color.rgb = rgb(accent)
        if head:
            r = p.add_run()
            r.text = head
            r.font.name = "Arial"
            r.font.size = Pt(size)
            r.font.bold = True
            r.font.color.rgb = rgb(color)
        r = p.add_run()
        r.text = rest
        r.font.name = "Arial"
        r.font.size = Pt(size)
        r.font.color.rgb = rgb(color)
    return shape


def add_card(slide, title, body, x, y, w, h, *, accent=BLUE, fill=WHITE, body_size=14):
    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = rgb(fill)
    card.line.color.rgb = rgb(LIGHT_GRAY)
    card.line.width = Pt(1.1)
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(0.09), Inches(h)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = rgb(accent)
    bar.line.fill.background()
    add_text(slide, title, x + 0.22, y + 0.14, w - 0.35, 0.34, size=17, color=accent, bold=True)
    add_text(slide, body, x + 0.22, y + 0.56, w - 0.35, h - 0.68, size=body_size, color=INK)
    return card


def add_badge(slide, text, x, y, w, *, fill=DEEP_BLUE, color=WHITE):
    return add_text(
        slide,
        text,
        x,
        y,
        w,
        0.32,
        size=11,
        color=color,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
        margin=0.02,
        fill=fill,
        line=fill,
        radius=True,
    )


def add_arrow(slide, x1, y1, x2, y2, *, color=BLUE, width=2.0):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    line.line.color.rgb = rgb(color)
    line.line.width = Pt(width)
    line.line.end_arrowhead = True
    return line


def add_command_placeholder(slide, title, command, crop, x, y, w, h):
    box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    box.fill.solid()
    box.fill.fore_color.rgb = rgb(PALE_ORANGE)
    box.line.color.rgb = rgb(ORANGE)
    box.line.width = Pt(1.5)
    box.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    add_text(slide, "ẢNH CẦN BỔ SUNG", x + 0.18, y + 0.12, w - 0.36, 0.25, size=11, color=RED, bold=True)
    add_text(slide, title, x + 0.18, y + 0.42, w - 0.36, 0.45, size=16, color=NAVY, bold=True)
    add_text(slide, "Chạy:", x + 0.18, y + 0.95, 0.55, 0.25, size=11, color=GRAY, bold=True)
    add_text(
        slide,
        command,
        x + 0.18,
        y + 1.20,
        w - 0.36,
        max(0.75, h - 2.05),
        size=9.5,
        color=INK,
        font="DejaVu Sans Mono",
        fill=WHITE,
        line=LIGHT_GRAY,
        radius=True,
        margin=0.09,
        autosize=True,
    )
    add_text(slide, "Khung cần chụp: " + crop, x + 0.18, y + h - 0.56, w - 0.36, 0.38, size=10.5, color=GRAY, italic=True)
    return box


def add_table(slide, headers, rows, x, y, widths, row_h=0.45, font_size=12):
    total_w = sum(widths)
    current_y = y
    current_x = x
    for header, width in zip(headers, widths):
        add_text(
            slide,
            header,
            current_x,
            current_y,
            width,
            row_h,
            size=font_size,
            color=WHITE,
            bold=True,
            align=PP_ALIGN.CENTER,
            valign=MSO_ANCHOR.MIDDLE,
            fill=DEEP_BLUE,
            line=WHITE,
            margin=0.04,
        )
        current_x += width
    current_y += row_h
    for r_idx, row in enumerate(rows):
        current_x = x
        fill = WHITE if r_idx % 2 == 0 else PAPER
        for c_idx, (value, width) in enumerate(zip(row, widths)):
            align = PP_ALIGN.LEFT if c_idx == 0 else PP_ALIGN.CENTER
            add_text(
                slide,
                str(value),
                current_x,
                current_y,
                width,
                row_h,
                size=font_size,
                color=INK,
                bold=(c_idx == 0),
                align=align,
                valign=MSO_ANCHOR.MIDDLE,
                fill=fill,
                line=LIGHT_GRAY,
                margin=0.06,
                autosize=True,
            )
            current_x += width
        current_y += row_h
    return total_w, current_y - y


def add_timeline(slide, phases, x, y, w, h, *, label_width=0.85):
    total = sum(p[2] for p in phases)
    add_text(slide, "Phase", x, y, label_width, h, size=12, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=NAVY, line=NAVY)
    cur = x + label_width
    usable = w - label_width
    palette = [BLUE, CYAN, GREEN, ORANGE, DEEP_BLUE, "7D5BA6", "667788"]
    for idx, (name, core, weight) in enumerate(phases):
        bw = usable * weight / total
        add_text(
            slide,
            f"{name}\n{core}",
            cur,
            y,
            bw,
            h,
            size=9.5,
            color=WHITE,
            bold=True,
            align=PP_ALIGN.CENTER,
            valign=MSO_ANCHOR.MIDDLE,
            fill=palette[idx % len(palette)],
            line=WHITE,
            margin=0.02,
            autosize=True,
        )
        cur += bw


class DeckBuilder:
    def __init__(self):
        if not TEMPLATE.exists():
            raise FileNotFoundError(TEMPLATE)
        self.prs = Presentation(str(TEMPLATE))
        self.chrome = [copy.deepcopy(shape.element) for shape in list(self.prs.slides[1].shapes)[:5]]
        for element in self.chrome:
            for node in element.iter():
                if node.tag.endswith("}t") and (node.text or "").strip() == "Nhiệm vụ":
                    node.text = ""
        self.blank_layout = self.prs.slide_layouts[6]
        self.slide_no = 1
        self._prepare_title_slide()
        self.end_slide = self.prs.slides[3]
        # Keep the two sample slides until all new slides have been allocated.
        # Removing them here would let python-pptx reuse slide3.xml/slide4.xml
        # while the original parts are still present in the package, producing
        # duplicate ZIP members on save.
        self.sample_slides = [self.prs.slides[1], self.prs.slides[2]]

    def _prepare_title_slide(self):
        slide = self.prs.slides[0]
        for shape in iter_shapes(slide.shapes):
            if not getattr(shape, "has_text_frame", False):
                continue
            if shape.text.strip() == "Báo cáo tiến độ":
                set_shape_text(
                    shape,
                    "NGHIÊN CỨU FLOW THỰC THI ELF\nTRÊN PULP: GVSoC VÀ RTL",
                    size=30,
                    color=WHITE,
                )
                for paragraph in shape.text_frame.paragraphs:
                    paragraph.alignment = PP_ALIGN.CENTER
            elif shape.text.strip().startswith("Thực hiện"):
                set_shape_text(
                    shape,
                    "Thực hiện\t: Phạm Hùng Hòa\n"
                    "                  Phạm Chí Dũng\n"
                    "                  Đỗ Xuân Hào\n"
                    "GVHD\t: Thầy Nguyễn Đức Minh\n"
                    "                  Cô Hoàng Phương Chi\n\n"
                    "Ngày báo cáo: 03/10/2026",
                    size=16.5,
                    color=NAVY,
                )

    def content_slide(self, title, section="NGHIÊN CỨU GVSoC / RTL", backup=False):
        slide = self.prs.slides.add_slide(self.blank_layout)
        for element in self.chrome:
            slide.shapes._spTree.insert_element_before(copy.deepcopy(element), "p:extLst")
        add_text(slide, title, 1.32, 0.09, 8.55, 0.56, size=23, color=WHITE, bold=True,
                 valign=MSO_ANCHOR.MIDDLE, margin=0.02, autosize=True)
        add_text(slide, section, 0.46, 7.08, 4.5, 0.23, size=9.5, color=GRAY, bold=True)
        self.slide_no += 1
        page_label = f"{self.slide_no}"
        if backup:
            page_label = f"BACKUP · {self.slide_no}"
        add_text(slide, page_label, 8.90 if backup else 9.75, 7.05,
                 1.10 if backup else 0.28, 0.28, size=10, color=GRAY,
                 bold=backup, align=PP_ALIGN.RIGHT)
        return slide

    def finish(self):
        for sample in self.sample_slides:
            remove_slide(self.prs, sample)
        # Move the original ending slide to the end and customize its text.
        end_id = None
        for item in self.prs.slides._sldIdLst:
            if int(item.id) == self.end_slide.slide_id:
                end_id = item
                break
        if end_id is not None:
            self.prs.slides._sldIdLst.remove(end_id)
            self.prs.slides._sldIdLst.append(end_id)
        for shape in iter_shapes(self.end_slide.shapes):
            if not getattr(shape, "has_text_frame", False):
                continue
            if shape.text.strip() == "Thank You !":
                set_shape_text(shape, "THANK YOU!\nQ & A", size=34, color="99CCFF")
            elif shape.text.strip() == "www.themegallery.com":
                set_shape_text(shape, "PULP · GVSoC · RTL", size=17, color=WHITE)
            elif shape.text.strip().isdigit():
                set_shape_text(shape, str(len(self.prs.slides)), size=10, color=GRAY)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        self.prs.core_properties.title = "Nghiên cứu flow thực thi ELF trên PULP: GVSoC và RTL"
        self.prs.core_properties.subject = "Báo cáo nghiên cứu và kết quả mô phỏng ngày 03/10/2026"
        self.prs.core_properties.author = "Phạm Hùng Hòa; Phạm Chí Dũng; Đỗ Xuân Hào"
        self.prs.core_properties.keywords = "PULP, GVSoC, RTL, Questa, ELF, instruction trace, waveform"
        self.prs.save(str(OUTPUT))


def build():
    d = DeckBuilder()

    # 2 — Problem
    s = d.content_slide("Bài toán cần giải quyết", "BỐI CẢNH VÀ MỤC TIÊU")
    add_text(s, "Từ chương trình C đến hoạt động phần cứng", 0.55, 1.05, 9.5, 0.48,
             size=25, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    questions = [
        ("01", "Một file C/ELF được thực thi trong PULP như thế nào?"),
        ("02", "Có thể chạy đúng cùng một ELF trên GVSoC và RTL không?"),
        ("03", "Làm sao nối lệnh CPU với giao dịch interconnect và waveform?"),
    ]
    for idx, (num, text) in enumerate(questions):
        y = 1.85 + idx * 1.25
        add_text(s, num, 0.85, y, 0.75, 0.75, size=22, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE,
                 fill=[BLUE, CYAN, GREEN][idx], line=[BLUE, CYAN, GREEN][idx], radius=True)
        add_text(s, text, 1.85, y, 7.85, 0.75, size=20, color=INK, bold=True,
                 valign=MSO_ANCHOR.MIDDLE, fill=WHITE, line=LIGHT_GRAY, radius=True)
    add_text(s, "Đầu ra mong muốn: một chuỗi bằng chứng có thể kiểm tra lại — ELF → trace → transaction → waveform → kết quả.",
             0.85, 5.85, 8.85, 0.72, size=16.5, color=DEEP_BLUE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE,
             fill=SKY, line=CYAN, radius=True)

    # 3 — Goals
    s = d.content_slide("Mục tiêu nghiên cứu", "BỐI CẢNH VÀ MỤC TIÊU")
    goals = [
        ("Workload đại diện", "Tạo chương trình vừa đủ để quan sát FC, cluster, TCDM, DMA và peripheral."),
        ("Một ELF duy nhất", "Khóa danh tính bằng SHA-256 trước khi chạy hai backend."),
        ("Hai lớp quan sát", "Instruction trace cho software; waveform cho hoạt động RTL tự trị."),
        ("Trực quan hóa", "Timeline, replay và liên kết đến raw trace/VCD trong một viewer độc lập."),
        ("Tái lập được", "Lưu command, log, trace, VCD và hướng dẫn từng bước."),
        ("Diễn giải đúng", "Không đánh đồng mô hình kiến trúc với mô phỏng cycle-accurate."),
    ]
    for idx, (title, body) in enumerate(goals):
        col, row = idx % 2, idx // 2
        add_card(s, title, body, 0.55 + col * 5.0, 1.08 + row * 1.80, 4.60, 1.48,
                 accent=[BLUE, CYAN, GREEN, ORANGE, DEEP_BLUE, "7D5BA6"][idx], body_size=13.2)

    # 4 — Architecture
    s = d.content_slide("Tổng quan kiến trúc PULP quan sát trong demo", "KIẾN TRÚC VÀ PHƯƠNG PHÁP")
    if ARCH.exists():
        s.shapes.add_picture(str(ARCH), Inches(0.55), Inches(1.05), width=Inches(9.55))
        add_badge(s, "CLUSTER: PE0…PE7 · TCDM · MCHAN", 0.72, 1.42, 3.25, fill=GREEN)
        add_badge(s, "SoC: FC · L2 · UDMA · UART", 6.25, 1.42, 3.20, fill=BLUE)
        add_text(s, "Sơ đồ được GVSoC tự sinh; slide phân tích sẽ chỉ theo các đường dữ liệu liên quan đến workload.",
                 0.7, 6.42, 9.25, 0.42, size=12.5, color=GRAY, italic=True,
                 align=PP_ALIGN.CENTER, fill=WHITE, line=LIGHT_GRAY, radius=True)
    else:
        add_command_placeholder(s, "Sơ đồ kiến trúc GVSoC", "Mở: report/gvsoc_manual_run/step2/architecture.png",
                                "toàn bộ chip; nhấn mạnh FC/L2/cluster/UDMA/UART", 0.7, 1.2, 9.2, 5.3)

    # 5 — Roles
    s = d.content_slide("Vai trò của GVSoC, RTL và HTML Viewer", "KIẾN TRÚC VÀ PHƯƠNG PHÁP")
    add_card(s, "GVSoC", "Mô hình kiến trúc nhanh\n\n• Chạy software\n• Sinh reference trace\n• Kiểm tra chức năng sớm",
             0.50, 1.15, 3.05, 4.65, accent=CYAN, fill=SKY, body_size=16)
    add_card(s, "RTL / Questa", "Mô phỏng hiện thực phần cứng\n\n• Timing và handshake\n• Clock/reset/event\n• Waveform từng tín hiệu",
             3.80, 1.15, 3.05, 4.65, accent=GREEN, fill=PALE_GREEN, body_size=16)
    add_card(s, "HTML Viewer", "Lớp tổng hợp và replay\n\n• Hai timeline\n• Instruction replay\n• Liên kết raw trace/VCD",
             7.10, 1.15, 3.05, 4.65, accent=ORANGE, fill=PALE_ORANGE, body_size=16)
    add_text(s, "GVSoC ≠ RTL  |  Viewer ≠ simulator  |  Waveform mới là bằng chứng về signal-level behavior",
             0.75, 6.15, 9.20, 0.58, size=15, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=WHITE, line=NAVY, radius=True)

    # 6 — flow
    s = d.content_slide("Flow nghiên cứu tổng thể", "KIẾN TRÚC VÀ PHƯƠNG PHÁP")
    xs = [0.55, 2.22, 4.04, 6.04, 8.26]
    labels = [("C source", BLUE), ("ELF", NAVY), ("Hai backend", CYAN), ("Artifacts", GREEN), ("Phân tích", ORANGE)]
    for idx, ((label, color), x) in enumerate(zip(labels, xs)):
        add_text(s, label, x, 1.28, 1.45 if idx < 4 else 1.80, 0.68, size=16, color=WHITE,
                 bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE,
                 fill=color, line=color, radius=True)
        if idx < 4:
            add_arrow(s, x + 1.47, 1.62, xs[idx + 1] - 0.10, 1.62, color=MID_GRAY, width=1.6)
    add_text(s, "Build + DWARF", 1.02, 2.28, 1.60, 0.35, size=12, color=GRAY, align=PP_ALIGN.CENTER)
    add_text(s, "SHA-256", 2.18, 2.76, 1.55, 0.48, size=15, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=SKY, line=CYAN, radius=True)
    add_arrow(s, 2.95, 2.00, 2.95, 2.70, color=CYAN)
    add_card(s, "GVSoC", "stdout + FC/PE instruction trace", 3.65, 2.35, 2.55, 1.22, accent=CYAN, body_size=12.5)
    add_card(s, "RTL / Questa", "transcript + trace + selected VCD", 3.65, 4.12, 2.55, 1.22, accent=GREEN, body_size=12.5)
    add_arrow(s, 4.73, 1.98, 4.73, 2.29, color=CYAN)
    add_arrow(s, 4.73, 1.98, 4.73, 4.05, color=GREEN)
    add_card(s, "Đối chiếu", "Kết quả chức năng\nPhase / event\nTrace ↔ waveform", 7.05, 3.05, 2.55, 2.05, accent=ORANGE, body_size=14)
    add_arrow(s, 6.25, 2.95, 7.00, 3.65, color=CYAN)
    add_arrow(s, 6.25, 4.72, 7.00, 4.40, color=GREEN)
    add_text(s, "Nguyên tắc: không build lại ELF giữa hai lượt chạy.", 1.0, 6.25, 8.7, 0.48,
             size=15.5, color=RED, bold=True, align=PP_ALIGN.CENTER,
             valign=MSO_ANCHOR.MIDDLE, fill=PALE_RED, line=RED, radius=True)

    # 7 — principles
    s = d.content_slide("Nguyên tắc đối chiếu hai hệ thống", "KIẾN TRÚC VÀ PHƯƠNG PHÁP")
    principles = [
        ("1", "Cùng ELF", "Hash phải giống trước và sau hai lượt chạy."),
        ("2", "So chức năng trước", "PASS/status/checksum/UART là điều kiện nghiệm thu."),
        ("3", "Không lockstep", "GVSoC và RTL có mô hình timing/runtime khác nhau."),
        ("4", "Đồng bộ theo phase", "Dùng main, phase function, MMIO và event làm anchor."),
        ("5", "Trace + waveform", "CPU trace không mô tả các beat DMA chạy tự trị."),
    ]
    for idx, (num, head, body) in enumerate(principles):
        y = 1.10 + idx * 1.08
        add_text(s, num, 0.70, y, 0.62, 0.62, size=19, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE,
                 fill=[BLUE, CYAN, GREEN, ORANGE, DEEP_BLUE][idx], line=[BLUE, CYAN, GREEN, ORANGE, DEEP_BLUE][idx], radius=True)
        add_rich_text(s, [(head + " — ", True, NAVY, None), (body, False, INK, None)],
                      1.58, y + 0.02, 8.30, 0.58, size=17, valign=MSO_ANCHOR.MIDDLE)
    add_text(s, "So sánh đúng câu hỏi ở đúng abstraction level.", 2.0, 6.35, 6.7, 0.42,
             size=17, color=WHITE, bold=True, align=PP_ALIGN.CENTER,
             valign=MSO_ANCHOR.MIDDLE, fill=NAVY, line=NAVY, radius=True)

    # 8 — flow_demo
    s = d.content_slide("Workload flow_demo: bảy giai đoạn", "THỬ NGHIỆM 1 · FC + CLUSTER + DMA")
    phases = [
        ("P0\nFC + L2", "FC", 1), ("P1\nTimer + ALU", "FC", 1),
        ("P2\nLaunch cluster", "FC", 1), ("P3\n8 PE ghi L1", "PE0…7", 1),
        ("P4\nBarrier", "PE0…7", 1), ("P5\nDMA round-trip", "PE0", 1),
        ("P6\nSummary", "FC", 1),
    ]
    add_timeline(s, phases, 0.55, 1.18, 9.55, 0.92, label_width=0.70)
    blocks = [
        ("L2", "checksum", BLUE), ("FC", "timer + ALU", CYAN),
        ("CLUSTER", "fork 8 PE", GREEN), ("TCDM", "parallel write", GREEN),
        ("EVENT", "barrier", ORANGE), ("MCHAN", "L2→L1→L2", DEEP_BLUE),
        ("FC", "verify PASS", BLUE),
    ]
    for idx, (head, body, color) in enumerate(blocks):
        x = 0.56 + idx * 1.36
        add_text(s, head, x, 2.68, 1.14, 0.48, size=13, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=color, line=color, radius=True)
        add_text(s, body, x, 3.22, 1.14, 0.68, size=11, color=INK, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=WHITE, line=LIGHT_GRAY, radius=True)
        if idx < len(blocks) - 1:
            add_arrow(s, x + 1.15, 3.02, x + 1.34, 3.02, color=MID_GRAY, width=1.4)
    add_card(s, "Vì sao chọn workload này?", "Một chương trình nhưng chạm đủ các lớp: software FC, hand-off cluster, song song 8 PE, TCDM, event/barrier và DMA tự trị.",
             0.75, 4.55, 9.05, 1.30, accent=ORANGE, body_size=15)
    add_text(s, "Kết quả chức năng: checksum và dữ liệu DMA khớp; FLOW|6|RESULT|PASS|errors=0",
             1.10, 6.15, 8.45, 0.48, size=14.5, color=GREEN, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=PALE_GREEN, line=GREEN, radius=True)

    # 9 — results + waveform placeholder
    s = d.content_slide("Kết quả flow_demo: trace, cycle và waveform", "THỬ NGHIỆM 1 · FC + CLUSTER + DMA")
    rows = [
        ("P0 · FC + L2", "12,224", "5,761", "2.122×"),
        ("P1 · Timer + ALU", "15,598", "7,143", "2.183×"),
        ("P2 · Launch/wait", "191,663", "175,519", "1.092×"),
        ("P3 · 8 PE ghi L1", "44,674", "43,317", "1.031×"),
        ("P4 · Barrier", "11,397", "10,991", "1.037×"),
        ("P5 · DMA", "20,025", "19,493", "1.027×"),
        ("P6 · Summary", "11,989", "5,559", "2.157×"),
    ]
    add_table(s, ["Phase", "GVSoC", "RTL", "Tỷ lệ"], rows, 0.48, 1.08,
              [2.10, 1.05, 1.05, 0.90], row_h=0.48, font_size=11.2)
    add_command_placeholder(
        s,
        "Waveform phase 5 — DMA tự trị",
        "cd report/gvsoc_demo/rtl/wave\ngtkwave flow_demo.gtkw",
        "s_dmac_busy; TCDM req/gnt; AXI AR/R và AW/W handshake trong phase 5",
        5.05, 1.08, 5.08, 4.55,
    )
    add_text(s, "Trace thô: 207,451 lệnh  |  Viewer giữ 7,344 lệnh trọng tâm  |  VCD chọn lọc: 24 nhóm signal",
             0.72, 5.95, 9.25, 0.58, size=13.5, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=SKY, line=CYAN, radius=True)
    add_text(s, "Nhận xét: phần cluster gần nhau; phần FC có nhiều printf/runtime nên chênh khoảng 2.1×.",
             0.72, 6.57, 9.25, 0.34, size=12.5, color=GRAY, italic=True, align=PP_ALIGN.CENTER)

    # 10 — UART workloads
    s = d.content_slide("Hai workload UART ZCU104", "THỬ NGHIỆM 2 · FC + UDMA UART")
    add_card(s, "zcu104_uart_smoke", "main → printf → nhiều lớp formatted I/O\n\nGVSoC FC: 5,397 lệnh\nRTL FC: 35,405 lệnh\nKết quả: 23 byte đúng",
             0.62, 1.22, 4.55, 4.25, accent=CYAN, fill=SKY, body_size=16)
    add_card(s, "zcu104_uart_direct", "main → uart_write(0, buffer, 23)\n\nGVSoC FC: 4,634 lệnh\nRTL FC: 22,957 lệnh\nKết quả: 23 byte đúng",
             5.48, 1.22, 4.55, 4.25, accent=GREEN, fill=PALE_GREEN, body_size=16)
    add_text(s, "Hello PULP from ZCU104\\n", 2.05, 5.78, 6.58, 0.62, size=21,
             color=WHITE, bold=True, font="DejaVu Sans Mono", align=PP_ALIGN.CENTER,
             valign=MSO_ANCHOR.MIDDLE, fill=NAVY, line=NAVY, radius=True)
    add_text(s, "Cả hai chỉ dùng FC + L2 + UDMA UART; cluster/PE/TCDM/MCHAN không hoạt động.",
             1.35, 6.48, 8.0, 0.34, size=12.5, color=GRAY, italic=True, align=PP_ALIGN.CENTER)

    # 11 — direct flow
    s = d.content_slide("Luồng zcu104_uart_direct", "THỬ NGHIỆM 2 · FC + UDMA UART")
    flow = [
        ("Runtime boot", "_start / pos_init_start", DEEP_BLUE),
        ("uart_open", "clock + setup", BLUE),
        ("main", "buffer=0x1c000820\nsize=23", CYAN),
        ("UDMA TX", "đọc L2 tự trị", GREEN),
        ("UART", "serialize 23 byte", ORANGE),
        ("exit(0)", "status=0", NAVY),
    ]
    for idx, (head, body, color) in enumerate(flow):
        x = 0.42 + idx * 1.69
        add_text(s, head, x, 1.62, 1.42, 0.58, size=14, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=color, line=color, radius=True)
        add_text(s, body, x, 2.25, 1.42, 0.78, size=10.5, color=INK, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=WHITE, line=LIGHT_GRAY, radius=True,
                 autosize=True)
        if idx < len(flow) - 1:
            add_arrow(s, x + 1.43, 2.00, x + 1.66, 2.00, color=MID_GRAY, width=1.5)
    add_text(s, "CPU chủ động", 0.62, 3.48, 4.42, 0.38, size=13, color=BLUE, bold=True,
             align=PP_ALIGN.CENTER, fill=SKY, line=CYAN, radius=True)
    add_text(s, "Phần cứng tự trị", 5.12, 3.48, 3.18, 0.38, size=13, color=GREEN, bold=True,
             align=PP_ALIGN.CENTER, fill=PALE_GREEN, line=GREEN, radius=True)
    add_text(s, "CPU tiếp tục", 8.40, 3.48, 1.64, 0.38, size=13, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, fill=LIGHT_GRAY, line=NAVY, radius=True)
    add_card(s, "Điểm cần quan sát", "Instruction trace chỉ cho thấy CPU ghi cấu hình và poll. Các byte được UDMA đọc từ L2 và UART dịch nối tiếp phải được xác nhận bằng waveform RTL.",
             0.75, 4.42, 9.10, 1.35, accent=ORANGE, body_size=15)
    add_text(s, "Đây là chuỗi diễn giải xuyên suốt: instruction → MMIO → autonomous hardware → event/status → instruction.",
             0.95, 6.15, 8.70, 0.52, size=14.5, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=WHITE, line=NAVY, radius=True)

    # 12 — MMIO
    s = d.content_slide("Bằng chứng instruction trace và MMIO", "THỬ NGHIỆM 2 · FC + UDMA UART")
    rows = [
        ("UART setup", "0x1a1020a4", "0x00560306", "bật/cấu hình UART"),
        ("TX address", "0x1a102090", "0x1c000820", "buffer 23 byte tại L2"),
        ("TX size", "0x1a102094", "0x00000017", "khởi động transfer"),
        ("SoC exit", "0x1a1040a0", "0x80000000", "exit(0) / status PASS"),
    ]
    add_table(s, ["Sự kiện", "Địa chỉ", "Giá trị", "Ý nghĩa"], rows,
              0.55, 1.20, [1.55, 1.85, 1.85, 4.25], row_h=0.63, font_size=13)
    add_text(s, "CPU", 0.78, 4.72, 1.05, 0.60, size=17, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=BLUE, line=BLUE, radius=True)
    add_text(s, "MMIO / interconnect", 2.35, 4.72, 2.25, 0.60, size=15, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=CYAN, line=CYAN, radius=True)
    add_text(s, "UDMA UART TX", 5.10, 4.72, 1.85, 0.60, size=15, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=GREEN, line=GREEN, radius=True)
    add_text(s, "UART pad", 7.48, 4.72, 1.45, 0.60, size=15, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=ORANGE, line=ORANGE, radius=True)
    add_arrow(s, 1.85, 5.02, 2.30, 5.02)
    add_arrow(s, 4.62, 5.02, 5.05, 5.02)
    add_arrow(s, 6.98, 5.02, 7.43, 5.02)
    add_text(s, "23 bytes", 4.02, 5.63, 2.60, 0.42, size=15, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, fill=SKY, line=CYAN, radius=True)
    add_text(s, "Trace xác nhận lệnh ghi; waveform xác nhận request/handshake và serial bitstream.",
             1.25, 6.28, 8.15, 0.46, size=14, color=GRAY, italic=True, align=PP_ALIGN.CENTER)

    # 13 — timing
    s = d.content_slide("Đối chiếu GVSoC và RTL", "KẾT QUẢ VÀ DIỄN GIẢI")
    add_text(s, "zcu104_uart_direct — timeline từ _start", 0.62, 1.08, 5.0, 0.35, size=15, color=NAVY, bold=True)
    max_t = 1166.590
    for label, dur, y, color in [("GVSoC", 295.187, 1.62, CYAN), ("RTL", 1166.590, 2.38, GREEN)]:
        add_text(s, label, 0.62, y, 0.78, 0.48, size=13, color=INK, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_text(s, f"{dur:.3f} µs", 1.50, y, 7.65 * dur / max_t, 0.48, size=11, color=WHITE, bold=True,
                 align=PP_ALIGN.RIGHT, valign=MSO_ANCHOR.MIDDLE, fill=color, line=color, radius=True, margin=0.06)
    add_text(s, "Cùng thang thời gian tuyệt đối; GVSoC chiếm 25.3% độ dài RTL.",
             1.48, 3.02, 7.70, 0.32, size=12, color=GRAY, italic=True)
    rows = [
        ("ELF", "cùng SHA-256", "cùng SHA-256"),
        ("UART output", "23 byte đúng", "23 byte đúng"),
        ("FC instruction", "4,634", "22,957"),
        ("Cluster", "không chạy", "không chạy"),
        ("Mức timing", "model kiến trúc", "signal/cycle RTL"),
    ]
    add_table(s, ["Tiêu chí", "GVSoC", "RTL"], rows, 0.72, 3.72, [2.35, 3.20, 3.20], row_h=0.48, font_size=12)
    add_text(s, "Kết luận: đồng nhất chức năng, không đồng nhất số lệnh hoặc cycle.",
             1.15, 6.43, 8.35, 0.46, size=15, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=NAVY, line=NAVY, radius=True)

    # 14 — Viewer
    s = d.content_slide("HTML Flow Viewer đã xây dựng", "TRỰC QUAN HÓA")
    add_command_placeholder(
        s,
        "Ảnh giao diện viewer — timeline + replay",
        "firefox report/zcu104_uart_direct/flow_viewer.html",
        "thanh thống kê, hai lane GVSoC/RTL, nút Play và 8–12 dòng instruction",
        0.55, 1.05, 6.25, 5.65,
    )
    add_card(s, "Viewer làm được", "• Hiển thị hai timeline\n• Replay instruction\n• Đồng bộ theo phase\n• Chọn tốc độ Play\n• Mở raw trace và VCD",
             7.05, 1.05, 3.05, 2.50, accent=GREEN, fill=PALE_GREEN, body_size=13.5)
    add_card(s, "Viewer không làm", "• Không chạy GVSoC/RTL\n• Không chứng minh signal\n• Không đồng bộ lockstep\n• Không thay thế GTKWave",
             7.05, 3.80, 3.05, 2.28, accent=RED, fill=PALE_RED, body_size=13.5)
    add_text(s, "Vai trò đúng: cầu nối giữa software trace, simulation time và artifact RTL.",
             6.92, 6.34, 3.30, 0.48, size=12.5, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=SKY, line=CYAN, radius=True)

    # 15 — Combined method
    s = d.content_slide("Cách đọc trace cùng waveform RTL", "TRỰC QUAN HÓA")
    chain = [
        ("1", "Instruction", "CPU đang làm gì?", BLUE),
        ("2", "MMIO / memory", "địa chỉ + giá trị", CYAN),
        ("3", "HW tự trị", "UDMA / DMA / UART", GREEN),
        ("4", "Status / event", "busy, irq, wakeup", ORANGE),
        ("5", "Instruction", "CPU tiếp tục", NAVY),
    ]
    for idx, (num, head, body, color) in enumerate(chain):
        x = 0.50 + idx * 2.02
        add_text(s, num, x + 0.54, 1.15, 0.48, 0.48, size=15, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=color, line=color, radius=True)
        add_text(s, head, x, 1.78, 1.57, 0.56, size=14, color=color, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=WHITE, line=color, radius=True)
        add_text(s, body, x, 2.41, 1.57, 0.55, size=10.5, color=INK, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=PAPER, line=LIGHT_GRAY, radius=True)
        if idx < len(chain) - 1:
            add_arrow(s, x + 1.59, 2.06, x + 1.99, 2.06, color=MID_GRAY, width=1.4)
    add_command_placeholder(
        s,
        "Waveform UART — nối transaction với bitstream",
        "cd report/zcu104_uart_direct/rtl/wave\ngtkwave zcu104_uart_direct.gtkw",
        "w_uart_rx; FC fetch; reset; exit_status; zoom đủ một ký tự UART",
        0.70, 3.55, 4.70, 2.75,
    )
    add_card(s, "Cách thuyết trình một sự kiện", "① Chỉ PC/hàm trong trace\n② Chỉ write MMIO tương ứng\n③ Highlight khối trên kiến trúc\n④ Chỉ handshake/signal trên wave\n⑤ Kết luận bằng output/status",
             5.72, 3.55, 4.20, 2.75, accent=DEEP_BLUE, body_size=14)
    add_text(s, "Không nói “lệnh chạy qua mọi khối”; nói “lệnh cấu hình khối, sau đó phần cứng tự hoạt động”.",
             0.85, 6.48, 9.00, 0.42, size=13, color=RED, bold=True, align=PP_ALIGN.CENTER)

    # 16 — issues
    s = d.content_slide("Vấn đề gặp phải và cách xử lý", "BÀI HỌC KỸ THUẬT")
    rows = [
        ("UART GVSoC ra byte nhiễu", "checker mặc định 115200", "đặt 825000 baud"),
        ("RTL log toàn warning", "transcript Questa rất dài", "lọc result; giữ full log riêng"),
        ("ELF ngoài không có phase", "không có phaseN_* symbol", "suy luận _start/main/exit"),
        ("Hai timeline khác độ dài", "timing model khác nhau", "cùng thang tuyệt đối + phase map"),
        ("Play kéo trang", "scrollIntoView()", "chỉ scroll trong trace panel"),
        ("Trace không thấy DMA", "hardware hoạt động tự trị", "đọc thêm VCD handshake"),
    ]
    add_table(s, ["Hiện tượng", "Nguyên nhân", "Cách xử lý"], rows,
              0.50, 1.12, [3.10, 3.05, 3.55], row_h=0.72, font_size=12.2)
    add_text(s, "Bài học chung: một log đơn lẻ hiếm khi đủ — cần chuỗi bằng chứng nhiều lớp.",
             0.90, 5.82, 8.95, 0.58, size=16, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=NAVY, line=NAVY, radius=True)
    add_text(s, "Ba lớp kiểm tra: functional output · architectural trace · RTL signal behavior",
             1.35, 6.52, 8.05, 0.32, size=13, color=GRAY, italic=True, align=PP_ALIGN.CENTER)

    # 17 — conclusion
    s = d.content_slide("Kết luận và hướng phát triển", "KẾT LUẬN")
    add_card(s, "Đã hoàn thành", "✓ Một ELF chạy trên GVSoC và RTL\n✓ Kết quả chức năng được xác minh\n✓ Có instruction trace + VCD\n✓ Có viewer và tài liệu tái lập\n✓ Có ba workload bổ trợ nhau",
             0.58, 1.10, 4.60, 4.68, accent=GREEN, fill=PALE_GREEN, body_size=16)
    add_card(s, "Tiếp theo", "1. Bổ sung signal UDMA/interconnect\n2. Chụp waveform theo sự kiện\n3. Animate đường dữ liệu trên kiến trúc\n4. Tự động hóa nhập ELF mới\n5. Đóng gói demo cho báo cáo",
             5.48, 1.10, 4.60, 4.68, accent=ORANGE, fill=PALE_ORANGE, body_size=16)
    add_text(s, "GVSoC cho reference kiến trúc nhanh; RTL cho bằng chứng hiện thực; viewer giúp nối hai góc nhìn.",
             0.78, 6.12, 9.18, 0.62, size=17, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=NAVY, line=NAVY, radius=True)

    # Backup 1 — commands
    s = d.content_slide("Phụ lục A — Các lệnh tái lập chính", "BACKUP", backup=True)
    commands = [
        ("GVSoC", "source sw/gvsoc/env.sh\ngvsoc --target=pulp-open --binary=<ELF> \\\n+  --trace=chip/soc/fc/insn:fc.log run"),
        ("RTL", "APP_DIR=\"$PWD/sw/flow_demo\" SIM_TIMEOUT=\"80 ms\" \\\n+  PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \\\n+  sw/full_system/run_sim.sh all run"),
        ("Viewer", "/usr/bin/python3 sw/flow_demo/flow_visualize.py \\\n+  --elf <ELF> --gvsoc-fc <fc.log> --rtl-dir <raw> \\\n+  --output <flow_viewer.html>"),
    ]
    for idx, (head, cmd) in enumerate(commands):
        y = 1.10 + idx * 1.77
        add_badge(s, head, 0.55, y, 1.20, fill=[CYAN, GREEN, ORANGE][idx])
        add_text(s, cmd, 1.95, y, 8.12, 1.35, size=11, color=INK, font="DejaVu Sans Mono",
                 fill=PAPER, line=LIGHT_GRAY, radius=True, margin=0.12, autosize=True)
    add_text(s, "Chi tiết đầy đủ: report/gvsoc_demo/HUONG_DAN_TUNG_BUOC.md",
             1.1, 6.47, 8.55, 0.38, size=13, color=NAVY, bold=True, align=PP_ALIGN.CENTER)

    # Backup 2 — artifacts
    s = d.content_slide("Phụ lục B — Artifact bàn giao", "BACKUP", backup=True)
    artifact_rows = [
        ("flow_demo", "report/gvsoc_demo/", "viewer, log, trace, VCD, docs"),
        ("UART smoke", "report/zcu104_uart_smoke/", "ELF snapshot, viewer, UART/VCD"),
        ("UART direct", "report/zcu104_uart_direct/", "ELF snapshot, viewer, UART/VCD"),
        ("Phương pháp", "report/GVSOC_RTL_VISUAL_ANALYSIS_APPROACH.md", "storyboard + signal list"),
        ("Kiểm tra UART", "report/ZCU104_UART_RECHECK.md", "baud, status, integrity"),
        ("Báo cáo DOCX", "doc/gvsoc_demo/research/", "tài liệu nghiên cứu đầy đủ"),
    ]
    add_table(s, ["Nhóm", "Đường dẫn", "Nội dung"], artifact_rows,
              0.45, 1.15, [1.70, 5.10, 3.00], row_h=0.72, font_size=11.5)
    add_text(s, "Mỗi report giữ raw artifact; viewer chỉ là lớp đọc/lọc, không thay đổi dữ liệu gốc.",
             0.8, 6.18, 9.1, 0.55, size=15, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=NAVY, line=NAVY, radius=True)

    # Backup 3 — integrity
    s = d.content_slide("Phụ lục C — Danh tính ELF và kết quả", "BACKUP", backup=True)
    rows = [
        ("flow_demo", "7fff5157…c39a", "PASS; checksum/DMA khớp"),
        ("zcu104_uart_smoke", "40d9d50a…e6da", "exit(0); UART 23 byte"),
        ("zcu104_uart_direct", "13f7b410…2ed3", "exit(0); UART 23 byte"),
    ]
    add_table(s, ["ELF", "SHA-256 rút gọn", "Kết quả hai backend"], rows,
              0.62, 1.25, [2.70, 2.60, 4.65], row_h=0.82, font_size=14)
    add_card(s, "Điều kiện PASS", "• Process/runner exit code 0\n• Marker hoặc status testbench đúng\n• Output/checksum khớp\n• Trace/VCD tồn tại và parse được",
             0.72, 4.45, 4.30, 1.80, accent=GREEN, fill=PALE_GREEN, body_size=14)
    add_card(s, "Không dùng làm tiêu chí duy nhất", "• Dòng Errors cuối transcript\n• Số instruction bằng nhau\n• Thời gian hai backend bằng nhau\n• HTML timeline tự thân",
             5.35, 4.45, 4.55, 1.80, accent=RED, fill=PALE_RED, body_size=14)

    # Backup 4 — signals
    s = d.content_slide("Phụ lục D — Signal RTL cần quan sát", "BACKUP", backup=True)
    signal_rows = [
        ("FC", "fetch_en, core_busy, PC/trace, exit_status"),
        ("Cluster", "cluster clock/reset/fetch; PE0…7 busy/clock enable"),
        ("MCHAN", "s_dmac_busy, dma event, TCDM req/gnt"),
        ("AXI", "AR/R valid-ready; AW/W/B valid-ready"),
        ("UDMA UART", "clock gate, setup, TX addr/size, busy/event"),
        ("UART pad", "DUT TX / tb w_uart_rx; receiver enable"),
    ]
    add_table(s, ["Khối", "Signal / nhóm signal"], signal_rows,
              0.68, 1.10, [2.25, 7.15], row_h=0.72, font_size=13)
    add_command_placeholder(s, "Ảnh signal hierarchy sau khi add wave",
                            "gtkwave report/gvsoc_demo/rtl/wave/flow_demo.gtkw",
                            "Signal list bên trái và cửa sổ wave có phase DMA", 0.68, 5.65, 9.40, 1.20)

    # Backup 5 — capture checklist
    s = d.content_slide("Phụ lục E — Checklist ảnh cần chụp", "BACKUP", backup=True)
    shots = [
        ("1", "flow_demo waveform", "DMA busy + TCDM + AXI", "report/gvsoc_demo/rtl/wave/flow_demo.gtkw"),
        ("2", "UART direct waveform", "w_uart_rx + exit", "report/zcu104_uart_direct/rtl/wave/zcu104_uart_direct.gtkw"),
        ("3", "UART direct viewer", "2 timeline + replay", "report/zcu104_uart_direct/flow_viewer.html"),
        ("4", "flow_demo viewer", "phase timeline + cycle table", "report/gvsoc_demo/flow_viewer.html"),
    ]
    for idx, (num, head, crop, path) in enumerate(shots):
        y = 1.10 + idx * 1.30
        add_text(s, num, 0.55, y, 0.58, 0.58, size=18, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=ORANGE, line=ORANGE, radius=True)
        add_rich_text(s, [(head + " — ", True, NAVY, None), (crop, False, INK, None)],
                      1.40, y, 4.42, 0.42, size=15)
        command = ("gtkwave " if path.endswith(".gtkw") else "firefox ") + path
        add_text(s, command, 5.85, y - 0.05, 4.20, 0.72, size=9.7, color=INK,
                 font="DejaVu Sans Mono", fill=PAPER, line=LIGHT_GRAY, radius=True,
                 valign=MSO_ANCHOR.MIDDLE, autosize=True)
    add_text(s, "Quy ước crop: bỏ toolbar thừa; giữ tên signal, time cursor, phase/PC anchor và giá trị cần chứng minh.",
             0.75, 6.40, 9.20, 0.48, size=13, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, fill=SKY, line=CYAN, radius=True)

    d.finish()
    print(OUTPUT)
    print(f"slides={len(d.prs.slides)}")


if __name__ == "__main__":
    build()
