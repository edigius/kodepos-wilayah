#!/usr/bin/env python3
"""Generate the Kode Pos & Wilayah static site into ~/workspace/deploy/kodepos-wilayah/.

Inputs: ANGGATYASIA/wilayah-indonesia dataset (structure) + official_overlay.json
(postal codes verified against the Pos Indonesia official lookup) + join_stats.json.
Fails loudly if the overlay/stats are missing or counts do not match the dataset.
"""
import json, glob, os, re, sys, unicodedata, collections, html as htmlmod

# ---- Single place for the working brand (rename = change here + regenerate) ----
BRAND = "Kode Pos & Wilayah"
BASE_URL = "https://cekkodepos.my.id"
ADSENSE_HEAD = "<script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1022633424055636\" crossorigin=\"anonymous\"></script>"
VERIFY_DATE = "13 November 2026"
RETRIEVAL_DATE = "13 November 2026"
YEAR = "2026"
OFFICIAL_URL = "https://kodepos.posindonesia.co.id/"
CONTACT_EMAIL = "halo@squishie.my.id"

DATA_DIR = os.path.join(os.environ.get("KD_DIR", os.path.expanduser("~/workspace/kodepos-data")),
                         "wilayah-indonesia/api")
KD = os.environ.get("KD_DIR", os.path.expanduser("~/workspace/kodepos-data"))
OUT = os.environ.get("OUT_DIR", os.path.expanduser("~/workspace/deploy/kodepos-wilayah"))

def slugify(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

def esc(s):
    return htmlmod.escape(str(s), quote=True)

def fmt(n):
    return f"{n:,}".replace(",", ".")

def load_all():
    provinces = json.load(open(f"{DATA_DIR}/provinces.json", encoding="utf-8"))
    regencies = []
    for p in sorted(glob.glob(f"{DATA_DIR}/regencies/*.json")):
        regencies.extend(json.load(open(p, encoding="utf-8")))
    districts = []
    for p in sorted(glob.glob(f"{DATA_DIR}/districts/*.json")):
        districts.extend(json.load(open(p, encoding="utf-8")))
    villages = []
    for p in sorted(glob.glob(f"{DATA_DIR}/villages/*.json")):
        villages.extend(json.load(open(p, encoding="utf-8")))
    return provinces, regencies, districts, villages

def build_slugs(provinces, regencies, districts):
    prov_slug = {}
    seen = set()
    for p in sorted(provinces, key=lambda x: x["code"]):
        s = slugify(p["name"])
        assert s and s not in seen, f"province slug collision: {s}"
        seen.add(s)
        prov_slug[p["code"]] = s
    reg_slug = {}
    seen = set()
    for r in sorted(regencies, key=lambda x: x["code"]):
        s = slugify(r["name"])
        assert s and s not in seen, f"regency slug collision: {s}"
        seen.add(s)
        reg_slug[r["code"]] = s
    reg_by_code = {r["code"]: r for r in regencies}
    def short_reg_name(r):
        n = r["name"]
        for prefix in ("Kabupaten ", "Kota Administrasi ", "Kota "):
            if n.startswith(prefix):
                return n[len(prefix):]
        return n
    dist_slug = {}
    seen = set()
    collisions = 0
    for d in sorted(districts, key=lambda x: x["code"]):
        r = reg_by_code[d["regency_code"]]
        s = slugify(f"{d['name']}-{short_reg_name(r)}")
        if s in seen:
            collisions += 1
            s = f"{s}-{d['code'].replace('.', '-')}"
        assert s not in seen, f"district slug collision after suffix: {s}"
        seen.add(s)
        dist_slug[d["code"]] = s
    print(f"slugs: {len(prov_slug)} provinces, {len(reg_slug)} regencies, "
          f"{len(dist_slug)} districts ({collisions} needed code suffix)")
    return prov_slug, reg_slug, dist_slug

def resolve_codes(villages, overlay):
    """Return (final_code, source) per village code. Official overlay wins."""
    resolved = {}
    counts = collections.Counter()
    for v in villages:
        if v["code"] in overlay:
            resolved[v["code"]] = (overlay[v["code"]], "official")
            counts["official"] += 1
        elif v.get("postal_code"):
            resolved[v["code"]] = (v["postal_code"], "dataset")
            counts["dataset"] += 1
        else:
            resolved[v["code"]] = (None, "missing")
            counts["missing"] += 1
    print(f"code resolution: {dict(counts)}")
    return resolved, counts

def write_indexes(provinces, regencies, districts, villages, resolved,
                  prov_slug, reg_slug, dist_slug):
    """Per-province search indexes + per-digit reverse indexes."""
    reg_by_code = {r["code"]: r for r in regencies}
    dist_by_code = {d["code"]: d for d in districts}
    prov_by_code = {p["code"]: p for p in provinces}
    os.makedirs(f"{OUT}/data/wilayah", exist_ok=True)
    os.makedirs(f"{OUT}/data/kodepos", exist_ok=True)

    villages_by_prov = collections.defaultdict(list)
    for v in villages:
        villages_by_prov[v["district_code"][:2]].append(v)
    districts_by_prov = collections.defaultdict(list)
    for d in districts:
        districts_by_prov[d["regency_code"][:2]].append(d)

    total_indexed = 0
    for p in provinces:
        pc = p["code"]
        dlist = sorted(districts_by_prov[pc], key=lambda d: d["code"])
        didx = {d["code"]: i for i, d in enumerate(dlist)}
        d_entries = [[d["code"], d["name"], reg_by_code[d["regency_code"]]["name"],
                      dist_slug[d["code"]]] for d in dlist]
        v_entries = []
        for v in sorted(villages_by_prov[pc], key=lambda v: v["code"]):
            code, _src = resolved[v["code"]]
            v_entries.append([v["name"], 1 if v["type"] == "Kelurahan" else 0,
                              code, didx[v["district_code"]], v["code"]])
        total_indexed += len(v_entries)
        with open(f"{OUT}/data/wilayah/{pc}.json", "w", encoding="utf-8") as f:
            json.dump({"p": p["name"], "d": d_entries, "v": v_entries}, f,
                      ensure_ascii=False, separators=(",", ":"))
    print(f"search indexes: {total_indexed} villages across {len(provinces)} province files")

    reverse = collections.defaultdict(lambda: collections.defaultdict(list))
    for v in villages:
        code, _src = resolved[v["code"]]
        if not code:
            continue
        d = dist_by_code[v["district_code"]]
        r = reg_by_code[d["regency_code"]]
        reverse[code[0]][code].append(
            [v["name"], d["name"], r["name"], prov_by_code[v["district_code"][:2]]["name"],
             dist_slug[d["code"]], v["code"]])
    n_rev = 0
    for digit in "0123456789":
        chunk = reverse.get(digit, {})
        for code in chunk:
            chunk[code].sort()
            n_rev += len(chunk[code])
        with open(f"{OUT}/data/kodepos/{digit}.json", "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, separators=(",", ":"))
    print(f"reverse indexes: {n_rev} coded villages across 10 digit files")
    return total_indexed, n_rev

# ---------------- HTML templates ----------------

def shell(title, desc, path, body, jsonld=None, extra_head=""):
    ld = ""
    if jsonld is not None:
        ld = ('<script type="application/ld+json">\n'
              + json.dumps(jsonld, ensure_ascii=False, indent=1) + '\n</script>\n')
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{BASE_URL}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(BRAND)}">
<meta property="og:locale" content="id_ID">
<meta property="og:url" content="{BASE_URL}{path}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{BASE_URL}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{BASE_URL}/og-image.png">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/styles.css">
{ADSENSE_HEAD}
{ld}{extra_head}</head>
<body>
<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="/">Kode Pos <span>&amp; Wilayah</span></a>
  </div>
</header>
{body}
<footer class="site-footer">
  <div class="footer-inner">
    <nav aria-label="Tautan footer">
      <a href="/tentang">Tentang</a>
      <a href="/kontak">Kontak</a>
      <a href="/kebijakan-privasi">Kebijakan Privasi</a>
      <a href="/disclaimer">Disclaimer</a>
    </nav>
    <p>© {YEAR} {esc(BRAND)}. Direktori kode pos dan wilayah Indonesia. Data terakhir diverifikasi {VERIFY_DATE}.</p>
  </div>
</footer>
</body>
</html>
"""

def breadcrumb(items):
    """items: list of (label, url or None)."""
    lis = []
    for label, url in items:
        if url:
            lis.append(f'<li><a href="{esc(url)}">{esc(label)}</a></li>')
        else:
            lis.append(f"<li>{esc(label)}</li>")
    return '<nav class="breadcrumb" aria-label="Navigasi"><ol>' + "".join(lis) + "</ol></nav>"

def breadcrumb_ld(items):
    """items: list of (label, absolute url)."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": label, "item": url}
            for i, (label, url) in enumerate(items)
        ],
    }

def code_range_text(codes):
    codes = sorted(set(codes))
    if not codes:
        return None
    if len(codes) == 1:
        return codes[0]
    return f"{codes[0]}–{codes[-1]}"

# ---------------- Homepage ----------------

FAQ = [
    ("Apa itu kode pos?",
     "Kode pos adalah serangkaian lima angka yang menunjukkan lokasi suatu daerah untuk keperluan pengiriman surat dan paket. Di Indonesia, kode pos ditetapkan oleh Pos Indonesia dan umumnya melekat pada tingkat desa atau kelurahan."),
    ("Bagaimana cara mencari kode pos di situs ini?",
     "Ketik nama desa, kelurahan, atau kecamatan di kolom pencarian di atas, lalu pilih provinsi bila perlu untuk mempersempit hasil. Kamu juga bisa menelusuri dari daftar provinsi ke kabupaten/kota, lalu ke kecamatan. Setiap halaman kecamatan menampilkan semua desa dan kelurahan beserta kode posnya."),
    ("Apakah datanya lengkap untuk seluruh Indonesia?",
     "Ya. Situs ini memuat seluruh 38 provinsi, 514 kabupaten/kota, 7.285 kecamatan, dan 83.762 desa/kelurahan di Indonesia, berdasarkan struktur wilayah Kepmendagri Tahun 2025. Kode pos diverifikasi ke pencarian resmi Pos Indonesia; detail metode dan tanggal verifikasi ada di halaman Tentang."),
    ("Bisakah saya mencari wilayah dari kode pos?",
     "Bisa. Buka halaman Cari Kode Pos, masukkan lima angka kode pos, dan situs akan menampilkan semua desa/kelurahan yang memakai kode pos tersebut beserta kecamatan, kabupaten/kota, dan provinsinya."),
]

PROVINCE_ROTATE_SCRIPT = """<script>
/* Tiga provinsi pilihan berganti setiap hari (seed = tanggal lokal pengunjung). */
(function () {
  var grids = document.querySelectorAll(".prov-grid");
  if (grids.length < 2) return;
  var visible = grids[0], rest = grids[1];
  var cards = [];
  var i;
  for (i = 0; i < visible.children.length; i++) cards.push(visible.children[i]);
  for (i = 0; i < rest.children.length; i++) cards.push(rest.children[i]);
  if (cards.length <= 3) return;
  var now = new Date();
  var seed = (now.getFullYear() * 10000 + (now.getMonth() + 1) * 100 + now.getDate()) >>> 0;
  function rnd() {
    seed = (seed + 0x6D2B79F5) >>> 0;
    var t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  var idx = [];
  for (i = 0; i < cards.length; i++) idx.push(i);
  for (i = idx.length - 1; i > 0; i--) {
    var j = Math.floor(rnd() * (i + 1));
    var tmp = idx[i]; idx[i] = idx[j]; idx[j] = tmp;
  }
  var picked = {};
  var featured = idx.slice(0, 3);
  for (i = 0; i < featured.length; i++) picked[featured[i]] = true;
  while (visible.firstChild) visible.removeChild(visible.firstChild);
  while (rest.firstChild) rest.removeChild(rest.firstChild);
  for (i = 0; i < featured.length; i++) visible.appendChild(cards[featured[i]]);
  for (i = 0; i < cards.length; i++) if (!picked[i]) rest.appendChild(cards[i]);
})();
</script>"""

def render_home(ctx):
    provinces = ctx["provinces"]
    prov_counts = ctx["prov_counts"]
    def prov_card(p):
        return (
            f'<a class="prov-card" href="/provinsi/{ctx["prov_slug"][p["code"]]}">'
            f"<h3>{esc(p['name'])}</h3>"
            f"<p>{fmt(prov_counts[p['code']]['reg'])} kabupaten/kota · "
            f"{fmt(prov_counts[p['code']]['dist'])} kecamatan · "
            f"{fmt(prov_counts[p['code']]['vill'])} desa/kelurahan</p>"
            f'<span class="go">Lihat kode pos &rarr;</span></a>'
        )
    cards_first = "".join(prov_card(p) for p in provinces[:3])
    cards_rest = "".join(prov_card(p) for p in provinces[3:])
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in FAQ)
    faq_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ
        ],
    }
    website_ld = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": BRAND,
        "url": BASE_URL + "/",
        "inLanguage": "id",
        "description": "Direktori kode pos dan wilayah seluruh Indonesia: 38 provinsi, 514 kabupaten/kota, 7.285 kecamatan, dan 83.762 desa/kelurahan.",
    }
    body = f"""<main class="home">
  <h1>Cari kode pos <span class="accent">seluruh Indonesia</span></h1>
  <p class="lede">Direktori kode pos dan wilayah untuk 38 provinsi, 514 kabupaten/kota, 7.285 kecamatan, dan 83.762 desa/kelurahan. Cepat, gratis, dan bisa dibuka di HP.</p>

  <form class="searchbox" id="search-form" role="search" aria-label="Cari kode pos">
    <label for="q">Cari kode pos atau nama wilayah</label>
    <div class="search-row">
      <input type="search" id="q" name="q" placeholder="Misalnya: 23719, Bakongan, atau Cakung" autocomplete="off">
    </div>
    <button class="btn btn-block" type="submit">Cari kode pos</button>
    <p class="search-hint">Ketik 5 angka kode pos atau minimal 2 huruf nama wilayah.</p>
    <div class="search-results" id="search-results" aria-live="polite"></div>
  </form>

  <p class="small">Punya kode pos dan ingin tahu wilayahnya? <a href="/cari-kode-pos">Cari wilayah dari kode pos</a>.</p>

  <div class="stats" aria-label="Cakupan data">
    <div class="stat"><b>38</b><span>provinsi</span></div>
    <div class="stat"><b>514</b><span>kabupaten/kota</span></div>
    <div class="stat"><b>7.285</b><span>kecamatan</span></div>
    <div class="stat"><b>83.762</b><span>desa/kelurahan</span></div>
  </div>

  <h2>Daftar provinsi</h2>
  <p class="small">Tiga provinsi pilihan berganti setiap hari.</p>
  <div class="prov-grid">
    {cards_first}
  </div>
  <details class="province-more">
    <summary><span class="lbl-more">Lihat semuanya</span><span class="lbl-less">Lihat lebih sedikit</span></summary>
    <div class="prov-grid">
      {cards_rest}
    </div>
  </details>

  <section class="prose">
    <h2>Apa itu kode pos?</h2>
    <p>Kode pos adalah lima angka yang menunjukkan lokasi suatu daerah dalam sistem pengiriman Pos Indonesia. Kode pos melekat pada tingkat desa atau kelurahan: satu desa atau kelurahan memiliki satu kode pos, dan satu kode pos dapat dipakai oleh beberapa desa atau kelurahan yang berdekatan.</p>
    <p>Menulis kode pos yang benar pada alamat membantu paket sampai lebih cepat dan mengurangi risiko salah kirim. Untuk pengiriman penting, selalu periksa kembali kode pos ke <a href="{OFFICIAL_URL}" target="_blank" rel="noopener">pencarian resmi Pos Indonesia</a>, karena Pos Indonesia adalah sumber resmi kode pos.</p>
    <h2>Pertanyaan umum</h2>
    <div class="faq">
      {faq_html}
    </div>
  </section>
</main>
<script src="/search.js"></script>
{PROVINCE_ROTATE_SCRIPT}"""
    title = f"{BRAND} — Cari Kode Pos Seluruh Indonesia"
    desc = ("Direktori kode pos dan wilayah seluruh Indonesia: 38 provinsi, 514 kabupaten/kota, "
            "7.285 kecamatan, dan 83.762 desa/kelurahan. Cari kode pos berdasarkan nama desa, "
            "kelurahan, atau kecamatan.")
    jsonld = [website_ld, faq_ld]
    page = shell(title, desc, "/", body, jsonld)
    return page

# ---------------- Province pages ----------------

def render_province(ctx, prov):
    pc = prov["code"]
    regs = sorted(ctx["regs_by_prov"][pc], key=lambda r: r["name"])
    counts = ctx["prov_counts"][pc]
    codes = ctx["prov_codes"][pc]
    rng = code_range_text(codes)
    range_sentence = f" Kode pos di provinsi ini berkisar {rng}." if rng else ""
    rows = "".join(
        f'<tr><td><a href="/kabupaten/{ctx["reg_slug"][r["code"]]}">{esc(r["name"])}</a></td>'
        f'<td class="num">{fmt(len(ctx["dists_by_reg"][r["code"]]))}</td>'
        f'<td class="num">{fmt(ctx["reg_counts"][r["code"]]["vill"])}</td>'
        f'<td class="muted">{esc(code_range_text(ctx["reg_codes"][r["code"]]) or "—")}</td></tr>'
        for r in regs)
    url = f"/provinsi/{ctx['prov_slug'][pc]}"
    body = f"""<main>
  {breadcrumb([("Beranda", "/"), (f"Provinsi {prov['name']}", None)])}
  <h1>Kode Pos Provinsi {esc(prov['name'])}</h1>
  <p class="lede">Provinsi {esc(prov['name'])} terdiri dari {fmt(counts['reg'])} kabupaten/kota, {fmt(counts['dist'])} kecamatan, dan {fmt(counts['vill'])} desa/kelurahan.{range_sentence} Kode wilayah Kemendagri provinsi ini adalah {pc}.</p>

  <form class="searchbox" id="search-form" data-province="{pc}" role="search" aria-label="Cari di provinsi {esc(prov['name'])}">
    <label for="q">Cari desa, kelurahan, atau kecamatan di {esc(prov['name'])}</label>
    <input type="search" id="q" name="q" placeholder="Misalnya nama desa atau kecamatan" autocomplete="off">
    <div class="search-results" id="search-results" aria-live="polite"></div>
  </form>

  <h2>Daftar kabupaten/kota di {esc(prov['name'])}</h2>
  <div class="table-wrap"><table class="dtable">
    <thead><tr><th>Kabupaten/Kota</th><th class="num">Kecamatan</th><th class="num">Desa/Kelurahan</th><th>Kode Pos</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>

</main>
<script src="/search.js"></script>"""
    title = f"Kode Pos {prov['name']} — Daftar Kode Pos per Kabupaten/Kota"
    desc = (f"Daftar kode pos Provinsi {prov['name']}: {fmt(counts['reg'])} kabupaten/kota, "
            f"{fmt(counts['dist'])} kecamatan, {fmt(counts['vill'])} desa/kelurahan."
            + (f" Kode pos berkisar {rng}." if rng else ""))
    ld = breadcrumb_ld([("Beranda", BASE_URL + "/"), (f"Provinsi {prov['name']}", BASE_URL + url)])
    return shell(title, desc, url, body, ld)

# ---------------- Regency pages ----------------

def render_regency(ctx, reg):
    rc = reg["code"]
    prov = ctx["prov_by_code"][reg["province_code"]]
    dists = sorted(ctx["dists_by_reg"][rc], key=lambda d: d["name"])
    counts = ctx["reg_counts"][rc]
    codes = ctx["reg_codes"][rc]
    rng = code_range_text(codes)
    range_sentence = f" Kode pos di wilayah ini berkisar {rng}." if rng else ""
    rows = "".join(
        f'<tr><td><a href="/kecamatan/{ctx["dist_slug"][d["code"]]}">Kecamatan {esc(d["name"])}</a></td>'
        f'<td class="num">{fmt(len(ctx["vills_by_dist"][d["code"]]))}</td>'
        f'<td class="muted">{esc(code_range_text(ctx["dist_codes"][d["code"]]) or "—")}</td></tr>'
        for d in dists)
    sib_sorted = sorted(ctx["regs_by_prov"][prov["code"]], key=lambda r: r["name"])
    pos = next(i for i, r in enumerate(sib_sorted) if r["code"] == rc)
    nav_items = []
    if pos > 0:
        pr = sib_sorted[pos - 1]
        nav_items.append(f'<li><a href="/kabupaten/{ctx["reg_slug"][pr["code"]]}">&larr; {esc(pr["name"])}</a></li>')
    nav_items.append(f'<li><a href="/provinsi/{ctx["prov_slug"][prov["code"]]}">Semua kabupaten/kota di {esc(prov["name"])}</a></li>')
    if pos < len(sib_sorted) - 1:
        nr = sib_sorted[pos + 1]
        nav_items.append(f'<li><a href="/kabupaten/{ctx["reg_slug"][nr["code"]]}">{esc(nr["name"])} &rarr;</a></li>')
    siblings = "".join(nav_items)
    url = f"/kabupaten/{ctx['reg_slug'][rc]}"
    prov_url = f"/provinsi/{ctx['prov_slug'][prov['code']]}"
    body = f"""<main>
  {breadcrumb([("Beranda", "/"), (f"Provinsi {prov['name']}", prov_url), (reg["name"], None)])}
  <h1>Kode Pos {esc(reg['name'])}</h1>
  <p class="lede">{esc(reg['name'])} adalah satu dari {fmt(ctx['prov_counts'][prov['code']]['reg'])} kabupaten/kota di Provinsi {esc(prov['name'])}. Wilayah ini terdiri dari {fmt(counts['dist'])} kecamatan dan {fmt(counts['vill'])} desa/kelurahan.{range_sentence} Kode wilayah Kemendagri {esc(reg['name'])} adalah {rc}.</p>

  <h2>Daftar kecamatan di {esc(reg['name'])}</h2>
  <div class="table-wrap"><table class="dtable">
    <thead><tr><th>Kecamatan</th><th class="num">Desa/Kelurahan</th><th>Kode Pos</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>

  <h2>Jelajahi kabupaten/kota di {esc(prov['name'])}</h2>
  <ul class="chiplist">{siblings}</ul>
</main>"""
    title = f"Kode Pos {reg['name']}, {prov['name']} — Daftar Kecamatan"
    desc = (f"Daftar kode pos {reg['name']}, Provinsi {prov['name']}: {fmt(counts['dist'])} kecamatan, "
            f"{fmt(counts['vill'])} desa/kelurahan."
            + (f" Kode pos berkisar {rng}." if rng else ""))
    ld = breadcrumb_ld([("Beranda", BASE_URL + "/"),
                        (f"Provinsi {prov['name']}", BASE_URL + prov_url),
                        (reg["name"], BASE_URL + url)])
    return shell(title, desc, url, body, ld)

# ---------------- District pages ----------------

def render_district(ctx, dist):
    dc = dist["code"]
    reg = ctx["reg_by_code"][dist["regency_code"]]
    prov = ctx["prov_by_code"][reg["province_code"]]
    vills = sorted(ctx["vills_by_dist"][dc], key=lambda v: (v["name"].lower(), v["code"]))
    resolved = ctx["resolved"]
    codes = sorted({resolved[v["code"]][0] for v in vills if resolved[v["code"]][0]})
    n_desa = sum(1 for v in vills if v["type"] == "Desa")
    n_kel = len(vills) - n_desa
    n_missing = sum(1 for v in vills if resolved[v["code"]][0] is None)
    n_sib = len(ctx["dists_by_reg"][reg["code"]])

    if len(codes) == 1:
        code_sentence = f"Seluruh desa/kelurahan di kecamatan ini memakai kode pos {codes[0]}."
    elif 2 <= len(codes) <= 4:
        code_sentence = f"Kode pos yang dipakai di kecamatan ini: {', '.join(codes)}."
    elif codes:
        code_sentence = f"Kode pos di kecamatan ini berkisar {codes[0]}–{codes[-1]} ({len(codes)} kode pos berbeda)."
    else:
        code_sentence = "Kode pos untuk desa/kelurahan di kecamatan ini belum tersedia di data kami."
    mix = f"{n_desa} desa dan {n_kel} kelurahan" if n_desa and n_kel else (
        f"{n_desa} desa" if n_desa else f"{n_kel} kelurahan")
    missing_note = ""
    if n_missing:
        missing_note = (f' <span class="small">{n_missing} desa/kelurahan belum memiliki kode pos '
                        f'yang terverifikasi; periksa ke <a href="{OFFICIAL_URL}" target="_blank" '
                        f'rel="noopener">pencarian resmi Pos Indonesia</a>.</span>')

    rows = []
    for v in vills:
        code, _src = resolved[v["code"]]
        anchor = "desa-" + v["code"].replace(".", "-")
        if code:
            code_cell = f'<td><span class="code">{code}</span></td>'
        else:
            code_cell = '<td><span class="nocode">Belum tersedia</span></td>'
        rows.append(
            f'<tr id="{anchor}"><td>{esc(v["name"])} '
            f'<span class="vtype">{esc(v["type"])}</span></td>{code_cell}'
            f'<td class="muted">{esc(v["code"])}</td></tr>')
    sib_sorted = sorted(ctx["dists_by_reg"][reg["code"]], key=lambda d: d["name"])
    pos = next(i for i, d in enumerate(sib_sorted) if d["code"] == dc)
    nav_items = []
    if pos > 0:
        pd = sib_sorted[pos - 1]
        nav_items.append(f'<li><a href="/kecamatan/{ctx["dist_slug"][pd["code"]]}">&larr; Kecamatan {esc(pd["name"])}</a></li>')
    nav_items.append(f'<li><a href="/kabupaten/{ctx["reg_slug"][reg["code"]]}">Semua kecamatan di {esc(reg["name"])}</a></li>')
    if pos < len(sib_sorted) - 1:
        nd = sib_sorted[pos + 1]
        nav_items.append(f'<li><a href="/kecamatan/{ctx["dist_slug"][nd["code"]]}">Kecamatan {esc(nd["name"])} &rarr;</a></li>')
    siblings = "".join(nav_items)

    url = f"/kecamatan/{ctx['dist_slug'][dc]}"
    prov_url = f"/provinsi/{ctx['prov_slug'][prov['code']]}"
    reg_url = f"/kabupaten/{ctx['reg_slug'][reg['code']]}"
    body = f"""<main>
  {breadcrumb([("Beranda", "/"), (f"Provinsi {prov['name']}", prov_url), (reg["name"], reg_url), (f"Kecamatan {dist['name']}", None)])}
  <h1>Kode Pos Kecamatan {esc(dist['name'])}</h1>
  <p class="lede">Kecamatan {esc(dist['name'])} adalah satu dari {fmt(n_sib)} kecamatan di {esc(reg['name'])}, Provinsi {esc(prov['name'])}. Kecamatan ini memiliki {fmt(len(vills))} desa/kelurahan — {mix}. {code_sentence} Kode wilayah Kemendagri kecamatan ini adalah {dc}.{missing_note}</p>

  <h2>Daftar desa/kelurahan dan kode pos</h2>
  <div class="table-wrap"><table class="dtable">
    <thead><tr><th>Desa/Kelurahan</th><th>Kode Pos</th><th>Kode Wilayah</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table></div>

  <h2>Jelajahi kecamatan di {esc(reg['name'])}</h2>
  <ul class="chiplist">{siblings}</ul>
</main>"""
    title = f"Kode Pos Kecamatan {dist['name']}, {reg['name']} ({prov['name']})"
    desc = (f"Kode pos Kecamatan {dist['name']}, {reg['name']}, Provinsi {prov['name']}: "
            f"{fmt(len(vills))} desa/kelurahan."
            + (f" Kode pos berkisar {codes[0]}–{codes[-1]}." if len(codes) > 1 else
               f" Kode pos {codes[0]}." if codes else ""))
    ld = breadcrumb_ld([("Beranda", BASE_URL + "/"),
                        (f"Provinsi {prov['name']}", BASE_URL + prov_url),
                        (reg["name"], BASE_URL + reg_url),
                        (f"Kecamatan {dist['name']}", BASE_URL + url)])
    return shell(title, desc, url, body, ld)

# ---------------- Reverse lookup page ----------------

def render_reverse():
    body = f"""<main class="narrow">
  {breadcrumb([("Beranda", "/"), ("Cari Kode Pos", None)])}
  <h1>Cari wilayah dari kode pos</h1>
  <p class="lede">Masukkan lima angka kode pos untuk melihat semua desa/kelurahan yang memakainya, beserta kecamatan, kabupaten/kota, dan provinsinya.</p>

  <form class="searchbox" id="reverse-form">
    <label for="kodepos-input">Kode pos (5 angka)</label>
    <div class="search-row">
      <input type="text" id="kodepos-input" inputmode="numeric" pattern="[0-9]{{5}}" maxlength="5" placeholder="Misalnya: 23773" autocomplete="off">
      <button class="btn btn-block" type="submit">Cari wilayah</button>
    </div>
    <div class="search-results" id="reverse-results" aria-live="polite"></div>
  </form>

  <section class="prose">
    <h2>Tentang pencarian ini</h2>
    <p>Satu kode pos dapat dipakai oleh beberapa desa atau kelurahan yang berdekatan, terutama di wilayah pedesaan. Hasil pencarian menampilkan seluruh desa/kelurahan yang tercatat memakai kode pos tersebut di data kami.</p>
    <p>Jika kode pos tidak ditemukan, kemungkinan kode pos tersebut belum terpetakan di data kami atau penulisannya keliru. Periksa ke <a href="{OFFICIAL_URL}" target="_blank" rel="noopener">pencarian resmi Pos Indonesia</a>, sumber resmi kode pos di Indonesia.</p>
  </section>
</main>
<script src="/search.js"></script>"""
    title = "Cari Kode Pos — Lacak Wilayah dari Kode Pos"
    desc = ("Masukkan kode pos dan temukan semua desa/kelurahan yang memakainya, beserta kecamatan, "
            "kabupaten/kota, dan provinsinya, di seluruh Indonesia.")
    return shell(title, desc, "/cari-kode-pos", body)

# ---------------- Legal pages ----------------

def legal_shell(title, desc, path, h1, inner):
    body = f"""<main class="narrow">
  {breadcrumb([("Beranda", "/"), (h1, None)])}
  <h1>{esc(h1)}</h1>
  <div class="prose">
  {inner}
  </div>
</main>"""
    return shell(title, desc, path, body)

def render_tentang(stats):
    s = stats["stats"]
    compared = s["agree"] + s["disagree"]
    agree_pct = 100 * s["agree"] / compared if compared else 0
    inner = f"""
    <p><b>{esc(BRAND)}</b> adalah direktori kode pos dan wilayah seluruh Indonesia. Situs ini memuat 38 provinsi, 514 kabupaten/kota, 7.285 kecamatan, dan 83.762 desa/kelurahan, dan bertujuan membantu siapa pun menemukan kode pos yang benar dengan cepat, terutama di HP.</p>
    <h2>Sumber data</h2>
    <p>Struktur wilayah — nama dan kode wilayah provinsi, kabupaten/kota, kecamatan, dan desa/kelurahan — mengikuti <b>Kepmendagri No. 300.2.2-2430 Tahun 2025</b>, melalui dataset terbuka wilayah-indonesia (GitHub: ANGGATYASIA/wilayah-indonesia, lisensi MIT), yang diambil pada {RETRIEVAL_DATE}.</p>
    <p>Kode pos <b>diverifikasi ke pencarian resmi Pos Indonesia</b> (kodepos.posindonesia.co.id) pada {VERIFY_DATE}. Verifikasi dilakukan dengan menanyakan setiap kabupaten/kota ke pencarian resmi tersebut, lalu mencocokkan hasilnya ke data wilayah berdasarkan nama desa/kelurahan, kecamatan, dan kabupaten/kota. Sebanyak {fmt(s['agree'] + s['disagree'])} desa/kelurahan dapat dibandingkan langsung dengan data resmi; {agree_pct:.1f}% cocok persis, dan sisanya memakai kode dari pencarian resmi karena Pos Indonesia adalah sumber resmi kode pos.</p>
    <p>Sebanyak {fmt(s['gap_filled'])} desa/kelurahan yang sebelumnya belum memiliki kode pos mendapatkan kode pos dari pencarian resmi. Desa/kelurahan yang kode posnya tidak ditemukan di pencarian resmi maupun di dataset ditampilkan sebagai &ldquo;Belum tersedia&rdquo; dan tidak pernah diisi dengan angka perkiraan.</p>
    <h2>Keakuratan dan tanggung jawab</h2>
    <p>Kami berusaha menjaga data tetap akurat dan mutakhir, tetapi wilayah administratif dan kode pos dapat berubah karena pemekaran atau kebijakan Pos Indonesia. <b>Pos Indonesia adalah sumber resmi kode pos.</b> Untuk pengiriman penting, periksa kembali kode pos ke <a href="{OFFICIAL_URL}" target="_blank" rel="noopener">pencarian resmi Pos Indonesia</a> sebelum mengirim.</p>
    <p>Jika menemukan kode pos yang keliru, hubungi kami melalui halaman <a href="/kontak">Kontak</a> dengan menyebutkan nama desa/kelurahan, kecamatan, dan kabupaten/kota, serta kode pos yang benar menurut sumber resmi.</p>
    <h2>Terakhir diverifikasi</h2>
    <p>Data di situs ini terakhir diverifikasi pada <b>{VERIFY_DATE}</b>.</p>
    """
    return legal_shell(f"Tentang {BRAND} — Sumber Data dan Metode Verifikasi",
                       f"Tentang {BRAND}: sumber data wilayah Kepmendagri 2025, metode verifikasi kode pos "
                       f"ke pencarian resmi Pos Indonesia, dan tanggal verifikasi terakhir.",
                       "/tentang", "Tentang", inner)

def render_kontak():
    inner = f"""
    <p>Untuk pertanyaan, koreksi data, atau masukan tentang situs ini, hubungi kami melalui email:</p>
    <p><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>
    <p>Untuk koreksi kode pos, sertakan nama desa/kelurahan, kecamatan, dan kabupaten/kota, serta kode pos yang benar menurut sumber resmi (misalnya pencarian resmi Pos Indonesia). Koreksi yang terverifikasi akan kami perbarui pada pembaruan data berikutnya.</p>
    """
    return legal_shell(f"Kontak {BRAND}",
                       f"Hubungi {BRAND} untuk pertanyaan dan koreksi data kode pos.",
                       "/kontak", "Kontak", inner)

def render_privasi():
    inner = """
    <p>Situs ini tidak mengumpulkan, menyimpan, atau membagikan data pribadi pengunjung.</p>
    <h2>Tidak ada pelacakan</h2>
    <p>Situs ini tidak memakai analitik, cookie pelacak, atau iklan. Semua pencarian — pencarian nama wilayah dan pencarian balik kode pos — berjalan sepenuhnya di browser pengunjung; kata kunci yang diketik tidak pernah dikirim ke server kami.</p>
    <h2>Tautan ke situs lain</h2>
    <p>Situs ini menautkan ke pencarian resmi Pos Indonesia sebagai sumber resmi kode pos. Kebijakan privasi situs tersebut berlaku saat pengunjung membukanya.</p>
    <h2>Kontak</h2>
    <p>Pertanyaan tentang kebijakan ini dapat dikirim melalui halaman <a href="/kontak">Kontak</a>.</p>
    """
    return legal_shell(f"Kebijakan Privasi {BRAND}",
                       f"Kebijakan privasi {BRAND}: tidak ada data yang dikumpulkan, semua pencarian berjalan di browser.",
                       "/kebijakan-privasi", "Kebijakan Privasi", inner)

def render_disclaimer():
    inner = f"""
    <p>Informasi di situs ini disediakan untuk membantu menemukan kode pos dan wilayah di Indonesia. Meskipun kami memverifikasi data ke pencarian resmi Pos Indonesia, kami tidak menjamin bahwa seluruh data bebas dari kesalahan atau selalu mutakhir, karena wilayah administratif dan kode pos dapat berubah.</p>
    <p><b>Pos Indonesia adalah sumber resmi kode pos.</b> Untuk pengiriman surat dan paket yang penting, periksa kembali kode pos ke <a href="{OFFICIAL_URL}" target="_blank" rel="noopener">pencarian resmi Pos Indonesia</a> sebelum mengirim. Situs ini tidak bertanggung jawab atas keterlambatan atau salah kirim akibat penggunaan data di situs ini.</p>
    <p>Situs ini tidak berafiliasi dengan Pos Indonesia atau Kementerian Dalam Negeri. Nama wilayah dan kode wilayah mengikuti data resmi yang dirujuk di halaman <a href="/tentang">Tentang</a>.</p>
    """
    return legal_shell(f"Disclaimer {BRAND}",
                       f"Disclaimer {BRAND}: data bersifat informatif; Pos Indonesia adalah sumber resmi kode pos.",
                       "/disclaimer", "Disclaimer", inner)

# ---------------- Sitemap / robots / main ----------------

def write_sitemap(urls):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append(f"  <url><loc>{BASE_URL}{u}</loc><lastmod>2026-11-13</lastmod></url>")
    lines.append("</urlset>")
    with open(f"{OUT}/sitemap.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def write_robots():
    with open(f"{OUT}/robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")

def main():
    overlay_path = f"{KD}/official_overlay.json"
    stats_path = f"{KD}/join_stats.json"
    if not os.path.exists(overlay_path) or not os.path.exists(stats_path):
        sys.exit("ERROR: official_overlay.json / join_stats.json missing — run harvest.py + join.py first.")
    overlay = json.load(open(overlay_path, encoding="utf-8"))
    stats = json.load(open(stats_path, encoding="utf-8"))
    print(f"overlay: {len(overlay)} villages with official codes")

    provinces, regencies, districts, villages = load_all()
    assert len(provinces) == 38, len(provinces)
    assert len(regencies) == 514, len(regencies)
    assert len(districts) == 7285, len(districts)
    assert len(villages) == 83762, len(villages)
    print("dataset counts OK: 38 / 514 / 7285 / 83762")

    prov_slug, reg_slug, dist_slug = build_slugs(provinces, regencies, districts)
    resolved, code_counts = resolve_codes(villages, overlay)

    prov_by_code = {p["code"]: p for p in provinces}
    reg_by_code = {r["code"]: r for r in regencies}
    regs_by_prov = collections.defaultdict(list)
    for r in regencies:
        regs_by_prov[r["province_code"]].append(r)
    dists_by_reg = collections.defaultdict(list)
    for d in districts:
        dists_by_reg[d["regency_code"]].append(d)
    vills_by_dist = collections.defaultdict(list)
    for v in villages:
        vills_by_dist[v["district_code"]].append(v)

    def codes_for(vlist):
        return [resolved[v["code"]][0] for v in vlist if resolved[v["code"]][0]]
    vills_by_prov = collections.defaultdict(list)
    vills_by_reg = collections.defaultdict(list)
    for v in villages:
        vills_by_prov[v["district_code"][:2]].append(v)
        vills_by_reg[v["district_code"][:5]].append(v)
    prov_counts, prov_codes, reg_counts, reg_codes, dist_codes = {}, {}, {}, {}, {}
    for p in provinces:
        pc = p["code"]
        pv = vills_by_prov[pc]
        prov_counts[pc] = {"reg": len(regs_by_prov[pc]),
                           "dist": sum(len(dists_by_reg[r["code"]]) for r in regs_by_prov[pc]),
                           "vill": len(pv)}
        prov_codes[pc] = codes_for(pv)
    for r in regencies:
        rv = vills_by_reg[r["code"]]
        reg_counts[r["code"]] = {"dist": len(dists_by_reg[r["code"]]), "vill": len(rv)}
        reg_codes[r["code"]] = codes_for(rv)
    for d in districts:
        dist_codes[d["code"]] = codes_for(vills_by_dist[d["code"]])

    ctx = {"provinces": sorted(provinces, key=lambda p: p["name"]),
           "prov_by_code": prov_by_code, "reg_by_code": reg_by_code,
           "regs_by_prov": regs_by_prov, "dists_by_reg": dists_by_reg,
           "vills_by_dist": vills_by_dist, "prov_slug": prov_slug,
           "reg_slug": reg_slug, "dist_slug": dist_slug, "resolved": resolved,
           "prov_counts": prov_counts, "prov_codes": prov_codes,
           "reg_counts": reg_counts, "reg_codes": reg_codes, "dist_codes": dist_codes}

    os.makedirs(f"{OUT}/provinsi", exist_ok=True)
    os.makedirs(f"{OUT}/kabupaten", exist_ok=True)
    os.makedirs(f"{OUT}/kecamatan", exist_ok=True)
    urls = ["/"]

    with open(f"{OUT}/index.html", "w", encoding="utf-8") as f:
        f.write(render_home(ctx))
    for p in provinces:
        url = f"/provinsi/{prov_slug[p['code']]}"
        with open(f"{OUT}{url}.html", "w", encoding="utf-8") as f:
            f.write(render_province(ctx, p))
        urls.append(url)
    for r in regencies:
        url = f"/kabupaten/{reg_slug[r['code']]}"
        with open(f"{OUT}{url}.html", "w", encoding="utf-8") as f:
            f.write(render_regency(ctx, r))
        urls.append(url)
    for d in districts:
        url = f"/kecamatan/{dist_slug[d['code']]}"
        with open(f"{OUT}{url}.html", "w", encoding="utf-8") as f:
            f.write(render_district(ctx, d))
        urls.append(url)
    with open(f"{OUT}/cari-kode-pos.html", "w", encoding="utf-8") as f:
        f.write(render_reverse())
    urls.append("/cari-kode-pos")
    for name, fn in [("tentang", lambda: render_tentang(stats)),
                     ("kontak", render_kontak),
                     ("kebijakan-privasi", render_privasi),
                     ("disclaimer", render_disclaimer)]:
        with open(f"{OUT}/{name}.html", "w", encoding="utf-8") as f:
            f.write(fn())
        urls.append(f"/{name}")

    total_indexed, n_rev = write_indexes(provinces, regencies, districts, villages,
                                         resolved, prov_slug, reg_slug, dist_slug)
    assert total_indexed == len(villages), (total_indexed, len(villages))
    write_sitemap(urls)
    write_robots()
    print(f"pages written: {len(urls)} (1 home + 38 prov + 514 reg + 7285 dist + 1 reverse + 4 legal)")
    print(f"sitemap urls: {len(urls)}")

if __name__ == "__main__":
    main()
