"""
Islamweb Fatawa Desktop Application UI
Modern Arabic GUI built with CustomTkinter.
Supports live scraping, threading, status tracking, logging, and file opening.
"""

import os
import queue
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional
import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.scraper import IslamwebScraper, FatwaItem
from core.exporter import FatwaExporter, sanitize_filename


class FatawaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Configuration
        self.title("مستخرج ومصمم فتاوى إسلام ويب | Islamweb Fatawa Scraper & Designer")
        self.geometry("1060x820")
        self.minsize(920, 680)

        # Theme
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("green")

        # Runtime State
        self.worker_thread: Optional[threading.Thread] = None
        self.msg_queue: queue.Queue = queue.Queue()
        self.scraper: Optional[IslamwebScraper] = None
        self.is_running = False
        self.is_paused = False
        self.last_merged_pdf: Optional[str] = None
        self.last_output_dir: Optional[str] = None

        # Statistics
        self.stats = {
            "found": 0,
            "processed": 0,
            "pdf": 0,
            "jpeg": 0,
        }

        # Build UI
        self._build_ui()

        # Start Queue Poller
        self.after(100, self._process_queue)

    def _build_ui(self):
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # Log area expands

        # ----------------------------------------------------
        # 1. Header Frame
        # ----------------------------------------------------
        header_frame = ctk.CTkFrame(self, corner_radius=12, fg_color=("#E8F5E9", "#1B3320"))
        header_frame.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        # Logo / Badge
        logo_lbl = ctk.CTkLabel(
            header_frame,
            text=" 🕌 ",
            font=("Segoe UI Emoji", 26),
        )
        logo_lbl.grid(row=0, column=0, rowspan=2, padx=(14, 6), pady=8)

        # Title & Subtitle
        title_lbl = ctk.CTkLabel(
            header_frame,
            text="مستخرج ومصمم فتاوى إسلام ويب (العرض الموضوعي)",
            font=("Cairo", 18, "bold"),
            text_color=("#0D5C3A", "#81C784"),
            anchor="e",
        )
        title_lbl.grid(row=0, column=1, sticky="w", padx=6, pady=(8, 0))

        sub_lbl = ctk.CTkLabel(
            header_frame,
            text="سحب الفتاوى، إعادة التصميم بالخطوط الإسلامية (مصحف أميري)، تصدير PDF وصور، ودمج في ملف واحد",
            font=("Cairo", 11),
            text_color=("#4B6B58", "#A5D6A7"),
            anchor="e",
        )
        sub_lbl.grid(row=1, column=1, sticky="w", padx=6, pady=(0, 8))

        # Mode toggle button
        self.theme_btn = ctk.CTkButton(
            header_frame,
            text="🌙 الوضع الداكن",
            width=110,
            height=32,
            font=("Cairo", 11),
            command=self._toggle_theme,
        )
        self.theme_btn.grid(row=0, column=2, rowspan=2, padx=14, pady=8)

        # ----------------------------------------------------
        # 2. Source Link & Presets Card
        # ----------------------------------------------------
        url_frame = ctk.CTkFrame(self, corner_radius=12)
        url_frame.grid(row=1, column=0, padx=16, pady=6, sticky="ew")
        url_frame.grid_columnconfigure(1, weight=1)

        url_label = ctk.CTkLabel(
            url_frame,
            text="رابط المصدر:",
            font=("Cairo", 12, "bold"),
            width=85,
            anchor="e",
        )
        url_label.grid(row=0, column=0, padx=(12, 4), pady=10)

        # Default URL: الإيمان ونواقضه (188)
        default_url = "https://islamweb.net/ar/fatawa/188/%D8%A7%D9%84%D8%A5%D9%8A%D9%85%D8%A7%D9%86-%D9%88%D9%86%D9%88%D8%A7%D9%82%D8%B6%D9%87"
        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="أدخل رابط تصنيف أو فتوى مفردة من موقع إسلام ويب...",
            font=("Segoe UI", 12),
            height=36,
        )
        self.url_entry.insert(0, default_url)
        self.url_entry.grid(row=0, column=1, padx=6, pady=10, sticky="ew")

        # Paste Button
        paste_btn = ctk.CTkButton(
            url_frame,
            text="📋 لصق",
            width=70,
            height=36,
            font=("Cairo", 11),
            command=self._paste_url,
        )
        paste_btn.grid(row=0, column=2, padx=4, pady=10)

        # Presets Menu
        self.preset_menu = ctk.CTkOptionMenu(
            url_frame,
            values=[
                "📌 الإيمان ونواقضه (188)",
                "📌 العقيدة الإسلامية (4)",
                "📌 القرآن الكريم (350)",
                "📌 فتوى مفردة (123958)",
            ],
            width=160,
            height=36,
            font=("Cairo", 11),
            command=self._on_preset_select,
        )
        self.preset_menu.grid(row=0, column=3, padx=(4, 12), pady=10)

        # ----------------------------------------------------
        # 3. Settings & Export Options Card
        # ----------------------------------------------------
        opts_frame = ctk.CTkFrame(self, corner_radius=12)
        opts_frame.grid(row=2, column=0, padx=16, pady=6, sticky="ew")
        opts_frame.grid_columnconfigure(1, weight=1)

        # Output Folder Row
        folder_lbl = ctk.CTkLabel(
            opts_frame,
            text="مجلد الحفظ:",
            font=("Cairo", 12, "bold"),
            width=85,
            anchor="e",
        )
        folder_lbl.grid(row=0, column=0, padx=(12, 4), pady=(10, 6))

        # Default output folder: ./fatawa_output in current directory
        default_dir = os.path.abspath("./fatawa_output")
        self.dir_entry = ctk.CTkEntry(
            opts_frame,
            font=("Segoe UI", 12),
            height=34,
        )
        self.dir_entry.insert(0, default_dir)
        self.dir_entry.grid(row=0, column=1, padx=6, pady=(10, 6), sticky="ew")

        browse_btn = ctk.CTkButton(
            opts_frame,
            text="📁 استعراض...",
            width=95,
            height=34,
            font=("Cairo", 11),
            command=self._browse_dir,
        )
        browse_btn.grid(row=0, column=2, padx=(4, 12), pady=(10, 6))

        # Divider
        divider = ctk.CTkFrame(opts_frame, height=1, fg_color=("#E0E0E0", "#333333"))
        divider.grid(row=1, column=0, columnspan=3, padx=12, pady=6, sticky="ew")

        # Checkboxes & Options Row
        sub_opts = ctk.CTkFrame(opts_frame, fg_color="transparent")
        sub_opts.grid(row=2, column=0, columnspan=3, padx=12, pady=(4, 10), sticky="ew")
        sub_opts.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Export Checkboxes
        self.cb_html = ctk.CTkCheckBox(
            sub_opts,
            text="صفحات HTML مصممة",
            font=("Cairo", 11, "bold"),
            state="disabled",  # Always true
        )
        self.cb_html.select()
        self.cb_html.grid(row=0, column=0, padx=6, pady=4, sticky="w")

        self.cb_pdf = ctk.CTkCheckBox(
            sub_opts,
            text="ملفات PDF لكل فتوى",
            font=("Cairo", 11, "bold"),
        )
        self.cb_pdf.select()
        self.cb_pdf.grid(row=0, column=1, padx=6, pady=4, sticky="w")

        self.cb_jpeg = ctk.CTkCheckBox(
            sub_opts,
            text="صور JPEG (دمج الصفحات)",
            font=("Cairo", 11, "bold"),
        )
        self.cb_jpeg.select()
        self.cb_jpeg.grid(row=0, column=2, padx=6, pady=4, sticky="w")

        self.cb_merge = ctk.CTkCheckBox(
            sub_opts,
            text="دمج الكل في PDF مفهرس",
            font=("Cairo", 11, "bold"),
        )
        self.cb_merge.select()
        self.cb_merge.grid(row=0, column=3, padx=6, pady=4, sticky="w")

        # Second row of options: Subcategories, Limit, Delay
        opts_row2 = ctk.CTkFrame(sub_opts, fg_color="transparent")
        opts_row2.grid(row=1, column=0, columnspan=4, pady=(6, 0), sticky="ew")
        opts_row2.grid_columnconfigure(4, weight=1)

        self.cb_subcats = ctk.CTkCheckBox(
            opts_row2,
            text="تضمين الأقسام الفرعية (Recursive)",
            font=("Cairo", 11),
        )
        self.cb_subcats.grid(row=0, column=0, padx=6, pady=4, sticky="w")

        # Limit Radio/Input
        self.limit_switch = ctk.CTkSwitch(
            opts_row2,
            text="تحديد حد أقصى للعدد:",
            font=("Cairo", 11),
            command=self._toggle_limit,
        )
        self.limit_switch.grid(row=0, column=1, padx=(16, 4), pady=4, sticky="w")

        self.limit_entry = ctk.CTkEntry(
            opts_row2,
            width=65,
            height=28,
            font=("Segoe UI", 11),
        )
        self.limit_entry.insert(0, "10")
        self.limit_entry.configure(state="disabled")
        self.limit_entry.grid(row=0, column=2, padx=4, pady=4, sticky="w")

        # Request Delay
        delay_lbl = ctk.CTkLabel(
            opts_row2,
            text="الفاصل الزمني (ثواني):",
            font=("Cairo", 11),
        )
        delay_lbl.grid(row=0, column=3, padx=(18, 4), pady=4, sticky="e")

        self.delay_spin = ctk.CTkEntry(
            opts_row2,
            width=50,
            height=28,
            font=("Segoe UI", 11),
        )
        self.delay_spin.insert(0, "0.5")
        self.delay_spin.grid(row=0, column=4, padx=4, pady=4, sticky="w")

        # ----------------------------------------------------
        # 4. Action Buttons & Progress Card
        # ----------------------------------------------------
        act_frame = ctk.CTkFrame(self, corner_radius=12)
        act_frame.grid(row=3, column=0, padx=16, pady=6, sticky="ew")
        act_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        # Start Button (Emerald Green, prominent)
        self.start_btn = ctk.CTkButton(
            act_frame,
            text="🚀 ابدأ الاستخراج والمعالجة",
            font=("Cairo", 14, "bold"),
            height=42,
            fg_color="#0D5C3A",
            hover_color="#073B24",
            command=self._start_scraping,
        )
        self.start_btn.grid(row=0, column=0, padx=6, pady=10, sticky="ew")

        # Pause / Resume Button
        self.pause_btn = ctk.CTkButton(
            act_frame,
            text="⏸️ إيقاف مؤقت",
            font=("Cairo", 12),
            height=42,
            fg_color="#D97706",
            hover_color="#B45309",
            state="disabled",
            command=self._toggle_pause,
        )
        self.pause_btn.grid(row=0, column=1, padx=6, pady=10, sticky="ew")

        # Stop Button
        self.stop_btn = ctk.CTkButton(
            act_frame,
            text="🛑 إلغاء / إيقاف",
            font=("Cairo", 12),
            height=42,
            fg_color="#DC2626",
            hover_color="#991B1B",
            state="disabled",
            command=self._stop_scraping,
        )
        self.stop_btn.grid(row=0, column=2, padx=6, pady=10, sticky="ew")

        # Open Output Folder Button
        self.open_folder_btn = ctk.CTkButton(
            act_frame,
            text="📂 فتح المجلد",
            font=("Cairo", 12),
            height=42,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._open_output_dir,
        )
        self.open_folder_btn.grid(row=0, column=3, padx=6, pady=10, sticky="ew")

        # Open Merged PDF Button
        self.open_pdf_btn = ctk.CTkButton(
            act_frame,
            text="📕 فتح PDF المجمّع",
            font=("Cairo", 12),
            height=42,
            fg_color="#7C3AED",
            hover_color="#5B21B6",
            state="disabled",
            command=self._open_merged_pdf,
        )
        self.open_pdf_btn.grid(row=0, column=4, padx=6, pady=10, sticky="ew")

        # Progress Section within act_frame
        prog_sub = ctk.CTkFrame(act_frame, fg_color="transparent")
        prog_sub.grid(row=1, column=0, columnspan=5, padx=8, pady=(4, 12), sticky="ew")
        prog_sub.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            prog_sub,
            orientation="horizontal",
            mode="determinate",
            height=14,
            progress_color="#0D5C3A",
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, padx=4, pady=(2, 6), sticky="ew")

        # Info Labels (Status & Stats)
        info_row = ctk.CTkFrame(prog_sub, fg_color="transparent")
        info_row.grid(row=1, column=0, sticky="ew")
        info_row.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            info_row,
            text="الحالة: جاهز للبدء.",
            font=("Cairo", 11),
            anchor="w",
            text_color=("#334155", "#94A3B8"),
        )
        self.status_lbl.grid(row=0, column=0, sticky="w", padx=4)

        self.stats_lbl = ctk.CTkLabel(
            info_row,
            text="المكتشف: 0 | المكتمل: 0 | PDF: 0 | JPEG: 0",
            font=("Cairo", 11, "bold"),
            anchor="e",
            text_color=("#0D5C3A", "#81C784"),
        )
        self.stats_lbl.grid(row=0, column=1, sticky="e", padx=4)

        # ----------------------------------------------------
        # 5. Live Activity Log Console
        # ----------------------------------------------------
        log_frame = ctk.CTkFrame(self, corner_radius=12)
        log_frame.grid(row=4, column=0, padx=16, pady=(4, 14), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        # Header for logs
        log_top = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_top.grid(row=0, column=0, padx=8, pady=(6, 2), sticky="ew")
        log_top.grid_columnconfigure(0, weight=1)

        log_title = ctk.CTkLabel(
            log_top,
            text="📋 سجل النشاط والتنفيذ المباشر:",
            font=("Cairo", 12, "bold"),
            anchor="w",
        )
        log_title.grid(row=0, column=0, sticky="w")

        clear_log_btn = ctk.CTkButton(
            log_top,
            text="مسح السجل",
            width=75,
            height=24,
            font=("Cairo", 10),
            fg_color="transparent",
            text_color=("#475569", "#94A3B8"),
            hover_color=("#E2E8F0", "#334155"),
            command=self._clear_log,
        )
        clear_log_btn.grid(row=0, column=1, sticky="e")

        # Text Console
        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=("Consolas", 11),
            wrap="word",
        )
        self.log_text.grid(row=1, column=0, padx=8, pady=(2, 8), sticky="nsew")

        # Initial Log Message
        self._log("مرحباً بك في تطبيق مستخرج فتاوى إسلام ويب المطور.", "INFO")
        self._log("يمكنك إدخال رابط التصنيف أو الفتوى والبدء مباشرة.", "INFO")

    # ----------------------------------------------------
    # UI Helpers & Events
    # ----------------------------------------------------
    def _toggle_theme(self):
        curr = ctk.get_appearance_mode()
        if curr == "Light":
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text="☀️ الوضع الفاتح")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text="🌙 الوضع الداكن")

    def _paste_url(self):
        try:
            clipboard = self.clipboard_get()
            if clipboard:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clipboard.strip())
        except Exception:
            pass

    def _on_preset_select(self, choice: str):
        if "188" in choice:
            url = "https://islamweb.net/ar/fatawa/188/%D8%A7%D9%84%D8%A5%D9%8A%D9%85%D8%A7%D9%86-%D9%88%D9%86%D9%88%D8%A7%D9%82%D8%B6%D9%87"
        elif "4" in choice:
            url = "https://islamweb.net/ar/fatawa/4/%D8%A7%D9%84%D8%B9%D9%82%D9%8A%D8%AF%D8%A9-%D8%A7%D9%84%D8%A5%D8%B3%D9%84%D8%A7%D9%85%D9%8A%D8%A9"
        elif "350" in choice:
            url = "https://islamweb.net/ar/fatawa/350/%D8%A7%D9%84%D9%82%D8%B1%D8%A2%D9%86-%D8%A7%D9%84%D9%83%D8%B1%D9%8A%D9%85"
        elif "123958" in choice:
            url = "https://islamweb.net/ar/fatwa/123958/%D8%AD%D9%83%D9%85-%D9%85%D9%86-%D8%B5%D8%A7%D8%B1-%D8%B3%D8%A8-%D8%A7%D9%84%D8%AF%D9%8A%D9%86-%D8%B9%D8%A7%D8%AF%D8%A9-%D9%84%D9%87"
        else:
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)

    def _browse_dir(self):
        selected = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if selected:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, selected)

    def _toggle_limit(self):
        if self.limit_switch.get():
            self.limit_entry.configure(state="normal")
        else:
            self.limit_entry.configure(state="disabled")

    def _clear_log(self):
        self.log_text.delete("1.0", "end")

    def _log(self, msg: str, level: str = "INFO"):
        t_str = time.strftime("%H:%M:%S")
        prefix = {
            "INFO": "🔵 [معلومة]",
            "SUCCESS": "🟢 [نجاح]",
            "WARNING": "🟡 [تنبيه]",
            "ERROR": "🔴 [خطأ]",
            "DEBUG": "⚪ [فحص]",
        }.get(level, f"[{level}]")
        formatted = f"[{t_str}] {prefix} {msg}\n"
        self.log_text.insert("end", formatted)
        self.log_text.see("end")

    def _open_output_dir(self):
        target = self.last_output_dir or self.dir_entry.get()
        if os.path.exists(target):
            if sys.platform == "win32":
                os.startfile(target)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        else:
            messagebox.showinfo("تنبيه", "المجلد غير موجود حالياً، سيتكون تلقائياً عند بدء الاستخراج.")

    def _open_merged_pdf(self):
        if self.last_merged_pdf and os.path.exists(self.last_merged_pdf):
            if sys.platform == "win32":
                os.startfile(self.last_merged_pdf)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.last_merged_pdf])
            else:
                subprocess.Popen(["xdg-open", self.last_merged_pdf])
        else:
            messagebox.showinfo("تنبيه", "ملف PDF المجمّع غير متوفر بعد.")

    # ----------------------------------------------------
    # Scraping Controller (Threaded Worker)
    # ----------------------------------------------------
    def _start_scraping(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("تنبيه", "يرجى إدخال رابط إسلام ويب المطلوب أولاً.")
            return

        out_dir = self.dir_entry.get().strip()
        if not out_dir:
            messagebox.showwarning("تنبيه", "يرجى تحديد مجلد حفظ المخرجات.")
            return

        # Parse limit
        max_fatawa = None
        if self.limit_switch.get():
            try:
                max_fatawa = int(self.limit_entry.get().strip())
                if max_fatawa <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("خطأ", "يرجى إدخال رقم صحيح للحد الأقصى للفتاوى.")
                return

        # Parse delay
        try:
            delay = float(self.delay_spin.get().strip())
            if delay < 0:
                delay = 0.5
        except ValueError:
            delay = 0.5

        # Check options
        gen_html = True
        gen_pdf = self.cb_pdf.get() == 1
        gen_jpeg = self.cb_jpeg.get() == 1
        merge_pdf = self.cb_merge.get() == 1
        include_subs = self.cb_subcats.get() == 1

        # Reset State & Stats
        self.stats = {"found": 0, "processed": 0, "pdf": 0, "jpeg": 0}
        self.progress_bar.set(0)
        self.is_running = True
        self.is_paused = False

        # Update UI Controls
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="⏸️ إيقاف مؤقت")
        self.stop_btn.configure(state="normal")
        self.open_pdf_btn.configure(state="disabled")

        # Initialize Scraper
        self.scraper = IslamwebScraper(request_delay=delay)

        # Launch Worker Thread
        self.worker_thread = threading.Thread(
            target=self._worker_run,
            args=(url, out_dir, gen_html, gen_pdf, gen_jpeg, merge_pdf, include_subs, max_fatawa),
            daemon=True,
        )
        self.worker_thread.start()

    def _toggle_pause(self):
        if not self.scraper or not self.is_running:
            return
        if self.is_paused:
            self.scraper.resume()
            self.is_paused = False
            self.pause_btn.configure(text="⏸️ إيقاف مؤقت")
            self._log("تم استئناف عملية الاستخراج.", "INFO")
            self.status_lbl.configure(text="الحالة: تم الاستئناف ومتابعة العمل...")
        else:
            self.scraper.pause()
            self.is_paused = True
            self.pause_btn.configure(text="▶️ متابعة")
            self._log("تم إيقاف العملية مؤقتاً.", "WARNING")
            self.status_lbl.configure(text="الحالة: العملية متوقفة مؤقتاً.")

    def _stop_scraping(self):
        if self.scraper:
            self.scraper.cancel()
            self._log("جاري إيقاف العملية وإلغاء المهام...", "WARNING")
            self.status_lbl.configure(text="الحالة: جاري الإلغاء...")
            self.stop_btn.configure(state="disabled")

    def _worker_run(
        self,
        url: str,
        out_dir: str,
        gen_html: bool,
        gen_pdf: bool,
        gen_jpeg: bool,
        merge_pdf: bool,
        include_subs: bool,
        max_fatawa: Optional[int],
    ):
        try:
            self.msg_queue.put(("LOG", ("بدء عملية الاستخراج والمعالجة...", "INFO")))
            exporter = FatwaExporter(base_output_dir=out_dir)

            # Check if URL is single fatwa or category
            if self.scraper.is_single_fatwa_url(url):
                self.msg_queue.put(("LOG", ("تم الكشف عن رابط فتوى مفردة.", "INFO")))
                fatwa_items_to_fetch = [{"id": "single", "url": url, "title": "فتوى مفردة"}]
                category_title = "فتاوى_مفردة"
            else:
                cat_info = self.scraper.extract_category_info(url)
                category_title = cat_info["title"]
                self.msg_queue.put(("LOG", (f"القسم المستهدف: {category_title} (رقم {cat_info['id']})", "INFO")))

                # Gather fatwa links
                self.msg_queue.put(("STATUS", "جاري فحص صفحات القسم وجمع روابط الفتاوى..."))
                fatwa_items_to_fetch = self.scraper.collect_all_fatwa_links(
                    category_url=url,
                    include_subcategories=include_subs,
                    max_fatawa=max_fatawa,
                    on_log=lambda m, l: self.msg_queue.put(("LOG", (m, l))),
                    on_progress=lambda cur, tot, st: self.msg_queue.put(("FOUND_COUNT", cur)),
                )

            total_found = len(fatwa_items_to_fetch)
            self.msg_queue.put(("STATS_FOUND", total_found))

            if total_found == 0:
                self.msg_queue.put(("LOG", ("لم يتم العثور على أية فتاوى في الرابط المعطى.", "WARNING")))
                self.msg_queue.put(("FINISHED", None))
                return

            self.msg_queue.put(("LOG", (f"بدء تنزيل وتصميم {total_found} فتوى بشكل منظم...", "SUCCESS")))

            safe_cat_dir = f"فتاوى_{sanitize_filename(category_title, max_length=40)}"
            category_full_path = os.path.join(out_dir, safe_cat_dir)
            self.last_output_dir = category_full_path

            pdf_items_for_merge = []

            for idx, item in enumerate(fatwa_items_to_fetch, 1):
                if self.scraper.cancelled:
                    self.msg_queue.put(("LOG", ("تم إلغاء العملية بناءً على طلب المستخدم.", "WARNING")))
                    break

                fatwa_url = item["url"]
                self.msg_queue.put(("STATUS", f"معالجة {idx}/{total_found}: {item.get('title', 'فتوى')}..."))

                # Fetch details
                fatwa = self.scraper.fetch_single_fatwa(fatwa_url)
                if not fatwa:
                    self.msg_queue.put(("LOG", (f"تعذر جلب الفتوى من الرابط: {fatwa_url}", "WARNING")))
                    continue

                # Export (HTML, PDF, JPEG in separate folder)
                export_res = exporter.export_single_fatwa(
                    fatwa=fatwa,
                    category_dir_name=safe_cat_dir,
                    generate_html=gen_html,
                    generate_pdf=gen_pdf,
                    generate_jpeg=gen_jpeg,
                )

                if export_res["pdf"]:
                    pdf_items_for_merge.append((fatwa.id, fatwa.title, export_res["pdf"]))

                # Update progress
                self.msg_queue.put(("ITEM_DONE", {
                    "idx": idx,
                    "total": total_found,
                    "id": fatwa.id,
                    "title": fatwa.title,
                    "pdf": bool(export_res["pdf"]),
                    "jpeg": bool(export_res["jpeg"]),
                }))

            # Merge all PDFs if enabled
            if merge_pdf and pdf_items_for_merge and not self.scraper.cancelled:
                self.msg_queue.put(("STATUS", "جاري دمج كافة ملفات PDF في ملف رئيسي واحد مع فهرس تفاعلي..."))
                self.msg_queue.put(("LOG", (f"جاري دمج {len(pdf_items_for_merge)} ملف PDF...", "INFO")))
                
                merged_path = exporter.merge_all_fatawa_pdfs(
                    pdf_items=pdf_items_for_merge,
                    category_title=category_title,
                    category_dir_name=safe_cat_dir,
                )
                if merged_path:
                    self.last_merged_pdf = merged_path
                    self.msg_queue.put(("MERGED_SUCCESS", merged_path))
                    self.msg_queue.put(("LOG", (f"تم إنشاء ملف PDF المجمّع بنجاح:\n{merged_path}", "SUCCESS")))

            self.msg_queue.put(("FINISHED", None))

        except Exception as e:
            self.msg_queue.put(("LOG", (f"حدث خطأ أثناء التنفيذ: {e}", "ERROR")))
            self.msg_queue.put(("FINISHED", None))

    def _process_queue(self):
        """Processes messages delivered from the background worker thread."""
        try:
            while not self.msg_queue.empty():
                msg_type, data = self.msg_queue.get_nowait()

                if msg_type == "LOG":
                    text, level = data
                    self._log(text, level)

                elif msg_type == "STATUS":
                    self.status_lbl.configure(text=f"الحالة: {data}")

                elif msg_type == "FOUND_COUNT":
                    self.stats["found"] = data
                    self._update_stats_display()

                elif msg_type == "STATS_FOUND":
                    self.stats["found"] = data
                    self._update_stats_display()

                elif msg_type == "ITEM_DONE":
                    self.stats["processed"] = data["idx"]
                    if data["pdf"]:
                        self.stats["pdf"] += 1
                    if data["jpeg"]:
                        self.stats["jpeg"] += 1
                    
                    pct = data["idx"] / max(data["total"], 1)
                    self.progress_bar.set(pct)
                    self._update_stats_display()
                    self._log(f"تم حفظ فتوى [{data['id']}]: {data['title'][:40]}...", "SUCCESS")

                elif msg_type == "MERGED_SUCCESS":
                    self.last_merged_pdf = data
                    self.open_pdf_btn.configure(state="normal")

                elif msg_type == "FINISHED":
                    self.is_running = False
                    self.is_paused = False
                    self.start_btn.configure(state="normal")
                    self.pause_btn.configure(state="disabled", text="⏸️ إيقاف مؤقت")
                    self.stop_btn.configure(state="disabled")
                    self.status_lbl.configure(text="الحالة: اكتملت العملية بنجاح!")
                    self.progress_bar.set(1.0)
                    self._log("🎉 اكتملت المهمة بالكامل! يمكنك الآن تصفح المجلد أو فتح ملف PDF المجمّع.", "SUCCESS")
                    messagebox.showinfo("اكتملت العملية", "تم استخراج وتصميم وتصدير الفتاوى بنجاح!")

        except Exception as e:
            print("Error in _process_queue:", e)
        finally:
            self.after(120, self._process_queue)

    def _update_stats_display(self):
        self.stats_lbl.configure(
            text=f"المكتشف: {self.stats['found']} | المنجز: {self.stats['processed']} | PDF: {self.stats['pdf']} | JPEG: {self.stats['jpeg']}"
        )


def main():
    app = FatawaApp()
    app.mainloop()


if __name__ == "__main__":
    main()

