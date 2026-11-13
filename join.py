#!/usr/bin/env python3
"""Join harvested official Pos Indonesia rows to dataset villages (two passes).

Pass 1: exact normalized match on (village, district, regency).
Pass 2 (unmatched only): village name unique within the regency on BOTH sides
+ district-name similarity >= 0.75 (recovers spelling variants such as
official "Pasi Raja" vs Kemendagri "Pasie Raja").
Province is NOT part of the key (official province naming can lag pemekaran).

Outputs: official_overlay.json, join_stats.json
"""
import json, glob, os, re, unicodedata, collections, difflib

BASE = os.path.expanduser("~/workspace/kodepos-data/wilayah-indonesia/api")
HARV = os.path.expanduser("~/workspace/kodepos-data/harvest")
OUT = os.path.expanduser("~/workspace/kodepos-data")

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def norm_village(s, strip_prefix=True):
    s = norm(s)
    if strip_prefix:
        for prefix in ("GAMPONG ", "DESA ", "KELURAHAN ", "KEL ", "KAMPUNG ", "NAGARI "):
            if s.startswith(prefix):
                s = s[len(prefix):]
                break
    return s

def norm_regency(s):
    s = norm(s)
    s = re.sub(r"^KOTA ADM ", "KOTA ADMINISTRASI ", s)
    s = re.sub(r"^ADM ", "ADMINISTRASI ", s)
    for prefix in ("KABUPATEN ", "KAB ", "KOTA "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s

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

def main():
    villages, districts, regencies, provinces = load_all()

    official = collections.defaultdict(list)
    official_by_village_reg = collections.defaultdict(list)
    n_rows = 0
    for p in sorted(glob.glob(f"{HARV}/*.json")):
        if os.path.basename(p).startswith("failed"):
            continue
        data = json.load(open(p, encoding="utf-8"))
        for row in data["rows"]:
            n_rows += 1
            key = (norm_village(row["desa"]), norm(row["kecamatan"]), norm_regency(row["kab"]))
            official[key].append(row)
            official_by_village_reg[(norm_village(row["desa"]), norm_regency(row["kab"]))].append(row)
    print(f"official rows indexed: {n_rows}, unique keys: {len(official)}")

    per_dist_keys = collections.defaultdict(list)
    for v in villages:
        per_dist_keys[v["district_code"]].append(norm_village(v["name"]))
    dup_districts = {dc for dc, names in per_dist_keys.items()
                     if len(names) != len(set(names))}
    print(f"districts with duplicate normalized village names: {len(dup_districts)}")

    # Village-name uniqueness within regency (dataset side, for pass 2)
    reg_village_counts = collections.Counter()
    for v in villages:
        d = districts[v["district_code"]]
        reg_village_counts[(norm_village(v["name"]), norm_regency(regencies[d["regency_code"]]["name"]))] += 1

    overlay = {}
    stats = collections.Counter()
    per_prov = collections.defaultdict(collections.Counter)
    mismatches, ambiguous, no_match_samples = [], [], []
    pass2_matches = 0

    def record(v, d, r, codes, matched_rows, via):
        nonlocal pass2_matches
        prov = v["district_code"][:2]
        st = per_prov[prov]
        if via == "pass2":
            pass2_matches += 1
            st["pass2"] += 1
        if len(codes) > 1:
            stats["ambiguous"] += 1
            st["ambiguous"] += 1
            ambiguous.append({"village": v, "district": d["name"], "regency": r["name"],
                              "dataset_code": v.get("postal_code"), "official_codes": codes, "via": via})
            return
        code = codes[0]
        overlay[v["code"]] = code
        if v.get("postal_code"):
            if v["postal_code"] == code:
                stats["agree"] += 1
                st["agree"] += 1
            else:
                stats["disagree"] += 1
                st["disagree"] += 1
                if len(mismatches) < 40:
                    mismatches.append({"village": v, "district": d["name"], "regency": r["name"],
                                       "dataset_code": v["postal_code"], "official_code": code, "via": via})
        else:
            stats["gap_filled"] += 1
            st["gap_filled"] += 1

    for v in villages:
        d = districts[v["district_code"]]
        r = regencies[d["regency_code"]]
        prov = v["district_code"][:2]
        key = (norm_village(v["name"]), norm(d["name"]), norm_regency(r["name"]))
        rows = official.get(key, [])
        if v["district_code"] in dup_districts:
            exact = norm_village(v["name"], strip_prefix=False)
            rows = [row for row in rows
                    if norm_village(row["desa"], strip_prefix=False) == exact]
        codes = sorted({row["kodepos"] for row in rows if re.fullmatch(r"\d{5}", row["kodepos"] or "")})
        if rows and codes:
            record(v, d, r, codes, rows, "pass1")
            continue
        # Pass 2: unique village name within regency + similar district name
        vkey = (norm_village(v["name"]), norm_regency(r["name"]))
        matched = False
        if reg_village_counts[vkey] == 1:
            cands = official_by_village_reg.get(vkey, [])
            cand_districts = {norm(row["kecamatan"]) for row in cands}
            if len(cand_districts) == 1:
                od = next(iter(cand_districts))
                sim = difflib.SequenceMatcher(None, norm(d["name"]), od).ratio()
                if sim >= 0.75:
                    codes2 = sorted({row["kodepos"] for row in cands
                                     if re.fullmatch(r"\d{5}", row["kodepos"] or "")})
                    if codes2:
                        record(v, d, r, codes2, cands, "pass2")
                        matched = True
        if not matched:
            stats["no_official_match"] += 1
            per_prov[prov]["no_official_match"] += 1
            if len(no_match_samples) < 30:
                no_match_samples.append({"village": v, "district": d["name"], "regency": r["name"]})

    village_keys = set()
    for v in villages:
        d = districts[v["district_code"]]
        r = regencies[d["regency_code"]]
        village_keys.add((norm_village(v["name"]), norm(d["name"]), norm_regency(r["name"])))
    orphan_rows = 0
    orphan_samples = []
    for key, rows in official.items():
        if key not in village_keys:
            orphan_rows += len(rows)
            if len(orphan_samples) < 20:
                orphan_samples.append({"key": key, "row": rows[0]})

    total = len(villages)
    print(f"\nTOTAL villages: {total}")
    print(f"  agree: {stats['agree']}, disagree: {stats['disagree']}, "
          f"gap_filled: {stats['gap_filled']}, ambiguous: {stats['ambiguous']}, "
          f"no_official_match: {stats['no_official_match']}, pass2: {pass2_matches}")
    compared = stats["agree"] + stats["disagree"]
    if compared:
        print(f"  agreement rate on compared: {100*stats['agree']/compared:.2f}%")
    print(f"  overlay size: {len(overlay)}")
    print(f"  official rows matching no dataset village (exact keys): {orphan_rows}")
    print("\nPER-PROVINCE (agree/disagree/gap_filled/ambiguous/no_match/pass2):")
    for pc in sorted(per_prov):
        s = per_prov[pc]
        print(f"  {pc} {provinces.get(pc,'?')}: {s['agree']}/{s['disagree']}/{s['gap_filled']}/{s['ambiguous']}/{s['no_official_match']}/{s['pass2']}")

    json.dump(overlay, open(f"{OUT}/official_overlay.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    json.dump({"stats": dict(stats), "per_province": {k: dict(v) for k, v in per_prov.items()},
               "total_villages": total, "official_rows": n_rows,
               "orphan_official_rows": orphan_rows, "pass2_matches": pass2_matches,
               "mismatch_samples": mismatches, "ambiguous_samples": ambiguous[:20],
               "no_match_samples": no_match_samples, "orphan_samples": orphan_samples,
               "generated": "2026-11-13",
               "method": "Pos Indonesia official lookup harvested per regency; pass 1 exact normalized match on village+district+regency, pass 2 unique-village-in-regency + district similarity >= 0.75"},
              open(f"{OUT}/join_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nWrote official_overlay.json and join_stats.json")

if __name__ == "__main__":
    main()
