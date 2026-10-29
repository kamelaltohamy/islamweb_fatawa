"""
End-to-End Integration Test for Islamweb Fatawa Desktop Application
Tests scraping, formatting, PDF generation, JPEG generation, and PDF merging.
"""
import os
import shutil
from core.scraper import IslamwebScraper, FatwaItem
from core.formatter import FatwaHTMLFormatter
from core.exporter import FatwaExporter

def run_e2e_test():
    print("==================================================")
    print("Starting End-to-End Test for Islamweb Application")
    print("==================================================")
    
    test_output_dir = os.path.abspath("./test_e2e_output")
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir)
    os.makedirs(test_output_dir, exist_ok=True)

    scraper = IslamwebScraper(request_delay=0.2)
    exporter = FatwaExporter(base_output_dir=test_output_dir)

    # Category URL: الإيمان ونواقضه (188)
    cat_url = "https://islamweb.net/ar/fatawa/188/%D8%A7%D9%84%D8%A5%D9%8A%D9%85%D8%A7%D9%86-%D9%88%D9%86%D9%88%D8%A7%D9%82%D8%B6%D9%87"
    
    print("\n1. Testing category info extraction:")
    info = scraper.extract_category_info(cat_url)
    print("   Category ID:", info["id"])
    print("   Category Title:", info["title"])
    assert info["id"] == "188", "Category ID should be 188"

    print("\n2. Testing collecting first 2 fatwa links from live category:")
    links = scraper.collect_all_fatwa_links(
        category_url=cat_url,
        include_subcategories=False,
        max_fatawa=2,
        on_log=lambda msg, lvl: print(f"   [{lvl}] {msg}"),
    )
    print(f"   Collected {len(links)} links.")
    assert len(links) >= 1, "Should have collected at least 1 link"

    print("\n3. Testing fetching and formatting individual fatwa:")
    first_item = links[0]
    fatwa = scraper.fetch_single_fatwa(first_item["url"])
    assert fatwa is not None, "Failed to fetch fatwa"
    print("   Fatwa ID:", fatwa.id)
    print("   Fatwa Title:", fatwa.title)
    print("   Fatwa Date:", fatwa.date)
    print("   Fatwa Question snippet:", fatwa.question[:80])
    print("   Fatwa Answer len:", len(fatwa.answer_text))

    print("\n4. Testing export to separate folder (HTML + PDF + JPEG):")
    cat_dir_name = "فتاوى_الإيمان_ونواقضه"
    export_res = exporter.export_single_fatwa(
        fatwa=fatwa,
        category_dir_name=cat_dir_name,
        generate_html=True,
        generate_pdf=True,
        generate_jpeg=True,
    )
    
    print("   Saved Folder:", export_res["dir"])
    print("   HTML File:", export_res["html"])
    print("   PDF File:", export_res["pdf"])
    print("   JPEG File:", export_res["jpeg"])

    assert os.path.exists(export_res["html"]), "HTML file must exist"
    assert os.path.exists(export_res["pdf"]), "PDF file must exist"
    assert os.path.exists(export_res["jpeg"]), "JPEG file must exist"
    print("   All 3 formats verified successfully!")

    print("\n5. Testing merging multiple PDFs into one Master PDF with bookmarks:")
    pdf_items = [
        (fatwa.id, fatwa.title, export_res["pdf"]),
        (fatwa.id + "_demo", fatwa.title + " (ملف تجريبي إضافي)", export_res["pdf"]),
    ]
    merged_pdf_path = exporter.merge_all_fatawa_pdfs(
        pdf_items=pdf_items,
        category_title="الإيمان ونواقضه",
        category_dir_name=cat_dir_name,
    )
    print("   Merged PDF:", merged_pdf_path)
    assert os.path.exists(merged_pdf_path), "Merged PDF must exist"
    assert os.path.getsize(merged_pdf_path) > 10000, "Merged PDF should have content"

    master_index_html = os.path.join(test_output_dir, cat_dir_name, "فهرس_الفتاوى.html")
    assert os.path.exists(master_index_html), "Master HTML index must exist"
    print("   Master HTML Index:", master_index_html)

    print("\n6. Testing UI module import & instantiation:")
    from ui.app import FatawaApp
    app = FatawaApp()
    app.withdraw()
    print("   UI Window initialized successfully.")
    app.destroy()
    print("   UI Window destroyed cleanly.")

    print("\n==================================================")
    print("[SUCCESS] ALL TESTS PASSED SUCCESSFULLY! E2E VERIFIED!")
    print("==================================================")

    # Clean up test output
    shutil.rmtree(test_output_dir)
    print("Cleaned up test_e2e_output.")

if __name__ == "__main__":
    run_e2e_test()
