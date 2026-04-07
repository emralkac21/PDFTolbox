
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import threading
from typing import List, Dict
from pypdf import PdfReader, PdfWriter
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# PDF düzenleme için ek kütüphaneler
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import pypdfium2 as pdfium
    PYPDFIUM_AVAILABLE = True
except ImportError:
    PYPDFIUM_AVAILABLE = False

class ModernButton(tk.Canvas):
    """Modern görünümlü buton widget'ı"""
    def __init__(self, parent, text, command, bg_color="#4A90E2", hover_color="#357ABD", 
                 text_color="white", width=120, height=40, icon=None):
        super().__init__(parent, width=width, height=height, bg=parent['bg'], 
                        highlightthickness=0, cursor="hand2")
        
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.text = text
        
        self.rect = self.create_rectangle(0, 0, width, height, fill=bg_color, 
                                          outline="", tags="button")
        
        if icon:
            self.create_text(width//2, height//2 - 3, text=icon, 
                            fill=text_color, font=('Segoe UI', 12), tags="button")
            self.create_text(width//2, height//2 + 12, text=text, 
                            fill=text_color, font=('Segoe UI', 9, 'bold'), tags="button")
        else:
            self.create_text(width//2, height//2, text=text, 
                            fill=text_color, font=('Segoe UI', 10, 'bold'), tags="button")
        
        self.bind("<Enter>", lambda e: self.itemconfig(self.rect, fill=self.hover_color))
        self.bind("<Leave>", lambda e: self.itemconfig(self.rect, fill=self.bg_color))
        self.bind("<Button-1>", lambda e: self.command() if self.command else None)

class PageSelectorDialog:
    """Sayfa seçim diyalogu"""
    def __init__(self, parent, pdf_info: Dict, callback):
        self.pdf_info = pdf_info
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Sayfa Seçimi - {pdf_info['name']}")
        self.dialog.geometry("500x650")
        self.dialog.configure(bg="#F5F6FA")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_ui()
        
    def create_ui(self):
        header = tk.Frame(self.dialog, bg="#34495E", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"📄 {self.pdf_info['name']}", font=('Segoe UI', 12, 'bold'), bg="#34495E", fg="white").pack(pady=15)
        
        info_frame = tk.Frame(self.dialog, bg="#F5F6FA")
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(info_frame, text=f"Toplam Sayfa: {self.pdf_info['total_pages']}", font=('Segoe UI', 10), bg="#F5F6FA").pack(anchor='w')
        
        quick_frame = tk.Frame(self.dialog, bg="#F5F6FA")
        quick_frame.pack(fill=tk.X, padx=20)
        
        ttk.Button(quick_frame, text="Tümünü Seç", command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="Temizle", command=self.deselect_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="Tekler", command=self.select_odd).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_frame, text="Çiftler", command=self.select_even).pack(side=tk.LEFT, padx=2)
        
        range_frame = tk.Frame(self.dialog, bg="#F5F6FA")
        range_frame.pack(fill=tk.X, padx=20, pady=15)
        tk.Label(range_frame, text="Sayfa Aralığı (Örn: 1-5, 8, 10-12):", font=('Segoe UI', 9), bg="#F5F6FA").pack(anchor='w')
        
        self.range_entry = tk.Entry(range_frame, font=('Segoe UI', 10))
        self.range_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(range_frame, text="Uygula", command=self.apply_range).pack(side=tk.LEFT)
        
        list_frame = tk.Frame(self.dialog, bg="white")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        scrl = ttk.Scrollbar(list_frame)
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrl.set, selectmode=tk.MULTIPLE, font=('Segoe UI', 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrl.config(command=self.listbox.yview)
        scrl.pack(side=tk.RIGHT, fill=tk.Y)
        
        for i in range(1, self.pdf_info['total_pages'] + 1):
            self.listbox.insert(tk.END, f"Sayfa {i}")
            if i in self.pdf_info.get('selected_pages', []):
                self.listbox.selection_set(i - 1)
                
        footer = tk.Frame(self.dialog, bg="#F5F6FA")
        footer.pack(fill=tk.X, padx=20, pady=20)
        ttk.Button(footer, text="Kaydet", command=self.save_selection).pack(side=tk.RIGHT, padx=5)
        ttk.Button(footer, text="İptal", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def select_all(self): self.listbox.selection_set(0, tk.END)
    def deselect_all(self): self.listbox.selection_clear(0, tk.END)
    def select_odd(self):
        self.deselect_all()
        for i in range(0, self.pdf_info['total_pages'], 2): self.listbox.selection_set(i)
    def select_even(self):
        self.deselect_all()
        for i in range(1, self.pdf_info['total_pages'], 2): self.listbox.selection_set(i)
        
    def apply_range(self):
        txt = self.range_entry.get().strip()
        if not txt: return
        try:
            pages = set()
            for part in txt.split(','):
                part = part.strip()
                if '-' in part:
                    s, e = map(int, part.split('-'))
                    pages.update(range(s, e + 1))
                else:
                    pages.add(int(part))
            self.deselect_all()
            for p in pages:
                if 1 <= p <= self.pdf_info['total_pages']: self.listbox.selection_set(p - 1)
        except: messagebox.showerror("Hata", "Geçersiz aralık formatı!")

    def save_selection(self):
        sel = [i + 1 for i in self.listbox.curselection()]
        if not sel:
            messagebox.showwarning("Uyarı", "En az bir sayfa seçmelisiniz!")
            return
        self.pdf_info['selected_pages'] = sel
        self.callback()
        self.dialog.destroy()

class PDFToolboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modern PDF Toolbox - Birleştir, Böl, Dönüştür, Düzenle")
        self.root.geometry("1100x850")
        self.root.configure(bg="#F5F6FA")
        
        self.pdf_files: List[Dict] = []
        # Bölme işlemi için veri yapısı
        self.split_data = {
            'path': None,
            'name': "",
            'total_pages': 0,
            'selected_pages': []
        }
        
        # PDF Düzenleme için veri yapısı
        self.edit_data = {
            'path': None,
            'name': "",
            'total_pages': 0,
            'current_page': 1,
            'preview_image': None,
            'edits': [],  # Her düzenleme: {'type': 'text'/'rect'/'circle'/'line'/'image', 'params': {...}}
            'selected_tool': None,  # Seçili araç: 'text', 'rectangle', 'circle', 'line', 'image'
            'temp_params': {},  # Geçici çizim parametreleri
            'scale_factor': 1.0,  # Canvas'tan PDF koordinatlarına dönüşüm faktörü
            'canvas_items': [],  # Canvas üzerindeki görsel nesneler
            'drag_start': None  # Sürükleme başlangıç noktası
        }
        
        self.setup_styles()
        self.create_ui()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background="#F5F6FA", borderwidth=0)
        style.configure("TNotebook.Tab", font=('Segoe UI', 11, 'bold'), padding=[20, 10])
        style.configure("Treeview", rowheight=35, font=('Segoe UI', 10))
        style.configure("Treeview.Heading", background="#34495E", foreground="white", font=('Segoe UI', 10, 'bold'))
        style.map("Treeview", background=[('selected', '#4A90E2')])

    def create_ui(self):
        header = tk.Frame(self.root, bg="#2C3E50", height=70)
        header.pack(fill=tk.X)
        tk.Label(header, text="🛠️ PDF Toolbox", font=('Segoe UI', 20, 'bold'), bg="#2C3E50", fg="white").pack(pady=15)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Sekme 1: Birleştirme
        self.merge_tab = tk.Frame(self.notebook, bg="#F5F6FA")
        self.notebook.add(self.merge_tab, text="  PDF Birleştir  ")
        self.setup_merge_ui()

        # Sekme 2: Bölme
        self.split_tab = tk.Frame(self.notebook, bg="#F5F6FA")
        self.notebook.add(self.split_tab, text="  PDF Böl  ")
        self.setup_split_ui()

        # Sekme 3: Dosya → PDF Dönüştür & Birleştir
        self.convert_tab = tk.Frame(self.notebook, bg="#F5F6FA")
        self.notebook.add(self.convert_tab, text="  Dosya → PDF  ")
        self.setup_convert_ui()
        
        # Sekme 4: PDF Düzenle
        self.edit_tab = tk.Frame(self.notebook, bg="#F5F6FA")
        self.notebook.add(self.edit_tab, text="  PDF Düzenle  ")
        self.setup_edit_ui()

        self.status_label = tk.Label(self.root, text="📌 Hazır", font=('Segoe UI', 10), bg="#34495E", fg="white", anchor='w', padx=20)
        self.status_label.pack(fill=tk.X)

    def setup_merge_ui(self):
        content = tk.Frame(self.merge_tab, bg="#F5F6FA")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        btn_frame = tk.Frame(content, bg="#F5F6FA", width=180)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))

        btns = [
            ("PDF Ekle", self.add_pdf_files, "#27AE60", "#229954", "➕"),
            ("Seçileni Çıkar", self.remove_selected, "#E74C3C", "#C0392B", "➖"),
            ("Yukarı Taşı", self.move_up, "#3498DB", "#2980B9", "⬆"),
            ("Aşağı Taşı", self.move_down, "#3498DB", "#2980B9", "⬇"),
            ("Sayfa Seç", self.select_pages, "#9B59B6", "#8E44AD", "📑"),
            ("Temizle", self.clear_all, "#95A5A6", "#7F8C8D", "🗑")
        ]

        for text, cmd, bg, hov, ico in btns:
            ModernButton(btn_frame, text, cmd, bg, hov, icon=ico, width=160, height=55).pack(pady=5)

        tk.Frame(btn_frame, bg="#F5F6FA", height=40).pack()
        ModernButton(btn_frame, "BİRLEŞTİR", self.merge_pdfs, "#E67E22", "#D35400", icon="🔗", width=160, height=70).pack(side=tk.BOTTOM)

        tree_frame = tk.Frame(content, bg="white")
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_frame, columns=('Dosya', 'Sayfa', 'Seçili'), show='headings')
        self.tree.heading('Dosya', text='Dosya Adı')
        self.tree.heading('Sayfa', text='Toplam Sayfa')
        self.tree.heading('Seçili', text='Seçili Aralık')
        self.tree.column('Dosya', width=300)
        self.tree.column('Sayfa', width=100, anchor='center')
        self.tree.column('Seçili', width=180, anchor='center')
        
        scrl = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrl.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrl.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_split_ui(self):
        container = tk.Frame(self.split_tab, bg="#F5F6FA")
        container.pack(pady=40, padx=50, fill=tk.BOTH)

        # Dosya Seçimi Başlığı
        tk.Label(container, text="Bölünecek PDF Dosyası", font=('Segoe UI', 12, 'bold'), bg="#F5F6FA").pack(anchor='w')
        
        f_frame = tk.Frame(container, bg="#F5F6FA")
        f_frame.pack(fill=tk.X, pady=10)
        
        self.split_file_label = tk.Label(f_frame, text="Lütfen bir dosya seçin...", bg="white", relief="solid", borderwidth=1, anchor="w", padx=10, height=2)
        self.split_file_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        ModernButton(f_frame, "Dosya Seç", self.select_split_pdf, "#34495E", "#2C3E50", width=120, height=40).pack(side=tk.RIGHT)

        # Sayfa Seçim Bilgisi ve Butonu
        selection_frame = tk.Frame(container, bg="#F5F6FA")
        selection_frame.pack(fill=tk.X, pady=10)
        
        self.split_info = tk.Label(selection_frame, text="Seçili Sayfalar: -", font=('Segoe UI', 10), bg="#F5F6FA", fg="#2C3E50")
        self.split_info.pack(side=tk.LEFT)
        
        self.btn_select_split_pages = ModernButton(selection_frame, "Sayfaları Düzenle", self.open_split_page_selector, "#9B59B6", "#8E44AD", width=150, height=35)
        self.btn_select_split_pages.pack(side=tk.RIGHT)

        # Ayarlar
        settings_box = tk.LabelFrame(container, text=" Bölme Ayarları ", font=('Segoe UI', 10, 'bold'), bg="#F5F6FA", padx=20, pady=20)
        settings_box.pack(fill=tk.X, pady=20)

        tk.Label(settings_box, text="Her yeni dosyada kaç sayfa olsun?", font=('Segoe UI', 11), bg="#F5F6FA").pack(side=tk.LEFT)
        self.pages_per_file_entry = tk.Entry(settings_box, font=('Segoe UI', 12), width=8, justify='center')
        self.pages_per_file_entry.insert(0, "1")
        self.pages_per_file_entry.pack(side=tk.LEFT, padx=15)
        
        tk.Label(settings_box, text="(Seçtiğiniz sayfalar bu düzende parçalanacaktır)", font=('Segoe UI', 9, 'italic'), bg="#F5F6FA", fg="gray").pack(side=tk.LEFT)

        self.split_progress = ttk.Progressbar(container, mode='determinate')
        self.split_progress.pack(fill=tk.X, pady=20)
        
        ModernButton(container, "PDF'İ BÖL VE KAYDET", self.execute_split, "#27AE60", "#229954", icon="✂️", width=250, height=60).pack(pady=10)

    # --- YARDIMCI VE YENİ FONKSİYONLAR ---
    def format_page_ranges(self, pages: List[int]) -> str:
        if not pages: return "Hiçbiri"
        pages = sorted(pages)
        ranges = []
        start = end = pages[0]
        for i in range(1, len(pages)):
            if pages[i] == end + 1: end = pages[i]
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = end = pages[i]
        ranges.append(f"{start}-{end}" if start != end else str(start))
        res = ", ".join(ranges)
        return res if len(res) < 40 else res[:37] + "..."

    def select_pages(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Uyarı", "Lütfen bir dosya seçin!")
            return
        idx = self.tree.index(sel[0])
        PageSelectorDialog(self.root, self.pdf_files[idx], self.refresh_tree)

    def open_split_page_selector(self):
        if not self.split_data['path']:
            messagebox.showwarning("Uyarı", "Lütfen önce bir PDF dosyası seçin!")
            return
        PageSelectorDialog(self.root, self.split_data, self.update_split_ui_info)

    def update_split_ui_info(self):
        range_text = self.format_page_ranges(self.split_data['selected_pages'])
        self.split_info.config(text=f"Seçili Sayfalar ({len(self.split_data['selected_pages'])}): {range_text}")

    def select_split_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Dosyaları", "*.pdf")])
        if path:
            reader = PdfReader(path)
            total = len(reader.pages)
            self.split_data = {
                'path': path,
                'name': Path(path).name,
                'total_pages': total,
                'selected_pages': list(range(1, total + 1))
            }
            self.split_file_label.config(text=self.split_data['name'])
            self.update_split_ui_info()

    def add_pdf_files(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Dosyaları", "*.pdf")])
        for f in files:
            try:
                reader = PdfReader(f)
                info = {
                    'path': f, 'name': Path(f).name,
                    'total_pages': len(reader.pages),
                    'selected_pages': list(range(1, len(reader.pages) + 1))
                }
                self.pdf_files.append(info)
            except: continue
        self.refresh_tree()

    def refresh_tree(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        for f in self.pdf_files:
            p_range = "Tümü" if len(f['selected_pages']) == f['total_pages'] else self.format_page_ranges(f['selected_pages'])
            self.tree.insert('', 'end', values=(f['name'], f['total_pages'], p_range))

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel: return
        del self.pdf_files[self.tree.index(sel[0])]
        self.refresh_tree()

    def move_up(self):
        sel = self.tree.selection()
        if not sel: return
        idx = self.tree.index(sel[0])
        if idx > 0:
            self.pdf_files[idx], self.pdf_files[idx-1] = self.pdf_files[idx-1], self.pdf_files[idx]
            self.refresh_tree()
            self.tree.selection_set(self.tree.get_children()[idx-1])

    def move_down(self):
        sel = self.tree.selection()
        if not sel: return
        idx = self.tree.index(sel[0])
        if idx < len(self.pdf_files)-1:
            self.pdf_files[idx], self.pdf_files[idx+1] = self.pdf_files[idx+1], self.pdf_files[idx]
            self.refresh_tree()
            self.tree.selection_set(self.tree.get_children()[idx+1])

    def merge_pdfs(self):
        if not self.pdf_files: return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Dosyaları", "*.pdf")])
        if not out: return
        try:
            writer = PdfWriter()
            for info in self.pdf_files:
                reader = PdfReader(info['path'])
                for p in sorted(info['selected_pages']):
                    writer.add_page(reader.pages[p-1])
            with open(out, "wb") as f: writer.write(f)
            messagebox.showinfo("Başarılı", "PDF başarıyla oluşturuldu.")
        except Exception as e: messagebox.showerror("Hata", str(e))

    def execute_split(self):
        if not self.split_data['path']: 
            messagebox.showwarning("Uyarı", "Dosya seçilmedi!")
            return
        
        try:
            step = int(self.pages_per_file_entry.get())
            if step <= 0: raise ValueError
            
            output_dir = filedialog.askdirectory()
            if not output_dir: return
            
            reader = PdfReader(self.split_data['path'])
            selected_pages = sorted(self.split_data['selected_pages'])
            total_selected = len(selected_pages)
            
            self.split_progress['maximum'] = total_selected
            
            for i in range(0, total_selected, step):
                writer = PdfWriter()
                current_chunk = selected_pages[i : i + step]
                
                for page_num in current_chunk:
                    writer.add_page(reader.pages[page_num - 1])
                    self.split_progress['value'] += 1
                    self.root.update_idletasks()
                
                file_name = f"{Path(self.split_data['path']).stem}_part_{i//step + 1}.pdf"
                with open(os.path.join(output_dir, file_name), "wb") as f:
                    writer.write(f)
            
            self.split_progress['value'] = 0
            messagebox.showinfo("Başarılı", f"Bölme işlemi tamamlandı.\n{total_selected} sayfa, {(total_selected + step - 1)//step} dosyaya bölündü.")
            
        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli bir sayfa sayısı girin (Örn: 1, 2, 5).")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def clear_all(self):
        self.pdf_files.clear()
        self.refresh_tree()

    # ─────────────────────────────────────────────
    #  MODÜL 3: DOSYA → PDF DÖNÜŞTÜR & BİRLEŞTİR
    # ─────────────────────────────────────────────

    SUPPORTED_TYPES = {
        "Tüm Desteklenen": ("*.doc", "*.docx", "*.odt", "*.png", "*.jpg", "*.jpeg"),
        "Word / Metin": ("*.doc", "*.docx", "*.odt"),
        "Görüntü": ("*.png", "*.jpg", "*.jpeg"),
    }

    def setup_convert_ui(self):
        container = tk.Frame(self.convert_tab, bg="#F5F6FA")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Bilgi bandı
        info = tk.Frame(container, bg="#D5E8D4", pady=8)
        info.pack(fill=tk.X, pady=(0, 10))
        tk.Label(info, text="📂  Desteklenen formatlar: DOC · DOCX · ODT · PNG · JPG / JPEG   →   PDF",
                 font=('Segoe UI', 10), bg="#D5E8D4", fg="#1A5E1A").pack()

        # Ortadaki iki sütun düzeni
        mid = tk.Frame(container, bg="#F5F6FA")
        mid.pack(fill=tk.BOTH, expand=True)

        # Sol: butonlar
        btn_frame = tk.Frame(mid, bg="#F5F6FA", width=180)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))

        ModernButton(btn_frame, "Dosya Ekle", self.conv_add_files, "#27AE60", "#229954", icon="➕", width=160, height=55).pack(pady=5)
        ModernButton(btn_frame, "Seçileni Çıkar", self.conv_remove_selected, "#E74C3C", "#C0392B", icon="➖", width=160, height=55).pack(pady=5)
        ModernButton(btn_frame, "Yukarı Taşı", self.conv_move_up, "#3498DB", "#2980B9", icon="⬆", width=160, height=55).pack(pady=5)
        ModernButton(btn_frame, "Aşağı Taşı", self.conv_move_down, "#3498DB", "#2980B9", icon="⬇", width=160, height=55).pack(pady=5)
        ModernButton(btn_frame, "Listeyi Temizle", self.conv_clear, "#95A5A6", "#7F8C8D", icon="🗑", width=160, height=55).pack(pady=5)

        tk.Frame(btn_frame, bg="#F5F6FA", height=20).pack()

        # Tek tek dönüştür
        ModernButton(btn_frame, "Tek Kaydet", self.conv_export_single, "#8E44AD", "#6C3483", icon="💾", width=160, height=55).pack(pady=3)
        # Birleştirerek dönüştür
        ModernButton(btn_frame, "BİRLEŞTİR\n& DÖNÜŞTÜR", self.conv_export_merged, "#E67E22", "#D35400", icon="🔗", width=160, height=70).pack(side=tk.BOTTOM, pady=5)

        # Sağ: liste
        list_frame = tk.Frame(mid, bg="white")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.conv_tree = ttk.Treeview(list_frame, columns=('Dosya', 'Tür', 'Durum'), show='headings')
        self.conv_tree.heading('Dosya', text='Dosya Adı')
        self.conv_tree.heading('Tür', text='Tür')
        self.conv_tree.heading('Durum', text='Durum')
        self.conv_tree.column('Dosya', width=380)
        self.conv_tree.column('Tür', width=80, anchor='center')
        self.conv_tree.column('Durum', width=120, anchor='center')
        scrl = ttk.Scrollbar(list_frame, orient="vertical", command=self.conv_tree.yview)
        self.conv_tree.configure(yscrollcommand=scrl.set)
        self.conv_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrl.pack(side=tk.RIGHT, fill=tk.Y)

        # Alt: ilerleme
        bottom = tk.Frame(container, bg="#F5F6FA")
        bottom.pack(fill=tk.X, pady=(10, 0))
        self.conv_progress = ttk.Progressbar(bottom, mode='determinate')
        self.conv_progress.pack(fill=tk.X)
        self.conv_status = tk.Label(bottom, text="Hazır.", font=('Segoe UI', 9), bg="#F5F6FA", fg="#555", anchor='w')
        self.conv_status.pack(anchor='w', pady=2)

        # Veri listesi
        self.conv_files: List[Dict] = []

    # --- Dönüştürme yardımcıları ---

    def conv_refresh_tree(self):
        for item in self.conv_tree.get_children():
            self.conv_tree.delete(item)
        for f in self.conv_files:
            ext = Path(f['path']).suffix.upper().lstrip('.')
            self.conv_tree.insert('', 'end', values=(f['name'], ext, f.get('status', '—')))

    def conv_add_files(self):
        filetypes = [
            ("Desteklenen Dosyalar", "*.doc *.docx *.odt *.png *.jpg *.jpeg"),
            ("Word Belgeleri", "*.doc *.docx *.odt"),
            ("Görüntüler", "*.png *.jpg *.jpeg"),
            ("Tüm Dosyalar", "*.*"),
        ]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        for f in files:
            self.conv_files.append({'path': f, 'name': Path(f).name, 'status': 'Bekliyor'})
        self.conv_refresh_tree()

    def conv_remove_selected(self):
        sel = self.conv_tree.selection()
        if not sel: return
        idx = self.conv_tree.index(sel[0])
        del self.conv_files[idx]
        self.conv_refresh_tree()

    def conv_move_up(self):
        sel = self.conv_tree.selection()
        if not sel: return
        idx = self.conv_tree.index(sel[0])
        if idx > 0:
            self.conv_files[idx], self.conv_files[idx-1] = self.conv_files[idx-1], self.conv_files[idx]
            self.conv_refresh_tree()
            self.conv_tree.selection_set(self.conv_tree.get_children()[idx-1])

    def conv_move_down(self):
        sel = self.conv_tree.selection()
        if not sel: return
        idx = self.conv_tree.index(sel[0])
        if idx < len(self.conv_files)-1:
            self.conv_files[idx], self.conv_files[idx+1] = self.conv_files[idx+1], self.conv_files[idx]
            self.conv_refresh_tree()
            self.conv_tree.selection_set(self.conv_tree.get_children()[idx+1])

    def conv_clear(self):
        self.conv_files.clear()
        self.conv_refresh_tree()

    def _convert_single_to_pdf(self, file_info: Dict, tmp_dir: str) -> str:
        """
        Tek bir dosyayı PDF'e dönüştürür. Başarılıysa PDF yolunu döndürür.
        Desteklenen: doc, docx, odt  (LibreOffice)
                     png, jpg, jpeg (Pillow)
        """
        src = file_info['path']
        ext = Path(src).suffix.lower()
        stem = Path(src).stem
        out_pdf = os.path.join(tmp_dir, stem + ".pdf")

        if ext in ('.doc', '.docx', '.odt'):
            # Kaynak dosyayı geçici dizine kopyala
            # (ağ sürücüleri veya salt-okunur yollar için zorunlu)
            local_src = os.path.join(tmp_dir, "input" + ext)
            shutil.copy2(src, local_src)

            # Her dönüşüm için izole bir LibreOffice profili oluştur
            # (aynı anda birden fazla dönüşüm veya çökme sonrası kilit sorununu önler)
            profile_dir = os.path.join(tmp_dir, "lo_profile")
            os.makedirs(profile_dir, exist_ok=True)
            profile_url = Path(profile_dir).as_uri()  # file:///... formatı

            result = subprocess.run(
                [
                    r'C:\Program Files\LibreOffice\program\soffice.exe', # 'libreoffice' yerine tam yol
                    '--headless',
                    '--convert-to', 'pdf',
                    '--headless',
                    '--norestore',
                    '--nofirststartwizard',
                    f'-env:UserInstallation={profile_url}',
                    '--convert-to', 'pdf',
                    '--outdir', tmp_dir,
                    local_src,
                ],
                capture_output=True,
                timeout=120,
            )

            stderr_txt = result.stderr.decode('utf-8', errors='replace')
            stdout_txt = result.stdout.decode('utf-8', errors='replace')

            if result.returncode != 0:
                raise RuntimeError(
                    f"LibreOffice hatası (kod {result.returncode}):\n"
                    f"{stderr_txt or stdout_txt or 'Bilinmeyen hata'}"
                )

            # LibreOffice, giriş adını kullandığı için "input.pdf" oluşturur
            expected = os.path.join(tmp_dir, "input.pdf")
            if os.path.exists(expected):
                out_pdf = expected
            else:
                # Fallback: tmp_dir içindeki ilk PDF'i bul
                pdfs = [f for f in os.listdir(tmp_dir) if f.endswith('.pdf')]
                if not pdfs:
                    raise RuntimeError(
                        f"PDF oluşturulamadı.\nLibreOffice çıktısı: {stdout_txt}\n{stderr_txt}"
                    )
                out_pdf = os.path.join(tmp_dir, pdfs[0])

        elif ext in ('.png', '.jpg', '.jpeg'):
            if not PIL_AVAILABLE:
                raise RuntimeError(
                    "Pillow kütüphanesi bulunamadı.\n"
                    "Terminalde şunu çalıştırın: pip install Pillow"
                )
            img = Image.open(src)
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(out_pdf, 'PDF', resolution=150)

        else:
            raise RuntimeError(f"Desteklenmeyen dosya türü: {ext}")

        if not os.path.exists(out_pdf):
            raise RuntimeError("PDF dosyası oluşturulamadı.")
        return out_pdf

    def conv_export_single(self):
        """Her dosyayı ayrı ayrı PDF olarak kaydeder."""
        if not self.conv_files:
            messagebox.showwarning("Uyarı", "Lütfen önce dosya ekleyin!")
            return
        out_dir = filedialog.askdirectory(title="Çıktı Klasörünü Seçin")
        if not out_dir: return

        def run():
            self.conv_progress['maximum'] = len(self.conv_files)
            self.conv_progress['value'] = 0
            success = 0
            for i, f in enumerate(self.conv_files):
                self.conv_status.config(text=f"Dönüştürülüyor: {f['name']}")
                self.root.update_idletasks()
                # Her dosya için ayrı geçici dizin → LibreOffice çakışması önlenir
                with tempfile.TemporaryDirectory() as tmp:
                    try:
                        pdf_path = self._convert_single_to_pdf(f, tmp)
                        base = Path(f['name']).stem
                        dest = os.path.join(out_dir, base + ".pdf")
                        if os.path.exists(dest):
                            dest = os.path.join(out_dir, f"{base}_{i+1}.pdf")
                        shutil.copy2(pdf_path, dest)
                        self.conv_files[i]['status'] = '✅ Tamam'
                        success += 1
                    except Exception as e:
                        self.conv_files[i]['status'] = f'❌ Hata'
                        # Hata mesajını durum çubuğunda göster
                        self.conv_status.config(text=f"Hata [{f['name']}]: {e}")
                        print(f"Hata [{f['name']}]: {e}")
                self.conv_progress['value'] += 1
                self.conv_refresh_tree()
                self.root.update_idletasks()
            self.conv_status.config(text=f"Tamamlandı. {success}/{len(self.conv_files)} dosya dönüştürüldü.")
            messagebox.showinfo("Tamamlandı", f"{success} dosya PDF olarak kaydedildi:\n{out_dir}")

        threading.Thread(target=run, daemon=True).start()

    def conv_export_merged(self):
        """Tüm dosyaları PDF'e dönüştürüp tek bir PDF'te birleştirir."""
        if not self.conv_files:
            messagebox.showwarning("Uyarı", "Lütfen önce dosya ekleyin!")
            return
        out_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Dosyaları", "*.pdf")],
            title="Birleşik PDF'i Kaydet"
        )
        if not out_path: return

        def run():
            self.conv_progress['maximum'] = len(self.conv_files)
            self.conv_progress['value'] = 0
            writer = PdfWriter()
            success = 0
            for i, f in enumerate(self.conv_files):
                self.conv_status.config(text=f"Dönüştürülüyor: {f['name']}")
                self.root.update_idletasks()
                # Her dosya için ayrı geçici dizin → LibreOffice çakışması önlenir
                with tempfile.TemporaryDirectory() as tmp:
                    try:
                        pdf_path = self._convert_single_to_pdf(f, tmp)
                        reader = PdfReader(pdf_path)
                        for page in reader.pages:
                            writer.add_page(page)
                        self.conv_files[i]['status'] = '✅ Eklendi'
                        success += 1
                    except Exception as e:
                        self.conv_files[i]['status'] = '❌ Hata'
                        self.conv_status.config(text=f"Hata [{f['name']}]: {e}")
                        print(f"Hata [{f['name']}]: {e}")
                self.conv_progress['value'] += 1
                self.conv_refresh_tree()
                self.root.update_idletasks()

            if writer.pages:
                self.conv_status.config(text="PDF yazılıyor…")
                self.root.update_idletasks()
                with open(out_path, 'wb') as fp:
                    writer.write(fp)
                self.conv_status.config(text=f"Tamamlandı. {success} dosya birleştirildi.")
                messagebox.showinfo("Başarılı", f"{success}/{len(self.conv_files)} dosya birleştirildi:\n{out_path}")
            else:
                self.conv_status.config(text="Hata: Hiçbir sayfa eklenemedi.")
                messagebox.showerror("Hata", "Hiçbir dosya dönüştürülemedi. Lütfen dosyaları kontrol edin.")

        threading.Thread(target=run, daemon=True).start()

    # ============================================================================
    # PDF DÜZENLEME SEKMESI - UI SETUP
    # ============================================================================
    
    def setup_edit_ui(self):
        """PDF düzenleme sekmesi UI'sini oluşturur"""
        if not REPORTLAB_AVAILABLE:
            warning_frame = tk.Frame(self.edit_tab, bg="#F5F6FA")
            warning_frame.pack(expand=True)
            tk.Label(warning_frame, text="⚠️ PDF Düzenleme Özellikleri İçin reportlab Gerekli", 
                    font=('Segoe UI', 14, 'bold'), bg="#F5F6FA", fg="#E74C3C").pack(pady=20)
            tk.Label(warning_frame, text="Terminalde şunu çalıştırın: pip install reportlab", 
                    font=('Segoe UI', 11), bg="#F5F6FA").pack()
            return
        
        # Ana container
        container = tk.Frame(self.edit_tab, bg="#F5F6FA")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Sol panel - Araçlar
        tools_panel = tk.Frame(container, bg="#FFFFFF", width=200, relief=tk.RAISED, bd=1)
        tools_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        tools_panel.pack_propagate(False)
        
        tk.Label(tools_panel, text="🎨 Düzenleme Araçları", font=('Segoe UI', 12, 'bold'), 
                bg="#34495E", fg="white", pady=10).pack(fill=tk.X)
        
        # Dosya işlemleri
        tk.Label(tools_panel, text="Dosya", font=('Segoe UI', 9, 'bold'), 
                bg="white", anchor='w', padx=10, pady=5).pack(fill=tk.X)
        ttk.Button(tools_panel, text="📂 PDF Aç", command=self.edit_open_pdf).pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(tools_panel, text="💾 Kaydet", command=self.edit_save_pdf).pack(fill=tk.X, padx=10, pady=2)
        
        # Metin işlemleri
        tk.Frame(tools_panel, bg="#E0E0E0", height=1).pack(fill=tk.X, pady=10)
        tk.Label(tools_panel, text="Metin & Şekil", font=('Segoe UI', 9, 'bold'), 
                bg="white", anchor='w', padx=10, pady=5).pack(fill=tk.X)
        
        # Araç seçim butonları (toggle)
        self.edit_tool_buttons = {}
        tools = [
            ("text", "✏️ Metin", "Tıklayarak metin ekle"),
            ("rectangle", "⬜ Dikdörtgen", "Sürükleyerek dikdörtgen çiz"),
            ("circle", "⭕ Daire", "Sürükleyerek daire çiz"),
            ("line", "📏 Çizgi", "Sürükleyerek çizgi çiz")
        ]
        
        for tool_id, text, tooltip in tools:
            btn = tk.Button(tools_panel, text=text, bg="#E8E8E8", fg="black",
                          font=('Segoe UI', 9), relief=tk.RAISED, bd=2,
                          command=lambda t=tool_id: self.edit_select_tool(t))
            btn.pack(fill=tk.X, padx=10, pady=2)
            self.edit_tool_buttons[tool_id] = btn
        
        ttk.Button(tools_panel, text="🖼️ Resim Ekle", command=self.edit_add_image).pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(tools_panel, text="💧 Filigran", command=self.edit_add_watermark).pack(fill=tk.X, padx=10, pady=2)
        
        # Görsel işlemleri
        tk.Frame(tools_panel, bg="#E0E0E0", height=1).pack(fill=tk.X, pady=10)
        tk.Label(tools_panel, text="Araç Ayarları", font=('Segoe UI', 9, 'bold'), 
                bg="white", anchor='w', padx=10, pady=5).pack(fill=tk.X)
        
        # Renk seçici
        tk.Label(tools_panel, text="Renk:", bg="white", font=('Segoe UI', 8)).pack(anchor='w', padx=10)
        self.edit_color_var = tk.StringVar(value="black")
        color_combo = ttk.Combobox(tools_panel, textvariable=self.edit_color_var, 
                                   values=["black", "red", "blue", "green", "yellow", "white"], 
                                   state="readonly", width=12)
        color_combo.pack(padx=10, pady=2)
        
        # Font/kalınlık
        tk.Label(tools_panel, text="Boyut/Kalınlık:", bg="white", font=('Segoe UI', 8)).pack(anchor='w', padx=10)
        self.edit_size_var = tk.IntVar(value=12)
        size_spin = ttk.Spinbox(tools_panel, from_=6, to=72, textvariable=self.edit_size_var, width=12)
        size_spin.pack(padx=10, pady=2)
        
        # Dolgu seçeneği
        self.edit_fill_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(tools_panel, text="Dolgulu", variable=self.edit_fill_var).pack(anchor='w', padx=10, pady=2)
        
        # Sayfa işlemleri
        tk.Frame(tools_panel, bg="#E0E0E0", height=1).pack(fill=tk.X, pady=10)
        tk.Label(tools_panel, text="Sayfa", font=('Segoe UI', 9, 'bold'), 
                bg="white", anchor='w', padx=10, pady=5).pack(fill=tk.X)
        ttk.Button(tools_panel, text="🔄 Döndür (90°)", command=self.edit_rotate_page).pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(tools_panel, text="❌ Sayfa Sil", command=self.edit_delete_page).pack(fill=tk.X, padx=10, pady=2)
        
        # Liste ve temizleme
        tk.Frame(tools_panel, bg="#E0E0E0", height=1).pack(fill=tk.X, pady=10)
        ttk.Button(tools_panel, text="📋 Düzenleme Listesi", command=self.edit_show_edits).pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(tools_panel, text="🗑️ Tümünü Temizle", command=self.edit_clear_all).pack(fill=tk.X, padx=10, pady=2)
        
        # Sağ panel - Önizleme ve Sayfa Kontrolü
        right_panel = tk.Frame(container, bg="#F5F6FA")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Üst kısım - Dosya bilgisi
        info_frame = tk.Frame(right_panel, bg="#FFFFFF", relief=tk.RAISED, bd=1)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.edit_file_label = tk.Label(info_frame, text="📄 Dosya seçilmedi", font=('Segoe UI', 11, 'bold'), 
                                       bg="white", anchor='w', padx=10, pady=10)
        self.edit_file_label.pack(fill=tk.X)
        
        # Sayfa navigasyonu
        nav_frame = tk.Frame(info_frame, bg="white")
        nav_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(nav_frame, text="◀ Önceki", command=self.edit_prev_page).pack(side=tk.LEFT, padx=2)
        self.edit_page_label = tk.Label(nav_frame, text="Sayfa: -", font=('Segoe UI', 10), bg="white")
        self.edit_page_label.pack(side=tk.LEFT, padx=20)
        ttk.Button(nav_frame, text="Sonraki ▶", command=self.edit_next_page).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(nav_frame, text="🔄 Önizlemeyi Yenile", command=self.edit_refresh_preview).pack(side=tk.RIGHT, padx=2)
        
        # Önizleme alanı
        preview_frame = tk.Frame(right_panel, bg="#FFFFFF", relief=tk.SUNKEN, bd=2)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas ile kaydırılabilir önizleme
        canvas_frame = tk.Frame(preview_frame, bg="white")
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_v = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        scrollbar_h = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        
        self.edit_canvas = tk.Canvas(canvas_frame, bg="#E0E0E0", 
                                     yscrollcommand=scrollbar_v.set,
                                     xscrollcommand=scrollbar_h.set)
        
        scrollbar_v.config(command=self.edit_canvas.yview)
        scrollbar_h.config(command=self.edit_canvas.xview)
        
        scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
        self.edit_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas'a görsel için image item oluştur
        self.edit_canvas_image = None
        
        # Canvas mouse event'leri
        self.edit_canvas.bind("<Button-1>", self.edit_canvas_click)
        self.edit_canvas.bind("<B1-Motion>", self.edit_canvas_drag)
        self.edit_canvas.bind("<ButtonRelease-1>", self.edit_canvas_release)
        self.edit_canvas.bind("<Motion>", self.edit_canvas_motion)
        
        # Durum çubuğu
        status_frame = tk.Frame(right_panel, bg="#ECEFF1")
        status_frame.pack(fill=tk.X)
        
        self.edit_tool_label = tk.Label(status_frame, text="🖱️ Araç: Yok", font=('Segoe UI', 9, 'bold'), 
                                        bg="#ECEFF1", anchor='w', padx=10)
        self.edit_tool_label.pack(side=tk.LEFT)
        
        self.edit_status = tk.Label(status_frame, text="Hazır", font=('Segoe UI', 9), 
                                    bg="#ECEFF1", anchor='w', padx=10, pady=5)
        self.edit_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ============================================================================
    # PDF DÜZENLEME - TEMEL İŞLEMLER
    # ============================================================================
    
    def edit_open_pdf(self):
        """PDF dosyası açar"""
        file_path = filedialog.askopenfilename(
            title="PDF Dosyası Seç",
            filetypes=[("PDF Dosyaları", "*.pdf")]
        )
        if not file_path:
            return
        
        try:
            reader = PdfReader(file_path)
            self.edit_data['path'] = file_path
            self.edit_data['name'] = Path(file_path).name
            self.edit_data['total_pages'] = len(reader.pages)
            self.edit_data['current_page'] = 1
            self.edit_data['edits'] = []
            
            self.edit_file_label.config(text=f"📄 {self.edit_data['name']}")
            self.edit_page_label.config(text=f"Sayfa: 1 / {self.edit_data['total_pages']}")
            self.edit_status.config(text=f"PDF yüklendi: {self.edit_data['total_pages']} sayfa")
            
            self.edit_refresh_preview()
            
        except Exception as e:
            messagebox.showerror("Hata", f"PDF açılamadı: {e}")
    
    def edit_refresh_preview(self):
        """Mevcut sayfanın önizlemesini oluşturur"""
        if not self.edit_data['path']:
            self.edit_status.config(text="Önce bir PDF dosyası açın")
            return
        
        if not PYPDFIUM_AVAILABLE:
            self.edit_status.config(text="Önizleme için pypdfium2 gerekli: pip install pypdfium2")
            messagebox.showwarning("Uyarı", "Önizleme için pypdfium2 kütüphanesi gerekli.\nTerminalde: pip install pypdfium2")
            return
        
        try:
            self.edit_status.config(text="Önizleme oluşturuluyor...")
            self.root.update_idletasks()
            
            # PDF'i yükle ve sayfayı render et
            pdf = pdfium.PdfDocument(self.edit_data['path'])
            page = pdf[self.edit_data['current_page'] - 1]
            
            # Yüksek çözünürlükte render et
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil()
            
            # Orijinal PDF boyutları
            pdf_width = float(PdfReader(self.edit_data['path']).pages[self.edit_data['current_page'] - 1].mediabox.width)
            pdf_height = float(PdfReader(self.edit_data['path']).pages[self.edit_data['current_page'] - 1].mediabox.height)
            
            # Tkinter için PhotoImage'e çevir
            # Önce boyutunu kontrol et, çok büyükse küçült
            max_width = 700
            max_height = 900
            
            img_width, img_height = pil_image.size
            scale_factor = min(max_width / img_width, max_height / img_height, 1.0)
            
            if scale_factor < 1.0:
                new_width = int(img_width * scale_factor)
                new_height = int(img_height * scale_factor)
                pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
            
            # Canvas'a göre PDF'e dönüşüm faktörü
            # Canvas pixel -> PDF punto dönüşümü
            self.edit_data['scale_factor'] = pdf_width / pil_image.size[0]
            self.edit_data['pdf_width'] = pdf_width
            self.edit_data['pdf_height'] = pdf_height
            
            # PhotoImage'e çevir
            self.edit_data['preview_image'] = ImageTk.PhotoImage(pil_image)
            
            # Canvas'ı temizle ve resmi yerleştir
            self.edit_canvas.delete("all")
            self.edit_canvas_image = self.edit_canvas.create_image(
                0, 0, anchor=tk.NW, image=self.edit_data['preview_image']
            )
            
            # Mevcut düzenlemeleri canvas'ta göster
            self.edit_redraw_edits()
            
            # Scrollregion'u ayarla
            self.edit_canvas.config(scrollregion=self.edit_canvas.bbox(tk.ALL))
            
            self.edit_status.config(text=f"Önizleme hazır - Sayfa {self.edit_data['current_page']}")
            
        except Exception as e:
            self.edit_status.config(text=f"Önizleme hatası: {e}")
            messagebox.showerror("Hata", f"Önizleme oluşturulamadı: {e}")
    
    def edit_redraw_edits(self):
        """Mevcut sayfadaki düzenlemeleri canvas'ta gösterir"""
        # Canvas'taki düzenleme nesnelerini temizle
        for item_id in self.edit_data.get('canvas_items', []):
            try:
                self.edit_canvas.delete(item_id)
            except:
                pass
        self.edit_data['canvas_items'] = []
        
        if not self.edit_data['path']:
            return
        
        # Bu sayfadaki düzenlemeleri filtrele
        page_edits = [e for e in self.edit_data['edits'] if e['page'] == self.edit_data['current_page']]
        
        scale = self.edit_data.get('scale_factor', 1.0)
        pdf_height = self.edit_data.get('pdf_height', 842)
        
        for edit in page_edits:
            edit_type = edit['type']
            params = edit['params']
            
            if edit_type == 'text':
                # PDF koordinatlarından canvas'a çevir
                x_canvas = params['x'] / scale
                y_canvas = (pdf_height - params['y']) / scale
                
                item_id = self.edit_canvas.create_text(
                    x_canvas, y_canvas, 
                    text=params['text'],
                    fill=params['color'],
                    font=('Helvetica', max(8, int(params['size'] / scale))),
                    anchor='nw',
                    tags='edit_item'
                )
                self.edit_data['canvas_items'].append(item_id)
            
            elif edit_type == 'rectangle':
                x1 = params['x'] / scale
                y1 = (pdf_height - params['y']) / scale
                x2 = (params['x'] + params['width']) / scale
                y2 = (pdf_height - params['y'] - params['height']) / scale
                
                fill_color = params['fill'] if params['fill'] != 'none' else ''
                outline_color = params['stroke'] if params['stroke'] != 'none' else ''
                
                item_id = self.edit_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=fill_color,
                    outline=outline_color,
                    width=2,
                    tags='edit_item'
                )
                self.edit_data['canvas_items'].append(item_id)
            
            elif edit_type == 'circle':
                x_canvas = params['x'] / scale
                y_canvas = (pdf_height - params['y']) / scale
                r_canvas = params['radius'] / scale
                
                fill_color = params['fill'] if params['fill'] != 'none' else ''
                outline_color = params['stroke'] if params['stroke'] != 'none' else ''
                
                item_id = self.edit_canvas.create_oval(
                    x_canvas - r_canvas, y_canvas - r_canvas,
                    x_canvas + r_canvas, y_canvas + r_canvas,
                    fill=fill_color,
                    outline=outline_color,
                    width=2,
                    tags='edit_item'
                )
                self.edit_data['canvas_items'].append(item_id)
            
            elif edit_type == 'line':
                x1 = params['x1'] / scale
                y1 = (pdf_height - params['y1']) / scale
                x2 = params['x2'] / scale
                y2 = (pdf_height - params['y2']) / scale
                
                item_id = self.edit_canvas.create_line(
                    x1, y1, x2, y2,
                    fill=params['color'],
                    width=params['width'],
                    tags='edit_item'
                )
                self.edit_data['canvas_items'].append(item_id)
    
    def edit_select_tool(self, tool):
        """Düzenleme aracını seçer"""
        # Önceki seçimi temizle
        if self.edit_data['selected_tool']:
            old_btn = self.edit_tool_buttons.get(self.edit_data['selected_tool'])
            if old_btn:
                old_btn.config(bg="#E8E8E8", relief=tk.RAISED)
        
        # Aynı araca tıklandıysa seçimi kaldır
        if self.edit_data['selected_tool'] == tool:
            self.edit_data['selected_tool'] = None
            self.edit_tool_label.config(text="🖱️ Araç: Yok")
            self.edit_canvas.config(cursor="")
        else:
            # Yeni aracı seç
            self.edit_data['selected_tool'] = tool
            new_btn = self.edit_tool_buttons.get(tool)
            if new_btn:
                new_btn.config(bg="#4CAF50", relief=tk.SUNKEN)
            
            tool_names = {
                'text': '✏️ Metin (Tıkla)',
                'rectangle': '⬜ Dikdörtgen (Sürükle)',
                'circle': '⭕ Daire (Sürükle)',
                'line': '📏 Çizgi (Sürükle)'
            }
            self.edit_tool_label.config(text=f"🖱️ {tool_names.get(tool, tool)}")
            self.edit_canvas.config(cursor="crosshair")
    
    def edit_canvas_click(self, event):
        """Canvas'a tıklama"""
        if not self.edit_data['path'] or not self.edit_data['selected_tool']:
            return
        
        # Canvas koordinatlarını al (scroll pozisyonunu hesaba kat)
        canvas_x = self.edit_canvas.canvasx(event.x)
        canvas_y = self.edit_canvas.canvasy(event.y)
        
        tool = self.edit_data['selected_tool']
        
        if tool == 'text':
            # Metin ekle
            self.edit_add_text_at_position(canvas_x, canvas_y)
        else:
            # Sürükleme başlangıcı
            self.edit_data['drag_start'] = (canvas_x, canvas_y)
            self.edit_data['temp_shape'] = None
    
    def edit_canvas_drag(self, event):
        """Canvas'ta sürükleme"""
        if not self.edit_data['path'] or not self.edit_data.get('drag_start'):
            return
        
        canvas_x = self.edit_canvas.canvasx(event.x)
        canvas_y = self.edit_canvas.canvasy(event.y)
        
        start_x, start_y = self.edit_data['drag_start']
        tool = self.edit_data['selected_tool']
        
        # Önceki geçici şekli sil
        if self.edit_data.get('temp_shape'):
            self.edit_canvas.delete(self.edit_data['temp_shape'])
        
        # Yeni geçici şekil çiz
        color = self.edit_color_var.get()
        fill_color = color if self.edit_fill_var.get() else ''
        
        if tool == 'rectangle':
            self.edit_data['temp_shape'] = self.edit_canvas.create_rectangle(
                start_x, start_y, canvas_x, canvas_y,
                outline=color, fill=fill_color, width=2, dash=(4, 4)
            )
        elif tool == 'circle':
            # Merkez ve yarıçap hesapla
            radius = ((canvas_x - start_x)**2 + (canvas_y - start_y)**2)**0.5
            self.edit_data['temp_shape'] = self.edit_canvas.create_oval(
                start_x - radius, start_y - radius,
                start_x + radius, start_y + radius,
                outline=color, fill=fill_color, width=2, dash=(4, 4)
            )
        elif tool == 'line':
            self.edit_data['temp_shape'] = self.edit_canvas.create_line(
                start_x, start_y, canvas_x, canvas_y,
                fill=color, width=self.edit_size_var.get(), dash=(4, 4)
            )
    
    def edit_canvas_release(self, event):
        """Canvas'ta mouse serbest bırakma"""
        if not self.edit_data['path'] or not self.edit_data.get('drag_start'):
            return
        
        canvas_x = self.edit_canvas.canvasx(event.x)
        canvas_y = self.edit_canvas.canvasy(event.y)
        
        start_x, start_y = self.edit_data['drag_start']
        tool = self.edit_data['selected_tool']
        
        # Geçici şekli sil
        if self.edit_data.get('temp_shape'):
            self.edit_canvas.delete(self.edit_data['temp_shape'])
            self.edit_data['temp_shape'] = None
        
        # Çok küçük sürüklemeler için işlem yapma
        if abs(canvas_x - start_x) < 5 and abs(canvas_y - start_y) < 5:
            self.edit_data['drag_start'] = None
            return
        
        # Canvas koordinatlarını PDF koordinatlarına çevir
        scale = self.edit_data.get('scale_factor', 1.0)
        pdf_height = self.edit_data.get('pdf_height', 842)
        
        pdf_start_x = start_x * scale
        pdf_start_y = pdf_height - (start_y * scale)
        pdf_end_x = canvas_x * scale
        pdf_end_y = pdf_height - (canvas_y * scale)
        
        # Düzenlemeyi kaydet
        color = self.edit_color_var.get()
        
        if tool == 'rectangle':
            width = abs(pdf_end_x - pdf_start_x)
            height = abs(pdf_start_y - pdf_end_y)
            x = min(pdf_start_x, pdf_end_x)
            y = max(pdf_start_y, pdf_end_y)
            
            edit_info = {
                'type': 'rectangle',
                'page': self.edit_data['current_page'],
                'params': {
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'fill': color if self.edit_fill_var.get() else 'none',
                    'stroke': color
                }
            }
            self.edit_data['edits'].append(edit_info)
            self.edit_status.config(text="Dikdörtgen eklendi")
        
        elif tool == 'circle':
            radius = ((canvas_x - start_x)**2 + (canvas_y - start_y)**2)**0.5 * scale
            
            edit_info = {
                'type': 'circle',
                'page': self.edit_data['current_page'],
                'params': {
                    'x': pdf_start_x,
                    'y': pdf_start_y,
                    'radius': radius,
                    'fill': color if self.edit_fill_var.get() else 'none',
                    'stroke': color
                }
            }
            self.edit_data['edits'].append(edit_info)
            self.edit_status.config(text="Daire eklendi")
        
        elif tool == 'line':
            edit_info = {
                'type': 'line',
                'page': self.edit_data['current_page'],
                'params': {
                    'x1': pdf_start_x,
                    'y1': pdf_start_y,
                    'x2': pdf_end_x,
                    'y2': pdf_end_y,
                    'color': color,
                    'width': self.edit_size_var.get()
                }
            }
            self.edit_data['edits'].append(edit_info)
            self.edit_status.config(text="Çizgi eklendi")
        
        # Canvas'ı güncelle
        self.edit_redraw_edits()
        self.edit_data['drag_start'] = None
    
    def edit_canvas_motion(self, event):
        """Canvas üzerinde mouse hareketi - koordinatları göster"""
        if not self.edit_data['path']:
            return
        
        canvas_x = self.edit_canvas.canvasx(event.x)
        canvas_y = self.edit_canvas.canvasy(event.y)
        
        scale = self.edit_data.get('scale_factor', 1.0)
        pdf_height = self.edit_data.get('pdf_height', 842)
        
        pdf_x = int(canvas_x * scale)
        pdf_y = int(pdf_height - (canvas_y * scale))
        
        if not self.edit_data.get('drag_start'):
            self.edit_status.config(text=f"PDF Koord: X={pdf_x}, Y={pdf_y}")
    
    def edit_add_text_at_position(self, canvas_x, canvas_y):
        """Belirtilen canvas pozisyonuna metin ekler"""
        # Canvas koordinatlarını PDF'e çevir
        scale = self.edit_data.get('scale_factor', 1.0)
        pdf_height = self.edit_data.get('pdf_height', 842)
        
        pdf_x = canvas_x * scale
        pdf_y = pdf_height - (canvas_y * scale)
        
        # Metin girişi diyalogu
        dialog = tk.Toplevel(self.root)
        dialog.title("Metin Ekle")
        dialog.geometry("350x200")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Metin Ekle", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        tk.Label(dialog, text=f"Pozisyon: X={int(pdf_x)}, Y={int(pdf_y)}", 
                bg="#F5F6FA", fg="#666").pack()
        
        tk.Label(dialog, text="Metin:", bg="#F5F6FA").pack(anchor='w', padx=20, pady=(10,0))
        text_entry = tk.Entry(dialog, font=('Segoe UI', 10), width=30)
        text_entry.pack(padx=20, pady=5)
        text_entry.focus()
        
        def save_text(event=None):
            text = text_entry.get()
            if not text:
                return
            
            edit_info = {
                'type': 'text',
                'page': self.edit_data['current_page'],
                'params': {
                    'text': text,
                    'x': pdf_x,
                    'y': pdf_y,
                    'size': self.edit_size_var.get(),
                    'color': self.edit_color_var.get()
                }
            }
            self.edit_data['edits'].append(edit_info)
            self.edit_status.config(text=f"Metin eklendi: '{text[:20]}...'")
            self.edit_redraw_edits()
            dialog.destroy()
        
        text_entry.bind('<Return>', save_text)
        ttk.Button(dialog, text="Ekle", command=save_text).pack(pady=15)
        ttk.Button(dialog, text="İptal", command=dialog.destroy).pack()
    
    def edit_prev_page(self):
        """Önceki sayfaya geç"""
        if not self.edit_data['path']:
            return
        if self.edit_data['current_page'] > 1:
            self.edit_data['current_page'] -= 1
            self.edit_page_label.config(text=f"Sayfa: {self.edit_data['current_page']} / {self.edit_data['total_pages']}")
            self.edit_refresh_preview()
    
    def edit_next_page(self):
        """Sonraki sayfaya geç"""
        if not self.edit_data['path']:
            return
        if self.edit_data['current_page'] < self.edit_data['total_pages']:
            self.edit_data['current_page'] += 1
            self.edit_page_label.config(text=f"Sayfa: {self.edit_data['current_page']} / {self.edit_data['total_pages']}")
            self.edit_refresh_preview()

    # ============================================================================
    # PDF DÜZENLEME - ARAÇLAR
    # ============================================================================
    
    def edit_add_text(self):
        """Sayfaya metin ekler"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        # Dialog penceresi
        dialog = tk.Toplevel(self.root)
        dialog.title("Metin Ekle")
        dialog.geometry("450x400")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Metin Ekle", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        
        # Koordinat bilgisi
        info_frame = tk.Frame(dialog, bg="#E3F2FD", relief=tk.RAISED, bd=1)
        info_frame.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(info_frame, text="💡 Koordinat Sistemi: Sol üst köşe (0,0), sağa X artar, aşağı Y artar", 
                font=('Segoe UI', 8), bg="#E3F2FD", fg="#1976D2").pack(pady=5)
        tk.Label(info_frame, text=f"📏 Sayfa boyutu: ~{int(float(PdfReader(self.edit_data['path']).pages[0].mediabox.width))} x {int(float(PdfReader(self.edit_data['path']).pages[0].mediabox.height))} punto", 
                font=('Segoe UI', 8), bg="#E3F2FD", fg="#1976D2").pack(pady=2)
        
        # Metin girişi
        tk.Label(dialog, text="Metin:", bg="#F5F6FA").pack(anchor='w', padx=20, pady=(10,0))
        text_entry = tk.Entry(dialog, font=('Segoe UI', 10), width=40)
        text_entry.pack(padx=20, pady=5)
        
        # Pozisyon
        tk.Label(dialog, text="Pozisyon (sol üstten):", bg="#F5F6FA").pack(anchor='w', padx=20)
        pos_frame = tk.Frame(dialog, bg="#F5F6FA")
        pos_frame.pack(pady=10)
        tk.Label(pos_frame, text="X:", bg="#F5F6FA").grid(row=0, column=0, padx=5)
        x_entry = tk.Entry(pos_frame, width=10)
        x_entry.insert(0, "50")  # Sol kenardan 50 punto
        x_entry.grid(row=0, column=1)
        
        tk.Label(pos_frame, text="Y:", bg="#F5F6FA").grid(row=0, column=2, padx=5)
        y_entry = tk.Entry(pos_frame, width=10)
        y_entry.insert(0, "100")  # Üstten 100 punto
        y_entry.grid(row=0, column=3)
        
        # Hızlı pozisyon butonları
        quick_pos_frame = tk.Frame(dialog, bg="#F5F6FA")
        quick_pos_frame.pack(pady=5)
        tk.Label(quick_pos_frame, text="Hızlı Konum:", bg="#F5F6FA", font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        
        def set_pos(x, y):
            x_entry.delete(0, tk.END)
            x_entry.insert(0, str(x))
            y_entry.delete(0, tk.END)
            y_entry.insert(0, str(y))
        
        ttk.Button(quick_pos_frame, text="Sol Üst", command=lambda: set_pos(50, 50)).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_pos_frame, text="Orta Üst", command=lambda: set_pos(250, 50)).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_pos_frame, text="Merkez", command=lambda: set_pos(250, 400)).pack(side=tk.LEFT, padx=2)
        
        # Font boyutu
        tk.Label(dialog, text="Font Boyutu:", bg="#F5F6FA").pack(anchor='w', padx=20)
        size_var = tk.IntVar(value=12)
        size_spin = ttk.Spinbox(dialog, from_=6, to=72, textvariable=size_var, width=10)
        size_spin.pack(padx=20, pady=5, anchor='w')
        
        # Renk
        tk.Label(dialog, text="Renk:", bg="#F5F6FA").pack(anchor='w', padx=20)
        color_var = tk.StringVar(value="black")
        color_combo = ttk.Combobox(dialog, textvariable=color_var, values=["black", "red", "blue", "green", "white"], state="readonly")
        color_combo.pack(padx=20, pady=5, anchor='w')
        
        def save_text():
            text = text_entry.get()
            if not text:
                messagebox.showwarning("Uyarı", "Lütfen metin girin!")
                return
            
            try:
                x = float(x_entry.get())
                y = float(y_entry.get())
                
                edit_info = {
                    'type': 'text',
                    'page': self.edit_data['current_page'],
                    'params': {
                        'text': text,
                        'x': x,
                        'y': y,
                        'size': size_var.get(),
                        'color': color_var.get()
                    }
                }
                self.edit_data['edits'].append(edit_info)
                self.edit_status.config(text=f"Metin eklendi: '{text[:20]}...'")
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Metin eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
            except ValueError:
                messagebox.showerror("Hata", "Geçersiz koordinat değeri!")
        
        ttk.Button(dialog, text="Ekle", command=save_text).pack(pady=20)
    
    def edit_add_rectangle(self):
        """Dikdörtgen ekler"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Dikdörtgen Ekle")
        dialog.geometry("450x380")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Dikdörtgen Ekle", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        
        # Koordinat bilgisi
        info_frame = tk.Frame(dialog, bg="#E3F2FD", relief=tk.RAISED, bd=1)
        info_frame.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(info_frame, text="💡 Sol üst köşeden başlayarak X (sağa) ve Y (aşağı) koordinatları", 
                font=('Segoe UI', 8), bg="#E3F2FD", fg="#1976D2").pack(pady=5)
        
        # Pozisyon ve boyut
        tk.Label(dialog, text="Pozisyon (sol üst köşe):", bg="#F5F6FA").pack(anchor='w', padx=20)
        pos_frame = tk.Frame(dialog, bg="#F5F6FA")
        pos_frame.pack(pady=5)
        
        tk.Label(pos_frame, text="X:", bg="#F5F6FA").grid(row=0, column=0, padx=2)
        x_entry = tk.Entry(pos_frame, width=8)
        x_entry.insert(0, "50")
        x_entry.grid(row=0, column=1)
        
        tk.Label(pos_frame, text="Y:", bg="#F5F6FA").grid(row=0, column=2, padx=2)
        y_entry = tk.Entry(pos_frame, width=8)
        y_entry.insert(0, "100")
        y_entry.grid(row=0, column=3)
        
        tk.Label(dialog, text="Boyut:", bg="#F5F6FA").pack(anchor='w', padx=20, pady=(10,0))
        size_frame = tk.Frame(dialog, bg="#F5F6FA")
        size_frame.pack(pady=5)
        
        tk.Label(size_frame, text="Genişlik:", bg="#F5F6FA").grid(row=0, column=0, padx=2)
        w_entry = tk.Entry(size_frame, width=8)
        w_entry.insert(0, "200")
        w_entry.grid(row=0, column=1)
        
        tk.Label(size_frame, text="Yükseklik:", bg="#F5F6FA").grid(row=0, column=2, padx=2)
        h_entry = tk.Entry(size_frame, width=8)
        h_entry.insert(0, "100")
        h_entry.grid(row=0, column=3)
        
        # Dolgu rengi
        tk.Label(dialog, text="Dolgu Rengi (içi):", bg="#F5F6FA").pack(anchor='w', padx=20, pady=(10, 0))
        fill_var = tk.StringVar(value="white")
        fill_combo = ttk.Combobox(dialog, textvariable=fill_var, 
                                  values=["none", "white", "black", "red", "blue", "green", "yellow"], state="readonly")
        fill_combo.pack(padx=20, pady=5, anchor='w')
        
        # Çerçeve rengi
        tk.Label(dialog, text="Çerçeve Rengi (kenar):", bg="#F5F6FA").pack(anchor='w', padx=20)
        stroke_var = tk.StringVar(value="black")
        stroke_combo = ttk.Combobox(dialog, textvariable=stroke_var, 
                                    values=["none", "black", "red", "blue", "green"], state="readonly")
        stroke_combo.pack(padx=20, pady=5, anchor='w')
        
        # İpucu
        tk.Label(dialog, text="💡 İpucu: Beyaz dolgu + çerçeve yok = Metni gizler", 
                font=('Segoe UI', 8, 'italic'), bg="#F5F6FA", fg="#666").pack(pady=5)
        
        def save_rect():
            try:
                x, y = float(x_entry.get()), float(y_entry.get())
                w, h = float(w_entry.get()), float(h_entry.get())
                
                edit_info = {
                    'type': 'rectangle',
                    'page': self.edit_data['current_page'],
                    'params': {
                        'x': x, 'y': y, 'width': w, 'height': h,
                        'fill': fill_var.get(), 'stroke': stroke_var.get()
                    }
                }
                self.edit_data['edits'].append(edit_info)
                self.edit_status.config(text="Dikdörtgen eklendi")
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Dikdörtgen eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
            except ValueError:
                messagebox.showerror("Hata", "Geçersiz değer!")
        
        ttk.Button(dialog, text="Ekle", command=save_rect).pack(pady=15)
    
    def edit_add_circle(self):
        """Daire ekler"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Daire Ekle")
        dialog.geometry("400x330")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Daire Ekle", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        
        # Koordinat bilgisi
        info_frame = tk.Frame(dialog, bg="#E3F2FD", relief=tk.RAISED, bd=1)
        info_frame.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(info_frame, text="💡 Merkez koordinatları (X, Y) ve yarıçap", 
                font=('Segoe UI', 8), bg="#E3F2FD", fg="#1976D2").pack(pady=5)
        
        # Merkez ve yarıçap
        tk.Label(dialog, text="Merkez Noktası:", bg="#F5F6FA").pack(anchor='w', padx=20)
        pos_frame = tk.Frame(dialog, bg="#F5F6FA")
        pos_frame.pack(pady=5)
        
        tk.Label(pos_frame, text="X:", bg="#F5F6FA").grid(row=0, column=0, padx=2)
        x_entry = tk.Entry(pos_frame, width=10)
        x_entry.insert(0, "200")
        x_entry.grid(row=0, column=1)
        
        tk.Label(pos_frame, text="Y:", bg="#F5F6FA").grid(row=0, column=2, padx=2)
        y_entry = tk.Entry(pos_frame, width=10)
        y_entry.insert(0, "150")
        y_entry.grid(row=0, column=3)
        
        tk.Label(pos_frame, text="Yarıçap:", bg="#F5F6FA").grid(row=1, column=0, padx=2, pady=5)
        r_entry = tk.Entry(pos_frame, width=10)
        r_entry.insert(0, "50")
        r_entry.grid(row=1, column=1)
        
        # Renkler
        tk.Label(dialog, text="Dolgu:", bg="#F5F6FA").pack(anchor='w', padx=20, pady=(10,0))
        fill_var = tk.StringVar(value="none")
        fill_combo = ttk.Combobox(dialog, textvariable=fill_var, 
                                  values=["none", "white", "black", "red", "blue", "green", "yellow"], state="readonly")
        fill_combo.pack(padx=20, pady=5, anchor='w')
        
        tk.Label(dialog, text="Çerçeve:", bg="#F5F6FA").pack(anchor='w', padx=20)
        stroke_var = tk.StringVar(value="black")
        stroke_combo = ttk.Combobox(dialog, textvariable=stroke_var, 
                                    values=["none", "black", "red", "blue", "green"], state="readonly")
        stroke_combo.pack(padx=20, pady=5, anchor='w')
        
        def save_circle():
            try:
                x, y = float(x_entry.get()), float(y_entry.get())
                r = float(r_entry.get())
                
                edit_info = {
                    'type': 'circle',
                    'page': self.edit_data['current_page'],
                    'params': {
                        'x': x, 'y': y, 'radius': r,
                        'fill': fill_var.get(), 'stroke': stroke_var.get()
                    }
                }
                self.edit_data['edits'].append(edit_info)
                self.edit_status.config(text="Daire eklendi")
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Daire eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
            except ValueError:
                messagebox.showerror("Hata", "Geçersiz değer!")
        
        ttk.Button(dialog, text="Ekle", command=save_circle).pack(pady=20)
    
    def edit_add_line(self):
        """Çizgi ekler"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Çizgi Ekle")
        dialog.geometry("420x300")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Çizgi Ekle", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        
        # Koordinat bilgisi
        info_frame = tk.Frame(dialog, bg="#E3F2FD", relief=tk.RAISED, bd=1)
        info_frame.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(info_frame, text="💡 Başlangıç (X1,Y1) ve Bitiş (X2,Y2) noktaları", 
                font=('Segoe UI', 8), bg="#E3F2FD", fg="#1976D2").pack(pady=5)
        
        # Başlangıç ve bitiş noktaları
        tk.Label(dialog, text="Başlangıç ve Bitiş:", bg="#F5F6FA").pack(anchor='w', padx=20)
        pos_frame = tk.Frame(dialog, bg="#F5F6FA")
        pos_frame.pack(pady=5)
        
        tk.Label(pos_frame, text="X1:", bg="#F5F6FA").grid(row=0, column=0, padx=2)
        x1_entry = tk.Entry(pos_frame, width=8)
        x1_entry.insert(0, "50")
        x1_entry.grid(row=0, column=1)
        
        tk.Label(pos_frame, text="Y1:", bg="#F5F6FA").grid(row=0, column=2, padx=2)
        y1_entry = tk.Entry(pos_frame, width=8)
        y1_entry.insert(0, "100")
        y1_entry.grid(row=0, column=3)
        
        tk.Label(pos_frame, text="X2:", bg="#F5F6FA").grid(row=1, column=0, padx=2, pady=5)
        x2_entry = tk.Entry(pos_frame, width=8)
        x2_entry.insert(0, "300")
        x2_entry.grid(row=1, column=1)
        
        tk.Label(pos_frame, text="Y2:", bg="#F5F6FA").grid(row=1, column=2, padx=2)
        y2_entry = tk.Entry(pos_frame, width=8)
        y2_entry.insert(0, "100")
        y2_entry.grid(row=1, column=3)
        
        # Renk ve kalınlık
        tk.Label(dialog, text="Renk:", bg="#F5F6FA").pack(anchor='w', padx=20, pady=(10,0))
        color_var = tk.StringVar(value="black")
        color_combo = ttk.Combobox(dialog, textvariable=color_var, 
                                   values=["black", "red", "blue", "green"], state="readonly")
        color_combo.pack(padx=20, pady=5, anchor='w')
        
        tk.Label(dialog, text="Kalınlık:", bg="#F5F6FA").pack(anchor='w', padx=20)
        width_var = tk.IntVar(value=1)
        width_spin = ttk.Spinbox(dialog, from_=1, to=10, textvariable=width_var, width=10)
        width_spin.pack(padx=20, pady=5, anchor='w')
        
        def save_line():
            try:
                x1, y1 = float(x1_entry.get()), float(y1_entry.get())
                x2, y2 = float(x2_entry.get()), float(y2_entry.get())
                
                edit_info = {
                    'type': 'line',
                    'page': self.edit_data['current_page'],
                    'params': {
                        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                        'color': color_var.get(), 'width': width_var.get()
                    }
                }
                self.edit_data['edits'].append(edit_info)
                self.edit_status.config(text="Çizgi eklendi")
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Çizgi eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
            except ValueError:
                messagebox.showerror("Hata", "Geçersiz değer!")
        
        ttk.Button(dialog, text="Ekle", command=save_line).pack(pady=15)
    
    def edit_add_image(self):
        """Resim ekler"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        # Resim dosyası seç
        image_path = filedialog.askopenfilename(
            title="Resim Seç",
            filetypes=[("Resim Dosyaları", "*.png *.jpg *.jpeg")]
        )
        if not image_path:
            return
        
        # Dialog penceresi
        dialog = tk.Toplevel(self.root)
        dialog.title("Resim Ekle")
        dialog.geometry("420x330")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Resim Ekle", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        
        # Dosya adı
        tk.Label(dialog, text=f"📷 {Path(image_path).name}", bg="#F5F6FA", fg="#1976D2", 
                font=('Segoe UI', 9, 'bold')).pack()
        
        # Koordinat bilgisi
        info_frame = tk.Frame(dialog, bg="#E3F2FD", relief=tk.RAISED, bd=1)
        info_frame.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(info_frame, text="💡 Sol üst köşe koordinatları ve boyut", 
                font=('Segoe UI', 8), bg="#E3F2FD", fg="#1976D2").pack(pady=5)
        
        # Pozisyon ve boyut
        tk.Label(dialog, text="Pozisyon (sol üst):", bg="#F5F6FA").pack(anchor='w', padx=20, pady=(10, 0))
        pos_frame = tk.Frame(dialog, bg="#F5F6FA")
        pos_frame.pack(pady=5)
        
        tk.Label(pos_frame, text="X:", bg="#F5F6FA").grid(row=0, column=0, padx=2)
        x_entry = tk.Entry(pos_frame, width=10)
        x_entry.insert(0, "50")
        x_entry.grid(row=0, column=1)
        
        tk.Label(pos_frame, text="Y:", bg="#F5F6FA").grid(row=0, column=2, padx=2)
        y_entry = tk.Entry(pos_frame, width=10)
        y_entry.insert(0, "100")
        y_entry.grid(row=0, column=3)
        
        tk.Label(dialog, text="Boyut:", bg="#F5F6FA").pack(anchor='w', padx=20)
        size_frame = tk.Frame(dialog, bg="#F5F6FA")
        size_frame.pack(pady=5)
        
        tk.Label(size_frame, text="Genişlik:", bg="#F5F6FA").grid(row=0, column=0, padx=2)
        w_entry = tk.Entry(size_frame, width=10)
        w_entry.insert(0, "200")
        w_entry.grid(row=0, column=1)
        
        tk.Label(size_frame, text="Yükseklik:", bg="#F5F6FA").grid(row=0, column=2, padx=2)
        h_entry = tk.Entry(size_frame, width=10)
        h_entry.insert(0, "150")
        h_entry.grid(row=0, column=3)
        
        def save_image():
            try:
                x, y = float(x_entry.get()), float(y_entry.get())
                w, h = float(w_entry.get()), float(h_entry.get())
                
                edit_info = {
                    'type': 'image',
                    'page': self.edit_data['current_page'],
                    'params': {
                        'image_path': image_path,
                        'x': x, 'y': y, 'width': w, 'height': h
                    }
                }
                self.edit_data['edits'].append(edit_info)
                self.edit_status.config(text=f"Resim eklendi: {Path(image_path).name}")
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Resim eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
            except ValueError:
                messagebox.showerror("Hata", "Geçersiz değer!")
        
        ttk.Button(dialog, text="Ekle", command=save_image).pack(pady=20)
    
    def edit_add_watermark(self):
        """Filigran ekler"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Filigran Ekle")
        dialog.geometry("400x300")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Filigran Ekle", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        
        # Filigran metni
        tk.Label(dialog, text="Filigran Metni:", bg="#F5F6FA").pack(anchor='w', padx=20)
        text_entry = tk.Entry(dialog, font=('Segoe UI', 10), width=40)
        text_entry.insert(0, "GİZLİ")
        text_entry.pack(padx=20, pady=5)
        
        # Pozisyon
        tk.Label(dialog, text="Pozisyon:", bg="#F5F6FA").pack(anchor='w', padx=20)
        pos_var = tk.StringVar(value="center")
        ttk.Radiobutton(dialog, text="Merkez", variable=pos_var, value="center").pack(anchor='w', padx=40)
        ttk.Radiobutton(dialog, text="Köşegen", variable=pos_var, value="diagonal").pack(anchor='w', padx=40)
        
        # Font boyutu
        tk.Label(dialog, text="Font Boyutu:", bg="#F5F6FA").pack(anchor='w', padx=20)
        size_var = tk.IntVar(value=48)
        size_spin = ttk.Spinbox(dialog, from_=12, to=100, textvariable=size_var, width=10)
        size_spin.pack(padx=20, pady=5, anchor='w')
        
        # Şeffaflık
        tk.Label(dialog, text="Şeffaflık (0.0 - 1.0):", bg="#F5F6FA").pack(anchor='w', padx=20)
        alpha_var = tk.DoubleVar(value=0.3)
        alpha_entry = tk.Entry(dialog, textvariable=alpha_var, width=10)
        alpha_entry.pack(padx=20, pady=5, anchor='w')
        
        # Tüm sayfalara uygula
        all_pages_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Tüm sayfalara uygula", variable=all_pages_var).pack(anchor='w', padx=20, pady=5)
        
        def save_watermark():
            text = text_entry.get()
            if not text:
                messagebox.showwarning("Uyarı", "Lütfen filigran metni girin!")
                return
            
            pages = list(range(1, self.edit_data['total_pages'] + 1)) if all_pages_var.get() else [self.edit_data['current_page']]
            
            for page_num in pages:
                edit_info = {
                    'type': 'watermark',
                    'page': page_num,
                    'params': {
                        'text': text,
                        'position': pos_var.get(),
                        'size': size_var.get(),
                        'alpha': alpha_var.get()
                    }
                }
                self.edit_data['edits'].append(edit_info)
            
            self.edit_status.config(text=f"Filigran eklendi ({len(pages)} sayfa)")
            dialog.destroy()
            messagebox.showinfo("Başarılı", f"Filigran {len(pages)} sayfaya eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
        
        ttk.Button(dialog, text="Ekle", command=save_watermark).pack(pady=20)
    
    def edit_rotate_page(self):
        """Sayfayı 90 derece döndürür"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        edit_info = {
            'type': 'rotate',
            'page': self.edit_data['current_page'],
            'params': {'angle': 90}
        }
        self.edit_data['edits'].append(edit_info)
        self.edit_status.config(text=f"Sayfa {self.edit_data['current_page']} döndürme eklendi")
        messagebox.showinfo("Başarılı", "Sayfa döndürme eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
    
    def edit_delete_page(self):
        """Sayfayı silme işareti koyar"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        result = messagebox.askyesno("Onay", f"Sayfa {self.edit_data['current_page']} silinsin mi?")
        if result:
            edit_info = {
                'type': 'delete_page',
                'page': self.edit_data['current_page'],
                'params': {}
            }
            self.edit_data['edits'].append(edit_info)
            self.edit_status.config(text=f"Sayfa {self.edit_data['current_page']} silme eklendi")
            messagebox.showinfo("Başarılı", "Sayfa silme eklendi! Kaydetmek için 'Kaydet' butonuna basın.")
    
    def edit_show_edits(self):
        """Yapılan düzenlemeleri listeler"""
        if not self.edit_data['edits']:
            messagebox.showinfo("Bilgi", "Henüz düzenleme yapılmadı.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Düzenleme Listesi")
        dialog.geometry("600x400")
        dialog.configure(bg="#F5F6FA")
        dialog.transient(self.root)
        
        tk.Label(dialog, text="Yapılan Düzenlemeler", font=('Segoe UI', 14, 'bold'), bg="#F5F6FA").pack(pady=10)
        
        # Liste
        frame = tk.Frame(dialog, bg="white")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = ttk.Scrollbar(frame)
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=('Courier', 9))
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Düzenlemeleri listele
        for i, edit in enumerate(self.edit_data['edits']):
            edit_type = edit['type']
            page = edit['page']
            
            if edit_type == 'text':
                text = edit['params']['text'][:30]
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: Metin '{text}...'")
            elif edit_type == 'rectangle':
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: Dikdörtgen")
            elif edit_type == 'circle':
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: Daire")
            elif edit_type == 'line':
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: Çizgi")
            elif edit_type == 'image':
                img_name = Path(edit['params']['image_path']).name
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: Resim '{img_name}'")
            elif edit_type == 'watermark':
                text = edit['params']['text']
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: Filigran '{text}'")
            elif edit_type == 'rotate':
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: Döndürme")
            elif edit_type == 'delete_page':
                listbox.insert(tk.END, f"{i+1}. Sayfa {page}: SAYFA SİLME")
        
        def delete_selected():
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if messagebox.askyesno("Onay", "Seçili düzenlemeyi sil?"):
                del self.edit_data['edits'][idx]
                listbox.delete(idx)
                self.edit_status.config(text="Düzenleme silindi")
        
        ttk.Button(dialog, text="Seçili Düzenlemeyi Sil", command=delete_selected).pack(pady=10)
        ttk.Button(dialog, text="Kapat", command=dialog.destroy).pack()
    
    def edit_clear_all(self):
        """Tüm düzenlemeleri temizler"""
        if not self.edit_data['edits']:
            messagebox.showinfo("Bilgi", "Zaten düzenleme yok.")
            return
        
        result = messagebox.askyesno("Onay", "Tüm düzenlemeler temizlensin mi?")
        if result:
            self.edit_data['edits'] = []
            self.edit_status.config(text="Tüm düzenlemeler temizlendi")
            messagebox.showinfo("Başarılı", "Tüm düzenlemeler temizlendi.")
    
    def edit_save_pdf(self):
        """Düzenlenmiş PDF'i kaydeder"""
        if not self.edit_data['path']:
            messagebox.showwarning("Uyarı", "Önce bir PDF dosyası açın!")
            return
        
        if not self.edit_data['edits']:
            messagebox.showwarning("Uyarı", "Henüz düzenleme yapılmadı!")
            return
        
        # Kayıt konumu seç
        out_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Dosyaları", "*.pdf")],
            initialfile=Path(self.edit_data['name']).stem + "_edited.pdf",
            title="Düzenlenmiş PDF'i Kaydet"
        )
        if not out_path:
            return
        
        def run():
            self.edit_status.config(text="PDF işleniyor...")
            self.root.update_idletasks()
            
            try:
                # Orijinal PDF'i oku
                reader = PdfReader(self.edit_data['path'])
                writer = PdfWriter()
                
                # Silinecek sayfaları tespit et
                pages_to_delete = set()
                for edit in self.edit_data['edits']:
                    if edit['type'] == 'delete_page':
                        pages_to_delete.add(edit['page'])
                
                # Her sayfa için overlay oluştur ve uygula
                for page_num in range(1, len(reader.pages) + 1):
                    # Sayfa silinecekse atla
                    if page_num in pages_to_delete:
                        continue
                    
                    page = reader.pages[page_num - 1]
                    
                    # Bu sayfaya ait düzenlemeleri bul
                    page_edits = [e for e in self.edit_data['edits'] 
                                 if e['page'] == page_num and e['type'] != 'delete_page']
                    
                    if page_edits:
                        # Overlay PDF oluştur
                        overlay_path = self._create_overlay_pdf(page, page_edits)
                        
                        if overlay_path and os.path.exists(overlay_path):
                            # Overlay'ı sayfaya ekle
                            overlay_reader = PdfReader(overlay_path)
                            overlay_page = overlay_reader.pages[0]
                            page.merge_page(overlay_page)
                            
                            # Geçici dosyayı sil
                            try:
                                os.remove(overlay_path)
                            except:
                                pass
                    
                    # Rotasyon varsa uygula
                    rotate_edits = [e for e in self.edit_data['edits'] 
                                   if e['page'] == page_num and e['type'] == 'rotate']
                    for _ in rotate_edits:
                        page.rotate(90)
                    
                    writer.add_page(page)
                
                # PDF'i kaydet
                with open(out_path, 'wb') as fp:
                    writer.write(fp)
                
                self.edit_status.config(text=f"PDF kaydedildi: {Path(out_path).name}")
                messagebox.showinfo("Başarılı", f"Düzenlenmiş PDF kaydedildi:\n{out_path}")
                
            except Exception as e:
                self.edit_status.config(text=f"Hata: {e}")
                messagebox.showerror("Hata", f"PDF kaydedilemedi:\n{e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def _create_overlay_pdf(self, original_page, edits):
        """Düzenlemeleri içeren overlay PDF oluşturur"""
        try:
            # Geçici dosya oluştur
            fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            
            # Sayfa boyutlarını al
            page_width = float(original_page.mediabox.width)
            page_height = float(original_page.mediabox.height)
            
            print(f"[DEBUG] Sayfa boyutu: {page_width} x {page_height}")
            
            # Canvas oluştur
            c = canvas.Canvas(temp_path, pagesize=(page_width, page_height))
            
            # Renk dönüştürme fonksiyonu
            def get_color(color_name):
                color_map = {
                    'black': rl_colors.black,
                    'white': rl_colors.white,
                    'red': rl_colors.red,
                    'blue': rl_colors.blue,
                    'green': rl_colors.green,
                    'yellow': rl_colors.yellow,
                    'none': None
                }
                return color_map.get(color_name, rl_colors.black)
            
            # Düzenlemeleri uygula
            for edit in edits:
                edit_type = edit['type']
                params = edit['params']
                
                print(f"[DEBUG] İşlem: {edit_type}, Parametreler: {params}")
                
                if edit_type == 'text':
                    # Y koordinatını PDF koordinat sistemine çevir (üstten alta)
                    # NOT: Kullanıcı üst sol köşeden koordinat veriyorsa
                    y_pdf = page_height - params['y']
                    
                    c.setFillColor(get_color(params['color']))
                    c.setFont("Helvetica", params['size'])
                    c.drawString(params['x'], y_pdf, params['text'])
                    print(f"[DEBUG] Metin çizildi: {params['text']} at ({params['x']}, {y_pdf})")
                
                elif edit_type == 'rectangle':
                    fill = get_color(params['fill'])
                    stroke = get_color(params['stroke'])
                    
                    # Y koordinatını çevir
                    y_pdf = page_height - params['y'] - params['height']
                    
                    # Renkleri ayarla
                    if fill and fill != 'none':
                        c.setFillColor(fill)
                    else:
                        fill = None
                        
                    if stroke and stroke != 'none':
                        c.setStrokeColor(stroke)
                    else:
                        stroke = None
                    
                    # Çiz
                    if fill and stroke:
                        c.rect(params['x'], y_pdf, params['width'], params['height'], fill=1, stroke=1)
                    elif fill:
                        c.rect(params['x'], y_pdf, params['width'], params['height'], fill=1, stroke=0)
                    elif stroke:
                        c.rect(params['x'], y_pdf, params['width'], params['height'], fill=0, stroke=1)
                    
                    print(f"[DEBUG] Dikdörtgen çizildi at ({params['x']}, {y_pdf})")
                
                elif edit_type == 'circle':
                    fill = get_color(params['fill'])
                    stroke = get_color(params['stroke'])
                    
                    # Y koordinatını çevir
                    y_pdf = page_height - params['y']
                    
                    if fill and fill != 'none':
                        c.setFillColor(fill)
                    else:
                        fill = None
                        
                    if stroke and stroke != 'none':
                        c.setStrokeColor(stroke)
                    else:
                        stroke = None
                    
                    if fill and stroke:
                        c.circle(params['x'], y_pdf, params['radius'], fill=1, stroke=1)
                    elif fill:
                        c.circle(params['x'], y_pdf, params['radius'], fill=1, stroke=0)
                    elif stroke:
                        c.circle(params['x'], y_pdf, params['radius'], fill=0, stroke=1)
                    
                    print(f"[DEBUG] Daire çizildi at ({params['x']}, {y_pdf})")
                
                elif edit_type == 'line':
                    # Her iki Y koordinatını da çevir
                    y1_pdf = page_height - params['y1']
                    y2_pdf = page_height - params['y2']
                    
                    c.setStrokeColor(get_color(params['color']))
                    c.setLineWidth(params['width'])
                    c.line(params['x1'], y1_pdf, params['x2'], y2_pdf)
                    print(f"[DEBUG] Çizgi çizildi: ({params['x1']}, {y1_pdf}) - ({params['x2']}, {y2_pdf})")
                
                elif edit_type == 'image':
                    if os.path.exists(params['image_path']):
                        # Y koordinatını çevir
                        y_pdf = page_height - params['y'] - params['height']
                        
                        c.drawImage(params['image_path'], params['x'], y_pdf, 
                                   width=params['width'], height=params['height'], 
                                   mask='auto', preserveAspectRatio=True)
                        print(f"[DEBUG] Resim eklendi at ({params['x']}, {y_pdf})")
                
                elif edit_type == 'watermark':
                    c.saveState()
                    c.setFillColorRGB(0.5, 0.5, 0.5, alpha=params['alpha'])
                    c.setFont("Helvetica-Bold", params['size'])
                    
                    if params['position'] == 'center':
                        # Merkeze yerleştir
                        text_width = c.stringWidth(params['text'], "Helvetica-Bold", params['size'])
                        x = (page_width - text_width) / 2
                        y = page_height / 2
                        c.drawString(x, y, params['text'])
                    elif params['position'] == 'diagonal':
                        # Köşegen yerleştir
                        c.translate(page_width / 2, page_height / 2)
                        c.rotate(45)
                        text_width = c.stringWidth(params['text'], "Helvetica-Bold", params['size'])
                        c.drawString(-text_width / 2, 0, params['text'])
                    
                    c.restoreState()
                    print(f"[DEBUG] Filigran eklendi")
            
            # Canvas'ı kaydet
            c.save()
            print(f"[DEBUG] Overlay PDF oluşturuldu: {temp_path}")
            return temp_path
            
        except Exception as e:
            print(f"Overlay oluşturma hatası: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFToolboxApp(root)
    root.mainloop()