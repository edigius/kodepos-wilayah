# Kode Pos & Wilayah

> **Live Demo & Pencarian Interaktif:** [https://cekkodepos.my.id](https://cekkodepos.my.id)

Direktori kode pos seluruh Indonesia: 38 provinsi, 514 kabupaten/kota,
7.285 kecamatan, dan 83.762 desa/kelurahan.

Situs live: https://kodepos-wilayah.pages.dev
Domain: https://cekkodepos.my.id

## Data

Struktur wilayah (nama dan kode wilayah) mengikuti Kepmendagri
No. 300.2.2-2430 Tahun 2025, melalui dataset terbuka
[wilayah-indonesia](https://github.com/ANGGATYASIA/wilayah-indonesia)
(lisensi MIT), yang disertakan di `wilayah-indonesia/` tanpa `.git`.

Kode pos berasal dari panen resmi situs Pos Indonesia
(`kodepos.posindonesia.co.id`, 96.006 baris, 514 kabupaten/kota).
Bila sumber resmi dan dataset pembanding berbeda, sumber resmi yang
dipakai. Hasilnya: 80.576 desa (96,2%) membawa kode resmi, 181 desa
ditampilkan jujur sebagai "Belum tersedia" — kode pos tidak pernah
dibuat-buat.

Sebagai pembanding, dataset turunan nomor.net (erlange,
`Kodepos-Wilayah-Indonesia`) hanya cocok 53,3% dengan sumber resmi.
Dataset pembanding tidak disertakan di repo ini; lihat `crosscheck.py`.

## Isi repo

- `generate.py` — membangkitkan seluruh situs statis (7.843 halaman).
- `harvest3.py`, `harvest.py`, `harvest2.py`, `retry_zero.py` — panen
  kode pos resmi per kabupaten/kota.
- `harvest/` — hasil panen mentah resmi per kabupaten/kota (522 berkas).
- `join.py` — menggabungkan struktur wilayah dengan kode resmi.
- `official_overlay.json` — peta kode wilayah desa -> kode pos resmi.
- `join_stats.json` — statistik hasil penggabungan.
- `crosscheck.py` — perbandingan sumber resmi vs dataset pembanding.
- `validate.py`, `validate_site.py` — pemeriksaan data dan situs hasil.
- `deploy_chunked.py` — deploy ke Cloudflare Pages (unggah bertahap).
- `og_image.py` — pembangkit gambar pratinjau `og-image.png`.
- `wilayah-indonesia/` — dataset struktur wilayah (tanpa `.git`).
- `assets/` — `styles.css`, `search.js`, dan `favicon.svg` yang disalin
  ke hasil bangkitan (tidak dihasilkan oleh `generate.py`).
- `DATA.md` — dokumentasi berkas JSON statis yang dilayani situs
  (`/data/wilayah/` dan `/data/kodepos/`), gratis dipakai dengan
  atribusi; bukan API.

Halaman HTML hasil bangkitan tidak disimpan di repo ini; itu keluaran
build yang di-deploy langsung ke Cloudflare Pages.

## Membangkitkan ulang

```sh
KD_DIR=. OUT_DIR=./output python3 generate.py
cp assets/* ./output/
python3 validate_site.py
```

Lalu deploy isi `./output/` ke Cloudflare Pages, misalnya dengan
`deploy_chunked.py`. Nilai `BASE_URL` di `generate.py` adalah alamat
kanonis situs; ubah bila domain berubah.

Ikon biner (`favicon.ico`, `apple-touch-icon.png`) dibuat dari
`favicon.svg` dengan PIL dan tidak disimpan di repo ini.
