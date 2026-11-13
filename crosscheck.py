#!/usr/bin/env python3
"""Cross-check dataset postal codes against the official Pos Indonesia lookup
AND attempt gap-fill for villages without postal codes (district-name queries).

Polite rate: ~1.5s between requests. Retries transient failures once.
Outputs: crosscheck.json, gapfill.json, crosscheck_log.txt
"""
import json, glob, os, re, random, time, sys, unicodedata
import urllib.request, urllib.parse, http.cookiejar

BASE = os.path.expanduser("~/workspace/kodepos-data/wilayah-indonesia/api")
OUT = os.path.expanduser("~/workspace/kodepos-data")
URL = "https://kodepos.posindonesia.co.id/CariKodepos"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

def load_all():
    villages = []
    for p in sorted(glob.glob(f"{BASE}/villages/*.json")):
        villages.extend(json.load(open(p, encoding="utf-8")))
    districts = {}
    for p in sorted(glob.glob(f"{BASE}/districts/*.json")):
        for d in json.load(open(p, encoding="utf-8")):
            districts[d["code"]] = d
    regencies = {}
    for p in sorted(glob.glob(f"{BASE}/regencies/*.json")):
        for r in json.load(open(p, encoding="utf-8")):
            regencies[r["code"]] = r
    provinces = {p["code"]: p["name"] for p in json.load(open(f"{BASE}/provinces.json", encoding="utf-8"))}
    return villages, districts, regencies, provinces

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def norm_village(s):
    s = norm(s)
    for prefix in ("GAMPONG ", "DESA ", "KELURAHAN ", "KEL ", "KAMPUNG ", "NAGARI "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s

def norm_regency(s):
    s = norm(s)
    for prefix in ("KABUPATEN ", "KAB ", "KOTA "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def query_official(q):
    """POST to the official lookup; return list of row dicts or None on failure."""
    data = urllib.parse.urlencode({"kodepos": q}).encode()
    req = urllib.request.Request(URL, data=data, headers={
        "User-Agent": UA, "Referer": "https://kodepos.posindonesia.co.id/",
        "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(2):
        try:
            with opener.open(req, timeout=45) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            cells = [re.sub(r"<[^>]+>", "", m.group(1)).strip()
                     for m in re.finditer(r"<t[dh][^>]*>(.*?)</t[dh]>", html, flags=re.S)]
            cells = [c for c in cells if c]
            rows = []
            # header is 6 cells: No, Kodepos, Desa/Kelurahan, Kecamatan, Kota/Kabupaten, Provinsi
            if len(cells) >= 6 and cells[0] == "No":
                body = cells[6:]
                for i in range(0, len(body) - 5, 6):
                    rows.append({"kodepos": body[i+1], "desa": body[i+2],
                                 "kecamatan": body[i+3], "kab": body[i+4], "prov": body[i+5]})
            return rows
        except Exception as e:
            print(f"  [retry] query {q!r} attempt {attempt+1} failed: {e}", flush=True)
            time.sleep(5)
    return None

def match_row(row, village, district, regency):
    return (norm_village(row["desa"]) == norm_village(village["name"])
            and norm(row["kecamatan"]) == norm(district["name"])
            and norm_regency(row["kab"]) == norm_regency(regency["name"]))

def main():
    villages, districts, regencies, provinces = load_all()
    log = open(f"{OUT}/crosscheck_log.txt", "w", encoding="utf-8")

    def say(msg):
        print(msg, flush=True)
        log.write(msg + "\n"); log.flush()

    # ---------- PART 1: cross-check 30 stratified samples ----------
    rng = random.Random(20261113)
    coded = [v for v in villages if v.get("postal_code")]
    by_prov = {}
    for v in coded:
        by_prov.setdefault(v["district_code"][:2], []).append(v)
    forced = ["91", "92", "93", "94", "95"]
    others = [p for p in sorted(by_prov) if p not in forced]
    chosen_provs = forced + rng.sample(others, 25)
    samples = []
    for pc in chosen_provs:
        samples.append(rng.choice(by_prov[pc]))
    say(f"PART 1: {len(samples)} cross-check samples across {len(chosen_provs)} provinces")

    results = []
    n_match = n_mismatch = n_notfound = n_failed = n_ambig = 0
    for i, v in enumerate(samples, 1):
        d = districts[v["district_code"]]
        r = regencies[d["regency_code"]]
        rows = query_official(v["name"])
        time.sleep(1.5)
        if rows is None:
            results.append({"village": v, "district": d["name"], "regency": r["name"],
                            "verdict": "QUERY_FAILED", "rows_returned": None})
            n_failed += 1
            say(f"[{i}/30] {v['name']} ({d['name']}, {r['name']}) -> QUERY FAILED")
            continue
        matched = [row for row in rows if match_row(row, v, d, r)]
        codes = sorted({row["kodepos"] for row in matched})
        if not matched:
            verdict = "NOT_FOUND"
            n_notfound += 1
        elif len(codes) > 1:
            verdict = "AMBIGUOUS"
            n_ambig += 1
        elif codes[0] == v["postal_code"]:
            verdict = "MATCH"
            n_match += 1
        else:
            verdict = "MISMATCH"
            n_mismatch += 1
        results.append({"village": v, "district": d["name"], "regency": r["name"],
                        "verdict": verdict, "rows_returned": len(rows),
                        "official_codes": codes,
                        "official_rows": matched[:3]})
        say(f"[{i}/30] {v['name']} ({d['name']}, {r['name']}) dataset={v['postal_code']} "
            f"official={codes} rows={len(rows)} -> {verdict}")

    say(f"PART 1 SUMMARY: MATCH={n_match} MISMATCH={n_mismatch} NOT_FOUND={n_notfound} "
        f"AMBIGUOUS={n_ambig} QUERY_FAILED={n_failed}")

    # ---------- PART 2: gap-fill via district-name queries ----------
    uncoded = [v for v in villages if not v.get("postal_code")]
    dist_with_uncoded = sorted({v["district_code"] for v in uncoded})
    say(f"\nPART 2: gap-fill for {len(uncoded)} uncoded villages in {len(dist_with_uncoded)} districts")
    uncoded_by_dist = {}
    for v in uncoded:
        uncoded_by_dist.setdefault(v["district_code"], []).append(v)

    fills = {}
    n_q_ok = n_q_fail = 0
    for i, dc in enumerate(dist_with_uncoded, 1):
        d = districts[dc]
        r = regencies[d["regency_code"]]
        rows = query_official(d["name"])
        time.sleep(1.5)
        if rows is None:
            n_q_fail += 1
            say(f"  [{i}/{len(dist_with_uncoded)}] {d['name']} ({r['name']}) -> QUERY FAILED")
            continue
        n_q_ok += 1
        # candidate uncoded villages in this district, keyed by normalized name
        cands = {}
        for v in uncoded_by_dist[dc]:
            cands.setdefault(norm_village(v["name"]), []).append(v)
        filled_here = 0
        for row in rows:
            if norm(row["kecamatan"]) != norm(d["name"]):
                continue
            if norm_regency(row["kab"]) != norm_regency(r["name"]):
                continue
            key = norm_village(row["desa"])
            cvs = cands.get(key, [])
            if len(cvs) == 1 and cvs[0]["code"] not in fills:
                if re.fullmatch(r"\d{5}", row["kodepos"] or ""):
                    fills[cvs[0]["code"]] = {
                        "postal_code": row["kodepos"],
                        "village_name": cvs[0]["name"],
                        "district": d["name"], "regency": r["name"],
                        "official_row": row,
                        "source": "Pos Indonesia official lookup (kodepos.posindonesia.co.id)",
                        "verified": "2026-11-13"}
                    filled_here += 1
        if filled_here or i % 50 == 0:
            say(f"  [{i}/{len(dist_with_uncoded)}] {d['name']} ({r['name']}): rows={len(rows)} filled={filled_here} total_fills={len(fills)}")

    say(f"PART 2 SUMMARY: queries_ok={n_q_ok} queries_failed={n_q_fail} "
        f"villages_filled={len(fills)} of {len(uncoded)} uncoded "
        f"({100*len(fills)/max(1,len(uncoded)):.1f}%)")
    remaining_zero = [dc for dc in dist_with_uncoded
                      if not any(v.get("postal_code") or v["code"] in fills
                                 for v in villages if v["district_code"] == dc)]
    # cheaper: recompute via per-district coded presence
    coded_or_filled = set()
    for v in villages:
        if v.get("postal_code") or v["code"] in fills:
            coded_or_filled.add(v["district_code"])
    still_zero = [dc for dc in districts if dc not in coded_or_filled]
    say(f"Districts still with zero coded villages after gap-fill: {len(still_zero)}")

    json.dump(results, open(f"{OUT}/crosscheck.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({"fills": fills, "still_zero_districts": still_zero,
               "generated": "2026-11-13",
               "method": "district-name queries to Pos Indonesia official lookup; exact normalized match on village+district+regency"},
              open(f"{OUT}/gapfill.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("DONE. Wrote crosscheck.json and gapfill.json")
    log.close()

if __name__ == "__main__":
    main()
