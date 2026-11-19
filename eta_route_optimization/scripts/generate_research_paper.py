from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
TEMPLATE = ROOT / "assets" / "report_template.docx"
OUTPUT = WORKSPACE / "paper" / "Nhom09_BaoCao_ETA_ToiUuTuyen.docx"
ASSET_DIR = WORKSPACE / "paper" / "word_assets_eta"
ARTIFACTS = ROOT / "artifacts" / "generated"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


REPORT_PAGE_LABELS = read_json(ROOT / "configs" / "report_page_map_v3.json")


def close(actual: float, expected: float, tolerance: float = 1e-6) -> None:
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance):
        raise RuntimeError(f"Artifact mismatch: {actual} != {expected}")


def fvi(value: float, decimals: int = 2) -> str:
    """Format a number with Vietnamese decimal and thousands separators."""
    rendered = f"{value:,.{decimals}f}"
    return rendered.replace(",", "X").replace(".", ",").replace("X", ".")


def ivi(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def verify_artifacts() -> dict:
    eta = read_json(ARTIFACTS / "eta_baselines_v3" / "summary.json")
    inference = read_json(ARTIFACTS / "statistics_v3" / "eta_paired_inference.json")
    integration = read_json(ARTIFACTS / "eta_integration_v3" / "summary.json")
    amazon = read_json(ARTIFACTS / "amazon_baselines_v2" / "summary.json")
    soft = read_json(ARTIFACTS / "amazon_soft_windows_v3" / "summary.json")
    graph = read_json(ARTIFACTS / "graph_ablation_v3" / "summary.json")
    robust = read_json(ARTIFACTS / "robustness_v3" / "summary.json")
    balanced = read_json(ARTIFACTS / "balanced_v3" / "summary.json")
    rolling = read_json(ARTIFACTS / "rolling_origin_v3" / "summary.json")
    deployment = read_json(ARTIFACTS / "deployment_v3" / "summary.json")
    slices = read_json(ARTIFACTS / "slice_analysis_v3" / "summary.json")
    audit = read_json(ARTIFACTS / "data_audit_v3.json")
    validation = read_json(ARTIFACTS / "eta_dataset_v3" / "validation.json")

    eta_metrics = {row["model"]: row for row in eta["overall_metrics"]}
    iterations = eta["model_selection"]["lightgbm_best_iterations"].values()
    if validation["status"] != "pass" or validation["outcome_based_horizon_filter_applied"]:
        raise RuntimeError("A required decision gate did not pass")
    if eta["model_selection"]["selected_model"] != "lightgbm_ensemble" or max(iterations) >= 10_000:
        raise RuntimeError("ETA model selection or convergence gate did not pass")
    if inference["courier_cluster_bootstrap_ci95"][1] >= 0:
        raise RuntimeError("ETA clustered inference gate did not pass")
    if not balanced["selection_performed_without_test_metric"]:
        raise RuntimeError("Balanced-model selection used the test set")
    if soft["all_routes"]["solver_solved_rate"] != 1.0:
        raise RuntimeError("Soft-window solver gate did not pass")
    if soft["protocol"]["repeats_per_route"] < 3 or soft["solver_stability"]["routes"] != 204:
        raise RuntimeError("Soft-window stability gate did not pass")
    if graph["decision"] != "no_stable_eta_gain_from_relational_features_do_not_implement_gnn":
        raise RuntimeError("Unexpected GNN decision")
    if graph["decision_split"] != "validation" or graph["test_metrics_used_for_decision"]:
        raise RuntimeError("GNN gate used the test set")
    return {
        "eta": eta,
        "eta_metrics": eta_metrics,
        "inference": inference,
        "integration": integration,
        "amazon": amazon,
        "soft": soft,
        "graph": graph,
        "robust": robust,
        "balanced": balanced,
        "rolling": rolling,
        "deployment": deployment,
        "slices": slices,
        "audit": audit,
        "validation": validation,
    }


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    element = OxmlElement("w:tblHeader")
    element.set(qn("w:val"), "true")
    tr_pr.append(element)


def add_field(paragraph, instruction: str, placeholder: str = "Nhấn F9 để cập nhật") -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])


def enable_field_updates(document: Document) -> None:
    settings = document.settings._element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")


def remove_body_after_cover(document: Document) -> None:
    last = document.paragraphs[24]._p
    body = document._element.body
    remove = False
    for child in list(body):
        if child is last:
            remove = True
            continue
        if remove and child.tag != qn("w:sectPr"):
            body.remove(child)


def configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(13)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.first_line_indent = Cm(1)
    normal.paragraph_format.line_spacing = 1.3
    normal.paragraph_format.space_after = Pt(4)
    for name, size in [("Heading 1", 14), ("Heading 2", 13), ("Heading 3", 13)]:
        style = styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.keep_with_next = True
    styles["Heading 1"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    styles["Heading 1"].paragraph_format.page_break_before = True
    for name in ["Table Caption", "Figure Caption", "Source Note", "Equation"]:
        if name not in styles:
            styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    for name, left in [("Static TOC 1", 0), ("Static TOC 2", 0.5), ("Static TOC 3", 1.0)]:
        if name not in styles:
            styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style = styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.left_indent = Cm(left)
        style.paragraph_format.first_line_indent = Cm(0)
        style.paragraph_format.space_after = Pt(1)
    for name in ["Table Caption", "Figure Caption"]:
        style = styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12)
        style.font.bold = True
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        style.paragraph_format.space_before = Pt(6)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.keep_with_next = True
    source = styles["Source Note"]
    source.font.name = "Times New Roman"
    source.font.size = Pt(10)
    source.font.italic = True
    source._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    source.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    source.paragraph_format.space_after = Pt(6)
    equation = styles["Equation"]
    equation.font.name = "Cambria Math"
    equation.font.size = Pt(12)
    equation.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    equation.paragraph_format.first_line_indent = Cm(0)


def configure_a4_pages(document: Document) -> None:
    """Normalize every inherited/new section to the required A4 paper size."""
    for section in document.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)


def add_paragraph(document: Document, text: str, style: str = "Normal", bold_lead: str | None = None):
    p = document.add_paragraph(style=style)
    if bold_lead and text.startswith(bold_lead):
        p.add_run(bold_lead).bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        p = document.add_paragraph(style="List Paragraph")
        p.paragraph_format.left_indent = Cm(0.7)
        p.paragraph_format.first_line_indent = Cm(-0.35)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.add_run("•  ")
        p.add_run(item)


def add_caption(document: Document, text: str, kind: str) -> None:
    document.add_paragraph(text, style="Table Caption" if kind == "table" else "Figure Caption")


def add_table(document: Document, caption: str, headers: list[str], rows: list[list[str]], widths=None, source=None):
    add_caption(document, caption, "table")
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "TableNormal"
    table.autofit = True
    header = table.rows[0]
    set_repeat_table_header(header)
    for idx, value in enumerate(headers):
        cell = header.cells[idx]
        cell.text = value
        set_cell_shading(cell, "D9EAF7")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.bold = True
                run.font.name = "Times New Roman"
                run.font.size = Pt(10.5)
    for row_values in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row_values):
            cells[idx].text = str(value)
            cells[idx].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cells[idx].paragraphs:
                p.paragraph_format.first_line_indent = Cm(0)
                p.paragraph_format.space_after = Pt(0)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(10.5)
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = Cm(width)
    if source:
        document.add_paragraph(source, style="Source Note")
    return table


def svg_to_png(svg: str, name: str, width: int = 1400) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = ASSET_DIR / f"{name}.svg"
    png_path = ASSET_DIR / f"{name}.png"
    svg_path.write_text(svg, encoding="utf-8")
    converter = shutil.which("rsvg-convert")
    if converter:
        subprocess.run(
            [converter, "-w", str(width), "-o", str(png_path), str(svg_path)],
            check=True,
        )
    else:
        import cairosvg

        cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            write_to=str(png_path),
            output_width=width,
        )
    return png_path


def make_figures(data: dict) -> dict[str, Path]:
    flow_svg = """<svg xmlns='http://www.w3.org/2000/svg' width='1400' height='300'>
    <rect width='1400' height='300' fill='white'/>
    <g font-family='Arial' font-size='25' text-anchor='middle'>
      <rect x='20' y='80' rx='16' width='230' height='120' fill='#d9eaf7' stroke='#2f5597' stroke-width='3'/>
      <text x='135' y='125'><tspan x='135'>Kiểm toán và</tspan><tspan x='135' dy='34'>hợp đồng dữ liệu</tspan></text>
      <rect x='300' y='80' rx='16' width='230' height='120' fill='#e2f0d9' stroke='#548235' stroke-width='3'/>
      <text x='415' y='125'><tspan x='415'>Split theo thời gian</tspan><tspan x='415' dy='34'>không rò rỉ</tspan></text>
      <rect x='580' y='80' rx='16' width='230' height='120' fill='#fff2cc' stroke='#bf9000' stroke-width='3'/>
      <text x='695' y='125'><tspan x='695'>Baseline ETA và</tspan><tspan x='695' dy='34'>baseline tuyến</tspan></text>
      <rect x='860' y='80' rx='16' width='230' height='120' fill='#fce4d6' stroke='#c65911' stroke-width='3'/>
      <text x='975' y='125'><tspan x='975'>Kiểm định, độ bền</tspan><tspan x='975' dy='34'>và ablation</tspan></text>
      <rect x='1140' y='80' rx='16' width='230' height='120' fill='#e4dfec' stroke='#7030a0' stroke-width='3'/>
      <text x='1255' y='125'><tspan x='1255'>Quyết định mô hình</tspan><tspan x='1255' dy='34'>và fallback</tspan></text>
    </g>
    <g stroke='#666' stroke-width='5' fill='none'><path d='M250 140 H290'/><path d='M530 140 H570'/><path d='M810 140 H850'/><path d='M1090 140 H1130'/></g>
    <g fill='#666'><path d='M290 140 l-16 -10 v20 z'/><path d='M570 140 l-16 -10 v20 z'/><path d='M850 140 l-16 -10 v20 z'/><path d='M1130 140 l-16 -10 v20 z'/></g>
    </svg>"""
    mae = data["eta_metrics"]
    models = [
        ("Trung vị lịch sử", mae["historical_median"]["mae_minutes"], "#7f7f7f"),
        ("Tốc độ hiệu dụng", mae["effective_speed"]["mae_minutes"], "#a5a5a5"),
        ("KNN", mae["knn"]["mae_minutes"], "#5b9bd5"),
        ("LightGBM", mae["lightgbm_ensemble"]["mae_minutes"], "#70ad47"),
        ("MLP", mae["mlp_ensemble"]["mae_minutes"], "#ed7d31"),
    ]
    max_mae = max(value for _, value, _ in models) * 1.1
    bars = []
    for i, (label, value, color) in enumerate(models):
        y = 80 + i * 75
        width = value / max_mae * 800
        bars.append(
            f"<text x='15' y='{y+29}' font-family='Arial' font-size='24'>{label}</text>"
            f"<rect x='270' y='{y}' width='{width:.1f}' height='42' fill='{color}'/>"
            f"<text x='{285+width:.1f}' y='{y+29}' font-family='Arial' font-size='24'>{value:.2f}</text>"
        )
    mae_svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='500'>
    <rect width='1200' height='500' fill='white'/><text x='600' y='38' text-anchor='middle' font-family='Arial' font-size='28' font-weight='bold'>MAE trên tập kiểm định LaDe-D (phút, thấp hơn là tốt hơn)</text>{''.join(bars)}</svg>"""
    soft = data["soft"]
    held = soft["held_out_evaluation"]
    station = soft["primary_station_cluster_inference"]
    stability = soft["solver_stability"]
    route_svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1300' height='430'>
    <rect width='1300' height='430' fill='white'/>
    <text x='650' y='40' text-anchor='middle' font-family='Arial' font-size='28' font-weight='bold'>Deadline mềm trên Amazon: hiệu ứng và độ ổn định</text>
    <g font-family='Arial' text-anchor='middle'>
      <rect x='55' y='95' width='365' height='245' rx='18' fill='#d9eaf7' stroke='#2f5597' stroke-width='3'/>
      <text x='238' y='145' font-size='23' font-weight='bold'>Chênh operational cost</text>
      <text x='238' y='220' font-size='48' fill='#2f5597'>{held['mean_operational_delta_vs_observed']:.0f} giây</text>
      <text x='238' y='285' font-size='21'>187 tuyến evaluation</text>
      <rect x='468' y='95' width='365' height='245' rx='18' fill='#e2f0d9' stroke='#548235' stroke-width='3'/>
      <text x='650' y='145' font-size='23' font-weight='bold'>Hiệu ứng theo station</text>
      <text x='650' y='220' font-size='48' fill='#548235'>{station['stations_better_than_observed']}/{station['stations']}</text>
      <text x='650' y='285' font-size='21'>station tốt hơn observed</text>
      <rect x='880' y='95' width='365' height='245' rx='18' fill='#fff2cc' stroke='#bf9000' stroke-width='3'/>
      <text x='1062' y='145' font-size='23' font-weight='bold'>Chuỗi ổn định qua 3 lần</text>
      <text x='1062' y='220' font-size='48' fill='#bf9000'>{stability['routes_with_identical_sequence_all_repeats']}/{stability['routes']}</text>
      <text x='1062' y='285' font-size='21'>tuyến có chuỗi giống nhau</text>
    </g></svg>"""
    return {
        "flow": svg_to_png(flow_svg, "research_flow"),
        "mae": svg_to_png(mae_svg, "eta_mae"),
        "route": svg_to_png(route_svg, "amazon_soft_windows"),
    }


def add_picture(document: Document, path: Path, caption: str, width: float = 6.4) -> None:
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.add_run().add_picture(str(path), width=Inches(width))
    add_caption(document, caption, "figure")
    document.add_paragraph("Nguồn: Nhóm tác giả tổng hợp từ kết quả thực nghiệm.", style="Source Note")


def add_static_index(document: Document, entries: list[tuple[str, int]]) -> None:
    for label, level in entries:
        if label not in REPORT_PAGE_LABELS:
            raise RuntimeError(f"Missing static page label: {label}")
        paragraph = document.add_paragraph(
            f"{label}\t{REPORT_PAGE_LABELS[label]}", style=f"Static TOC {level}"
        )
        paragraph.paragraph_format.tab_stops.add_tab_stop(
            Inches(6.15), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
        )


def add_front_matter(document: Document, data: dict) -> None:
    lgb = data["eta_metrics"]["lightgbm_ensemble"]
    hist = data["eta_metrics"]["historical_median"]
    inference = data["inference"]
    station = data["soft"]["primary_station_cluster_inference"]
    document.add_section(WD_SECTION.NEW_PAGE)
    p = document.add_paragraph("TÓM TẮT", style="Heading 1")
    p.paragraph_format.page_break_before = False
    add_paragraph(
        document,
        f"Nghiên cứu xây dựng quy trình dự đoán thời gian hoàn tất giao hàng trên LaDe-D và tối ưu thứ tự giao hàng tĩnh trên Amazon. Giao thức ETA chỉ dùng trạng thái quan sát tại thời điểm truy vấn, không lọc cohort bằng nhãn tương lai; mô hình được chọn trên validation và test chỉ dùng để xác nhận. Trên {ivi(lgb['n'])} mẫu test, LightGBM đạt MAE {fvi(lgb['mae_minutes'])} phút so với {fvi(hist['mae_minutes'])} phút của trung vị lịch sử; mức giảm query-MAE là {fvi(abs(inference['relative_mae_change']) * 100)}% và CI cụm courier không chứa 0. Đặc trưng quan hệ không vượt cổng validation nên chưa có cơ sở triển khai GNN. Phần định tuyến tách calibration khỏi 187 tuyến evaluation và chạy ba lần trên toàn bộ 204 tuyến. Deadline mềm tốt hơn observed tại {station['stations_better_than_observed']}/{station['stations']} station trong evaluator lịch sử, nhưng không được diễn giải là tối ưu toàn cục hoặc lợi ích thực địa.",
    )
    add_paragraph(
        document,
        "Từ khóa: ETA; giao hàng chặng cuối; LightGBM; tối ưu tuyến; OR-Tools; kiểm soát rò rỉ dữ liệu.",
        bold_lead="Từ khóa:",
    )
    document.add_section(WD_SECTION.NEW_PAGE)
    p = document.add_paragraph("MỤC LỤC", style="Heading 1")
    p.paragraph_format.page_break_before = False
    add_static_index(document, [
        ("CHƯƠNG 1: XÁC ĐỊNH VẤN ĐỀ NGHIÊN CỨU", 1),
        ("1.1 Lý do chọn đề tài", 2), ("1.2 Phát biểu bài toán", 2),
        ("1.3 Business use case và giá trị sử dụng", 2),
        ("1.4 Mục tiêu nghiên cứu", 2), ("1.5 Câu hỏi nghiên cứu", 2),
        ("1.6 Đối tượng và phạm vi nghiên cứu", 2), ("1.7 Đóng góp của đề tài", 2),
        ("CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ CÁC NGHIÊN CỨU TRƯỚC", 1),
        ("2.1 Dự đoán ETA trong giao hàng chặng cuối", 2),
        ("2.2 Mô hình cây tăng cường và mạng nơ-ron", 2),
        ("2.3 Bài toán tối ưu thứ tự giao hàng", 2),
        ("2.4 Biểu diễn đồ thị cho dự đoán tuyến", 2),
        ("2.5 Dữ liệu công nghiệp cho nghiên cứu chặng cuối", 2),
        ("2.6 Tổng hợp nghiên cứu liên quan", 2), ("2.7 Khoảng trống nghiên cứu", 2),
        ("CHƯƠNG 3: THIẾT KẾ NGHIÊN CỨU VÀ PHƯƠNG PHÁP", 1),
        ("3.1 Quy trình nghiên cứu", 2), ("3.2 Dữ liệu nghiên cứu", 2),
        ("3.3 Tạo truy vấn ETA và chia dữ liệu", 2),
        ("3.4 Đặc trưng và mô hình ETA", 2), ("3.5 Phương pháp định tuyến", 2),
        ("3.6 Kiểm soát rò rỉ, mất cân bằng và quá khớp", 2),
        ("3.7 Chỉ số và suy luận thống kê", 2),
        ("CHƯƠNG 4: KẾT QUẢ NGHIÊN CỨU VÀ THẢO LUẬN", 1),
        ("4.1 Kết quả dự đoán ETA", 2), ("4.2 Chất lượng xếp thứ tự trên LaDe-D", 2),
        ("4.3 Kết quả định tuyến Amazon", 2),
        ("4.4 Đánh giá nhánh quan hệ và quyết định GNN", 2),
        ("4.5 Khả năng triển khai và cơ chế dự phòng", 2),
        ("4.6 Trả lời câu hỏi nghiên cứu", 2),
        ("CHƯƠNG 5: KẾT LUẬN VÀ HÀM Ý", 1), ("CHƯƠNG 6: TÀI LIỆU THAM KHẢO", 1),
        ("PHỤ LỤC", 1),
    ])
    document.add_section(WD_SECTION.NEW_PAGE)
    p = document.add_paragraph("MỤC LỤC BẢNG", style="Heading 1")
    p.paragraph_format.page_break_before = False
    add_static_index(document, [
        ("Bảng 0.1. Các từ viết tắt sử dụng trong báo cáo", 1),
        ("Bảng 1.1. Câu hỏi nghiên cứu và tiêu chí trả lời", 1),
        ("Bảng 2.1. Các nghiên cứu và tài liệu làm cơ sở cho quyết định phương pháp", 1),
        ("Bảng 3.1. Vai trò của hai bộ dữ liệu", 1),
        ("Bảng 3.2. Quy mô dataset ETA sau khi áp dụng giao thức", 1),
        ("Bảng 3.3. Các mô hình ETA và vai trò", 1),
        ("Bảng 3.4. Rủi ro và biện pháp kiểm soát", 1),
        ("Bảng 3.5. Chỉ số đánh giá theo mô-đun", 1),
        ("Bảng 4.1. Kết quả ETA tổng thể trên tập kiểm định", 1),
        ("Bảng 4.2. MAE LightGBM theo thành phố", 1),
        ("Bảng 4.3. Kiểm tra độ bền của mô hình ETA", 1),
        ("Bảng 4.4. Kết quả xếp thứ tự trên 15.247 truy vấn", 1),
        ("Bảng 4.5. Kết quả deadline mềm trên tập đánh giá giữ lại", 1),
        ("Bảng 4.6. Lặp lại bộ giải trên toàn bộ 204 tuyến", 1),
        ("Bảng 4.7. Ablation đặc trưng quan hệ", 1),
        ("Bảng 4.8. Benchmark cục bộ và quy tắc giám sát", 1),
        ("Bảng 5.1. Phạm vi kết luận được dữ liệu hỗ trợ", 1),
        ("Bảng B.1. Artifact nguồn của các kết luận chính", 1),
    ])
    document.add_section(WD_SECTION.NEW_PAGE)
    p = document.add_paragraph("MỤC LỤC HÌNH", style="Heading 1")
    p.paragraph_format.page_break_before = False
    add_static_index(document, [
        ("Hình 3.1. Quy trình thực nghiệm và các cổng kiểm tra", 1),
        ("Hình 4.1. MAE của các mô hình ETA trên tập kiểm định", 1),
        ("Hình 4.2. Hiệu ứng và độ ổn định của bộ giải deadline mềm", 1),
    ])
    document.add_section(WD_SECTION.NEW_PAGE)
    p = document.add_paragraph("DANH MỤC TỪ VIẾT TẮT", style="Heading 1")
    p.paragraph_format.page_break_before = False
    add_table(
        document,
        "Bảng 0.1. Các từ viết tắt sử dụng trong báo cáo",
        ["Từ viết tắt", "Nội dung"],
        [
            ["ETA", "Estimated Time of Arrival, thời gian còn lại đến khi hoàn tất giao hàng"],
            ["MAE", "Mean Absolute Error, sai số tuyệt đối trung bình"],
            ["RMSE", "Root Mean Squared Error, căn bậc hai sai số bình phương trung bình"],
            ["ACC@20", "Tỷ lệ dự đoán có sai số tuyệt đối không quá 20 phút"],
            ["KRC", "Kendall Rank Correlation, tương quan thứ hạng Kendall"],
            ["LSD", "Location Square Deviation, độ lệch bình phương vị trí"],
            ["PSI", "Population Stability Index, chỉ số thay đổi phân phối"],
            ["GNN", "Graph Neural Network, mạng nơ-ron đồ thị"],
        ],
        source="Nguồn: Nhóm tác giả quy ước trong phạm vi nghiên cứu.",
    )


def chapter_one(document: Document) -> None:
    document.add_heading("CHƯƠNG 1: XÁC ĐỊNH VẤN ĐỀ NGHIÊN CỨU", level=1)
    document.add_heading("1.1 Lý do chọn đề tài", level=2)
    add_paragraph(document, "Trong một ca giao hàng, khách hàng muốn biết đơn còn bao lâu sẽ tới, người giao hàng cần biết nên phục vụ điểm nào tiếp theo, còn điều phối viên cần nhận ra sớm những đơn có nguy cơ chậm. Báo cáo dùng thuật ngữ ETA (Estimated Time of Arrival) để chỉ số phút còn lại, tính từ lúc hệ thống đưa ra dự báo đến khi đơn được hoàn tất. Ví dụ, ETA bằng 35 phút có nghĩa là hệ thống ước tính đơn sẽ được hoàn tất sau khoảng 35 phút; đây không chỉ là thời gian xe chạy mà còn có thể gồm thời gian dừng, tìm địa chỉ, liên hệ khách và giao nhận.")
    add_paragraph(document, "Nhu cầu này được thể hiện trên dữ liệu thực tế với quy mô đủ lớn, không chỉ từ nhận định chủ quan. LaDe-D chứa 4.514.661 đơn tại năm thành phố; riêng Hangzhou có 1.861.600 đơn, gần 59 lần Jilin với 31.415 đơn. Sau khi tạo các thời điểm dự báo theo đúng giao thức, tập test có 178.430 quan sát và 76.701 quan sát, tương đương 43,0%, có thời gian hoàn tất còn lại trên 120 phút. Quy mô chênh lệch giữa thành phố và tỷ lệ đuôi dài lớn cho thấy một quy tắc thời gian chung khó đại diện tốt cho mọi khu vực và mọi ca làm việc.")
    add_paragraph(document, "Bài toán sắp xếp điểm giao cũng có quy mô và ràng buộc rõ ràng. Phần model-building của Amazon gồm 6.112 tuyến tại 17 station, 904.527 điểm dừng có kiện và 1.457.175 kiện; chỉ 7,82% kiện có đủ hai đầu khung giờ giao. Các con số này cho thấy hệ thống phải đồng thời xử lý nhiều điểm dừng, dữ liệu không đồng đều và thông tin thời gian chỉ có ở một phần đơn hàng. Vì vậy, đề tài tập trung vào hai quyết định có thể đo được: dự báo thời gian hoàn tất và đề xuất thứ tự ghé thăm. Nguồn số liệu: data_audit_v3.json, eta_dataset_v3/manifest.json và tài liệu dữ liệu [1], [2].")
    add_paragraph(document, "Dữ liệu không ghi nhận chi phí tiền tệ, mức hài lòng của khách hàng hay kết quả của mọi tuyến chưa từng chạy. Do đó, báo cáo không quy đổi sai số ETA thành doanh thu hoặc khẳng định lợi ích tài chính. Giá trị của giải pháp được đánh giá bằng các chỉ số có thể kiểm chứng trực tiếp: sai số thời gian, tỷ lệ dự báo gần đúng, chất lượng thứ tự giao, mức trễ, tính khả thi và thời gian chạy.")

    document.add_heading("1.2 Phát biểu bài toán", level=2)
    add_paragraph(document, "Bài toán thứ nhất trả lời câu hỏi: “Tại thời điểm hiện tại, mỗi đơn đang chờ còn bao nhiêu phút nữa sẽ được hoàn tất?”. Hệ thống chỉ được dùng thông tin đã biết ở thời điểm đưa ra dự báo, chẳng hạn thời gian nhận đơn, vị trí, khu vực, người giao hàng, thời điểm trong ngày và số đơn đang chờ. Kết quả cần trả về là số phút còn lại cho từng đơn. Khi đánh giá bằng dữ liệu lịch sử, số phút thực tế được tính như sau:")
    document.add_paragraph("ETAᵢ = t hoàn tất,ᵢ − t truy vấn", style="Equation")
    add_paragraph(document, "Bài toán thứ hai trả lời câu hỏi: “Với danh sách điểm cần giao, nên ghé các điểm theo thứ tự nào?”. Đầu vào gồm điểm xuất phát, các điểm dừng, thời gian dự kiến giữa từng cặp điểm, thời gian phục vụ và khung giờ giao nếu có. Đầu ra là một thứ tự đi qua mỗi điểm đúng một lần và quay về điểm xuất phát. Một phương án được xem là tốt khi hạn chế thời gian di chuyển và trễ hẹn, đồng thời luôn tạo được tuyến hợp lệ.")
    add_paragraph(document, "Hai bài toán liên quan nhưng không được trộn lẫn khi đánh giá. LaDe-D được dùng để kiểm tra dự báo thời gian hoàn tất; Amazon được dùng để so sánh các thứ tự giao trên cùng một ma trận thời gian. Cách tách này giúp tránh việc dùng chính dự báo của mô hình làm bằng chứng duy nhất rằng tuyến do mô hình tạo ra tốt hơn.")

    document.add_heading("1.3 Business use case và giá trị sử dụng", level=2)
    add_paragraph(document, "Use case chính là hỗ trợ điều phối trong ca giao hàng. Sau khi người giao hoàn tất một điểm, hệ thống đọc danh sách đơn còn chờ và trả về ETA cho từng đơn, đơn có nguy cơ chậm và thứ tự ghé thăm được đề xuất. Điều phối viên vẫn là người quyết định cuối cùng; kết quả mô hình đóng vai trò cảnh báo và gợi ý, không tự động thay đổi tuyến ngoài thực địa.")
    add_bullets(document, [
        "Điều phối viên theo dõi ca làm việc: ưu tiên kiểm tra các đơn có ETA dài hoặc có nguy cơ vượt khung giờ, thay vì rà soát thủ công toàn bộ danh sách.",
        "Người giao hàng nhận gợi ý điểm tiếp theo: tham khảo một thứ tự hợp lệ có cân nhắc thời gian di chuyển và trễ hẹn, sau đó điều chỉnh khi gặp tình huống thực tế.",
        "Bộ phận chăm sóc khách hàng trả lời nhất quán hơn: sử dụng khoảng thời gian dự kiến từ cùng một nguồn thay vì ước lượng cảm tính theo khoảng cách.",
        "Quản lý vận hành đánh giá chất lượng theo khu vực: theo dõi sai số ETA, tỷ lệ dự báo trong ±20 phút, tỷ lệ tuyến có nghiệm, mức trễ và thời gian xử lý để phát hiện khu vực cần hiệu chỉnh.",
    ])
    add_paragraph(document, "Luồng nghiệp vụ đề xuất gồm bốn bước: (1) nhận trạng thái đơn đang chờ; (2) dự báo số phút còn lại; (3) đánh dấu rủi ro và tạo gợi ý thứ tự; (4) hiển thị cho điều phối viên kèm phương án dự phòng dựa trên lịch sử khi mô hình thiếu dữ liệu hoặc phát hiện phân phối đầu vào thay đổi. Use case này chưa bao gồm điều hướng GPS theo thời gian thực, tự động nhắn khách, phân bổ nhiều xe hoặc cam kết thời gian giao hàng mang tính pháp lý.")

    document.add_heading("1.4 Mục tiêu nghiên cứu", level=2)
    add_paragraph(document, "Mục tiêu tổng quát là xây dựng và kiểm tra một quy trình hỗ trợ hai câu hỏi nghiệp vụ: đơn còn bao lâu sẽ hoàn tất và nên phục vụ các điểm theo thứ tự nào. Quy trình phải dùng được trên dữ liệu tương lai, không nhìn trước kết quả và có thể truy lại mọi con số trong báo cáo.")
    add_bullets(document, [
        "So sánh dự báo của mô hình học máy với các cách ước lượng đơn giản dựa trên lịch sử.",
        "Kiểm tra kết quả trên các tháng, thành phố, người giao hàng và khu vực khác nhau.",
        "So sánh các cách sắp xếp điểm giao bằng cùng một bộ quy tắc chấm điểm.",
        "Tìm phương án xử lý khung giờ giao mà vẫn tạo được tuyến hợp lệ.",
        "Đo thời gian xử lý, độ ổn định và điều kiện cần chuyển sang phương án dự phòng.",
    ])

    document.add_heading("1.5 Câu hỏi nghiên cứu", level=2)
    add_table(document, "Bảng 1.1. Câu hỏi nghiên cứu và tiêu chí trả lời", ["Mã", "Câu hỏi", "Tiêu chí"], [
        ["RQ1", "Mô hình học máy dự báo thời gian hoàn tất tốt hơn cách ước lượng từ lịch sử bao nhiêu?", "Sai số trung bình, tỷ lệ lệch không quá 20 phút và khoảng tin cậy"],
        ["RQ2", "Kết quả có duy trì trên dữ liệu của thời gian và khu vực khác không?", "Đánh giá theo tháng, thành phố, người giao hàng và khu vực chưa thấy"],
        ["RQ3", "Phương án có xét khung giờ có giảm chi phí tuyến mà vẫn tạo được tuyến hợp lệ không?", "Tỷ lệ có nghiệm, thời gian di chuyển, mức trễ và thời gian xử lý"],
        ["RQ4", "Thông tin về quan hệ giữa các khu vực có đủ hữu ích để cần một mô hình đồ thị phức tạp hơn không?", "So sánh cùng điều kiện qua năm lần chạy và khoảng tin cậy"],
    ], source="Nguồn: Nhóm tác giả xây dựng trước khi tổng hợp kết quả.")

    document.add_heading("1.6 Đối tượng và phạm vi nghiên cứu", level=2)
    add_paragraph(document, "Đối tượng nghiên cứu là độ chính xác của thời gian hoàn tất dự kiến đối với các đơn đang chờ và chất lượng của thứ tự phục vụ trong giao hàng chặng cuối. Phạm vi dữ liệu gồm năm thành phố LaDe-D và phần model-building của Amazon. Kết quả được xem xét theo từng lần dự báo, người giao hàng, thành phố, tuyến và station để tránh kết luận chỉ từ một giá trị trung bình chung.")
    add_paragraph(document, "Nghiên cứu không có dữ liệu giao thông trực tiếp, trọng lượng kiện, chi phí tiền tệ, mức hài lòng khách hàng hoặc kết quả thực địa sau khi thay tuyến. Vì vậy, sản phẩm của đề tài là bằng chứng thực nghiệm và một nguyên mẫu hỗ trợ quyết định; chưa phải hệ thống tự động điều phối hoàn chỉnh và không được dùng để cam kết giờ giao chính thức cho khách hàng.")

    document.add_heading("1.7 Đóng góp của đề tài", level=2)
    add_paragraph(document, "Đề tài đóng góp một quy trình có thể kiểm tra lại từ dữ liệu đến kết luận. Quy trình tạo các thời điểm dự báo mà không sử dụng thông tin chỉ xuất hiện sau khi giao xong; so sánh mô hình trên dữ liệu tương lai và theo từng nhóm vận hành; chấm mọi phương án tuyến bằng cùng một bộ quy tắc; và chỉ chấp nhận mô hình phức tạp hơn khi có bằng chứng cải thiện ổn định. Bên cạnh kết quả mô hình, báo cáo còn xác định rõ business use case, chỉ số giám sát, phương án dự phòng và những quyết định chưa thể tự động hóa do giới hạn dữ liệu.")


def chapter_two(document: Document) -> None:
    document.add_heading("CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ CÁC NGHIÊN CỨU TRƯỚC", level=1)
    document.add_heading("2.1 Dự đoán ETA trong giao hàng chặng cuối", level=2)
    add_paragraph(document, "ETA trong nghiên cứu này là thời gian còn lại từ một thời điểm truy vấn đến khi đơn được hoàn tất. Định nghĩa phù hợp với bài toán ETA của LaDe, nơi trạng thái hiện tại và tập nhiệm vụ chưa hoàn thành được dùng để dự đoán thời điểm kết thúc [1]. Nhãn này rộng hơn thời gian di chuyển vì có thể bao gồm dừng xe, tìm địa chỉ, liên hệ khách và thao tác giao nhận.")
    add_paragraph(document, "Các baseline lịch sử giúp xác định mô hình học máy có tạo giá trị thực hay không. Trung vị lịch sử bền vững với ngoại lệ nhưng không thể hiện đầy đủ quan hệ phi tuyến. Quy tắc tốc độ hiệu dụng kết hợp khoảng cách thẳng và tốc độ ước lượng từ dữ liệu quá khứ; đại lượng này chỉ là proxy, không phải tốc độ giao thông. KNN tận dụng các trường hợp gần nhau trong không gian đặc trưng, nhưng chi phí suy luận và ảnh hưởng của chuẩn hóa tăng khi dữ liệu lớn.")

    document.add_heading("2.2 Mô hình cây tăng cường và mạng nơ-ron", level=2)
    add_paragraph(document, "LightGBM xây dựng cây quyết định theo cơ chế boosting và được thiết kế cho khả năng mở rộng trên dữ liệu lớn [3]. Dữ liệu ETA chứa nhiều quan hệ không tuyến tính giữa thời gian, vị trí, tải công việc và loại AOI, nên mô hình cây là baseline phù hợp. MLP được dùng như baseline học sâu không đồ thị. Việc so sánh này tách tác động của kiến trúc học sâu khỏi tác động của cấu trúc quan hệ.")

    document.add_heading("2.3 Bài toán tối ưu thứ tự giao hàng", level=2)
    add_paragraph(document, "Trong bài toán một xe, mỗi điểm dừng phải được thăm đúng một lần và hành trình bắt đầu tại depot. Báo cáo dùng tuyến khép kín làm thước đo chính, nghĩa là cộng cả thời gian quay lại depot. Chi phí cạnh lấy trực tiếp từ ma trận transit Amazon. Thời gian phục vụ được cộng sau khi đến điểm dừng; khung giờ quyết định thời gian chờ và độ trễ.")
    add_paragraph(document, "OR-Tools cung cấp bộ giải cho TSP, VRP, capacity và time window [6]. Khi thời gian tìm kiếm bị giới hạn, kết quả là nghiệm tốt nhất tìm được chứ không mặc nhiên là tối ưu toàn cục. Time window cứng có thể không có nghiệm nếu nhiều kiện tại cùng điểm dừng có khoảng thời gian giao không giao nhau. Deadline mềm cho phép vi phạm với penalty, nhờ đó biểu diễn được đánh đổi giữa transit và trễ.")

    document.add_heading("2.4 Biểu diễn đồ thị cho dự đoán tuyến", level=2)
    add_paragraph(document, "Graph2Route biểu diễn nhiệm vụ đang chờ bằng đồ thị không gian và thời gian, sau đó dự đoán thứ tự bằng mô hình đồ thị động [4]. M²G4RTP kết hợp dự đoán tuyến và thời gian trong kiến trúc đa mức, đa nhiệm [5]. Hai công trình cho thấy quan hệ cạnh có thể hữu ích, nhưng không chứng minh GNN luôn vượt mô hình bảng. Với split theo thời gian, cạnh hoặc AOI mới làm giảm tỷ lệ tái sử dụng lịch sử; một cổng ablation là cần thiết trước khi đầu tư vào mô hình phức tạp.")

    document.add_heading("2.5 Dữ liệu công nghiệp cho nghiên cứu chặng cuối", level=2)
    add_paragraph(document, "LaDe là bộ dữ liệu công nghiệp quy mô lớn cho dự đoán tuyến và ETA [1]. Amazon Last Mile Routing Research Challenge cung cấp 6.112 tuyến model-building, observed sequence, ma trận transit, planned service time, thông tin kiện và dung tích xe [2]. Hai bộ dữ liệu bổ sung cho nhau: LaDe có nhãn thời gian hoàn tất từng đơn, trong khi Amazon hỗ trợ chấm chi phí của nhiều thứ tự thay thế trên cùng ma trận.")

    document.add_heading("2.6 Tổng hợp nghiên cứu liên quan", level=2)
    add_table(document, "Bảng 2.1. Các nghiên cứu và tài liệu làm cơ sở cho quyết định phương pháp", ["Nguồn", "Nội dung liên quan", "Vai trò trong đề tài"], [
        ["Wu và cộng sự [1]", "Công bố LaDe, bài toán ETA và route prediction", "Định nghĩa nhãn, dữ liệu và nhóm baseline"],
        ["Merchán và cộng sự [2]", "Mô tả bộ Amazon và các trường dữ liệu", "Xác định phạm vi định tuyến tĩnh"],
        ["Ke và cộng sự [3]", "Thuật toán LightGBM", "Baseline chính cho dữ liệu bảng"],
        ["Wen và cộng sự [4]", "Graph2Route cho dự đoán tuyến", "Cơ sở cho nhánh quan hệ"],
        ["Cai và cộng sự [5]", "Dự đoán chung tuyến và thời gian", "Cơ sở cho giả thuyết đa nhiệm"],
        ["Google OR-Tools [6]", "Routing solver và time windows", "Bộ giải tuyến có ràng buộc"],
    ], source="Nguồn: Nhóm tác giả tổng hợp từ các tài liệu [1] đến [6].")

    document.add_heading("2.7 Khoảng trống nghiên cứu", level=2)
    add_paragraph(document, "Ba khoảng trống được xem xét. Thứ nhất, một mô hình ETA tốt chưa chắc tạo thứ tự tốt trên mọi chỉ số; cần đánh giá đồng thời sai số thời gian và chất lượng xếp hạng. Thứ hai, các công trình đồ thị thường tập trung vào kiến trúc, trong khi giá trị tăng thêm của lịch sử cạnh trên split tương lai ít khi được kiểm tra bằng cổng đơn giản. Thứ ba, tuyến tối thiểu transit có thể gây trễ lớn; cần báo cáo đánh đổi ràng buộc thay vì chỉ đưa ra tổng thời gian di chuyển.")


def chapter_three(document: Document, figures: dict[str, Path]) -> None:
    document.add_heading("CHƯƠNG 3: THIẾT KẾ NGHIÊN CỨU VÀ PHƯƠNG PHÁP", level=1)
    document.add_heading("3.1 Quy trình nghiên cứu", level=2)
    add_paragraph(document, "Quy trình được đóng băng theo thứ tự từ dữ liệu đến quyết định mô hình. Mỗi bước tạo artifact máy đọc và chỉ chuyển sang bước sau khi kiểm tra tương ứng đạt yêu cầu.")
    add_picture(document, figures["flow"], "Hình 3.1. Quy trình thực nghiệm và các cổng kiểm tra", width=6.6)

    document.add_heading("3.2 Dữ liệu nghiên cứu", level=2)
    document.add_heading("3.2.1 LaDe-D", level=3)
    add_paragraph(document, "Năm tệp LaDe-D chứa 4.514.661 đơn. Hangzhou có 1.861.600 đơn, lớn gần 59 lần Jilin với 31.415 đơn. Kiểm toán không phát hiện order ID trùng trong từng tệp. Có ba bản ghi Chongqing có thời điểm hoàn tất sớm hơn thời điểm nhận và được loại trước khi tạo query. Dữ liệu thiếu 3.377 cặp GPS tại thời điểm nhận; mô hình không dùng trường này làm vị trí điểm giao.")
    document.add_heading("3.2.2 Amazon", level=3)
    add_paragraph(document, "Phần model-building Amazon có 6.112 tuyến tại 17 station, 1.457.175 kiện và 904.527 stop có kiện. Chỉ 113.993 kiện có đủ hai đầu time window, tương ứng 7,82%. Trung vị tỷ lệ tổng thể tích kiện trên dung tích xe là 0,737; 12 tuyến có tỷ lệ tính toán lớn hơn một và được giữ lại để báo cáo, không tự động sửa dữ liệu.")
    add_table(document, "Bảng 3.1. Vai trò của hai bộ dữ liệu", ["Nội dung", "LaDe-D", "Amazon"], [
        ["Quy mô", "4.514.661 đơn, 5 thành phố", "6.112 tuyến, 17 station"],
        ["Nhãn ETA từng đơn", "Có", "Không có arrival time thực tế"],
        ["Observed sequence", "Suy từ delivery time", "Có sẵn"],
        ["Ma trận chi phí mọi cạnh", "Không", "Có transit matrix"],
        ["Khung giờ", "Không", "Có cho 7,82% kiện"],
        ["Giao thông thời gian thực", "Không", "Không"],
        ["Trọng lượng", "Không", "Không, chỉ có kích thước"],
    ], source="Nguồn: Kết quả kiểm toán data_audit_v3.json và mô tả dữ liệu [1], [2].")

    document.add_heading("3.3 Tạo truy vấn ETA và chia dữ liệu", level=2)
    add_paragraph(document, "Đơn được gom theo city, courier_id và ngày vận hành ds. Thời điểm truy vấn là lần hoàn tất đầu tiên của courier trong ngày. Toàn bộ đơn thỏa accept_time ≤ query_time < delivery_time được dùng để tính số nhiệm vụ chờ, thứ tự nhận và áp dụng giới hạn tối đa 25 nhiệm vụ theo accept_time rồi order ID. Mọi ETA dương sau bước này đều được giữ. Các dải ETA chỉ phục vụ phân tích lát cắt, không quyết định cohort.")
    add_paragraph(document, "Split được xác định từ ngày của query, không lấy từ ngày hoàn tất tương lai của từng đơn. Query trước tháng 9 thuộc train, tháng 9 thuộc validation và tháng 10 thuộc test. Giới hạn hash xác định trước giữ tối đa 250.000 dòng train, 50.000 validation và 50.000 test cho mỗi thành phố.")
    add_table(document, "Bảng 3.2. Quy mô dataset ETA sau khi áp dụng giao thức", ["Tập", "Số dòng", "Số query", "Khoảng thời gian"], [
        ["Train", "769.458", "92.615", "Trước tháng 9"],
        ["Validation", "180.719", "20.721", "Tháng 9"],
        ["Test", "178.430", "16.346", "Từ tháng 10"],
    ], source="Nguồn: eta_dataset_v3/manifest.json và validation.json.")
    add_paragraph(document, "Tập test có 76.701 dòng ETA trên 120 phút và giá trị lớn nhất 54.549 phút. Đây là đuôi thời gian hoàn tất quan sát được, có thể gồm đơn tồn đọng hoặc trì hoãn quy trình. MAE được dùng làm chỉ số chính; RMSE và các lát cắt <=2 giờ, 2–8 giờ, 8–24 giờ và >24 giờ được báo cáo để không che khuất rủi ro đuôi dài.")

    document.add_heading("3.4 Đặc trưng và mô hình ETA", level=2)
    add_paragraph(document, "Đặc trưng thời gian gồm phút trong ngày, chu kỳ sin-cos của giờ và thứ, tháng và thời gian chờ kể từ lúc nhận. Đặc trưng không gian gồm tọa độ query, tọa độ điểm giao và khoảng cách Haversine. Trạng thái công việc gồm số nhiệm vụ chờ, thứ tự nhận, cùng AOI, cùng region và loại AOI. City được dùng như biến phân loại. Không có delivery time tương lai trong ma trận đầu vào.")
    add_table(document, "Bảng 3.3. Các mô hình ETA và vai trò", ["Mô hình", "Mô tả", "Vai trò"], [
        ["Historical median", "Trung vị theo city, loại AOI và khung hai giờ", "Mốc lịch sử"],
        ["Effective speed", "Khoảng cách chia tốc độ hiệu dụng lịch sử", "Mốc dựa trên khoảng cách"],
        ["KNN", "25 láng giềng, trọng số theo khoảng cách", "Baseline phi tham số"],
        ["LightGBM", "Ensemble năm seed, loss L1", "Mô hình bảng chính"],
        ["MLP", "Hai lớp 64 và 32 nút", "Baseline học sâu không đồ thị"],
    ], source="Nguồn: Cấu hình eta_experiment.py.")

    document.add_heading("3.5 Phương pháp định tuyến", level=2)
    add_paragraph(document, "Mẫu Amazon gồm tối đa 12 tuyến mỗi station, chọn bằng SHA-256 của route ID, tổng cộng 204 tuyến. Observed sequence là mốc hành vi. Nearest neighbor chọn điểm có transit nhỏ nhất từ vị trí hiện tại. Directed 2-opt cải thiện cục bộ trên tuyến tham lam. OR-Tools transit-only tối thiểu hóa transit và service trong giới hạn thời gian cố định.")
    add_paragraph(document, "Biến thể time window cứng dùng giao của các cửa sổ kiện tại cùng stop. Khi giao rỗng, tuyến không có nghiệm. Biến thể mềm giữ thời điểm bắt đầu như cận dưới cứng, còn deadline sớm nhất nhận penalty. Ba hệ số 1, 10 và 100 được chấm trên 17 tuyến calibration, một tuyến mỗi station. Mỗi cấu hình chạy ba lần; calibration dùng trung bình của cost-median theo tuyến và evaluation dùng median của ba lần trước khi suy luận. Phần đánh giá còn 187 tuyến, đúng 11 tuyến mỗi station. Fallback được cố định là nearest neighbor kết hợp directed 2-opt.")
    document.add_paragraph("Operational cost = closed duration + tổng package lateness", style="Equation")

    document.add_heading("3.6 Kiểm soát rò rỉ, mất cân bằng và quá khớp", level=2)
    add_table(document, "Bảng 3.4. Rủi ro và biện pháp kiểm soát", ["Rủi ro", "Biện pháp", "Kiểm tra"], [
        ["Thông tin tương lai", "Feature chỉ dùng trạng thái tại query", "accept ≤ query < delivery"],
        ["Query đi qua nhiều split", "Split ở cấp query theo thời gian", "Tập query và sample giao nhau bằng rỗng"],
        ["Thành phố lớn chi phối", "Cap theo city, macro MAE và báo cáo per-city", "Thử inverse-city weighting"],
        ["Overfitting", "Early stopping, năm seed, rolling-origin", "Train, validation, test và ba fold tháng"],
        ["AOI/cạnh mới", "Thống kê chỉ fit trên train", "Báo cáo AOI unseen và edge seen"],
        ["Chọn penalty trên test", "Tách 17 tuyến calibration", "187 tuyến còn lại chỉ dùng đánh giá"],
    ], source="Nguồn: Giao thức nghiên cứu và các bộ kiểm thử tự động.")

    document.add_heading("3.7 Chỉ số và suy luận thống kê", level=2)
    add_paragraph(document, "MAE là chỉ số ETA chính vì đơn vị phút dễ diễn giải. RMSE nhấn mạnh sai số lớn; median AE và ACC@20 bổ sung góc nhìn bền vững và tỷ lệ dự đoán đủ gần. Chất lượng thứ tự dùng HR@3, KRC, LSD và edit distance. Định tuyến báo cáo transit, service, waiting, lateness, số kiện trễ, tỷ lệ có nghiệm và runtime.")
    document.add_paragraph("MAE = (1/n) Σ |ŷᵢ − yᵢ|", style="Equation")
    document.add_paragraph("RMSE = √[(1/n) Σ (ŷᵢ − yᵢ)²]", style="Equation")
    add_paragraph(document, "So sánh ETA dùng chênh lệch ghép cặp trên cùng query; khoảng tin cậy chính bootstrap theo cụm city-courier và bootstrap query là độ nhạy. Với Amazon, suy luận chính bootstrap theo station và kiểm định dấu trên 17 station. Leave-one-city-out, leave-one-station-out và rolling-origin kiểm tra độ bền. Validation chọn mô hình và cổng GNN; test không tham gia chọn mô hình, city weighting hoặc penalty.")
    add_table(document, "Bảng 3.5. Chỉ số đánh giá theo mô-đun", ["Mô-đun", "Chỉ số chính", "Chỉ số bổ sung"], [
        ["ETA", "MAE, RMSE", "Median AE, ACC@20, macro MAE"],
        ["Thứ tự", "KRC, HR@3", "LSD, edit distance"],
        ["Định tuyến", "Operational cost, feasibility", "Transit, lateness, late packages, runtime"],
        ["Triển khai", "Latency, model size", "RSS, PSI, fallback rate"],
    ], source="Nguồn: Nhóm tác giả định nghĩa trong giao thức phiên bản 2.")


def chapter_four(document: Document, figures: dict[str, Path], data: dict) -> None:
    document.add_heading("CHƯƠNG 4: KẾT QUẢ NGHIÊN CỨU VÀ THẢO LUẬN", level=1)
    document.add_heading("4.1 Kết quả dự đoán ETA", level=2)
    add_paragraph(document, "Tập test có 162.762 đơn thuộc 24.318 query. LightGBM đạt MAE thấp nhất trong năm phương pháp, 22,71 phút. So với historical median, mức giảm trực tiếp theo đơn là 4,89 phút. ACC@20 tăng từ 39,09% lên 53,34%.")
    add_table(document, "Bảng 4.1. Kết quả ETA tổng thể trên tập kiểm định", ["Mô hình", "MAE", "RMSE", "Median AE", "ACC@20"], [
        ["Historical median", "27,60", "32,55", "26,00", "39,09%"],
        ["Effective speed", "32,33", "41,75", "25,55", "42,14%"],
        ["KNN", "25,61", "30,94", "23,12", "43,61%"],
        ["LightGBM, 5 seed", "22,71", "28,97", "18,45", "53,34%"],
        ["MLP, 5 seed", "24,69", "29,88", "22,24", "45,20%"],
    ], source="Nguồn: eta_baselines_v3/summary.json. Đơn vị sai số là phút.")
    add_paragraph(document, "Cả năm MLP đều chạm giới hạn 40 vòng lặp trước khi hội tụ, nên kết quả MLP chỉ được xem là baseline học sâu theo ngân sách đã đóng băng. LightGBM được chọn vì tốt hơn trên MAE và không phụ thuộc một seed cụ thể.")
    add_picture(document, figures["mae"], "Hình 4.1. MAE của các mô hình ETA trên tập kiểm định", width=6.2)
    add_paragraph(document, "Ở cấp query, LightGBM giảm MAE trung bình 4,89 phút, tương ứng 17,74%. Khoảng tin cậy bootstrap 95% là [-5,03; -4,76] phút. LightGBM tốt hơn historical median tại 17.182 trong 24.318 query. Khi lần lượt bỏ từng thành phố, chênh lệch vẫn âm, cho thấy kết luận không do một thành phố duy nhất tạo ra.")

    document.add_heading("4.1.1 Kết quả theo thành phố và nhóm chưa thấy", level=3)
    add_table(document, "Bảng 4.2. MAE LightGBM theo thành phố", ["Thành phố", "Số mẫu test", "MAE", "ACC@20", "Leave-one-city-out MAE"], [
        ["Chongqing", "49.998", "25,27", "47,34%", "31,93"],
        ["Hangzhou", "49.995", "22,88", "52,14%", "30,86"],
        ["Jilin", "399", "24,84", "46,87%", "50,19"],
        ["Shanghai", "50.000", "19,97", "60,96%", "29,24"],
        ["Yantai", "12.370", "22,72", "51,88%", "25,33"],
    ], source="Nguồn: eta_baselines_v3/metrics.csv và statistics_v3/leave_one_city_out.csv.")
    add_paragraph(document, "MAE trên 55.755 mẫu của courier chưa thấy là 23,81 phút, cao hơn mức 22,14 phút của courier đã thấy. AOI chưa thấy chiếm 5,60% test và có MAE 24,79 phút, so với 22,59 phút ở AOI đã thấy. Leave-one-city-out suy giảm mạnh, đặc biệt tại Jilin, nơi chỉ có 399 mẫu test. Kết quả hỗ trợ sử dụng mô hình trong năm thành phố đã hiệu chỉnh, nhưng chưa hỗ trợ triển khai tự động tại thành phố hoàn toàn mới.")

    document.add_heading("4.1.2 Overfitting, mất cân bằng và rolling-origin", level=3)
    add_table(document, "Bảng 4.3. Kiểm tra độ bền của mô hình ETA", ["Kiểm tra", "Kết quả", "Diễn giải"], [
        ["MAE train / validation / test", "20,92 / 21,59 / 22,71", "Suy giảm vừa phải trên dữ liệu tương lai"],
        ["MAE 5 seed", "22,73 đến 22,77", "Không phụ thuộc một seed"],
        ["Rolling tháng 7 / 8 / 9", "21,78 / 21,34 / 21,70", "Ổn định qua ba cửa sổ"],
        ["Macro MAE test", "23,13", "Cao hơn micro MAE 0,42 phút"],
        ["City weighting validation", "22,07 so với 21,88", "Trọng số làm macro MAE xấu hơn"],
        ["PSI feature chính", "0,015 đến 0,041", "Chưa vượt ngưỡng theo dõi 0,1"],
    ], source="Nguồn: robustness_v3, balanced_v3, rolling_origin_v3 và deployment_v3.")
    add_paragraph(document, "Inverse-city weighting cải thiện Jilin ở một số fold nhưng làm giảm chất lượng tại Hangzhou, Shanghai và các thành phố khác. Trên ba rolling fold, macro MAE trung bình tăng từ 22,15 lên 22,40 phút. Mô hình không trọng số được giữ vì tiêu chí validation đã định trước, không phải vì bỏ qua mất cân bằng.")

    document.add_heading("4.2 Chất lượng xếp thứ tự trên LaDe-D", level=2)
    add_table(document, "Bảng 4.4. Kết quả xếp thứ tự trên 22.033 query", ["Mô hình", "HR@3", "KRC", "LSD", "Edit distance"], [
        ["Historical median", "0,5244", "0,0052", "10,738", "5,679"],
        ["Effective speed", "0,7148", "0,3688", "5,560", "4,507"],
        ["KNN", "0,6139", "0,1586", "8,157", "5,259"],
        ["LightGBM", "0,7138", "0,3620", "5,453", "4,599"],
        ["MLP", "0,6516", "0,2322", "7,175", "4,994"],
    ], source="Nguồn: eta_integration_v3/summary.json.")
    add_paragraph(document, "LightGBM có LSD tốt hơn effective speed nhưng thấp hơn nhẹ về HR@3 và KRC. Do đó, giảm MAE không bảo đảm mọi chỉ số thứ tự cùng cải thiện. Khi cộng nhiễu chuẩn 5, 10 và 20 phút, KRC LightGBM giảm lần lượt còn 0,331; 0,283 và 0,207. Bộ tối ưu tuyến cần ràng buộc riêng thay vì chỉ sắp tăng dần theo ETA.")

    document.add_heading("4.3 Kết quả định tuyến Amazon", level=2)
    add_table(document, "Bảng 4.5. Baseline định tuyến trên 204 tuyến Amazon", ["Phương pháp", "Có nghiệm", "Transit khép kín", "Chênh observed", "Lateness"], [
        ["Observed sequence", "204/204", "11.927,93", "0,00", "320,30"],
        ["Nearest neighbor", "204/204", "12.171,00", "+243,08", "13.644,82"],
        ["Nearest neighbor + 2-opt", "204/204", "11.772,72", "-155,20", "13.326,87"],
        ["OR-Tools transit-only", "204/204", "10.732,01", "-1.195,92", "9.312,01"],
        ["OR-Tools time window cứng", "119/204", "10.638,50", "-1.068,03", "0,00"],
    ], source="Nguồn: amazon_baselines_v2/summary.json. Đơn vị là giây.")
    add_paragraph(document, "Tối thiểu transit mà bỏ qua deadline tạo độ trễ lớn. Time window cứng không trễ trên các tuyến có nghiệm, nhưng chỉ giải được 58,33% mẫu. Vì kết quả 119 tuyến có thể chịu thiên lệch chọn mẫu, không thể dùng chênh transit của nhóm này để kết luận tổng quát.")

    document.add_heading("4.3.1 Bộ giải deadline mềm", level=3)
    add_table(document, "Bảng 4.6. Kết quả deadline mềm trên tập đánh giá giữ lại", ["Chỉ số", "Observed", "Deadline mềm", "Chênh lệch"], [
        ["Số tuyến", "187", "187", "0"],
        ["Transit trung bình", "11.925,99", "11.102,04", "-823,95"],
        ["Lateness trung bình", "348,72", "185,66", "-163,06"],
        ["Operational cost", "Mốc", "Giảm 445,27", "CI 95% [-830,59; -20,93]"],
        ["Tuyến tốt hơn / xấu hơn", "Mốc", "147 / 40", ""],
        ["Tỷ lệ solver có nghiệm", "", "100%", "Không dùng fallback"],
        ["Runtime trung bình", "", "1,003 giây", "Giới hạn 1 giây"],
    ], source="Nguồn: amazon_soft_windows_v3/summary.json và route_results.csv.")
    add_picture(document, figures["route"], "Hình 4.2. Transit và lateness trên 187 tuyến Amazon giữ lại", width=6.2)
    add_paragraph(document, "Hệ số penalty 1 được chọn trên 17 tuyến calibration vì operational cost thấp nhất trong ba ứng viên. Mỗi station đóng góp đúng 11 tuyến vào tập đánh giá. Deadline mềm giải được toàn bộ 204 tuyến đã chọn, trong khi fallback không phải kích hoạt. Kết quả có ý nghĩa trong evaluator lịch sử Amazon; nó chưa thay thế thử nghiệm hiện trường.")

    document.add_heading("4.4 Đánh giá nhánh quan hệ và quyết định GNN", level=2)
    add_table(document, "Bảng 4.7. Ablation đặc trưng quan hệ", ["Cấu hình", "MAE", "Chênh ở cấp query", "CI 95%"], [
        ["LightGBM nền", "22,71", "Mốc", ""],
        ["LightGBM + lịch sử cạnh/AOI", "24,66", "+2,74", "[2,58; 2,89]"],
    ], source="Nguồn: graph_ablation_v3/summary.json.")
    add_paragraph(document, "Chỉ 65,42% cạnh test từng xuất hiện trong train. Thêm số lần thấy cạnh, số lần thấy đích, ETA trung vị cạnh và cờ edge seen làm kết quả xấu hơn ở cả năm seed. Cổng GNN không đạt; nghiên cứu dừng ở ablation và không trình bày số liệu của một GNN chưa được chạy.")

    document.add_heading("4.5 Khả năng triển khai và cơ chế dự phòng", level=2)
    add_table(document, "Bảng 4.8. Benchmark cục bộ và quy tắc giám sát", ["Nội dung", "Kết quả"], [
        ["Kích thước một model LightGBM", "2,07 MB"],
        ["Median latency 1 dòng", "1,83 ms"],
        ["Median latency batch 4.096", "76,70 ms"],
        ["RSS của tiến trình benchmark", "1,11 GB, gồm Python và dữ liệu"],
        ["PSI cần theo dõi", "0,1"],
        ["PSI cần điều tra hoặc huấn luyện lại", "0,25"],
        ["Fallback solver", "Nearest neighbor + directed 2-opt"],
    ], source="Nguồn: deployment_v3/summary.json.")
    add_paragraph(document, "Nếu schema hoặc tọa độ không hợp lệ, yêu cầu phải chuyển sang lập kế hoạch thủ công. Thành phố chưa thấy không được tự động dispatch; hệ thống dùng trung vị toàn cục làm giá trị tham khảo và gắn cờ. Dự đoán không hữu hạn được thay bằng trung vị train và ghi log. Các ngưỡng PSI là quy tắc nội bộ cần hiệu chỉnh lại khi có dữ liệu vận hành.")

    document.add_heading("4.6 Trả lời câu hỏi nghiên cứu", level=2)
    add_paragraph(document, "RQ1 được trả lời bằng mức giảm MAE 17,74% ở cấp query, với khoảng tin cậy không chứa 0. RQ2 nhận kết quả có điều kiện: mô hình ổn định theo rolling-origin và seed, nhưng suy giảm tại courier, AOI và thành phố chưa thấy. Với RQ3, deadline mềm khắc phục vấn đề không có nghiệm của ràng buộc cứng và cải thiện operational cost trên tập giữ lại. RQ4 không được ủng hộ; thông tin quan hệ hiện tại làm MAE tăng, nên GNN chưa phù hợp với giao thức này.")


def chapter_five(document: Document) -> None:
    document.add_heading("CHƯƠNG 5: KẾT LUẬN VÀ HÀM Ý", level=1)
    document.add_heading("5.1 Kết luận", level=2)
    add_paragraph(document, "Nghiên cứu xây dựng được quy trình ETA theo thời gian và evaluator định tuyến dùng chung. LightGBM đạt MAE 22,71 phút trên 162.762 mẫu tháng 10, tốt hơn historical median 4,89 phút ở cấp query. Kết luận ổn định qua năm seed và ba rolling-origin fold. Không có bằng chứng overfitting nghiêm trọng, dù hiệu năng giảm vừa phải trên dữ liệu tương lai.")
    add_paragraph(document, "Trong định tuyến Amazon, time window cứng chỉ có nghiệm cho 58,33% tuyến. Deadline mềm được hiệu chỉnh trên 17 tuyến calibration và giải được toàn bộ 204 tuyến. Trên 187 tuyến giữ lại, operational cost giảm trung bình 445,27 giây. Kết quả chỉ áp dụng cho ma trận lịch sử và khung giờ đã quan sát, không đồng nghĩa hiệu quả tương tự ngoài hiện trường.")

    document.add_heading("5.2 Đóng góp học thuật và phương pháp", level=2)
    add_paragraph(document, "Đề tài làm rõ đơn vị query và thời điểm thông tin được phép xuất hiện, nhờ đó tránh dùng ngày hoàn tất tương lai để tạo nhóm. Việc tách ETA khỏi định tuyến phản thực giúp giới hạn phát biểu đúng với dữ liệu. Các quyết định city weighting, GNN và penalty được đưa qua cổng validation hoặc calibration thay vì chọn theo test. Bảng claim-evidence liên kết từng kết luận định lượng với artifact máy đọc.")

    document.add_heading("5.3 Hàm ý thực tiễn", level=2)
    add_paragraph(document, "Trong phạm vi năm thành phố LaDe-D, LightGBM phù hợp làm mô hình ETA nền nhờ độ chính xác và latency thấp. Tuy nhiên, hệ thống cần theo dõi riêng courier và AOI mới, không chỉ dùng điểm trung bình toàn hệ thống. Với bộ giải tuyến, deadline mềm nên đi kèm fallback xác định và log nguyên nhân khi solver thất bại. Operational cost phải giữ riêng transit, waiting và lateness để người vận hành nhận biết đánh đổi.")

    document.add_heading("5.4 Hạn chế", level=2)
    add_bullets(document, [
        "LaDe-D không có giao thông thời gian thực, trọng lượng hoặc dung tích xe; số nhiệm vụ chờ chỉ phản ánh tải công việc.",
        "Amazon không có arrival time thực tế tại từng stop; transit matrix là dữ liệu lịch sử và chỉ 7,82% kiện có time window đầy đủ.",
        "Jilin chỉ có 399 mẫu test, nên kết luận riêng cho thành phố này có độ bất định cao.",
        "Leave-one-city-out suy giảm mạnh; mô hình chưa đủ cơ sở để tự động triển khai ở thành phố hoàn toàn mới.",
        "Deadline mềm xấp xỉ nhiều cửa sổ kiện thành một release và deadline ở cấp stop.",
        "Benchmark latency được đo cục bộ, chưa bao gồm API, truy xuất feature, mạng và giám sát production.",
    ])

    document.add_heading("5.5 Hướng nghiên cứu tiếp theo", level=2)
    add_paragraph(document, "Hướng tiếp theo cần ưu tiên dữ liệu hơn kiến trúc. Nếu có trạng thái giao thông, arrival time và thông tin xe, mô hình có thể chuyển từ ETA theo nhiệm vụ sang dự đoán thời gian cạnh. Đối với thành phố mới, cần hiệu chỉnh ít mẫu hoặc mô hình phân cấp thay vì chỉ gán trọng số nghịch đảo. Nhánh GNN chỉ nên mở lại khi node có biểu diễn quy nạp và validation cho thấy lịch sử quan hệ bổ sung thông tin ngoài feature bảng.")
    add_table(document, "Bảng 5.1. Phạm vi kết luận được dữ liệu hỗ trợ", ["Phát biểu", "Trạng thái"], [
        ["LightGBM cải thiện ETA so với historical median trên test tháng 10", "Được hỗ trợ"],
        ["Kết quả ổn định qua seed và ba rolling fold", "Được hỗ trợ"],
        ["Inverse-city weighting cải thiện macro MAE", "Không được hỗ trợ"],
        ["Deadline mềm cải thiện operational cost trong evaluator Amazon", "Được hỗ trợ trên 187 tuyến giữ lại"],
        ["GNN tốt hơn mô hình bảng", "Không được hỗ trợ"],
        ["Hệ thống sử dụng giao thông thời gian thực hoặc trọng lượng", "Không được dữ liệu hỗ trợ"],
        ["Mô hình sẵn sàng tự động triển khai tại thành phố mới", "Chưa được hỗ trợ"],
    ], source="Nguồn: Tổng hợp từ các artifact phiên bản v3; baseline Amazon giữ nguyên ở v2.")


def chapter_four_corrected(document: Document, figures: dict[str, Path], data: dict) -> None:
    metrics = data["eta_metrics"]
    inf = data["inference"]
    robust = data["robust"]
    balanced = data["balanced"]
    rolling = data["rolling"]
    integration = data["integration"]
    graph = data["graph"]
    soft = data["soft"]
    deploy = data["deployment"]
    stability = soft["solver_stability"]
    lgb = metrics["lightgbm_ensemble"]
    hist = metrics["historical_median"]
    by_city = robust["evaluation"]["test"]["by_city"]
    held = soft["held_out_evaluation"]
    station = soft["primary_station_cluster_inference"]

    document.add_heading("CHƯƠNG 4: KẾT QUẢ NGHIÊN CỨU VÀ THẢO LUẬN", level=1)
    document.add_heading("4.1 Kết quả dự đoán ETA", level=2)
    add_paragraph(document, f"Tập test có {ivi(lgb['n'])} đơn thuộc {ivi(inf['queries'])} thời điểm truy vấn. LightGBM đạt MAE {fvi(lgb['mae_minutes'])} phút, thấp nhất trong năm phương pháp. ACC@20 tăng từ {fvi(hist['acc_at_20'] * 100)}% lên {fvi(lgb['acc_at_20'] * 100)}%.")
    rows = []
    labels = {"historical_median": "Historical median", "effective_speed": "Effective speed", "knn": "KNN", "lightgbm_ensemble": "LightGBM, 5 seed", "mlp_ensemble": "MLP, 5 seed"}
    for key, label in labels.items():
        row = metrics[key]
        rows.append([label, fvi(row["mae_minutes"]), fvi(row["rmse_minutes"]), fvi(row["median_absolute_error"]), fvi(row["acc_at_20"] * 100) + "%"])
    add_table(document, "Bảng 4.1. Kết quả ETA tổng thể trên tập kiểm định", ["Mô hình", "MAE", "RMSE", "Median AE", "ACC@20"], rows, source="Nguồn: eta_baselines_v3/summary.json. Đơn vị sai số là phút.")
    mlp_iterations = data["eta"]["model_selection"]["mlp_iterations"].values()
    add_paragraph(document, f"Năm MLP dừng sớm hợp lệ sau {min(mlp_iterations)}–{max(mlp_iterations)} vòng trong trần 250. LightGBM được chọn trước khi mở test vì có query-MAE validation thấp nhất; năm LightGBM dừng sau {min(data['eta']['model_selection']['lightgbm_best_iterations'].values())}–{max(data['eta']['model_selection']['lightgbm_best_iterations'].values())} vòng trong trần 10.000.")
    add_picture(document, figures["mae"], "Hình 4.1. MAE của các mô hình ETA trên tập kiểm định", width=6.2)
    add_paragraph(document, f"Ở cấp truy vấn, mô hình được chọn giảm MAE trung bình {fvi(abs(inf['mean_delta_mae_selected_minus_historical']))} phút, tương ứng {fvi(abs(inf['relative_mae_change']) * 100)}%. CI bootstrap cụm city-courier 95% là [{fvi(inf['courier_cluster_bootstrap_ci95'][0], 3)}; {fvi(inf['courier_cluster_bootstrap_ci95'][1], 3)}] phút. Mô hình tốt hơn tại {ivi(inf['queries_selected_better'])} trong {ivi(inf['queries'])} truy vấn và {ivi(inf['couriers_selected_better'])} trong {ivi(inf['courier_clusters'])} cụm courier. Chênh lệch vẫn âm khi lần lượt bỏ từng thành phố.")

    document.add_heading("4.1.1 Kết quả theo thành phố và nhóm chưa thấy", level=3)
    loo = {row["held_city"]: row for row in data["eta"]["leave_one_city_out"]}
    city_rows = []
    for city in ["Chongqing", "Hangzhou", "Jilin", "Shanghai", "Yantai"]:
        row = by_city[city]
        city_rows.append([city, ivi(row["n"]), fvi(row["mae_minutes"]), fvi(row["acc_at_20"] * 100) + "%", fvi(loo[city]["mae_minutes"])])
    add_table(document, "Bảng 4.2. MAE LightGBM theo thành phố", ["Thành phố", "Số mẫu test", "MAE", "ACC@20", "Leave-one-city-out MAE"], city_rows, source="Nguồn: robustness_v3/summary.json và eta_baselines_v3/summary.json.")
    add_paragraph(document, f"AOI chưa thấy có {ivi(data['slices']['aoi_unseen_rows'])} dòng, chiếm {fvi(data['slices']['aoi_unseen_ratio'] * 100)}% tập test. Leave-one-city-out đều suy giảm so với mô hình có dữ liệu cùng thành phố; Jilin đạt {fvi(loo['Jilin']['mae_minutes'])} phút nhưng chỉ có 939 mẫu test. Vì vậy, kết quả chưa hỗ trợ tự động triển khai tại thành phố hoàn toàn mới.")

    document.add_heading("4.1.2 Quá khớp, mất cân bằng và rolling-origin", level=3)
    ev = robust["evaluation"]
    roll_u = rolling["aggregate"]["unweighted"]
    roll_w = rolling["aggregate"]["city_balanced"]
    val_u = balanced["candidates"]["unweighted"]["validation"]["macro_city_mae"]
    val_w = balanced["candidates"]["city_balanced"]["validation"]["macro_city_mae"]
    lgb_iterations = data["eta"]["model_selection"]["lightgbm_best_iterations"].values()
    rolling_unweighted = [
        row for row in rolling["folds"] if row["candidate"] == "unweighted"
    ]
    rolling_text = " / ".join(fvi(row["micro"]["mae_minutes"]) for row in rolling_unweighted)
    macro_gap = ev["test"]["macro_city_mae"] - ev["test"]["overall"]["mae_minutes"]
    add_table(document, "Bảng 4.3. Kiểm tra độ bền của mô hình ETA", ["Kiểm tra", "Kết quả", "Diễn giải"], [
        ["MAE train / validation / test", f"{fvi(ev['train']['overall']['mae_minutes'])} / {fvi(ev['validation']['overall']['mae_minutes'])} / {fvi(ev['test']['overall']['mae_minutes'])}", "Phân phối validation khó hơn test; không giả định sai số tăng đơn điệu"],
        ["Vòng dừng LightGBM", f"{min(lgb_iterations)}–{max(lgb_iterations)} / 10.000", "Cả năm seed dừng trước trần"],
        ["Rolling tháng 7 / 8 / 9", rolling_text, "Ba cửa sổ chỉ dùng dữ liệu quá khứ"],
        ["Macro MAE test", fvi(ev['test']['macro_city_mae']), f"Chênh micro MAE {fvi(macro_gap)} phút"],
        ["City weighting trên validation", f"{fvi(val_w)} so với {fvi(val_u)}", f"Chọn {balanced['selected']} trên validation"],
        ["PSI lớn nhất", fvi(max(deploy['drift_psi_train_vs_october_test'].values()), 3), "Chưa vượt ngưỡng theo dõi 0,1"],
    ], source="Nguồn: robustness_v3, balanced_v3, rolling_origin_v3 và deployment_v3.")
    add_paragraph(document, f"Test thấp hơn validation {fvi(abs(robust['mae_gaps']['test_minus_validation']))} phút nhưng cao hơn train {fvi(robust['mae_gaps']['test_minus_train'])} phút; do độ khó giữa các tháng không đơn điệu, báo cáo không dùng riêng khoảng cách này để kết luận quá khớp. Gán trọng số nghịch đảo cho macro-MAE validation {fvi(val_w)} so với {fvi(val_u)} phút ở mô hình không trọng số; rolling macro-MAE tương ứng là {fvi(roll_w['macro_city_mae_mean'])} và {fvi(roll_u['macro_city_mae_mean'])} phút. Quyết định `{balanced['selected']}` chỉ dựa trên validation.")

    document.add_heading("4.2 Chất lượng xếp thứ tự trên LaDe-D", level=2)
    order_rows = []
    for row in integration["primary"]:
        order_rows.append([row["model"], fvi(row["hr_at_3"], 4), fvi(row["krc"], 4), fvi(row["lsd"], 3), fvi(row["edit_distance"], 3)])
    add_table(document, f"Bảng 4.4. Kết quả xếp thứ tự trên {ivi(integration['eligible_queries_with_at_least_two_tasks'])} truy vấn", ["Mô hình", "HR@3", "KRC", "LSD", "Edit distance"], order_rows, source="Nguồn: eta_integration_v3/summary.json.")
    noise = integration["noise_sensitivity"]
    add_paragraph(document, f"LightGBM tốt nhất trong các baseline chính trên cả HR@3, KRC, LSD và edit distance. Khi thêm nhiễu chuẩn 5, 10 và 20 phút, KRC trung bình giảm lần lượt còn {fvi(noise['5.0']['krc_mean'], 3)}, {fvi(noise['10.0']['krc_mean'], 3)} và {fvi(noise['20.0']['krc_mean'], 3)}. Giảm sai số ETA hỗ trợ xếp hạng nhưng không thay thế các ràng buộc tuyến.")

    document.add_heading("4.3 Kết quả định tuyến Amazon", level=2)
    add_paragraph(document, "Baseline transit-only giảm thời gian di chuyển nhưng tạo độ trễ lớn. Time window cứng chỉ có nghiệm cho 119 trong 204 tuyến, tương ứng 58,33%, nên không thể dùng riêng nhóm có nghiệm để kết luận cho toàn bộ mẫu. Deadline mềm được dùng để duy trì tính khả thi và định lượng đánh đổi giữa thời gian tuyến với độ trễ.")
    document.add_heading("4.3.1 Bộ giải deadline mềm và suy luận theo station", level=3)
    ci = station["station_cluster_bootstrap_ci95"]
    add_table(document, "Bảng 4.5. Kết quả deadline mềm trên tập đánh giá giữ lại", ["Chỉ số", "Kết quả"], [
        ["Tuyến đánh giá / station", f"{held['routes']} / {station['stations']}"],
        ["Chênh operational cost trung bình theo tuyến", fvi(held["mean_operational_delta_vs_observed"]) + " giây"],
        ["Chênh trung bình khi mỗi station có trọng số bằng nhau", fvi(station["equal_station_mean_operational_delta"]) + " giây"],
        ["CI bootstrap cụm station 95%", f"[{fvi(ci[0])}; {fvi(ci[1])}] giây"],
        ["Station tốt hơn / xấu hơn observed", f"{station['stations_better_than_observed']} / {station['stations_worse_than_observed']}"],
        ["Kiểm định dấu hai phía", "p = " + fvi(station["exact_sign_test_two_sided_p"], 4)],
        ["Tỷ lệ có nghiệm / fallback", f"{fvi(soft['all_routes']['solver_solved_rate'] * 100)}% / {fvi(soft['all_routes']['fallback_rate'] * 100)}%"],
    ], source="Nguồn: amazon_soft_windows_v3/summary.json. Operational cost gồm closed duration và tổng độ trễ kiện.")
    add_picture(
        document,
        figures["route"],
        "Hình 4.2. Hiệu ứng và độ ổn định của bộ giải deadline mềm",
        width=6.2,
    )
    add_paragraph(document, "Hệ số penalty được chọn trên 17 tuyến calibration, một tuyến mỗi station. Phân tích chính không xem 187 tuyến là các quan sát độc lập mà bootstrap theo 17 station. Hiệu ứng thuận lợi xuất hiện tại đa số station; kiểm định dấu đạt ngưỡng 5% và CI cụm station không chứa 0 trong lần chạy chính. Bằng chứng thống kê này chỉ mô tả nghiệm tìm được dưới ngân sách một giây, không loại bỏ rủi ro biến thiên thuật toán được kiểm tra ở mục tiếp theo.")
    document.add_heading("4.3.2 Độ ổn định của bộ giải", level=3)
    add_table(document, "Bảng 4.6. Lặp lại bộ giải trên toàn bộ 204 tuyến", ["Kiểm tra", "Kết quả"], [
        ["Số lần lặp mỗi tuyến", str(soft["protocol"]["repeats_per_route"])],
        ["Tuyến có cùng chuỗi ở mọi lần", f"{stability['routes_with_identical_sequence_all_repeats']}/{stability['routes']}"],
        ["Tuyến có cùng operational cost", f"{stability['routes_with_identical_cost_all_repeats']}/{stability['routes']}"],
        ["Biên độ cost trung bình trong từng tuyến", fvi(stability["mean_within_route_operational_cost_range"]) + " giây"],
        ["Biên độ cost lớn nhất", fvi(stability["maximum_within_route_operational_cost_range"]) + " giây"],
    ], source="Nguồn: amazon_soft_windows_v3/summary.json.")
    add_paragraph(document, f"Bộ giải giới hạn một giây không luôn tạo duy nhất một chuỗi: {stability['routes_with_identical_sequence_all_repeats']} trong {stability['routes']} tuyến có cùng chuỗi ở cả ba lần. Báo cáo dùng median theo tuyến và chỉ diễn giải chất lượng tổng hợp, không tuyên bố nghiệm tối ưu toàn cục hoặc duy nhất.")

    document.add_heading("4.4 Đánh giá nhánh quan hệ và quyết định GNN", level=2)
    gci = graph["validation_bootstrap_ci95"]
    add_table(document, "Bảng 4.7. Ablation đặc trưng quan hệ", ["Cấu hình", "MAE", "Chênh ở cấp query", "CI 95%"], [
        ["LightGBM nền", fvi(lgb["mae_minutes"]), "Mốc", ""],
        ["LightGBM + lịch sử cạnh/AOI", fvi(graph["validation_ensemble_metrics"]["mae_minutes"]), "+" + fvi(graph["validation_paired_query_mean_delta"]), f"[{fvi(gci[0])}; {fvi(gci[1])}]"],
    ], source="Nguồn: graph_ablation_v3/summary.json; quyết định chỉ dùng validation.")
    add_paragraph(document, f"Trên validation, đặc trưng quan hệ làm query-MAE xấu hơn {fvi(graph['validation_paired_query_mean_delta'])} phút và CI nằm hoàn toàn trên 0. Chỉ {fvi(graph['edge_seen_rate_test'] * 100)}% cạnh test từng xuất hiện trong train. Test xác nhận cùng chiều nhưng không tham gia quyết định. Cổng GNN không đạt; nghiên cứu không gán kết quả cho một GNN chưa được huấn luyện.")

    document.add_heading("4.5 Khả năng triển khai và cơ chế dự phòng", level=2)
    add_table(document, "Bảng 4.8. Benchmark cục bộ và quy tắc giám sát", ["Nội dung", "Kết quả"], [
        ["Kích thước một model LightGBM", fvi(deploy["model_file_bytes"] / 1_000_000) + " MB"],
        ["Median latency 1 dòng", fvi(deploy["latency"]["1"]["median_batch_milliseconds"], 3) + " ms"],
        ["Median latency batch 4.096", fvi(deploy["latency"]["4096"]["median_batch_milliseconds"], 2) + " ms"],
        ["RSS tiến trình", fvi(deploy["process_max_rss"] / 1_000_000) + " MB, gồm Python và dữ liệu"],
        ["Ngưỡng PSI theo dõi / điều tra", "0,1 / 0,25"],
        ["Fallback solver", "Nearest neighbor + directed 2-opt"],
    ], source="Nguồn: deployment_v3/summary.json. Latency là suy luận cục bộ, không phải độ trễ dịch vụ đầu cuối.")
    add_paragraph(document, "Dữ liệu sai schema hoặc tọa độ phải chuyển sang lập kế hoạch thủ công. Thành phố chưa thấy không được tự động dispatch. Dự đoán không hữu hạn được thay bằng trung vị train và ghi log. Các ngưỡng PSI là quy tắc vận hành ban đầu, cần hiệu chỉnh khi có dữ liệu production.")

    document.add_heading("4.6 Trả lời câu hỏi nghiên cứu", level=2)
    add_paragraph(document, f"RQ1 được trả lời bằng mức giảm query-MAE {fvi(abs(inf['relative_mae_change']) * 100)}%, với CI cụm courier không chứa 0. RQ2 nhận kết quả có điều kiện: mô hình ổn định qua rolling-origin và seed, nhưng suy giảm trên AOI và thành phố chưa thấy. Với RQ3, deadline mềm giải được toàn bộ mẫu và operational cost tốt hơn ở 14 trong 17 station; CI cụm station không chứa 0, song chuỗi không hoàn toàn bất biến giữa các lần chạy. RQ4 không được ủng hộ vì đặc trưng quan hệ làm MAE validation tăng.")


def chapter_five_corrected(document: Document, data: dict) -> None:
    lgb = data["eta_metrics"]["lightgbm_ensemble"]
    inf = data["inference"]
    station = data["soft"]["primary_station_cluster_inference"]
    document.add_heading("CHƯƠNG 5: KẾT LUẬN VÀ HÀM Ý", level=1)
    document.add_heading("5.1 Kết luận", level=2)
    add_paragraph(document, f"Nghiên cứu xây dựng quy trình ETA theo thời gian và evaluator định tuyến dùng chung. Sau khi loại bộ lọc cohort dựa trên nhãn tương lai, LightGBM được chọn trên validation và đạt MAE {fvi(lgb['mae_minutes'])} phút trên {ivi(lgb['n'])} mẫu test. Ở cấp truy vấn, MAE giảm {fvi(abs(inf['relative_mae_change']) * 100)}% so với historical median; CI bootstrap cụm courier không chứa 0. Kết quả được kiểm tra qua năm seed và ba rolling-origin fold.")
    add_paragraph(document, f"Trong định tuyến Amazon, deadline mềm giải được toàn bộ 204 tuyến đã chọn. Trên 187 tuyến đánh giá, hướng cải thiện xuất hiện ở {station['stations_better_than_observed']} trong {station['stations']} station và CI bootstrap cụm station của lần chạy chính không chứa 0. Dù vậy, nghiệm có thể thay đổi khi chạy lại bộ giải giới hạn một giây. Kết quả hỗ trợ tiếp tục thử nghiệm có kiểm soát, chưa đủ để khẳng định lợi ích thực địa hoặc nghiệm tối ưu toàn cục.")
    document.add_heading("5.2 Đóng góp học thuật và phương pháp", level=2)
    add_paragraph(document, "Đóng góp thứ nhất là giao thức tạo truy vấn ETA không dùng chân trời nhãn tương lai để chọn cohort. Đóng góp thứ hai là đánh giá theo thời gian, thành phố, AOI và seed, đồng thời chọn mô hình chỉ trên validation. Đóng góp thứ ba là cách đánh giá deadline mềm tách calibration khỏi evaluation, chạy lặp toàn bộ tuyến và suy luận theo station. Cuối cùng, cổng ablation validation ngăn việc triển khai GNN khi thông tin quan hệ chưa tạo giá trị đo được.")
    document.add_heading("5.3 Hàm ý thực tiễn", level=2)
    add_paragraph(document, "LightGBM phù hợp làm mô hình ETA nền trong năm thành phố đã quan sát, nhưng cần giám sát AOI mới và từ chối tự động điều phối ở thành phố chưa hiệu chỉnh. Bộ giải tuyến phải lưu seed, giới hạn thời gian, chuỗi tìm được và fallback. Khi dùng trong vận hành, cần thử nghiệm đối chứng hoặc shadow mode trước khi thay thế quy trình hiện tại.")
    document.add_heading("5.4 Hạn chế", level=2)
    add_bullets(document, [
        "LaDe-D không có giao thông thời gian thực, trọng lượng hoặc dung tích xe; số nhiệm vụ chờ chỉ phản ánh tải công việc quan sát được.",
        "Amazon không có arrival time thực tế tại từng stop; transit matrix là dữ liệu lịch sử và chỉ 7,82% kiện có time window đầy đủ.",
        "Jilin chỉ có 939 mẫu test, nên kết quả riêng cho thành phố này có độ bất định cao.",
        "ETA có đuôi rất dài và có thể chứa độ trễ quy trình; mô hình không được diễn giải là dự đoán thời gian lái xe thuần túy.",
        "Bootstrap cụm chỉ có 17 station; CI của lần chạy chính không phản ánh đầy đủ biến thiên do bộ giải giới hạn thời gian.",
        "Bộ giải giới hạn một giây không tái tạo cùng chuỗi trên mọi lần chạy và không chứng minh tối ưu toàn cục.",
        "Benchmark latency là phép đo cục bộ, chưa gồm API, truy xuất feature, mạng và giám sát production.",
    ])
    document.add_heading("5.5 Hướng nghiên cứu tiếp theo", level=2)
    add_paragraph(document, "Ưu tiên tiếp theo là bổ sung arrival time, trạng thái giao thông và thông tin xe để có thể dự đoán thời gian cạnh thay vì dùng proxy. Thực nghiệm định tuyến cần tăng số lần lặp, cố định random seed khi bộ giải hỗ trợ và đánh giá theo nhiều ngân sách thời gian. Nhánh GNN chỉ nên mở lại khi có biểu diễn quy nạp cho node mới và validation cho thấy quan hệ bổ sung thông tin ngoài feature bảng.")
    add_table(document, "Bảng 5.1. Phạm vi kết luận được dữ liệu hỗ trợ", ["Phát biểu", "Trạng thái"], [
        ["LightGBM cải thiện ETA so với historical median trên test tháng 10", "Được hỗ trợ"],
        ["Kết quả ổn định qua seed và ba rolling fold", "Được hỗ trợ"],
        ["Inverse-city weighting cải thiện macro MAE", "Không được hỗ trợ"],
        ["Deadline mềm có xu hướng cải thiện tại đa số station", "Được hỗ trợ có điều kiện"],
        ["Operational cost cải thiện trong lần chạy chính ở cấp station", "Được CI cụm hỗ trợ"],
        ["Mức cải thiện giữ nguyên khi chạy lại bộ giải", "Chưa được hỗ trợ"],
        ["GNN tốt hơn mô hình bảng", "Không được hỗ trợ"],
        ["Mô hình sẵn sàng tự động triển khai tại thành phố mới", "Chưa được hỗ trợ"],
    ], source="Nguồn: Tổng hợp từ các artifact phiên bản v3 đã kiểm tra lại.")


def chapter_six(document: Document) -> None:
    document.add_heading("CHƯƠNG 6: TÀI LIỆU THAM KHẢO", level=1)
    refs = [
        "[1] Wu, L., Wen, H., Hu, H., và cộng sự. (2024). LaDe: The First Comprehensive Last-mile Express Dataset from Industry. Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining, 5991-6002. https://doi.org/10.1145/3637528.3671548.",
        "[2] Merchán, D., Arora, J., Pachon, J., Konduri, K., Winkenbach, M., Parks, S., và Noszek, J. (2024). 2021 Amazon Last Mile Routing Research Challenge: Data Set. Transportation Science, 58(1), 8-11. https://doi.org/10.1287/trsc.2022.1173.",
        "[3] Ke, G., Meng, Q., Finley, T., và cộng sự. (2017). LightGBM: A Highly Efficient Gradient Boosting Decision Tree. Advances in Neural Information Processing Systems, 30. https://proceedings.neurips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html.",
        "[4] Wen, H., Lin, Y., Mao, X., và cộng sự. (2022). Graph2Route: A Dynamic Spatial-Temporal Graph Neural Network for Pick-up and Delivery Route Prediction. Proceedings of the 28th ACM SIGKDD Conference on Knowledge Discovery and Data Mining, 4143-4152. https://doi.org/10.1145/3534678.3539084.",
        "[5] Cai, T., Wan, H., Wu, F., và cộng sự. (2023). M2G4RTP: A Multi-Level and Multi-Task Graph Model for Instant-Logistics Route and Time Joint Prediction. 2023 IEEE 39th International Conference on Data Engineering, 3296-3308. https://doi.org/10.1109/ICDE55515.2023.00253.",
        "[6] Google. (2025). OR-Tools: Vehicle Routing. Tài liệu chính thức, cập nhật ngày 22/01/2025, truy cập ngày 17/11/2026. https://developers.google.com/optimization/routing.",
    ]
    for text in refs:
        p = document.add_paragraph(text)
        p.paragraph_format.first_line_indent = Cm(-0.8)
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(7)


def appendices(document: Document) -> None:
    document.add_heading("PHỤ LỤC", level=1)
    document.add_heading("Phụ lục A. Quy tắc đọc kết quả", level=2)
    add_paragraph(document, "MAE, RMSE, median AE, LSD, edit distance, transit, lateness và operational cost có hướng thấp hơn là tốt hơn. ACC@20, HR@3 và KRC có hướng cao hơn là tốt hơn. Chênh lệch ETA được tính bằng LightGBM trừ historical median; giá trị âm biểu thị cải thiện. Chênh lệch tuyến được tính bằng phương pháp đề xuất trừ observed.")
    document.add_heading("Phụ lục B. Liên kết phát biểu và artifact", level=2)
    add_table(document, "Bảng B.1. Artifact nguồn của các kết luận chính", ["Kết luận", "Artifact"], [
        ["Dataset không rò rỉ", "eta_dataset_v3/validation.json"],
        ["Kết quả ETA", "eta_baselines_v3/summary.json"],
        ["Kiểm định ghép cặp", "statistics_v3/eta_paired_inference.json"],
        ["Rolling-origin", "rolling_origin_v3/summary.json"],
        ["City weighting", "balanced_v3/summary.json"],
        ["Baseline Amazon", "amazon_baselines_v2/summary.json"],
        ["Deadline mềm và độ ổn định", "amazon_soft_windows_v3/summary.json"],
        ["Quyết định GNN", "graph_ablation_v3/summary.json"],
        ["Latency và drift", "deployment_v3/summary.json"],
        ["Checksum", "MANIFEST.json"],
    ], source="Nguồn: eta_route_optimization/artifacts/generated.")
    document.add_heading("Phụ lục C. Kiểm tra tái lập", level=2)
    add_paragraph(document, "Gói nghiên cứu lưu source độc lập, cấu hình, unit test, prediction cấp mẫu, kết quả cấp query và route, checksum cùng lệnh tái lập `scripts/reproduce_v3.sh`. Vòng kiểm tra cuối được ghi trong tài liệu tái lập và manifest; dữ liệu thô không được nhúng vào file Word.")
    document.add_heading("Phụ lục D. Công bố việc sử dụng công cụ", level=2)
    add_paragraph(document, "Công cụ lập trình được dùng để kiểm toán dữ liệu, chạy thực nghiệm, tính chỉ số, kiểm tra chéo artifact và định dạng báo cáo. Nội dung kết quả không được tạo từ số liệu ước đoán. Mỗi con số định lượng trong chương 4 có tệp nguồn được nêu tại Phụ lục B.")


def build() -> Path:
    data = verify_artifacts()
    figures = make_figures(data)
    shutil.copy2(TEMPLATE, OUTPUT)
    document = Document(OUTPUT)
    remove_body_after_cover(document)
    configure_styles(document)
    enable_field_updates(document)
    document.paragraphs[6].text = (
        "ĐỀ TÀI: DỰ ĐOÁN THỜI GIAN HOÀN TẤT VÀ TỐI ƯU THỨ TỰ GIAO HÀNG "
        "CHẶNG CUỐI DỰA TRÊN DỮ LIỆU LỊCH SỬ, ĐẶC ĐIỂM KHU VỰC VÀ TẢI CÔNG VIỆC"
    )
    document.paragraphs[6].style = "CoverTitle"
    document.core_properties.title = "Dự đoán ETA và tối ưu thứ tự giao hàng chặng cuối"
    document.core_properties.subject = "Chuyên đề ngoại khóa"
    document.core_properties.author = "Lưu Gia Mẫn"
    document.core_properties.keywords = "ETA, last-mile delivery, LightGBM, OR-Tools, LaDe-D, Amazon"
    add_front_matter(document, data)
    chapter_one(document)
    chapter_two(document)
    chapter_three(document, figures)
    chapter_four_corrected(document, figures, data)
    chapter_five_corrected(document, data)
    chapter_six(document)
    appendices(document)
    configure_a4_pages(document)
    document.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
