"""
Streamlit app: ekstrak nama produk + harga dari screenshot menu.
Struktur: Toko -> beberapa Category -> gambar per kategori.
Mesin OCR: RapidOCR (ONNXRuntime) - cepat di CPU.

Jalankan:
    streamlit run app.py
"""

import re
import io
import time
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

TARGET_WIDTH = 1600   # perkecil gambar sebelum OCR -> lebih cepat & skala seragam

# ---------------------------------------------------------------- OCR & aturan

@st.cache_resource(show_spinner="Menyiapkan OCR (sekali di awal)...")
def get_engine():
    return RapidOCR()


PRICE_RE = re.compile(r'^\d{1,3}(?:\.\d{3})+$')            # 72.000, 88.500, 495.000
VOLUME_RE = re.compile(r'^\d+\s*m[li]$', re.IGNORECASE)   # 620ml, 750Ml, 360MI
AGE_RE = re.compile(r'^\[?(?:18|21)\+?\]?$')              # 21+, [21+], 18+
NOISE = {'tambah', 'menu', 'masuk', 'beranda', 'rekomendasi',
         'gofood', 'gofood hemat', 'home'}


def is_price(text):
    return bool(PRICE_RE.match(text.strip()))


def is_name_line(text):
    t = text.strip()
    low = t.lower()
    if len(t) < 3 or is_price(t):
        return False
    if low in NOISE or AGE_RE.match(t) or VOLUME_RE.match(t):
        return False
    if low.startswith('abs') or low.startswith('lokal produk'):
        return False
    return any(c.isalpha() for c in t)


def center(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs) / 4, sum(ys) / 4


def _resize(img_bytes):
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    w, h = img.size
    if w > TARGET_WIDTH:
        img = img.resize((TARGET_WIDTH, int(h * TARGET_WIDTH / w)))
    return np.array(img)


@st.cache_data(show_spinner=False)
def extract_from_bytes(img_bytes, col_tol, row_tol):
    engine = get_engine()
    arr = _resize(img_bytes)
    result, _ = engine(arr)
    if not result:
        return []

    items = [{'text': text.strip(), **dict(zip(('cx', 'cy'), center(box)))}
             for box, text, score in result]
    prices = [it for it in items if is_price(it['text'])]
    names = [it for it in items if is_name_line(it['text'])]

    hasil = []
    for p in prices:
        near = [n for n in names
                if abs(n['cx'] - p['cx']) < col_tol
                and abs(n['cy'] - p['cy']) < row_tol]
        near.sort(key=lambda n: n['cy'])
        nama = ' '.join(n['text'] for n in near) if near else None
        hasil.append({'nama': nama, 'harga': int(p['text'].replace('.', ''))})
    return hasil


# ---------------------------------------------------------------- Tampilan

st.set_page_config(page_title="Ekstrak Produk & Harga", page_icon="🧾", layout="wide")
st.title("🧾 Ekstrak Nama Produk & Harga (Multi-Toko & Kategori)")
st.caption("Tiap toko bisa punya beberapa kategori, dan tiap kategori punya "
           "upload gambar sendiri. Hasil digabung ke satu file Excel.")

with st.sidebar:
    st.subheader("Setelan pairing")
    st.caption("Geser kalau nama & harga ketuker / kepotong.")
    col_tol = st.slider("COL_TOL (toleransi kolom, px)", 40, 400, 150, 10)
    row_tol = st.slider("ROW_TOL (toleransi baris, px)", 40, 300, 90, 10)

jumlah_toko = st.number_input("Jumlah toko", min_value=1, max_value=30, value=1, step=1)

# Struktur input: Toko -> beberapa Category -> uploader
toko_inputs = []
for i in range(int(jumlah_toko)):
    label = st.session_state.get(f"nama_{i}") or f"Toko {i + 1}"
    with st.expander(f"📍 {label}", expanded=(i == 0)):
        nama = st.text_input("Nama toko", key=f"nama_{i}",
                             placeholder="mis. Sobat Minum Madiun")
        jumlah_kat = st.number_input(
            "Jumlah kategori di toko ini", min_value=1, max_value=30,
            value=1, step=1, key=f"jkat_{i}")

        kategori_list = []
        for j in range(int(jumlah_kat)):
            with st.container(border=True):
                kat = st.text_input("Category", key=f"kat_{i}_{j}",
                                    placeholder="mis. Anggur, Bir, Wine")
                files = st.file_uploader(
                    "Upload screenshot untuk kategori ini (boleh banyak)",
                    type=['png', 'jpg', 'jpeg', 'webp', 'bmp'],
                    accept_multiple_files=True, key=f"files_{i}_{j}",
                )
                if files:
                    st.caption(f"{len(files)} gambar siap diproses.")
                kategori_list.append((kat, files))

        toko_inputs.append((nama, kategori_list))

# ------- Tombol proses -------
if st.button("🚀 Proses semua", type="primary"):
    total = sum(len(f) for _, kats in toko_inputs for _, f in kats if f)
    if total == 0:
        st.warning("Belum ada gambar yang diupload.")
        st.session_state.pop('hasil_df', None)
    else:
        rows, done = [], 0
        t0 = time.time()
        prog = st.progress(0.0, text="Memproses...")
        for i, (nama, kats) in enumerate(toko_inputs):
            toko = (nama or '').strip() or f"Toko {i + 1}"
            for j, (kat, files) in enumerate(kats):
                if not files:
                    continue
                kategori = (kat or '').strip() or f"Kategori {j + 1}"
                for f in files:
                    for r in extract_from_bytes(f.getvalue(), col_tol, row_tol):
                        rows.append({'nama_toko': toko, 'category': kategori,
                                     'sumber': f.name, 'nama': r['nama'],
                                     'harga': r['harga']})
                    done += 1
                    prog.progress(done / total,
                                  text=f"Memproses {done}/{total} gambar...")
        prog.empty()
        st.session_state['hasil_df'] = pd.DataFrame(
            rows, columns=['nama_toko', 'category', 'sumber', 'nama', 'harga'])
        st.session_state['durasi'] = time.time() - t0

# ------- Hasil (di luar blok tombol supaya tetap tampil saat tabel diedit) -------
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
