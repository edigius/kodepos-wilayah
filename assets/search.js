/* Kode Pos & Wilayah — pencarian sisi klien.
   Data dimuat per provinsi dari /data/wilayah/<kode>.json (di-cache di memori).
   Pencarian balik kode pos memakai /data/kodepos/<digit-pertama>.json.
   Semua berjalan di browser; tidak ada data yang dikirim ke server. */
(function () {
  "use strict";

  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  var cache = new Map();

  function loadProvince(code) {
    if (cache.has(code)) return cache.get(code);
    var p = fetch("/data/wilayah/" + code + ".json").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
    cache.set(code, p);
    return p;
  }

  /* ---------- Pencarian nama desa/kecamatan ---------- */
  var qEl = document.getElementById("q");
  var provEl = document.getElementById("provFilter");
  var outEl = document.getElementById("search-results");
  var formEl = document.getElementById("search-form");

  if (qEl && outEl) {
    var fixedProv = formEl ? formEl.getAttribute("data-province") : null;
    var timer = null;
    var runId = 0;

    /* Semua kode provinsi, dipakai saat tidak ada filter provinsi di halaman. */
    var ALL_PROVINCE_CODES = ["11", "51", "36", "17", "34", "31", "75", "15", "32", "33", "35", "61", "63", "62", "64", "65", "19", "21", "18", "81", "82", "52", "53", "91", "92", "96", "95", "93", "94", "14", "76", "73", "72", "74", "71", "13", "16", "12"];

    function provinceCodes() {
      if (fixedProv) return [fixedProv];
      if (provEl && provEl.value && provEl.value !== "all") return [provEl.value];
      if (!provEl) return ALL_PROVINCE_CODES.slice();
      var codes = [];
      for (var i = 0; i < provEl.options.length; i++) {
        var v = provEl.options[i].value;
        if (v && v !== "all") codes.push(v);
      }
      return codes;
    }

    /* Kode pos 5 angka dicari langsung ke indeks kode pos, tanpa pindah halaman. */
    function doCodeSearch(code, myRun) {
      outEl.innerHTML = '<p class="result-count">Mencari…</p>';
      fetch("/data/kodepos/" + code.charAt(0) + ".json").then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).then(function (chunk) {
        if (myRun !== runId) return;
        var hits = chunk[code] || [];
        if (!hits.length) {
          outEl.innerHTML = '<div class="result-empty">Kode pos <b>' + esc(code) +
            '</b> tidak ditemukan di data kami. Periksa ke ' +
            '<a href="https://kodepos.posindonesia.co.id/" target="_blank" rel="noopener">pencarian resmi Pos Indonesia</a>.</div>';
          return;
        }
        var html = '<p class="result-count">' + hits.length + " desa/kelurahan memakai kode pos " + esc(code) + '.</p><ul class="result-list">';
        hits.forEach(function (h) {
          var anchor = "desa-" + h[5].replace(/\./g, "-");
          html += '<li><a href="/kecamatan/' + esc(h[4]) + "#" + esc(anchor) + '">' +
            '<span class="r-name">' + esc(h[0]) + "</span>" +
            '<span class="r-meta">Kecamatan ' + esc(h[1]) + ", " + esc(h[2]) + ", " + esc(h[3]) + "</span></a></li>";
        });
        html += "</ul>";
        outEl.innerHTML = html;
      }).catch(function () {
        if (myRun !== runId) return;
        outEl.innerHTML = '<div class="result-empty">Data belum bisa dimuat. Periksa koneksimu lalu coba lagi.</div>';
      });
    }

    function doSearch() {
      var raw = qEl.value.trim();
      var q = norm(raw);
      var myRun = ++runId;
      if (q.length < 2) {
        outEl.innerHTML = "";
        return;
      }
      if (/^\d{5}$/.test(raw)) { doCodeSearch(raw, myRun); return; }
      outEl.innerHTML = '<p class="result-count">Mencari…</p>';
      var codes = provinceCodes();
      Promise.all(codes.map(loadProvince)).then(function (indexes) {
        if (myRun !== runId) return;
        var districtHits = [];
        var villageHits = [];
        var villageTotal = 0;
        indexes.forEach(function (idx) {
          idx.d.forEach(function (d, di) {
            if (norm(d[1]).indexOf(q) !== -1) {
              districtHits.push({ idx: idx, d: d, di: di });
            }
          });
          idx.v.forEach(function (v) {
            if (norm(v[0]).indexOf(q) !== -1) {
              villageTotal++;
              if (villageHits.length < 40) villageHits.push({ idx: idx, v: v });
            }
          });
        });
        if (myRun !== runId) return;
        var html = "";
        var totalShown = districtHits.length + villageHits.length;
        if (totalShown === 0) {
          html = '<div class="result-empty">Tidak ada hasil untuk <b>' + esc(qEl.value.trim()) +
            '</b>. Coba ejaan lain, nama kecamatan, atau periksa ke ' +
            '<a href="https://kodepos.posindonesia.co.id/" target="_blank" rel="noopener">pencarian resmi Pos Indonesia</a>.</div>';
        } else {
          var countText = "Menampilkan " + totalShown + " hasil";
          if (villageTotal > villageHits.length) {
            countText += " dari " + (districtHits.length + villageTotal) + " yang cocok — persempit dengan kata kunci yang lebih spesifik";
          }
          html += '<p class="result-count">' + esc(countText) + ".</p><ul class=\"result-list\">";
          districtHits.slice(0, 8).forEach(function (h) {
            html += '<li><a href="/kecamatan/' + esc(h.d[3]) + '">' +
              '<span class="r-name">Kecamatan ' + esc(h.d[1]) + "</span>" +
              '<span class="r-meta">' + esc(h.d[2]) + ", " + esc(h.idx.p) + " — lihat semua desa/kelurahan</span></a></li>";
          });
          villageHits.forEach(function (h) {
            var d = h.idx.d[h.v[3]];
            var anchor = "desa-" + h.v[4].replace(/\./g, "-");
            var codeBadge = h.v[2]
              ? '<span class="r-code">' + esc(h.v[2]) + "</span>"
              : '<span class="r-code">Belum tersedia</span>';
            html += '<li><a href="/kecamatan/' + esc(d[3]) + "#" + esc(anchor) + '">' +
              '<span class="r-name">' + esc(h.v[0]) + "</span>" + codeBadge +
              '<span class="r-meta">' + (h.v[1] === 1 ? "Kelurahan" : "Desa") +
              " · Kecamatan " + esc(d[1]) + ", " + esc(d[2]) + ", " + esc(h.idx.p) + "</span></a></li>";
          });
          html += "</ul>";
        }
        outEl.innerHTML = html;
      }).catch(function () {
        if (myRun !== runId) return;
        outEl.innerHTML = '<div class="result-empty">Data belum bisa dimuat. Periksa koneksimu lalu coba lagi.</div>';
      });
    }

    qEl.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(doSearch, 250);
    });
    if (provEl) provEl.addEventListener("change", doSearch);
    if (formEl) formEl.addEventListener("submit", function (e) { e.preventDefault(); doSearch(); });
  }

  /* ---------- Pencarian balik: kode pos -> wilayah ---------- */
  var revForm = document.getElementById("reverse-form");
  var revInput = document.getElementById("kodepos-input");
  var revOut = document.getElementById("reverse-results");

  if (revForm && revInput && revOut) {
    revForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var code = revInput.value.trim();
      if (!/^\d{5}$/.test(code)) {
        revOut.innerHTML = '<div class="result-empty">Masukkan 5 angka kode pos, misalnya 23773.</div>';
        return;
      }
      revOut.innerHTML = '<p class="result-count">Mencari…</p>';
      fetch("/data/kodepos/" + code.charAt(0) + ".json").then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).then(function (chunk) {
        var hits = chunk[code] || [];
        if (!hits.length) {
          revOut.innerHTML = '<div class="result-empty">Kode pos <b>' + esc(code) +
            '</b> tidak ditemukan di data kami. Periksa ke ' +
            '<a href="https://kodepos.posindonesia.co.id/" target="_blank" rel="noopener">pencarian resmi Pos Indonesia</a>.</div>';
          return;
        }
        var html = '<p class="result-count">' + hits.length + " desa/kelurahan memakai kode pos " + esc(code) + ".</p><ul class=\"result-list\">";
        hits.forEach(function (h) {
          var anchor = "desa-" + h[5].replace(/\./g, "-");
          html += '<li><a href="/kecamatan/' + esc(h[4]) + "#" + esc(anchor) + '">' +
            '<span class="r-name">' + esc(h[0]) + "</span>" +
            '<span class="r-meta">Kecamatan ' + esc(h[1]) + ", " + esc(h[2]) + ", " + esc(h[3]) + "</span></a></li>";
        });
        html += "</ul>";
        revOut.innerHTML = html;
      }).catch(function () {
        revOut.innerHTML = '<div class="result-empty">Data belum bisa dimuat. Periksa koneksimu lalu coba lagi.</div>';
      });
    });
  }
})();
