#!/usr/bin/env python3
"""Mop-up harvester: curl-based (robust against the IncompleteRead failures
urllib hits on large responses). Retries every regency that is missing or
has 0 rows, first by regency query, then by district-name fallback.
"""
import json, glob, os, re, subprocess, time, sys

BASE = os.path.expanduser("~/workspace/kodepos-data/wilayah-indonesia/api")
OUT = os.path.expanduser("~/workspace/kodepos-data/harvest")
URL = "https://kodepos.posindonesia.co.id/CariKodepos"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
TMP = f"/tmp/harvest3_{os.getpid()}.html"

def regencies():
    regs = []
    for p in sorted(glob.glob(f"{BASE}/regencies/*.json")):
        regs.extend(json.load(open(p, encoding="utf-8")))
    return sorted(regs, key=lambda r: r["code"])

def districts_by_reg():
    d = {}
    for p in sorted(glob.glob(f"{BASE}/districts/*.json")):
        for x in json.load(open(p, encoding="utf-8")):
            d.setdefault(x["regency_code"], []).append(x)
    return d

def query_string(reg):
    name = reg["name"]
    if name.startswith("Kabupaten "):
        return "KAB. " + name[len("Kabupaten "):]
    if name.startswith("Kota Administrasi "):
        return "KOTA ADM. " + name[len("Kota Administrasi "):]
    if name.startswith("Kota "):
        return "KOTA " + name[len("Kota "):]
    return name

def parse_rows(html):
    cells = [re.sub(r"<[^>]+>", "", m.group(1)).strip()
             for m in re.finditer(r"<t[dh][^>]*>(.*?)</t[dh]>", html, flags=re.S)]
    cells = [c for c in cells if c]
    rows = []
    if len(cells) >= 6 and cells[0] == "No":
        body = cells[6:]
        for i in range(0, len(body) - 5, 6):
            rows.append({"kodepos": body[i+1], "desa": body[i+2],
                         "kecamatan": body[i+3], "kab": body[i+4], "prov": body[i+5]})
    return rows

def query_official(q):
    """curl with retries; returns rows or raises."""
    last = None
    for attempt in range(3):
        if os.path.exists(TMP):
            os.remove(TMP)
        cmd = ["curl", "-s", "--max-time", "60", "--http1.1",
               "-A", UA, "-e", "https://kodepos.posindonesia.co.id/",
               "--data-urlencode", f"kodepos={q}", URL,
               "-o", TMP, "-w", "%{http_code}"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=70)
        except subprocess.TimeoutExpired:
            last = "curl timeout"
            time.sleep(10)
            continue
        code = r.stdout.strip()
        if code == "200" and os.path.exists(TMP) and os.path.getsize(TMP) > 200:
            html = open(TMP, encoding="utf-8", errors="ignore").read()
            if "Kodepos" in html or "No" in html:
                return parse_rows(html)
            last = "unexpected body"
        else:
            last = f"http={code} size={os.path.getsize(TMP) if os.path.exists(TMP) else 0}"
        time.sleep(10)
    raise RuntimeError(f"query {q!r} failed 3x via curl: {last}")

def norm_reg(s):
    s = re.sub(r"[^A-Z0-9 ]", " ", s.upper())
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^KOTA ADM ", "KOTA ADMINISTRASI ", s)
    for prefix in ("KABUPATEN ", "KAB ", "KOTA "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s

def main():
    shard, nshards = (int(a) for a in sys.argv[1:3]) if len(sys.argv) >= 3 else (0, 1)
    regs = regencies()
    dbr = districts_by_reg()
    targets = []
    for reg in regs:
        path = os.path.join(OUT, f"{reg['code']}.json")
        if not os.path.exists(path):
            targets.append(reg)
        else:
            data = json.load(open(path, encoding="utf-8"))
            if len(data.get("rows", [])) == 0:
                targets.append(reg)
    targets = [r for i, r in enumerate(targets) if i % nshards == shard]
    print(f"harvest3 shard {shard}/{nshards} targets: {len(targets)} regencies", flush=True)
    log = open(os.path.join(OUT, f"harvest3_log_s{shard}.txt"), "a", encoding="utf-8")
    failed = []
    for i, reg in enumerate(targets, 1):
        path = os.path.join(OUT, f"{reg['code']}.json")
        q = query_string(reg)
        try:
            rows = query_official(q)
        except Exception as e:
            failed.append({"code": reg["code"], "name": reg["name"], "query": q, "error": str(e)})
            msg = f"[{i}/{len(targets)}] {reg['code']} {reg['name']} FAILED: {e}"
            print(msg, flush=True); log.write(msg + "\n"); log.flush()
            time.sleep(2.0)
            continue
        method = "regency-curl"
        if not rows:
            want = norm_reg(reg["name"])
            got, seen = [], set()
            for d in dbr.get(reg["code"], []):
                try:
                    drows = query_official(d["name"])
                except Exception:
                    continue
                time.sleep(1.5)
                for row in drows:
                    if norm_reg(row["kab"]) == want:
                        key = (row["kodepos"], row["desa"], row["kecamatan"])
                        if key not in seen:
                            seen.add(key)
                            got.append(row)
            rows = got
            method = "district-fallback-curl"
        json.dump({"regency_code": reg["code"], "regency_name": reg["name"],
                   "query": q, "method": method, "rows": rows, "harvested": "2026-11-13"},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False)
        msg = f"[{i}/{len(targets)}] {reg['code']} {reg['name']}: {len(rows)} rows via {method}"
        print(msg, flush=True); log.write(msg + "\n"); log.flush()
        time.sleep(2.0)
    print(f"HARVEST3 SHARD {shard} DONE: {len(targets)-len(failed)}/{len(targets)} recovered, {len(failed)} still failed", flush=True)
    json.dump(failed, open(os.path.join(OUT, f"failed3_s{shard}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log.close()

if __name__ == "__main__":
    main()
