# 🧾 Ekstrak Nama Produk & Harga dari Screenshot

Aplikasi untuk mengekstrak **nama produk** dan **harga** dari screenshot menu
(GoFood / halaman merchant) secara otomatis, lalu mengunduhnya ke **CSV / Excel**.

Bekerja dengan **OCR + aturan (rule-based parsing)** — tanpa perlu melatih model
deep learning sendiri. Cocok karena screenshot menu adalah teks render layar yang
bersih dan konsisten.

---

## ✨ Fitur

- **Multi-toko**: tentukan jumlah toko, tiap toko punya nama & uploader sendiri.
- **Upload banyak gambar** sekaligus per toko (drag & drop).
- **Tabel hasil bisa diedit** langsung sebelum diunduh (perbaiki yang meleset).
- **Download CSV & Excel** dalam sekali klik.
- **Slider tuning** (`COL_TOL` / `ROW_TOL`) untuk menyetel pasangan nama–harga
  tanpa mengubah kode.
- Mesin OCR **RapidOCR (ONNXRuntime)** — ringan & cepat di CPU.

---

## 📦 Kebutuhan

Semua ada di `requirements.txt`:

```
streamlit
rapidocr-onnxruntime
pillow
pandas
openpyxl
```

Butuh **Python 3.9+**.

---

## 🚀 Instalasi & Menjalankan

```bash
# (disarankan) buat environment terpisah
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# install dependency
pip install -r requirements.txt

# jalankan
streamlit run app.py
```

Aplikasi otomatis terbuka di browser (biasanya http://localhost:8501).

---

## 🖱️ Cara Pakai

1. Atur **Jumlah toko** di bagian atas.
2. Untuk tiap toko: isi **Nama toko** dan **upload** screenshot menu toko tersebut.
   Karena uploader-nya terpisah per toko, gambar tidak akan tertukar.
3. Klik **🚀 Proses semua toko**.
4. Periksa tabel hasil — perbaiki nama/harga yang salah langsung di tabel bila perlu.
5. Klik **Download CSV** atau **Download Excel**.

---

## 📄 Format Output

| Kolom       | Keterangan                                  |
|-------------|---------------------------------------------|
| `nama_toko` | Nama toko (dari kotak input tiap blok)      |
| `sumber`    | Nama file screenshot asal data              |
| `nama`      | Nama produk hasil OCR                        |
| `harga`     | Harga sebagai angka bulat (mis. `72000`)    |

---

## ⚙️ Setelan (di sidebar & kode)

- **`COL_TOL`** (px) — toleransi jarak horizontal; seberapa jauh teks dianggap
  "sekolom" dengan harga. Naikkan bila nama tidak terpasang; turunkan bila
  nama produk tetangga ikut kegabung.
- **`ROW_TOL`** (px) — toleransi jarak vertikal; seberapa jauh teks dianggap
  masih satu kartu dengan harga.
- **`TARGET_WIDTH`** (di `app.py`, default `1600`) — gambar diperkecil ke lebar
  ini sebelum OCR agar lebih cepat. Naikkan bila teks kecil sulit terbaca
  (lebih akurat tapi lebih lambat).

---

## 🧠 Cara Kerja Singkat

1. **OCR** membaca semua teks beserta koordinatnya (bounding box).
2. **Deteksi harga** lewat regex angka bertitik ribuan (mis. `72.000`, `88.500`),
   sekaligus menyaring angka yang *bukan* harga: volume (`620ml`), kadar alkohol
   (`14,7%`), dan penanda umur (`21+`).
3. **Pasangkan nama–harga** berdasarkan kedekatan posisi: untuk tiap harga,
   diambil teks nama yang paling dekat di kolom yang sama (bisa di atas maupun
   di bawah harga, sehingga tahan terhadap layout yang berbeda-beda).

---

## ⚠️ Batasan & Tips

- **Akurasi tidak 100%.** OCR & pairing bisa meleset, terutama pada layout yang
  tidak biasa atau nama yang sangat panjang. Karena itu tabelnya dibuat
  **bisa diedit** sebelum diunduh.
- Harga diasumsikan berformat **titik ribuan tanpa "Rp"** (mis. `72.000`).
  Jika sumbermu memakai format lain (mis. ada `Rp`), sesuaikan `PRICE_RE`.
- Jika **sumbernya adalah halaman web** dan kamu bisa mengaksesnya langsung,
  mengambil data dari HTML/DOM jauh lebih akurat daripada OCR pada screenshot.
- **Error NumPy** (`Failed to initialize NumPy`) biasanya muncul di setup lama
  yang memakai PyTorch/EasyOCR. Versi ini memakai RapidOCR (tanpa PyTorch)
  sehingga umumnya aman; bila tetap muncul, coba `pip install "numpy<2"`.

---

## 🗂️ Struktur File

```
.
├── app.py             # Aplikasi Streamlit (multi-toko)
├── requirements.txt   # Daftar dependency
└── README.md          # Dokumentasi ini
```
