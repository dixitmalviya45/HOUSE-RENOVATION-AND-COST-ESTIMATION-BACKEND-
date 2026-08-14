"""ReportLab PDF report generator."""

from __future__ import annotations

import io
from datetime import datetime

import httpx
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


async def _fetch_image(url: str | None) -> io.BytesIO | None:
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return io.BytesIO(response.content)
    except Exception:
        return None


def _styles():
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "E2MTitle",
        parent=base["Title"],
        fontSize=22,
        textColor=colors.HexColor("#312e81"),
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    heading = ParagraphStyle(
        "E2MHeading",
        parent=base["Heading2"],
        textColor=colors.HexColor("#4338ca"),
        spaceBefore=8,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "E2MBody",
        parent=base["Normal"],
        fontSize=11,
        leading=15,
        alignment=TA_LEFT,
    )
    footer = ParagraphStyle(
        "E2MFooter",
        parent=base["Normal"],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )
    return title, heading, body, footer


async def generate_report(project, estimate) -> bytes:
    """
    Build a multi-page PDF: cover, before/after, materials, areas, costs.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    title, heading, body, footer = _styles()
    story = []

    # Cover
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("E2M Renovation Estimate", title))
    story.append(Paragraph(project.name, heading))
    story.append(
        Paragraph(
            f"Generated on {datetime.utcnow().strftime('%d %b %Y')}",
            body,
        )
    )
    story.append(Spacer(1, 0.4 * inch))
    story.append(
        Paragraph(
            "AI-assisted exterior renovation visualization and advisory cost estimate.",
            body,
        )
    )
    story.append(PageBreak())

    original = await _fetch_image(project.original_image_url)
    redesign = await _fetch_image(
        project.selected_redesign_url
        or (project.redesigned_image_urls[0] if project.redesigned_image_urls else None)
    )

    story.append(Paragraph("Original House", heading))
    if original:
        img = RLImage(original, width=5.5 * inch, height=4 * inch)
        story.append(img)
    else:
        story.append(Paragraph("Original image unavailable.", body))
    story.append(PageBreak())

    story.append(Paragraph("Redesigned House", heading))
    if redesign:
        img = RLImage(redesign, width=5.5 * inch, height=4 * inch)
        story.append(img)
    else:
        story.append(Paragraph("Redesigned image unavailable.", body))
    story.append(PageBreak())

    # Materials
    story.append(Paragraph("Selected Materials", heading))
    mat_rows = [["Region", "Segment", "Material"]]
    segment_map = {s.id: s for s in project.segments or []}
    for sel in project.material_selections or []:
        seg = segment_map.get(sel.segment_id)
        mat_rows.append(
            [
                seg.region_type if seg else "—",
                seg.label if seg else sel.segment_id,
                sel.material_name,
            ]
        )
    if len(mat_rows) == 1:
        mat_rows.append(["—", "—", "No materials selected"])
    table = Table(mat_rows, colWidths=[1.5 * inch, 1.8 * inch, 3 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.Color(0.93, 0.93, 0.98)]),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    story.append(PageBreak())

    # Areas
    story.append(Paragraph("Area Calculations", heading))
    area_rows = [["Segment", "Region", "Area (sq.ft)", "Pixels"]]
    for area in project.area_calculations or []:
        area_rows.append(
            [
                area.segment_label,
                area.region_type,
                f"{area.area_sqft:.2f}",
                str(area.pixel_area),
            ]
        )
    if len(area_rows) == 1:
        area_rows.append(["—", "—", "—", "—"])
    area_table = Table(area_rows, colWidths=[1.8 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
    area_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10b981")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(area_table)
    story.append(PageBreak())

    # Costs
    story.append(Paragraph("Detailed Cost Breakdown (INR)", heading))
    cost_rows = [
        ["Component", "Area", "Material", "Qty", "Waste%", "Mat. ₹", "Labor ₹", "Total ₹"]
    ]
    for item in estimate.line_items or []:
        cost_rows.append(
            [
                item.segment_label,
                f"{item.area_sqft:.1f}",
                item.material_name[:18],
                f"{item.material_qty_with_wastage:.2f}",
                f"{item.wastage_percent:.0f}",
                f"{item.material_cost:,.0f}",
                f"{item.labor_cost:,.0f}",
                f"{item.total_cost:,.0f}",
            ]
        )
    cost_rows.append(
        [
            "TOTAL",
            "",
            "",
            "",
            "",
            f"{estimate.total_material_cost:,.0f}",
            f"{estimate.total_labor_cost:,.0f}",
            f"{estimate.grand_total:,.0f}",
        ]
    )
    cost_table = Table(
        cost_rows,
        colWidths=[
            1.0 * inch,
            0.6 * inch,
            1.2 * inch,
            0.6 * inch,
            0.55 * inch,
            0.7 * inch,
            0.7 * inch,
            0.75 * inch,
        ],
    )
    cost_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312e81")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2ff")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(cost_table)
    story.append(Spacer(1, 0.4 * inch))
    story.append(
        Paragraph(
            f"<b>Grand Total: ₹{estimate.grand_total:,.2f}</b>",
            heading,
        )
    )
    story.append(Spacer(1, 0.5 * inch))
    story.append(
        Paragraph(
            "This estimate is advisory. Actual costs may vary.",
            footer,
        )
    )

    doc.build(story)
    return buffer.getvalue()
