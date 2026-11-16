# Data JSON statis — Kode Pos & Wilayah

Berkas JSON yang melayani pencarian di
[https://cekkodepos.my.id](https://cekkodepos.my.id) tersedia bebas
untuk dipakai siapa saja, dengan atribusi (lihat di bawah).

Ini **berkas statis, bukan API**: tidak ada endpoint kueri, tidak ada
parameter, tidak ada paginasi, dan tidak ada batas laju (rate limit)
atau SLA yang dijanjikan. Cukup unduh berkasnya lewat HTTPS biasa dan
pakai isinya. Format berkas dapat berubah saat situs dibangun ulang;
jangan mengandalkannya sebagai kontrak API.

Cakupan: 38 provinsi, 514 kabupaten/kota, 7.285 kecamatan, dan 83.762
desa/kelurahan. Total seluruh berkas ±12,4 MB.

## Berkas

Semua berkas dilayani dari domain kanonis `https://cekkodepos.my.id`
dan dihasilkan oleh `generate.py` (fungsi `write_indexes`) setiap kali
situs dibangun ulang.

### 1. Indeks wilayah per provinsi — `/data/wilayah/<KK>.json`

38 berkas, satu per provinsi. `<KK>` adalah 2 digit pertama kode
wilayah Kemendagri provinsi. Total ±4,2 MB.

```json
{
  "p": "Aceh",
  "d": [["11.01.01", "Bakongan", "Kabupaten Aceh Selatan", "bakongan-aceh-selatan"]],
  "v": [["Darul Ikhsan", 0, "23773", 0, "11.01.01.2015"]]
}
```

- `p`: nama provinsi.
- `d`: daftar kecamatan, urut kode wilayah. Tiap entri:
  `[kode_kecamatan, nama_kecamatan, nama_kabupaten_kota, slug]`.
  `slug` dipakai di URL halaman kecamatan:
  `/kecamatan/<slug>`.
- `v`: daftar desa/kelurahan, urut kode wilayah. Tiap entri:
  `[nama, tipe, kode_pos, indeks_kecamatan, kode_wilayah_desa]`.
  - `tipe`: `1` = Kelurahan, `0` = Desa.
  - `kode_pos`: string 5 digit, atau `null` bila tidak tersedia
    (181 desa — lihat "Kejujuran data").
  - `indeks_kecamatan`: posisi kecamatan desa tersebut di dalam
    array `d` (berbasis 0).
  - `kode_wilayah_desa`: kode Kemendagri lengkap, mis.
    `11.01.01.2015`. Jangkar (anchor) desa di halaman kecamatan
    memakai bentuk ini dengan titik diganti strip:
    `/kecamatan/bakongan-aceh-selatan#desa-11-01-01-2015`.

Daftar 38 kode provinsi:

| Kode | Provinsi | Kode | Provinsi |
|---|---|---|---|
| 11 | Aceh | 61 | Kalimantan Barat |
| 12 | Sumatera Utara | 62 | Kalimantan Tengah |
| 13 | Sumatera Barat | 63 | Kalimantan Selatan |
| 14 | Riau | 64 | Kalimantan Timur |
| 15 | Jambi | 65 | Kalimantan Utara |
| 16 | Sumatera Selatan | 71 | Sulawesi Utara |
| 17 | Bengkulu | 72 | Sulawesi Tengah |
| 18 | Lampung | 73 | Sulawesi Selatan |
| 19 | Kepulauan Bangka Belitung | 74 | Sulawesi Tenggara |
| 21 | Kepulauan Riau | 75 | Gorontalo |
| 31 | Daerah Khusus Ibukota Jakarta | 76 | Sulawesi Barat |
| 32 | Jawa Barat | 81 | Maluku |
| 33 | Jawa Tengah | 82 | Maluku Utara |
| 34 | Daerah Istimewa Yogyakarta | 91 | Papua |
| 35 | Jawa Timur | 92 | Papua Barat |
| 36 | Banten | 93 | Papua Selatan |
| 51 | Bali | 94 | Papua Tengah |
| 52 | Nusa Tenggara Barat | 95 | Papua Pegunungan |
| 53 | Nusa Tenggara Timur | 96 | Papua Barat Daya |

### 2. Indeks balik kode pos — `/data/kodepos/<digit>.json`

10 berkas, satu per digit pertama kode pos. Kunci adalah kode pos
5 digit; nilainya adalah daftar desa/kelurahan yang memakai kode
tersebut. Total ±8,7 MB. 11.890 kode pos berbeda, 83.581 entri desa.

```json
{
  "23773": [["Darul Ikhsan", "Bakongan", "Kabupaten Aceh Selatan", "Aceh", "bakongan-aceh-selatan", "11.01.01.2015"]]
}
```

Tiap entri:
`[nama_desa, nama_kecamatan, nama_kabupaten_kota, nama_provinsi,
slug_kecamatan, kode_wilayah_desa]`.
Entri dalam satu kode pos terurut alfabetis menurut nama desa.
`slug_kecamatan` dan `kode_wilayah_desa` dipakai membentuk URL dan
jangkar yang sama seperti di atas.

Untuk membaca manusia, tiap kode pos juga punya halaman web:
`https://cekkodepos.my.id/kode-pos/<5 digit>` (tanpa garis miring
di ujung).

## Contoh pemakaian

```sh
# Seluruh desa di satu provinsi
curl -s https://cekkodepos.my.id/data/wilayah/31.json

# Seluruh desa dengan kode pos berawalan 2
curl -s https://cekkodepos.my.id/data/kodepos/2.json
```

```js
// Cari desa dari kode pos, di browser
const digit = "24431"[0];
const shard = await (await fetch(`https://cekkodepos.my.id/data/kodepos/${digit}.json`)).json();
const desa = shard["24431"]; // array entri, lihat format di atas
```

```python
# Muat satu provinsi dengan Python
import json, urllib.request
url = "https://cekkodepos.my.id/data/wilayah/11.json"
data = json.load(urllib.request.urlopen(url))
print(data["p"], len(data["v"]), "desa/kelurahan")
```

## Pembaruan

Berkas dibuat ulang setiap kali situs dibangun ulang setelah ada
pembaruan data. Tidak ada jadwal pembaruan tetap dan tidak ada
penomoran versi pada berkas. Bila memakai berkas ini, unduh ulang
secara berkala; isinya dapat berubah tanpa pemberitahuan. Tanggal
verifikasi data terakhir tercantum di halaman Tentang situs.

## Atribusi

Bila memakai data ini, cantumkan atribusi berikut:

- Situs: Kode Pos & Wilayah — https://cekkodepos.my.id
- Sumber kode pos: pencarian resmi Pos Indonesia
  (`kodepos.posindonesia.co.id`)
- Sumber struktur wilayah: dataset terbuka
  [wilayah-indonesia](https://github.com/ANGGATYASIA/wilayah-indonesia)
  (lisensi MIT), mengikuti Kepmendagri No. 300.2.2-2430 Tahun 2025

Contoh kalimat atribusi:

> Data kode pos dari Kode Pos & Wilayah (cekkodepos.my.id), bersumber
> dari pencarian resmi Pos Indonesia dan dataset wilayah-indonesia.

## Kejujuran data (baca sebelum memakai)

- Bila sumber resmi Pos Indonesia dan dataset pembanding berbeda,
  kode resmi yang dipakai.
- Dataset pembanding turunan nomor.net (erlange,
  `Kodepos-Wilayah-Indonesia`) hanya cocok 53,3% dengan sumber resmi.
  Karena itu dataset pembanding tidak dipakai sebagai sumber dan
  tidak disertakan di repo ini; lihat `crosscheck.py`.
- 181 desa/kelurahan tidak memiliki kode pos dari sumber mana pun.
  Di berkas JSON nilainya `null`; di situs ditampilkan
  "Belum tersedia". Kode pos tidak pernah dibuat-buat.
- 9 kecamatan tidak memiliki satu pun desa berkode pos:

  | Kode | Kecamatan | Kabupaten/Kota |
  |---|---|---|
  | 72.01.24 | Toili Jaya | Kabupaten Banggai |
  | 81.05.16 | Ukar Sengan | Kabupaten Seram Bagian Timur |
  | 92.02.31 | Aimasi | Kabupaten Manokwari |
  | 92.02.32 | Mokwam | Kabupaten Manokwari |
  | 92.02.33 | Masni Utara | Kabupaten Manokwari |
  | 92.02.34 | Wasirawi | Kabupaten Manokwari |
  | 92.02.35 | Moruj Mega | Kabupaten Manokwari |
  | 96.03.05 | Ayau | Kabupaten Raja Ampat |
  | 96.03.23 | Kepulauan Ayau | Kabupaten Raja Ampat |

- Yang tidak ada di berkas ini: koordinat/GPS, data BPS, dan kode
  area telepon.

## Lisensi

Dataset struktur wilayah di `wilayah-indonesia/` berlisensi MIT
(lihat `wilayah-indonesia/LICENSE`, hak cipta ANGGATYASIA). Untuk
berkas JSON gabungan di atas, tidak ada lisensi formal terpisah yang
dinyatakan di repo ini; berkas dibagikan gratis untuk dipakai dengan
atribusi seperti di atas.
