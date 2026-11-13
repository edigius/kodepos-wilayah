#!/usr/bin/env python3
"""Hardened harvester: one worker, fresh connection per request, 3 attempts
with backoff, district-name fallback for regencies returning 0 rows.
Resumable: skips regencies with an existing harvest file.
"""
import json, glob, os, re, time, sys
import urllib.request, urllib.parse

BASE = os.path.expanduser("~/workspace/kodepos-data/wilayah-indonesia/api")
OUT = os.path.expanduser("~/workspace/kodepos-data/harvest")
os.makedirs(OUT, exist_ok=True)
URL = "https://kodepos.posindonesia.co.id/CariKodepos"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

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
    """Fresh opener per call, Connection: close, 3 attempts with backoff."""
    data = urllib.parse.urlencode({"kodepos": q}).encode()
    last_err = None
    for attempt, wait in enumerate((5, 15, 30)):
        try:
            opener = urllib.request.build_opener()
            req = urllib.request.Request(URL, data=data, headers={
                "User-Agent": UA, "Referer": "https://kodepos.posindonesia.co.id/",
                "Content-Type": "application/x-www-form-urlencoded",
                "Connection": "close"})
            with opener.open(req, timeout=40) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            return parse_rows(html)
        except Exception as e:
            last_err = e
            time.sleep(wait)
    raise RuntimeError(f"query {q!r} failed 3x: {last_err}")

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
    regs = regencies()
    dbr = districts_by_reg()
    log = open(os.path.join(OUT, "harvest2_log.txt"), "a", encoding="utf-8")
    failed = []
    n_done = n_new = 0
    for i, reg in enumerate(regs, 1):
        path = os.path.join(OUT, f"{reg['code']}.json")
        if os.path.exists(path):
            n_done += 1
            continue
        q = query_string(reg)
        try:
            rows = query_official(q)
        except Exception as e:
            failed.append({"code": reg["code"], "name": reg["name"], "query": q, "error": str(e)})
            msg = f"[{i}/{len(regs)}] {reg['code']} {reg['name']} FAILED: {e}"
            print(msg, flush=True); log.write(msg + "\n"); log.flush()
            time.sleep(2.0)
            continue
        method = "regency"
        if not rows:
            # Fallback: query each district name, keep rows matching this regency
            want = norm_reg(reg["name"])
            got = []
            seen = set()
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
            method = "district-fallback"
        json.dump({"regency_code": reg["code"], "regency_name": reg["name"],
                   "query": q, "method": method, "rows": rows, "harvested": "2026-11-13"},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False)
        n_done += 1
        n_new += 1
        if n_new % 10 == 0 or not rows:
            msg = f"[{i}/{len(regs)}] {reg['code']} {reg['name']}: {len(rows)} rows via {method} (done={n_done})"
            print(msg, flush=True); log.write(msg + "\n"); log.flush()
        time.sleep(2.0)
    msg = f"HARVEST2 DONE: {n_done}/{len(regs)} harvested, {len(failed)} failed"
    print(msg, flush=True); log.write(msg + "\n")
    json.dump(failed, open(os.path.join(OUT, "failed2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log.close()

if __name__ == "__main__":
    main()
