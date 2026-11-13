#!/usr/bin/env python3
"""Targeted retry for the 6 regencies that harvested 0 rows: try alternate
query spellings; keep only rows whose kecamatan belongs to the regency
(district-membership filter, robust to kab-field spelling variants)."""
import json, glob, os, re, sys, time
sys.path.insert(0, os.path.expanduser("~/workspace/kodepos-data"))
from harvest3 import query_official  # noqa: E402

BASE = os.path.expanduser("~/workspace/kodepos-data/wilayah-indonesia/api")
OUT = os.path.expanduser("~/workspace/kodepos-data/harvest")

ALTERNATES = {
    "12.74": ["TANJUNG BALAI", "Tanjungbalai"],
    "17.06": ["Mukomuko", "MUKO MUKO"],
    "31.01": ["Kepulauan Seribu", "KEPULAUAN SERIBU"],
    "73.10": ["Pangkajene", "PANGKAJENE KEPULAUAN"],
    "73.72": ["Parepare", "PARE PARE"],
    "75.04": ["Pohuwato"],
}

def norm(s):
    s = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper())
    return re.sub(r"\s+", " ", s).strip()

def main():
    regs = {}
    for p in sorted(glob.glob(f"{BASE}/regencies/*.json")):
        for r in json.load(open(p, encoding="utf-8")):
            regs[r["code"]] = r
    districts = {}
    for p in sorted(glob.glob(f"{BASE}/districts/*.json")):
        for d in json.load(open(p, encoding="utf-8")):
            districts.setdefault(d["regency_code"], set()).add(norm(d["name"]))
    for code, queries in ALTERNATES.items():
        reg = regs[code]
        want_districts = districts[code]
        got, seen = [], set()
        used = []
        for q in queries:
            try:
                rows = query_official(q)
            except Exception as e:
                print(f"{code} query {q!r} failed: {e}", flush=True)
                continue
            used.append((q, len(rows)))
            for row in rows:
                if norm(row["kecamatan"]) in want_districts:
                    key = (row["kodepos"], row["desa"], row["kecamatan"])
                    if key not in seen:
                        seen.add(key)
                        got.append(row)
            time.sleep(1.5)
        path = os.path.join(OUT, f"{code}.json")
        json.dump({"regency_code": code, "regency_name": reg["name"],
                   "query": str(used), "method": "zero-retry", "rows": got,
                   "harvested": "2026-11-13"},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{code} {reg['name']}: {len(got)} rows kept (queries: {used})", flush=True)

if __name__ == "__main__":
    main()
