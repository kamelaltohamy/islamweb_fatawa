"""
Fatwa HTML Formatter & Redesigner
Designs a beautiful, modern, Islamic-styled HTML page for scraped fatwas
with rich typography for Quranic verses, Hadiths, and scholar quotes.
"""

import re
from bs4 import BeautifulSoup
from typing import Optional
from core.scraper import FatwaItem


class FatwaHTMLFormatter:
    """
    Transforms raw fatwa data into a visually stunning, responsive,
    print-ready Arabic HTML document with specialized Islamic typography.
    """

    # Islamic honorifics
    HONORIFICS = [
        r'صلى الله عليه وسلم',
        r'عليه الصلاة والسلام',
        r'صلى الله عليه وآله وسلم',
        r'عليهما الصلاة والسلام',
        r'عليهم الصلاة والسلام',
        r'عليهما السلام',
        r'عليهم السلام',
        r'عليه السلام',
        r'عليها السلام',
        r'رضي الله عنهما',
        r'رضي الله عنهم',
        r'رضي الله عنها',
        r'رضي الله عنه',
        r'رحمه الله تعالى',
        r'رحمه الله',
        r'رحمهم الله',
        r'رحمها الله',
        r'عز وجل',
        r'سبحانه وتعالى',
        r'جل وعلا',
        r'تبارك وتعالى',
        r'جل جلاله',
    ]

    @classmethod
    def enhance_arabic_text(cls, html_or_text: str) -> str:
        """
        Cleans legacy tags and enhances Quranic verses, Hadiths, and scholar quotes.
        """
        if not html_or_text or not html_or_text.strip():
            return "<p>لا يوجد نص متوفر.</p>"

        # Wrap in root for BeautifulSoup parsing
        soup = BeautifulSoup(f"<div class='raw-root'>{html_or_text}</div>", "html.parser")

        # 1. Process legacy Islamweb font colors
        for font in soup.find_all('font'):
            color = (font.get('color') or '').lower().strip('#')
            if color in ['ff0000', 'red']:
                font.name = 'span'
                font['class'] = ['intro-praise']
            elif color in ['800000', 'maroon']:
                font.name = 'span'
                font['class'] = ['scholar-name']
            elif color in ['6600cc', 'purple']:
                font.name = 'span'
                font['class'] = ['quote-text']
            elif color in ['000000', 'black']:
                font.unwrap()
            else:
                font.unwrap()

        # 2. Convert relative links to absolute Islamweb links
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/'):
                a['href'] = f"https://islamweb.net{href}"
            a['class'] = a.get('class', []) + ['fatwa-ref-link']
            a['target'] = '_blank'
            a['title'] = 'فتح الفتوى الأصلية على إسلام ويب'

        raw_html = str(soup.find('div', class_='raw-root'))
        raw_html = raw_html[23:-6]  # remove <div class='raw-root'> and </div>

        # 3. Enhance Quranic verses
        # Case A: Explicit ornate brackets ﴿...﴾
        def format_quran(match):
            verse = match.group(1).strip()
            return f'<span class="quran-verse"><span class="quran-bracket">﴿</span> {verse} <span class="quran-bracket">﴾</span></span>'

        raw_html = re.sub(r'﴿([^﴾]+)﴾', format_quran, raw_html)

        # Case B: Prefixed by "قوله تعالى:" or "قال تعالى:" or "لقول الله تعالى:"
        # Matches verse followed by punctuation or ending transition
        verse_prefix_pattern = (
            r'((?:لقول|وقول|قول|قال|لقوله|وقوله)\s+(?:الله\s+)?(?:تعالى|عز وجل|سبحانه|جل وعلا)[:\s]+)'
            r'([\u0600-\u06FF\s،؛\'"«»\{\}\(\)]+?)'
            r'(?=[.\n]|(?:فإذا|وقد|ثم|اهـ|انتهى|قال|$))'
        )

        def wrap_prefix_verse(m):
            prefix = m.group(1)
            v_text = m.group(2).strip()
            # Clean outer quotes if any
            v_text = re.sub(r'^[\'"«\{\(]+|[\'"»\}\)]+$', '', v_text).strip()
            if len(v_text) > 4 and 'quran-verse' not in v_text and 'intro-praise' not in v_text:
                return f'{prefix}<span class="quran-verse"><span class="quran-bracket">﴿</span> {v_text} <span class="quran-bracket">﴾</span></span>. '
            return m.group(0)

        raw_html = re.sub(verse_prefix_pattern, wrap_prefix_verse, raw_html)

        # 4. Enhance Prophetic Hadiths in « ... »
        def format_hadith(m):
            hadith_content = m.group(1).strip()
            if 'quran-verse' in hadith_content:
                return m.group(0)
            return f'<span class="hadith-text">«{hadith_content}»</span>'

        raw_html = re.sub(r'«([^»]+)»', format_hadith, raw_html)

        # 5. Enhance Honorifics
        for h in cls.HONORIFICS:
            pattern = r'(?<![="\'\w/])(' + re.escape(h) + r')(?![="\'\w/])'
            raw_html = re.sub(pattern, r'<span class="honorific">\1</span>', raw_html)

        # 6. Enhance "والله أعلم" at the end
        raw_html = re.sub(
            r'(والله\s+أعلم[.!]?)',
            r'<div class="closing-phrase">\1</div>',
            raw_html
        )

        return raw_html

    @classmethod
    def generate_html(cls, fatwa: FatwaItem) -> str:
        """
        Generates the complete standalone HTML document with embedded CSS and modern Islamic design.
        """
        # Format question and answer
        formatted_question = cls.enhance_arabic_text(
            f"<p>{fatwa.question.replace('\n', '</p><p>')}</p>" if fatwa.question else "<p>لا يوجد نص للسؤال.</p>"
        )

        # Answer content
        if fatwa.answer_html and "<" in fatwa.answer_html:
            formatted_answer = cls.enhance_arabic_text(fatwa.answer_html)
        else:
            paragraphs = fatwa.answer_text.split('\n')
            p_html = "".join([f"<p>{p.strip()}</p>" for p in paragraphs if p.strip()])
            formatted_answer = cls.enhance_arabic_text(p_html)

        views_display = f"{fatwa.views} مشاهدة" if fatwa.views else "غير محدد"
        date_display = fatwa.date if fatwa.date else "غير محدد"

        html_template = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>فتوى رقم {fatwa.id}: {fatwa.title}</title>
    
    <!-- Google Fonts for High-Quality Islamic & Arabic Typography -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Amiri:ital,wght@0,400;0,700;1,400&family=Cairo:wght@400;600;700;800;900&family=Scheherazade+New:wght@400;600;700&display=swap" rel="stylesheet">

    <style>
        :root {{
            --primary-emerald: #0D5C3A;
            --primary-dark: #073B24;
            --primary-light: #EBF7EE;
            --accent-gold: #C69214;
            --accent-gold-light: #FDF8EC;
            --quran-green: #0C6444;
            --quran-bg: #F0FDF4;
            --quran-border: #86EFAC;
            --hadith-color: #7B341E;
            --hadith-bg: #FFFBEB;
            --hadith-border: #D97706;
            --text-main: #1E293B;
            --text-muted: #64748B;
            --bg-page: #F8FAFC;
            --card-bg: #FFFFFF;
            --border-light: #E2E8F0;
        }}

        @page {{
            size: A4;
            margin: 16mm 14mm 18mm 14mm;
            @top-right {{
                content: "موقع إسلام ويب - مركز الفتوى";
                font-family: 'Cairo', 'Traditional Arabic', sans-serif;
                font-size: 9pt;
                font-weight: 700;
                color: #0D5C3A;
            }}
            @top-left {{
                content: "فتوى رقم: {fatwa.id}";
                font-family: 'Cairo', sans-serif;
                font-size: 9pt;
                color: #64748B;
            }}
            @bottom-center {{
                content: "صفحة " counter(page) " من " counter(pages);
                font-family: 'Cairo', sans-serif;
                font-size: 9pt;
                color: #94A3B8;
                border-top: 1px solid #E2E8F0;
                padding-top: 6px;
                width: 100%;
            }}
        }}

        * {{
            box-sizing: border-box;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}

        body {{
            direction: rtl;
            text-align: right;
            font-family: 'Amiri', 'Traditional Arabic', 'Segoe UI', Tahoma, sans-serif;
            font-size: 15.5pt;
            line-height: 2.0;
            color: var(--text-main);
            background-color: var(--bg-page);
            margin: 0;
            padding: 25px 15px;
        }}

        .main-wrapper {{
            max-width: 900px;
            margin: 0 auto;
            background: var(--card-bg);
            border: 1px solid var(--border-light);
            border-radius: 16px;
            padding: 35px 40px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.03);
        }}

        /* Islamic Geometric Header */
        .header-section {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--primary-emerald);
            padding-bottom: 18px;
            margin-bottom: 22px;
            position: relative;
        }}

        .header-section::after {{
            content: "❖";
            position: absolute;
            bottom: -11px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--card-bg);
            padding: 0 10px;
            color: var(--accent-gold);
            font-size: 14pt;
        }}

        .brand-box {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .brand-icon {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, var(--primary-emerald), var(--primary-dark));
            color: #FFFFFF;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20pt;
            font-family: 'Cairo', sans-serif;
            font-weight: 800;
            box-shadow: 0 4px 6px rgba(13, 92, 58, 0.2);
        }}

        .brand-text h2 {{
            font-family: 'Cairo', sans-serif;
            font-size: 15pt;
            font-weight: 800;
            color: var(--primary-emerald);
            margin: 0;
            line-height: 1.2;
        }}

        .brand-text span {{
            font-family: 'Cairo', sans-serif;
            font-size: 9.5pt;
            color: var(--text-muted);
            font-weight: 600;
        }}

        .fatwa-badge {{
            background: linear-gradient(135deg, var(--primary-emerald), #15803D);
            color: #FFFFFF;
            padding: 6px 16px;
            border-radius: 20px;
            font-family: 'Cairo', sans-serif;
            font-size: 11pt;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}

        /* Fatwa Title */
        .title-container {{
            margin: 20px 0 24px 0;
        }}

        .fatwa-title {{
            font-family: 'Cairo', 'Amiri', sans-serif;
            font-size: 21pt;
            font-weight: 900;
            color: var(--primary-dark);
            line-height: 1.5;
            margin: 0;
            padding-right: 14px;
            border-right: 5px solid var(--accent-gold);
        }}

        /* Metadata Grid */
        .meta-card {{
            display: table;
            width: 100%;
            background-color: #F8FAFC;
            border: 1px solid var(--border-light);
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 28px;
        }}

        .meta-row {{
            display: table-row;
        }}

        .meta-item {{
            display: table-cell;
            padding: 8px 12px;
            font-family: 'Cairo', sans-serif;
            font-size: 10.5pt;
            vertical-align: middle;
        }}

        .meta-label {{
            color: var(--text-muted);
            font-weight: 600;
            margin-left: 6px;
        }}

        .meta-value {{
            color: var(--text-main);
            font-weight: 700;
        }}

        .meta-tag {{
            background: #E2E8F0;
            color: #334155;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 9.5pt;
        }}

        /* Content Sections */
        .content-card {{
            margin-bottom: 26px;
            border: 1px solid var(--border-light);
            border-radius: 12px;
            overflow: hidden;
            background: #FFFFFF;
            page-break-inside: avoid;
            break-inside: avoid;
        }}

        .card-header {{
            font-family: 'Cairo', sans-serif;
            font-size: 13.5pt;
            font-weight: 800;
            padding: 12px 22px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .question-card {{
            border-right: 5px solid #3B82F6;
        }}

        .question-header {{
            background-color: #EFF6FF;
            color: #1D4ED8;
            border-bottom: 1px solid #DBEAFE;
        }}

        .answer-card {{
            border-right: 5px solid var(--primary-emerald);
        }}

        .answer-header {{
            background-color: var(--primary-light);
            color: var(--primary-emerald);
            border-bottom: 1px solid #DCFCE7;
        }}

        .card-body {{
            padding: 22px 26px;
            font-size: 15.5pt;
            line-height: 2.1;
        }}

        .card-body p {{
            margin: 0 0 16px 0;
            text-align: justify;
        }}

        .card-body p:last-child {{
            margin-bottom: 0;
        }}

        /* Quranic Verses Styling */
        .quran-verse {{
            font-family: 'Amiri Quran', 'Scheherazade New', 'Amiri', serif;
            font-size: 17.5pt;
            font-weight: normal;
            color: var(--quran-green);
            background-color: var(--quran-bg);
            padding: 2px 8px;
            margin: 0 3px;
            border-radius: 8px;
            border: 1px dashed var(--quran-border);
            line-height: 2.3;
            display: inline;
        }}

        .quran-bracket {{
            color: var(--accent-gold);
            font-weight: bold;
            font-size: 1.2em;
            padding: 0 2px;
        }}

        /* Hadith Styling */
        .hadith-text {{
            font-family: 'Amiri', 'Traditional Arabic', serif;
            font-weight: bold;
            color: var(--hadith-color);
            background-color: var(--hadith-bg);
            border-right: 4px solid var(--hadith-border);
            padding: 4px 12px;
            margin: 0 2px;
            border-radius: 0 6px 6px 0;
            display: inline;
        }}

        /* Scholar Quotes & Names */
        .scholar-name {{
            font-weight: bold;
            color: #881337;
            background-color: #FFE4E6;
            padding: 1px 6px;
            border-radius: 4px;
        }}

        .quote-text {{
            background-color: #F8FAFC;
            color: #1E293B;
            border-right: 3px solid #64748B;
            padding: 4px 10px;
            margin: 6px 0;
            display: inline-block;
            border-radius: 0 4px 4px 0;
        }}

        /* Intro Praise / Hamd */
        .intro-praise {{
            color: #991B1B;
            font-weight: bold;
            font-size: 1.05em;
        }}

        /* Honorifics */
        .honorific {{
            color: #64748B;
            font-size: 0.88em;
            font-weight: normal;
            margin: 0 2px;
            background-color: #F1F5F9;
            padding: 0 4px;
            border-radius: 3px;
        }}

        /* Fatwa References Links */
        .fatwa-ref-link {{
            color: var(--primary-emerald);
            font-weight: 700;
            text-decoration: none;
            background: #E8F5E9;
            padding: 1px 8px;
            border-radius: 12px;
            border: 1px solid #A5D6A7;
            font-size: 0.9em;
            display: inline-block;
            transition: all 0.2s ease;
        }}

        .fatwa-ref-link:hover {{
            background: var(--primary-emerald);
            color: #FFFFFF;
        }}

        .closing-phrase {{
            font-family: 'Cairo', 'Amiri', sans-serif;
            font-weight: 800;
            font-size: 15pt;
            color: var(--primary-emerald);
            text-align: left;
            margin-top: 24px;
            padding-top: 10px;
            border-top: 1px dashed var(--border-light);
        }}

        /* Footer Info */
        .footer-section {{
            margin-top: 35px;
            border-top: 2px solid #E2E8F0;
            padding-top: 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-family: 'Cairo', sans-serif;
            font-size: 9.5pt;
            color: var(--text-muted);
            flex-wrap: wrap;
            gap: 10px;
        }}

        .source-link {{
            color: var(--primary-emerald);
            text-decoration: none;
            font-weight: 700;
        }}

        .source-link:hover {{
            text-decoration: underline;
        }}

        .watermark {{
            font-size: 8.5pt;
            color: #94A3B8;
        }}

        @media (max-width: 640px) {{
            body {{
                padding: 10px 5px;
                font-size: 14pt;
            }}
            .main-wrapper {{
                padding: 20px 15px;
                border-radius: 8px;
            }}
            .fatwa-title {{
                font-size: 17pt;
            }}
            .meta-card {{
                display: block;
            }}
            .meta-row {{
                display: block;
            }}
            .meta-item {{
                display: block;
                padding: 4px 0;
            }}
        }}
    </style>
</head>
<body>

<div class="main-wrapper">
    <!-- Header -->
    <header class="header-section">
        <div class="brand-box">
            <div class="brand-icon">ف</div>
            <div class="brand-text">
                <h2>موقع إسلام ويب</h2>
                <span>مركز الفتوى - العرض الموضوعي</span>
            </div>
        </div>
        <div class="fatwa-badge">
            <span>فتوى رقم:</span>
            <strong>{fatwa.id}</strong>
        </div>
    </header>

    <!-- Title -->
    <div class="title-container">
        <h1 class="fatwa-title">{fatwa.title}</h1>
    </div>

    <!-- Metadata Card -->
    <div class="meta-card">
        <div class="meta-row">
            <div class="meta-item">
                <span class="meta-label">التصنيف الموضوعي:</span>
                <span class="meta-value meta-tag">{fatwa.category_path}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">تاريخ الفتوى:</span>
                <span class="meta-value">{date_display}</span>
            </div>
        </div>
        <div class="meta-row">
            <div class="meta-item">
                <span class="meta-label">عدد القراءات:</span>
                <span class="meta-value">{views_display}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">المفتي:</span>
                <span class="meta-value">{fatwa.mufti}</span>
            </div>
        </div>
    </div>

    <!-- Question Section -->
    <section class="content-card question-card">
        <div class="card-header question-header">
            <span>❓</span>
            <span>الســــؤال</span>
        </div>
        <div class="card-body">
            {formatted_question}
        </div>
    </section>

    <!-- Answer Section -->
    <section class="content-card answer-card">
        <div class="card-header answer-header">
            <span>💬</span>
            <span>الإجـابــــة</span>
        </div>
        <div class="card-body">
            {formatted_answer}
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer-section">
        <div>
            <span>رابط الفتوى الأصلي:</span>
            <a href="{fatwa.url}" target="_blank" class="source-link">{fatwa.url}</a>
        </div>
        <div class="watermark">
            تم الاستخراج والتنسيق تلقائياً | {fatwa.scraped_at}
        </div>
    </footer>
</div>

</body>
</html>
"""
        return html_template

