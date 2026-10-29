"""
Fatwa Exporter Engine
Handles file organization, PDF generation via WeasyPrint,
JPEG generation via PyMuPDF + PIL, and PDF merging with interactive bookmarks.
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from PIL import Image
import pymupdf
from weasyprint import HTML

from core.formatter import FatwaHTMLFormatter
from core.scraper import FatwaItem


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Removes invalid OS filesystem characters and truncates safely."""
    # Replace invalid Windows chars: \ / : * ? " < > |
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    clean = re.sub(r'\s+', '_', clean).strip('._ ')
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip('._ ')
    return clean or "fatwa"


class FatwaExporter:
    def __init__(self, base_output_dir: str):
        self.base_output_dir = os.path.abspath(base_output_dir)
        os.makedirs(self.base_output_dir, exist_ok=True)

    def export_single_fatwa(
        self,
        fatwa: FatwaItem,
        category_dir_name: str,
        generate_html: bool = True,
        generate_pdf: bool = True,
        generate_jpeg: bool = True,
        jpeg_dpi: int = 150,
    ) -> Dict[str, Optional[str]]:
        """
        Creates a dedicated folder for the fatwa and saves HTML, PDF, and JPEG files.
        Returns paths of created files.
        """
        safe_title = sanitize_filename(fatwa.title, max_length=45)
        folder_name = f"فتوى_{fatwa.id}_{safe_title}"
        
        # Target directory: base_output_dir / category_dir_name / folder_name
        fatwa_dir = os.path.join(self.base_output_dir, category_dir_name, folder_name)
        os.makedirs(fatwa_dir, exist_ok=True)

        results = {
            "dir": fatwa_dir,
            "html": None,
            "pdf": None,
            "jpeg": None,
            "id": fatwa.id,
            "title": fatwa.title,
        }

        # 1. Generate & Save HTML
        html_content = FatwaHTMLFormatter.generate_html(fatwa)
        html_path = os.path.join(fatwa_dir, f"فتوى_{fatwa.id}.html")
        if generate_html or generate_pdf:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            results["html"] = html_path

        # 2. Render & Save PDF via WeasyPrint
        pdf_path = os.path.join(fatwa_dir, f"فتوى_{fatwa.id}.pdf")
        if generate_pdf or generate_jpeg:
            try:
                HTML(string=html_content).write_pdf(pdf_path)
                results["pdf"] = pdf_path
            except Exception as e:
                # Fallback writing from file
                HTML(filename=html_path).write_pdf(pdf_path)
                results["pdf"] = pdf_path

        # 3. Render & Save JPEG via PyMuPDF + PIL
        if generate_jpeg and results["pdf"] and os.path.exists(results["pdf"]):
            try:
                jpeg_path = self._render_pdf_to_jpeg(
                    pdf_path=results["pdf"],
                    output_dir=fatwa_dir,
                    fatwa_id=fatwa.id,
                    dpi=jpeg_dpi,
                )
                results["jpeg"] = jpeg_path
            except Exception as e:
                print(f"Error rendering JPEG for fatwa {fatwa.id}: {e}")

        return results

    def _render_pdf_to_jpeg(
        self,
        pdf_path: str,
        output_dir: str,
        fatwa_id: str,
        dpi: int = 150,
    ) -> str:
        """
        Renders all pages of a PDF to high-res images and stitches them
        vertically into a single continuous JPEG image.
        Also saves individual page JPEGs if multi-page.
        """
        doc = pymupdf.open(pdf_path)
        page_images: List[Image.Image] = []

        for page_idx, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_images.append(img)
            
            # If multi-page, also save individual page file
            if len(doc) > 1:
                single_page_path = os.path.join(output_dir, f"فتوى_{fatwa_id}_صفحة_{page_idx + 1}.jpeg")
                img.save(single_page_path, "JPEG", quality=92)

        main_jpeg_path = os.path.join(output_dir, f"فتوى_{fatwa_id}.jpeg")

        if len(page_images) == 1:
            page_images[0].save(main_jpeg_path, "JPEG", quality=92)
        elif len(page_images) > 1:
            # Stitch images vertically
            max_w = max(img.width for img in page_images)
            total_h = sum(img.height for img in page_images)

            stitched = Image.new("RGB", (max_w, total_h), (255, 255, 255))
            curr_y = 0
            for img in page_images:
                # center if widths differ
                x_offset = (max_w - img.width) // 2
                stitched.paste(img, (x_offset, curr_y))
                curr_y += img.height

            stitched.save(main_jpeg_path, "JPEG", quality=92)

        doc.close()
        return main_jpeg_path

    def merge_all_fatawa_pdfs(
        self,
        pdf_items: List[Tuple[str, str, str]],  # (fatwa_id, fatwa_title, pdf_path)
        category_title: str,
        category_dir_name: str,
    ) -> Optional[str]:
        """
        Merges all downloaded individual fatwa PDFs into a single Master PDF
        with an interactive Table of Contents / Bookmarks.
        """
        valid_items = [item for item in pdf_items if os.path.exists(item[2])]
        if not valid_items:
            return None

        cat_dir = os.path.join(self.base_output_dir, category_dir_name)
        os.makedirs(cat_dir, exist_ok=True)

        safe_cat = sanitize_filename(category_title, max_length=40)
        merged_pdf_path = os.path.join(cat_dir, f"جميع_فتاوى_{safe_cat}_المجمعة.pdf")

        merged_doc = pymupdf.open()
        toc = []

        # 1. Create a decorative Cover Page for the merged collection
        try:
            cover_html = self._generate_cover_html(category_title, len(valid_items))
            cover_pdf_path = os.path.join(cat_dir, "_temp_cover.pdf")
            HTML(string=cover_html).write_pdf(cover_pdf_path)
            cover_doc = pymupdf.open(cover_pdf_path)
            merged_doc.insert_pdf(cover_doc)
            toc.append([1, "غلاف المجموعة وفهرس المحتويات", 1])
            cover_doc.close()
            if os.path.exists(cover_pdf_path):
                os.remove(cover_pdf_path)
        except Exception as e:
            print(f"Warning: Could not create cover page: {e}")

        # 2. Insert each individual fatwa PDF
        for fid, ftitle, path in valid_items:
            try:
                single_doc = pymupdf.open(path)
                start_page = len(merged_doc) + 1  # 1-based page number
                merged_doc.insert_pdf(single_doc)
                
                # Add bookmark to TOC
                bookmark_title = f"فتوى {fid}: {ftitle}"
                toc.append([1, bookmark_title, start_page])
                single_doc.close()
            except Exception as e:
                print(f"Error inserting PDF for fatwa {fid}: {e}")

        # Set Table of Contents / Bookmarks
        merged_doc.set_toc(toc)
        merged_doc.save(merged_pdf_path)
        merged_doc.close()

        # 3. Also generate an HTML master index for the category
        self.generate_master_index_html(valid_items, category_title, cat_dir, merged_pdf_path)

        return merged_pdf_path

    def _generate_cover_html(self, category_title: str, total_count: int) -> str:
        """Generates a stylish cover page HTML for the merged PDF."""
        return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;800;900&family=Amiri:wght@400;700&display=swap');
@page {{
    size: A4;
    margin: 25mm 20mm;
}}
body {{
    direction: rtl;
    text-align: center;
    font-family: 'Cairo', 'Amiri', 'Traditional Arabic', sans-serif;
    color: #1E293B;
    background: #FFFFFF;
}}
.cover-box {{
    border: 3px double #0D5C3A;
    border-radius: 20px;
    padding: 60px 40px;
    height: 90%;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
}}
.logo-title {{
    font-size: 24pt;
    font-weight: 900;
    color: #0D5C3A;
    margin-bottom: 10px;
}}
.sub-logo {{
    font-size: 13pt;
    color: #C69214;
    font-weight: 700;
}}
.ornament {{
    font-size: 24pt;
    color: #C69214;
    margin: 30px 0;
}}
.main-title {{
    font-size: 28pt;
    font-weight: 900;
    color: #073B24;
    line-height: 1.6;
    margin: 20px 0;
}}
.badge-count {{
    display: inline-block;
    background: #EBF7EE;
    color: #0D5C3A;
    border: 2px solid #86EFAC;
    padding: 10px 30px;
    border-radius: 30px;
    font-size: 16pt;
    font-weight: 800;
    margin-top: 20px;
}}
.footer-text {{
    margin-top: 50px;
    font-size: 11pt;
    color: #64748B;
    border-top: 1px solid #E2E8F0;
    padding-top: 20px;
}}
</style>
</head>
<body>
<div class="cover-box">
    <div>
        <div class="logo-title">موقع إسلام ويب</div>
        <div class="sub-logo">مركز الفتوى - العرض الموضوعي</div>
    </div>
    
    <div class="ornament">❖ ❖ ❖</div>
    
    <div>
        <div style="font-size: 15pt; color: #64748B;">موسوعة فتاوى قسم:</div>
        <div class="main-title">{category_title}</div>
        <div class="badge-count">إجمالي الفتاوى المجمّعة: {total_count} فتوى</div>
    </div>
    
    <div class="ornament">❖ ❖ ❖</div>
    
    <div class="footer-text">
        تم استخراجها وتنسيقها ودمجها تلقائياً مع فهرس تفاعلي للبحث والتصفح
    </div>
</div>
</body>
</html>"""

    def generate_master_index_html(
        self,
        valid_items: List[Tuple[str, str, str]],
        category_title: str,
        cat_dir: str,
        merged_pdf_path: str,
    ):
        """Generates a responsive HTML index file listing all downloaded fatwas with clickable local links."""
        rows_html = []
        for idx, (fid, ftitle, pdf_path) in enumerate(valid_items, 1):
            folder_rel = os.path.relpath(os.path.dirname(pdf_path), cat_dir)
            html_rel = f"{folder_rel}/فتوى_{fid}.html"
            pdf_rel = f"{folder_rel}/فتوى_{fid}.pdf"
            jpeg_rel = f"{folder_rel}/فتوى_{fid}.jpeg"

            rows_html.append(f"""
            <tr>
                <td class="idx-col">{idx}</td>
                <td class="id-col"><span class="badge-id">{fid}</span></td>
                <td class="title-col">
                    <a href="{html_rel}" target="_blank" class="fatwa-name">{ftitle}</a>
                </td>
                <td class="actions-col">
                    <a href="{html_rel}" target="_blank" class="btn btn-html">HTML</a>
                    <a href="{pdf_rel}" target="_blank" class="btn btn-pdf">PDF</a>
                    <a href="{jpeg_rel}" target="_blank" class="btn btn-img">صورة</a>
                    <a href="https://islamweb.net/ar/fatwa/{fid}" target="_blank" class="btn btn-web">الأصل</a>
                </td>
            </tr>
            """)

        merged_rel = os.path.basename(merged_pdf_path)

        index_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>فهرس فتاوى: {category_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
    body {{
        direction: rtl;
        font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
        background: #F8FAFC;
        margin: 0;
        padding: 30px 20px;
        color: #1E293B;
    }}
    .container {{
        max-width: 1050px;
        margin: 0 auto;
        background: #FFFFFF;
        border-radius: 16px;
        padding: 35px 40px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
    }}
    .header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #0D5C3A;
        padding-bottom: 20px;
        margin-bottom: 25px;
        flex-wrap: wrap;
        gap: 15px;
    }}
    h1 {{
        color: #0D5C3A;
        margin: 0;
        font-size: 22pt;
        font-weight: 800;
    }}
    .merged-btn {{
        background: #0D5C3A;
        color: #FFFFFF;
        text-decoration: none;
        padding: 10px 22px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 11pt;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 2px 4px rgba(13,92,58,0.2);
    }}
    .merged-btn:hover {{
        background: #073B24;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
    }}
    th {{
        background: #F1F5F9;
        color: #475569;
        padding: 12px 14px;
        text-align: right;
        font-weight: 700;
        border-bottom: 2px solid #CBD5E1;
    }}
    td {{
        padding: 12px 14px;
        border-bottom: 1px solid #E2E8F0;
        vertical-align: middle;
    }}
    tr:hover {{
        background: #F8FAFC;
    }}
    .badge-id {{
        background: #EBF7EE;
        color: #0D5C3A;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        border: 1px solid #A7F3D0;
    }}
    .fatwa-name {{
        color: #0F172A;
        text-decoration: none;
        font-weight: 700;
        font-size: 11.5pt;
    }}
    .fatwa-name:hover {{
        color: #0D5C3A;
        text-decoration: underline;
    }}
    .btn {{
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 9.5pt;
        font-weight: 700;
        text-decoration: none;
        display: inline-block;
        margin-left: 4px;
    }}
    .btn-html {{ background: #E0E7FF; color: #4338CA; }}
    .btn-pdf {{ background: #FEE2E2; color: #B91C1C; }}
    .btn-img {{ background: #FEF3C7; color: #B45309; }}
    .btn-web {{ background: #F1F5F9; color: #475569; }}
    .btn:hover {{ opacity: 0.85; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>فهرس فتاوى: {category_title}</h1>
            <p style="color: #64748B; margin: 5px 0 0 0;">إجمالي الفتاوى المستخرجة: {len(valid_items)} فتوى</p>
        </div>
        <div>
            <a href="{merged_rel}" target="_blank" class="merged-btn">📕 فتح ملف PDF المجمّع</a>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th style="width: 50px;">#</th>
                <th style="width: 90px;">رقم الفتوى</th>
                <th>عنوان الفتوى</th>
                <th style="width: 220px;">الملفات والروابط</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
</div>
</body>
</html>"""

        index_path = os.path.join(cat_dir, "فهرس_الفتاوى.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_html)

