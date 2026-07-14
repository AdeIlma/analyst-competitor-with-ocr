"""
Streamlit app - ekstrak nama produk + harga dengan UPLOAD FOLDER (via ZIP).
Zip folder indukmu, upload, app membongkar & membaca strukturnya:
    DATA.zip  ->  DATA/ Nama Toko/ Kategori/ *.png
                        (nama_toko)  (category)

Jalankan:
    streamlit run app_folder.py

Bisa juga di-deploy ke Streamlit Cloud.

Install:
    pip install streamlit rapidocr-onnxruntime pillow pandas openpyxl
"""

import re
import io
import os
import time
import zipfile
import tempfile
from collections import Counter
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

TARGET_WIDTH = 1600
IMG_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}

# ---------------------------------------------------------------- OCR & aturan

@st.cache_resource(show_spinner="Menyiapkan OCR (sekali di awal)...")
def get_engine():
    return RapidOCR()


PRICE_RE = re.compile(r'^\d{1,3}(?:\.\d{3})+$')
NOISE = {'tambah', 'menu', 'masuk', 'beranda', 'rekomendasi',
         'gofood', 'gofood hemat', 'home'}

# Tag umur ("21+", "[18+]") dan kata generik disclaimer ("minuman beralkohol", atau
# variannya yg kepisah spasi jadi "minuman ber alkohol") -> ini yang dibuang.
# Volume/kadar alkohol (mis. "620ml", "19%") SENGAJA TIDAK dibuang -> tetap
# menempel jadi bagian dari nama produk.
AGE_FIND_RE = re.compile(r'\[?\b(?:18|21)\b\s*\+?\]?', re.IGNORECASE)
GENERIC_RE = re.compile(r'\b(?:minuman|ber|beralkohol|alkohol)\b', re.IGNORECASE)


def clean_disclaimer(text, age_match):
    """Buang tag umur & kata generik disclaimer dari suatu baris teks. Volume/kadar
    alkohol yang mungkin ada di baris yang sama TIDAK ikut dibuang, jadi kalau baris
    itu sebenarnya cuma disclaimer (mis. '21+ minuman beralkohol'), hasilnya jadi
    kosong; kalau ada volume/nama asli (mis. '700ml. 21+ minuman beralkohol' atau
    'ANGGUR MERAH GOLD 19% 620ML'), sisanya tetap ada."""
    cleaned = text
    if age_match:
        cleaned = cleaned.replace(age_match.group(), ' ')
    cleaned = GENERIC_RE.sub(' ', cleaned)
    cleaned = re.sub(r'[.,;:]+', ' ', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


def is_price(text):
    return bool(PRICE_RE.match(text.strip()))


def is_name_line(text):
    t = text.strip()
    low = t.lower()
    if len(t) < 3 or is_price(t):
        return False
    if low in NOISE:
        return False
    if low == 'abs' or low.startswith('lokal produk'):
        return False
    return any(c.isalpha() for c in t)


def center(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs) / 4, sum(ys) / 4


def _resize(path):
    img = Image.open(path).convert('RGB')
    w, h = img.size
    if w > TARGET_WIDTH:
        img = img.resize((TARGET_WIDTH, int(h * TARGET_WIDTH / w)))
    return np.array(img)


@st.cache_data(show_spinner=False)
def extract_path(path, col_tol, row_tol):
    engine = get_engine()
    result, _ = engine(_resize(path))
    if not result:
        return []
    items = [{'text': t.strip(), **dict(zip(('cx', 'cy'), center(b)))}
             for b, t, s in result]

    prices, names = [], []
    for it in items:
        text = it['text']
        if is_price(text):
            prices.append(it)
            continue
        age_match = AGE_FIND_RE.search(text)
        cleaned = clean_disclaimer(text, age_match)
        if not cleaned:
            continue  # murni disclaimer/tag umur (mis. "21+", "Minuman ber alkohol") -> buang total
        if is_name_line(cleaned):
            names.append({'text': cleaned, 'cx': it['cx'], 'cy': it['cy']})

    # Teks yang MUNCUL BERULANG di banyak kartu dalam satu gambar (mis. "Best
    # Seller", "Rekomendasi") hampir pasti label generik/template, bukan nama
    # produk -> deteksi otomatis & buang. Teks yang MENGANDUNG ANGKA (mis. "620ml",
    # "19%") dikecualikan dari pengecekan ini, karena volume/kadar alkohol yang
    # sama wajar muncul di banyak produk berbeda dan tetap harus dipertahankan.
    name_counts = Counter(n['text'].lower() for n in names
                          if not any(ch.isdigit() for ch in n['text']))
    dynamic_noise = {t for t, c in name_counts.items() if c >= 2}

    hasil = []
    for p in prices:
        # Nama HANYA diambil dari teks DI ATAS harga (cy lebih kecil), supaya
        # badge/keterangan di BAWAH harga (mis. "Dapat dicustom" sebelum tombol
        # Tambah) tidak ikut ke-gabung ke nama.
        candidates = [n for n in names
                      if abs(n['cx'] - p['cx']) < col_tol
                      and 0 <= p['cy'] - n['cy'] < row_tol]
        candidates.sort(key=lambda n: n['cy'])
        chosen = [n for n in candidates if n['text'].lower() not in dynamic_noise]
        nama = ' '.join(n['text'] for n in chosen) if chosen else None
        hasil.append({'nama': nama, 'harga': int(p['text'].replace('.', ''))})
    return hasil


# ---------------------------------------------------------------- Folder / ZIP

def _natkey(s):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', s)]


def _valid_dirs(folder):
    return sorted((e for e in os.listdir(folder)
                   if os.path.isdir(os.path.join(folder, e))
                   and not e.startswith('.') and e != '__MACOSX'), key=_natkey)


def images_in(folder):
    files = sorted((f for f in os.listdir(folder)
                    if not f.startswith('.')
                    and os.path.splitext(f)[1].lower() in IMG_EXT), key=_natkey)
    return [os.path.join(folder, f) for f in files]


@st.cache_data(show_spinner="Membongkar ZIP...")
def unzip(zip_bytes):
    tmp = tempfile.mkdtemp()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        z.extractall(tmp)
    # Turun melewati folder pembungkus (mis. Mac membungkus jadi "DATA/...")
    root = tmp
    while True:
        dirs = _valid_dirs(root)
        if len(dirs) == 1 and not images_in(root):
            root = os.path.join(root, dirs[0])
        else:
            break
    return root


def scan(root):
    """Daftar job: (nama_toko, category, path_gambar)."""
    jobs = []
    for store in _valid_dirs(root):
        sp = os.path.join(root, store)
        for img in images_in(sp):                       # gambar tanpa kategori
            jobs.append((store, '(tanpa kategori)', img))
        for cat in _valid_dirs(sp):                     # subfolder = kategori
            for img in images_in(os.path.join(sp, cat)):
                jobs.append((store, cat, img))
    return jobs


# ---------------------------------------------------------------- Tampilan

st.set_page_config(page_title="Ekstrak Produk & Harga (Upload Folder)",
                   page_icon="🧾", layout="wide")
st.title("🧾 Ekstrak Nama Produk & Harga — Upload Folder (ZIP)")
st.caption("Zip folder indukmu, lalu upload di sini. Nama subfolder = toko, "
           "sub-subfolder = kategori. Struktur folder tetap terbaca.")

with st.expander("ℹ️ Cara menyiapkan ZIP"):
    st.markdown(
        "1. Susun folder: `DATA/ Nama Toko/ Kategori/ *.png`\n"
        "2. **Mac**: klik kanan folder `DATA` → *Compress*.  "
        "**Windows**: klik kanan → *Send to* → *Compressed (zipped) folder*.\n"
        "3. Upload file `DATA.zip` di bawah.")

with st.sidebar:
    st.subheader("Setelan pairing")
    st.caption("Geser kalau nama & harga ketuker / kepotong.")
    col_tol = st.slider("COL_TOL (toleransi kolom, px)", 40, 400, 150, 10)
    row_tol = st.slider("ROW_TOL (toleransi baris, px)", 40, 300, 90, 10)

up = st.file_uploader("Upload folder (dalam bentuk .zip)", type=['zip'])

jobs = []
if up:
    root = unzip(up.getvalue())
    jobs = scan(root)
    if not jobs:
        st.warning("Tidak ada gambar terdeteksi. Pastikan struktur "
                   "folder/kategori di dalam ZIP sudah benar.")
    else:
        prev = (pd.DataFrame(jobs, columns=['nama_toko', 'category', 'path'])
                .groupby(['nama_toko', 'category'])
                .size().reset_index(name='jumlah_gambar'))
        st.success(f"Ditemukan {len(jobs)} gambar. Periksa dulu strukturnya:")
        st.dataframe(prev, use_container_width=True, hide_index=True)

if jobs and st.button("🚀 Proses semua", type="primary"):
    rows, done = [], 0
    t0 = time.time()
    prog = st.progress(0.0, text="Memproses...")
    for toko, kategori, path in jobs:
        for r in extract_path(path, col_tol, row_tol):
            rows.append({'nama_toko': toko, 'category': kategori,
                         'sumber': os.path.basename(path),
                         'nama': r['nama'], 'harga': r['harga']})
        done += 1
        prog.progress(done / len(jobs), text=f"Memproses {done}/{len(jobs)} gambar...")
    prog.empty()
    st.session_state['hasil_df'] = pd.DataFrame(
        rows, columns=['nama_toko', 'category', 'sumber', 'nama', 'harga'])
    st.session_state['durasi'] = time.time() - t0

# ------- Hasil -------
if 'hasil_df' in st.session_state and not st.session_state['hasil_df'].empty:
    df = st.session_state['hasil_df']
    st.success(f"Terdeteksi {len(df)} produk dari {df['nama_toko'].nunique()} toko "
               f"& {df['category'].nunique()} kategori dalam "
               f"{st.session_state.get('durasi', 0):.1f} detik. "
               "Perbaiki di tabel bila ada yang meleset:")

    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True,
                            key="editor")

    xlsx_buf = io.BytesIO()
    with pd.ExcelWriter(xlsx_buf, engine='openpyxl') as writer:
        edited.to_excel(writer, index=False, sheet_name='Produk')

    st.download_button("⬇️ Download Excel", xlsx_buf.getvalue(),
                       file_name="hasil_produk.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
