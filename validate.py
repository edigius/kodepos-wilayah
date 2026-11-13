#!/usr/bin/env python3
"""Validate ANGGATYASIA/wilayah-indonesia dataset: counts, schema, coverage, integrity."""
import json, glob, os, re, collections

BASE = os.path.expanduser("~/workspace/kodepos-data/wilayah-indonesia/api")

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

index = load(f"{BASE}/index.json")
print("INDEX:", json.dumps(index, ensure_ascii=False)[:500])

provinces = load(f"{BASE}/provinces.json")
print(f"\nPROVINCES: {len(provinces)}")
print("  sample:", provinces[0])
print("  keys:", sorted(provinces[0].keys()))
prov_codes = [p["code"] for p in provinces]
print("  dup province codes:", [c for c, n in collections.Counter(prov_codes).items() if n > 1] or "none")

regencies = []
for p in sorted(glob.glob(f"{BASE}/regencies/*.json")):
    regencies.extend(load(p))
print(f"\nREGENCIES: {len(regencies)}")
print("  sample:", regencies[0])
print("  keys:", sorted(regencies[0].keys()))
reg_codes = [r["code"] for r in regencies]
dups = [c for c, n in collections.Counter(reg_codes).items() if n > 1]
print("  dup regency codes:", dups or "none")
print("  types:", collections.Counter(r["type"] for r in regencies))
bad_parent = [r for r in regencies if r["province_code"] not in prov_codes]
print("  regencies with unknown province_code:", len(bad_parent))

districts = []
for p in sorted(glob.glob(f"{BASE}/districts/*.json")):
    districts.extend(load(p))
print(f"\nDISTRICTS: {len(districts)}")
print("  sample:", districts[0])
print("  keys:", sorted(districts[0].keys()))
dist_codes = [d["code"] for d in districts]
dups = [c for c, n in collections.Counter(dist_codes).items() if n > 1]
print("  dup district codes:", dups or "none")
bad_parent = [d for d in districts if d["regency_code"] not in reg_codes]
print("  districts with unknown regency_code:", len(bad_parent))

villages = []
village_files = sorted(glob.glob(f"{BASE}/villages/*.json"))
for p in village_files:
    villages.extend(load(p))
print(f"\nVILLAGES: {len(villages)} from {len(village_files)} files")
print("  sample:", villages[0])
print("  keys:", sorted(villages[0].keys()))
v_codes = [v["code"] for v in villages]
dups = [c for c, n in collections.Counter(v_codes).items() if n > 1]
print("  dup village codes:", len(dups), dups[:5])
print("  types:", collections.Counter(v["type"] for v in villages))

with_postal = [v for v in villages if v.get("postal_code")]
print(f"  with postal_code: {len(with_postal)} ({100*len(with_postal)/len(villages):.2f}%)")
print(f"  without postal_code: {len(villages)-len(with_postal)}")
bad_format = [v for v in with_postal if not re.fullmatch(r"\d{5}", str(v["postal_code"]))]
print("  postal codes not 5 digits:", len(bad_format), bad_format[:5])
bad_parent = [v for v in villages if v["district_code"] not in set(dist_codes)]
print("  villages with unknown district_code:", len(bad_parent))

# Per-district village counts
per_dist = collections.Counter(v["district_code"] for v in villages)
empty = [d["code"] for d in districts if per_dist.get(d["code"], 0) == 0]
print(f"\nDISTRICTS WITH ZERO VILLAGES: {len(empty)} {empty[:10]}")
per_dist_with_code = collections.Counter(v["district_code"] for v in with_postal)
no_code = [d["code"] for d in districts if per_dist_with_code.get(d["code"], 0) == 0]
print(f"DISTRICTS WITH ZERO CODED VILLAGES: {len(no_code)} {no_code[:10]}")
print(f"Villages per district: min={min(per_dist.values())} max={max(per_dist.values())} avg={len(villages)/len(districts):.1f}")

# Province-level coverage
prov_of_dist = {d["code"]: d["regency_code"][:2] for d in districts}
cov = {}
for v in villages:
    pc = prov_of_dist.get(v["district_code"], "?")
    cov.setdefault(pc, [0, 0])
    cov[pc][1] += 1
    if v.get("postal_code"):
        cov[pc][0] += 1
print("\nCOVERAGE BY PROVINCE (coded/total):")
for pc in sorted(cov):
    c, t = cov[pc]
    print(f"  {pc}: {c}/{t} ({100*c/t:.1f}%)")

# Name sanity: empty names?
print("\nEmpty names:", sum(1 for v in villages if not v.get("name")), "villages;",
      sum(1 for d in districts if not d.get("name")), "districts;",
      sum(1 for r in regencies if not r.get("name")), "regencies")
