"""
Islamweb Fatawa Scraper Engine
Extracts fatwa listings and individual fatwa details from Islamweb.net.
"""

import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set
import requests
from bs4 import BeautifulSoup


@dataclass
class FatwaItem:
    id: str
    title: str
    url: str
    date: str = ""
    views: str = ""
    category_path: str = ""
    question: str = ""
    answer_html: str = ""
    answer_text: str = ""
    mufti: str = "مركز الفتوى بإشراف د.عبدالله الفقيه"
    scraped_at: str = ""


class IslamwebScraper:
    def __init__(
        self,
        base_url: str = "https://islamweb.net",
        request_delay: float = 0.5,
        max_retries: int = 3,
        timeout: int = 20,
    ):
        self.base_url = base_url.rstrip("/")
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        
        # State control
        self.cancelled = False
        self.paused = False

    def cancel(self):
        self.cancelled = True

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def _wait_if_paused(self):
        while self.paused and not self.cancelled:
            time.sleep(0.3)

    def _get(self, url: str) -> Optional[requests.Response]:
        """Performs a GET request with retries and utf-8 handling."""
        self._wait_if_paused()
        if self.cancelled:
            return None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.encoding = "utf-8"
                if resp.status_code == 200:
                    if self.request_delay > 0:
                        time.sleep(self.request_delay)
                    return resp
                elif resp.status_code == 404:
                    return None
            except Exception as e:
                if attempt == self.max_retries:
                    raise e
                time.sleep(1.0 * attempt)
        return None

    def is_single_fatwa_url(self, url: str) -> bool:
        """Checks if URL points to a specific fatwa (/fatwa/{id}/...)."""
        clean = url.strip()
        return bool(re.search(r'/fatwa/\d+', clean) and '/fatawa/' not in clean)

    def is_category_url(self, url: str) -> bool:
        """Checks if URL points to a category (/fatawa/{id}/...)."""
        return bool(re.search(r'/fatawa/\d+', url.strip()))

    def extract_category_info(self, url: str) -> Dict[str, str]:
        """Extracts category ID and title slug from category URL."""
        m = re.search(r'/fatawa/(\d+)(?:/([^?#]+))?', url)
        if m:
            cat_id = m.group(1)
            raw_slug = m.group(2) or ""
            slug = urllib.parse.unquote(raw_slug).replace("-", " ").strip()
            return {"id": cat_id, "title": slug or f"تصنيف_{cat_id}"}
        return {"id": "custom", "title": "فتاوى"}

    def get_fatwa_links_from_category_page(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extracts individual fatwa links and metadata from a category listing page."""
        fatwas = []
        seen_ids = set()

        # Method 1: Find <li> items or cards with top-item & footer-item
        cards = soup.find_all(lambda tag: tag.name in ['div', 'li'] and tag.find('div', class_='top-item'))
        for card in cards:
            h2 = card.find('h2')
            if not h2:
                continue
            a_link = h2.find('a', href=True)
            if not a_link:
                continue
            href = a_link['href']
            m = re.search(r'/fatwa/(\d+)', href)
            if not m:
                continue
            fid = m.group(1)
            if fid in seen_ids:
                continue
            seen_ids.add(fid)

            title = a_link.get_text(strip=True)
            # Find date / views from footer-item if present
            date_str = ""
            views_str = ""
            footer = card.find('div', class_='footer-item')
            if footer:
                samps = footer.find_all('samp')
                if len(samps) >= 2:
                    views_str = samps[1].get_text(strip=True)
                if len(samps) >= 3:
                    date_str = samps[2].get_text(strip=True)

            fatwas.append({
                "id": fid,
                "title": title,
                "url": urllib.parse.urljoin(self.base_url, href),
                "date": date_str,
                "views": views_str,
            })

        # Method 2: Fallback scan for any link matching /fatwa/\d+/
        if not fatwas:
            for a in soup.find_all('a', href=re.compile(r'/fatwa/(\d+)/')):
                href = a['href']
                m = re.search(r'/fatwa/(\d+)/', href)
                if not m:
                    continue
                fid = m.group(1)
                if fid in seen_ids:
                    continue
                title = a.get_text(strip=True)
                if title and not title.isdigit() and len(title) > 3:
                    seen_ids.add(fid)
                    fatwas.append({
                        "id": fid,
                        "title": title,
                        "url": urllib.parse.urljoin(self.base_url, href),
                        "date": "",
                        "views": "",
                    })

        return fatwas

    def discover_subcategories(self, soup: BeautifulSoup, current_url: str) -> List[Dict[str, str]]:
        """Discovers subcategories listed under treeview or subtopics."""
        subcategories = []
        seen = set()

        # Subcategories usually have treeview=2 or are within topic tree
        for a in soup.find_all('a', href=re.compile(r'/fatawa/\d+/')):
            href = a['href']
            txt = a.get_text(strip=True)
            m = re.search(r'/fatawa/(\d+)/', href)
            if not m:
                continue
            cat_id = m.group(1)
            full_url = urllib.parse.urljoin(current_url, href)
            # Filter out self
            if full_url == current_url or cat_id in seen:
                continue
            if 'treeview=2' in href or 'fatCatleft' in str(a.parent):
                seen.add(cat_id)
                subcategories.append({
                    "id": cat_id,
                    "title": txt or f"قسم_{cat_id}",
                    "url": full_url
                })
        return subcategories

    def collect_all_fatwa_links(
        self,
        category_url: str,
        include_subcategories: bool = False,
        max_fatawa: Optional[int] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Dict[str, str]]:
        """
        Gathers all fatwa links across all pagination pages (and optionally subcategories).
        """
        log = on_log or (lambda msg, lvl="INFO": None)
        all_fatwas: List[Dict[str, str]] = []
        seen_ids: Set[str] = set()

        categories_to_crawl = [category_url]
        crawled_categories = set()

        while categories_to_crawl and not self.cancelled:
            current_cat_url = categories_to_crawl.pop(0)
            if current_cat_url in crawled_categories:
                continue
            crawled_categories.add(current_cat_url)

            cat_info = self.extract_category_info(current_cat_url)
            log(f"جاري فحص القسم: {cat_info['title']} (رقم {cat_info['id']})...", "INFO")

            page = 1
            consecutive_empty_pages = 0

            while not self.cancelled:
                self._wait_if_paused()
                if self.cancelled:
                    break

                page_url = f"{current_cat_url}?pageno={page}&order=" if "?" not in current_cat_url else f"{current_cat_url}&pageno={page}"
                log(f"جاري جلب الصفحة {page} للقسم: {cat_info['title']}...", "DEBUG")
                
                resp = self._get(page_url)
                if not resp or resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')

                # Check if page has subcategories on page 1
                if page == 1 and include_subcategories:
                    subs = self.discover_subcategories(soup, current_cat_url)
                    for sub in subs:
                        if sub['url'] not in crawled_categories and sub['url'] not in categories_to_crawl:
                            categories_to_crawl.append(sub['url'])
                            log(f"تم اكتشاف قسم فرعي: {sub['title']}", "INFO")

                page_fatwas = self.get_fatwa_links_from_category_page(soup)

                # Filter newly discovered fatwas
                new_in_page = 0
                for f in page_fatwas:
                    if f["id"] not in seen_ids:
                        seen_ids.add(f["id"])
                        all_fatwas.append(f)
                        new_in_page += 1
                        if max_fatawa and len(all_fatwas) >= max_fatawa:
                            log(f"تم الوصول إلى الحد الأقصى المطلوب ({max_fatawa} فتوى).", "SUCCESS")
                            return all_fatwas

                if new_in_page == 0:
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= 1:
                        # End of pages for this category
                        break
                else:
                    consecutive_empty_pages = 0
                    log(f"الصفحة {page}: تم العثور على {new_in_page} فتوى جديدة (الإجمالي حتى الآن: {len(all_fatwas)}).", "INFO")

                if on_progress:
                    on_progress(len(all_fatwas), max_fatawa or len(all_fatwas), f"تم العثور على {len(all_fatwas)} فتوى...")

                # Check pagination links in page to see if there's a next page
                pagination = soup.find('ul', class_='pagination')
                has_next = False
                if pagination:
                    for a in pagination.find_all('a', href=True):
                        if f'pageno={page + 1}' in a['href']:
                            has_next = True
                            break
                if not has_next and new_in_page < 15:
                    # Islamweb uses 15 items per page
                    break

                page += 1

        log(f"اكتمل جمع الروابط! إجمالي الفتاوى المكتشفة: {len(all_fatwas)} فتوى.", "SUCCESS")
        return all_fatwas

    def fetch_single_fatwa(self, fatwa_url_or_id: str) -> Optional[FatwaItem]:
        """
        Fetches and thoroughly parses a single fatwa from Islamweb.
        """
        if fatwa_url_or_id.isdigit():
            url = f"{self.base_url}/ar/fatwa/{fatwa_url_or_id}"
        else:
            url = fatwa_url_or_id

        resp = self._get(url)
        if not resp or resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 1. Fatwa ID
        fatwa_id = ""
        m_id = re.search(r'/fatwa/(\d+)', url)
        if m_id:
            fatwa_id = m_id.group(1)
        if not fatwa_id:
            # check rating or script
            m_rate = re.search(r'RATE_FATWA\[[A-Z]\]\[(\d+)\]', resp.text)
            if m_rate:
                fatwa_id = m_rate.group(1)

        # 2. Title
        title = ""
        h2 = soup.find('h2')
        if h2:
            title = h2.get_text(strip=True)
        if not title:
            # Fallback title from page title
            if soup.title:
                t = soup.title.get_text(strip=True)
                title = t.split('-')[0].strip()

        # 3. Metadata from footer-item
        views = ""
        date_str = ""
        footer_item = soup.find('div', class_='footer-item')
        if footer_item:
            samps = footer_item.find_all('samp')
            if len(samps) >= 1 and not fatwa_id:
                fatwa_id = samps[0].get_text(strip=True)
            if len(samps) >= 2:
                views = samps[1].get_text(strip=True)
            if len(samps) >= 3:
                date_str = samps[2].get_text(strip=True)

        # Fallback date search
        if not date_str:
            m_date = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})', resp.text)
            if m_date:
                date_str = m_date.group(1)

        # 4. Breadcrumbs / Category tree
        category_parts = []
        bc_elem = soup.find(lambda t: t.name in ['ol', 'ul'] and 'breadcrumb' in str(t.get('class', [])))
        if bc_elem:
            for li in bc_elem.find_all('li'):
                txt = li.get_text(strip=True)
                if txt and txt not in ['الرئيسية', 'الفتاوى']:
                    category_parts.append(txt)
        
        # If no breadcrumbs, look for category links in left/sidebar
        if not category_parts:
            for a in soup.find_all('a', href=re.compile(r'/fatawa/\d+/')):
                txt = a.get_text(strip=True)
                if txt and txt not in category_parts and len(txt) > 2:
                    category_parts.append(txt)
                    if len(category_parts) >= 3:
                        break

        category_path = " > ".join(category_parts) if category_parts else "العقيدة الإسلامية > الإيمان ونواقضه"

        # 5. Question & Answer
        question_text = ""
        answer_html = ""
        answer_text = ""

        quest_blocks = soup.find_all('div', class_='quest-fatwa')
        for b in quest_blocks:
            h3 = b.find('h3')
            heading = h3.get_text(strip=True) if h3 else ""

            content_div = b.find('div', itemprop='text') or b.find('div', class_='content')
            
            if 'السؤال' in heading or 'quest' in str(b.get('class', [])):
                if content_div:
                    question_text = content_div.get_text(separator='\n', strip=True)
                else:
                    # Extract from block directly
                    t = b.get_text(separator='\n', strip=True)
                    t = re.sub(r'https?://[^\s]+', '', t)
                    t = t.replace('تم نسخ الرابط', '').replace(heading, '').strip()
                    question_text = t

            elif 'الإجاب' in heading or 'Answer' in str(b.get('itemtype', '')):
                if content_div:
                    answer_html = str(content_div)
                    answer_text = content_div.get_text(separator='\n', strip=True)
                else:
                    answer_html = str(b)
                    answer_text = b.get_text(separator='\n', strip=True)

        # Fallback question & answer if blocks weren't cleanly labeled
        if not question_text and len(quest_blocks) >= 1:
            q_div = quest_blocks[0].find('div', itemprop='text')
            if q_div:
                question_text = q_div.get_text(strip=True)

        if not answer_html and len(quest_blocks) >= 2:
            a_div = quest_blocks[1].find('div', itemprop='text')
            if a_div:
                answer_html = str(a_div)
                answer_text = a_div.get_text(separator='\n', strip=True)

        # Clean question from copy-url leftovers
        question_text = re.sub(r'https%3A%2F%2F[^\s]+', '', question_text).strip()
        question_text = re.sub(r'^\d+\s*', '', question_text).strip()

        return FatwaItem(
            id=fatwa_id or "000000",
            title=title or f"فتوى رقم {fatwa_id}",
            url=url,
            date=date_str or "غير محدد",
            views=views or "غير محدد",
            category_path=category_path,
            question=question_text,
            answer_html=answer_html,
            answer_text=answer_text,
            scraped_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

