#!/usr/bin/env python3
"""Post-generation validation for the Kode Pos & Wilayah site.

Checks: file counts, H1 uniqueness (sample), JSON-LD parses (sample),
no TODO/placeholder strings, every district page has >=1 village row,
every village appears in exactly one district page + search index,
sitemap completeness, no empty pages.
"""
import json, glob, os, re, random, sys

OUT = os.environ.get("OUT_DIR", os.path.expanduser("~/workspace/deploy/kodepos-wilayah"))
KD = os.environ.get("KD_DIR", os.path.expanduser("~/workspace/kodepos-data"))
BASE = os.path.join(KD, "wilayah-indonesia/api")

errors = []
def check(cond, msg):
    print(("OK  " if cond else "FAIL") + " " + msg)
    if not cond:
        errors.append(msg)

# 1. File counts
prov_files = glob.glob(f"{OUT}/provinsi/*.html")
reg_files = glob.glob(f"{OUT}/kabupaten/*.html")
dist_files = glob.glob(f"{OUT}/kecamatan/*.html")
check(len(prov_files) == 38, f"province pages: {len(prov_files)} (expect 38)")
check(len(reg_files) == 514, f"regency pages: {len(reg_files)} (expect 514)")
check(len(dist_files) == 7285, f"district pages: {len(dist_files)} (expect 7285)")
for f in ["index.html", "cari-kode-pos.html", "tentang.html", "kontak.html",
          "kebijakan-privasi.html", "disclaimer.html", "styles.css", "search.js",
          "favicon.svg", "og-image.png", "robots.txt", "sitemap.xml"]:
    check(os.path.exists(f"{OUT}/{f}"), f"exists: {f}")
idx_files = glob.glob(f"{OUT}/data/wilayah/*.json")
rev_files = glob.glob(f"{OUT}/data/kodepos/*.json")
check(len(idx_files) == 38, f"province search indexes: {len(idx_files)}")
check(len(rev_files) == 10, f"reverse index chunks: {len(rev_files)}")

# 2. No placeholder / invented-data markers
bad = []
for p in glob.glob(f"{OUT}/**/*.html", recursive=True):
    t = open(p, encoding="utf-8").read()
    t = re.sub(r'placeholder="[^"]*"', "", t)  # legit input attributes, not placeholder content
    for marker in ["TODO", "Lorem", "XXX", "TBD", "FIXME"]:
        if marker in t:
            bad.append((p, marker))
check(not bad, f"no placeholder markers ({len(bad)} hits: {bad[:3]})")

# 3. H1 uniqueness + JSON-LD parse on a random sample of each type
rng = random.Random(42)
samples = ([f"{OUT}/index.html", f"{OUT}/cari-kode-pos.html", f"{OUT}/tentang.html"]
           + rng.sample(prov_files, 5) + rng.sample(reg_files, 5) + rng.sample(dist_files, 10))
h1_bad, ld_bad = [], []
for p in samples:
    t = open(p, encoding="utf-8").read()
    if t.count("<h1") != 1:
        h1_bad.append(p)
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', t, re.S):
        try:
            json.loads(m.group(1))
        except Exception as e:
            ld_bad.append((p, str(e)))
check(not h1_bad, f"exactly one <h1> in {len(samples)} sampled pages ({h1_bad})")
check(not ld_bad, f"JSON-LD parses in sampled pages ({ld_bad[:2]})")

# 4. Every district page has >=1 village row; count pages with zero coded villages
zero_coded = 0
empty_pages = 0
village_rows_total = 0
for p in dist_files:
    t = open(p, encoding="utf-8").read()
    rows = t.count('<tr id="desa-')
    village_rows_total += rows
    if rows == 0:
        empty_pages += 1
    if '<span class="code">' not in t:
        zero_coded += 1
check(empty_pages == 0, f"district pages with zero village rows: {empty_pages}")
check(village_rows_total == 83762, f"village rows across district pages: {village_rows_total} (expect 83762)")
print(f"INFO district pages with zero coded villages: {zero_coded} (honest 'Belum tersedia' pages)")

# 5. Search index completeness: every village exactly once
seen = set()
dup = 0
for p in idx_files:
    data = json.load(open(p, encoding="utf-8"))
    for v in data["v"]:
        if v[4] in seen:
            dup += 1
        seen.add(v[4])
check(len(seen) == 83762, f"villages in search indexes: {len(seen)} (expect 83762, dups {dup})")

# 6. Reverse index: every coded village exactly once
overlay = json.load(open(f"{KD}/official_overlay.json", encoding="utf-8"))
import collections
villages = []
for p in sorted(glob.glob(f"{BASE}/villages/*.json")):
    villages.extend(json.load(open(p, encoding="utf-8")))
expected_coded = sum(1 for v in villages if v["code"] in overlay or v.get("postal_code"))
rev_seen = set()
rev_dup = 0
for p in rev_files:
    chunk = json.load(open(p, encoding="utf-8"))
    for code, hits in chunk.items():
        for h in hits:
            if h[5] in rev_seen:
                rev_dup += 1
            rev_seen.add(h[5])
check(len(rev_seen) == expected_coded,
      f"villages in reverse indexes: {len(rev_seen)} (expect {expected_coded}, dups {rev_dup})")

# 7. Sitemap completeness
sm = open(f"{OUT}/sitemap.xml", encoding="utf-8").read()
n_urls = sm.count("<loc>")
expect_urls = 1 + 38 + 514 + 7285 + 1 + 4
check(n_urls == expect_urls, f"sitemap urls: {n_urls} (expect {expect_urls})")
check("kodepos-wilayah.pages.dev" in sm, "sitemap uses pages.dev base")

# 8. No page is empty / tiny
tiny = [p for p in glob.glob(f"{OUT}/**/*.html", recursive=True)
        if os.path.getsize(p) < 1500]
check(not tiny, f"no tiny HTML files (<1.5KB): {len(tiny)} {tiny[:3]}")

# 9. Brand consistency: no old working brand, no competitor brand
bad_brand = []
for p in glob.glob(f"{OUT}/**/*.html", recursive=True) + glob.glob(f"{OUT}/data/**/*.json", recursive=True):
    t = open(p, encoding="utf-8", errors="ignore").read()
    if "Kode Pos Indonesia" in t or "KodePos Indonesia" in t:
        bad_brand.append(p)
check(not bad_brand, f"no old/competitor brand strings ({bad_brand[:3]})")

# 10. Total size / file count for deploy limits
total_files = sum(len(files) for _, _, files in os.walk(OUT))
total_bytes = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, files in os.walk(OUT) for f in files)
print(f"INFO deploy tree: {total_files} files, {total_bytes/1e6:.1f} MB (limits: 20000 files, 25 MiB/file)")
check(total_files < 20000, "file count under Pages limit")
big = [os.path.join(dp, f) for dp, _, files in os.walk(OUT) for f in files
       if os.path.getsize(os.path.join(dp, f)) > 25 * 1024 * 1024]
check(not big, f"no file over 25 MiB ({big[:3]})")

print("\n" + ("ALL CHECKS PASSED" if not errors else f"{len(errors)} CHECK(S) FAILED"))
sys.exit(1 if errors else 0)
