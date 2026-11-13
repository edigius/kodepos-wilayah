#!/usr/bin/env python3
"""Harvest postal codes from the official Pos Indonesia lookup, one query per
regency (typed query: 'KAB. <NAME>' / 'KOTA <NAME>' / 'KOTA ADM. <NAME>').

Writes raw rows per regency to harvest/<regency_code>.json immediately, so the
run is resumable: already-harvested regencies are skipped on restart.
Polite rate: ~1.2s pause between requests, 40s timeout, 1 retry.
"""
import json, glob, os, re, time, sys, unicodedata
import urllib.request, urllib.parse, http.cookiejar

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

def query_string(reg):
    name = reg["name"]
    if name.startswith("Kabupaten "):
        return "KAB. " + name[len("Kabupaten "):]
    if name.startswith("Kota Administrasi "):
        return "KOTA ADM. " + name[len("Kota Administrasi "):]
    if name.startswith("Kota "):
        return "KOTA " + name[len("Kota "):]
    return name

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def query_official(q):
    data = urllib.parse.urlencode({"kodepos": q}).encode()
    req = urllib.request.Request(URL, data=data, headers={
        "User-Agent": UA, "Referer": "https://kodepos.posindonesia.co.id/",
        "Content-Type": "application/x-www-form-urlencoded"})
    last_err = None
    for attempt in range(2):
        try:
            with opener.open(req, timeout=40) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
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
        except Exception as e:
            last_err = e
            time.sleep(5)
    raise RuntimeError(f"query {q!r} failed twice: {last_err}")

def main():
    shard = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    shards = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    regs = [r for i, r in enumerate(regencies()) if i % shards == shard]
    log = open(os.path.join(OUT, f"harvest_log_s{shard}.txt"), "a", encoding="utf-8")
    done = 0
    failed = []
    for i, reg in enumerate(regs, 1):
        path = os.path.join(OUT, f"{reg['code']}.json")
        if os.path.exists(path):
            done += 1
            continue
        q = query_string(reg)
        try:
            rows = query_official(q)
        except Exception as e:
            failed.append({"code": reg["code"], "name": reg["name"], "query": q, "error": str(e)})
            msg = f"[{i}/{len(regs)}] {reg['code']} {reg['name']} q={q!r} FAILED: {e}"
            print(msg, flush=True); log.write(msg + "\n"); log.flush()
            time.sleep(1.2)
            continue
        json.dump({"regency_code": reg["code"], "regency_name": reg["name"],
                   "query": q, "rows": rows, "harvested": "2026-11-13"},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False)
        done += 1
        if i % 25 == 0 or len(rows) == 0:
            msg = f"[{i}/{len(regs)}] {reg['code']} {reg['name']}: {len(rows)} rows (done={done})"
            print(msg, flush=True); log.write(msg + "\n"); log.flush()
        time.sleep(1.2)
    msg = f"HARVEST DONE: {done}/{len(regs)} regencies harvested, {len(failed)} failed"
    print(msg, flush=True); log.write(msg + "\n")
    json.dump(failed, open(os.path.join(OUT, "failed.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log.close()

if __name__ == "__main__":
    main()
