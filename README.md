# Retail HQ Multi-Agent Analytics

Simulasi kantor pusat retail: 13 agent virtual (Operation, Merchandise, Finance, HR, Legal, Store Dev, Supply Chain, DC, IT, Marketing/CRM, Loss Prevention, ESG, GM) menganalisa data 50 toko fiktif di Bali lewat bot Telegram.

Stack: Python (uv) → BigQuery (raw/staging/mart) → dbt Core → Google ADK + Gemini → Telegram, Looker Studio, dashboard HTML.

## Status

- [x] Tahap 1a: generator data dummy (32 tabel, 2 tahun, seed tetap)
- [x] Tahap 1b: load ke BigQuery (`uv run load-bq`)
- [x] Tahap 1c: dbt staging + mart + tests (`uv run dbt-rhq build`)
- [x] Tahap 2: dashboard Looker Studio + HTML (`uv run export-dashboard`)
- [x] Tahap 3: 13 agent + bot Telegram (`uv run rhq-bot`, uji: `uv run rhq-eval`)
- [ ] Tahap 4: Data Mode (upload data asli, validasi, reset)
- [ ] Tahap 5: deploy Cloud Run + dokumentasi

## Mulai cepat

```bash
uv sync
uv run generate-data          # output ke data/raw
uv run generate-data --seed 7 # dataset lain dengan pola yang sama
uv run load-bq                # muat data/raw ke dataset raw di BigQuery
uv run dbt-rhq debug          # cek koneksi dbt ke BigQuery
uv run dbt-rhq build          # seed + staging + mart + semua test
```

Setup akun dan install lengkap: [docs/SETUP.md](docs/SETUP.md).

## Dashboard HTML

Satu file HTML tanpa dependensi (SVG manual, tanpa CDN): 5 halaman (Ringkasan, Operation, Merchandise, Finance, Supply Chain), filter bulan, kabupaten, AM, lokasi, dan tipe toko. Rasio dihitung ulang dari jumlah di browser, sama seperti Looker Studio.

```bash
uv run export-dashboard               # tarik mart dari BigQuery, tulis dashboard/data.json + dist/index.html
uv run export-dashboard --build-only  # build ulang HTML dari data.json (tanpa query)
```

Buka `dashboard/dist/index.html` langsung di browser. Spesifikasi Looker Studio: [docs/LOOKER_SPEC.md](docs/LOOKER_SPEC.md).

## Agent & bot Telegram (Tahap 3)

GM (koordinator) memanggil agent department yang relevan dari 12 department: Operation, Merchandise, Finance, Supply Chain, DC, HR, Loss Prevention, IT, Marketing & CRM, ESG, Legal, Store Development. Agent membaca mart BigQuery lewat tool berisi query tetap (tidak menulis SQL bebas), memakai Gemini lewat Google ADK.

```bash
uv run rhq-ask --tools                         # cek semua tool BigQuery (tanpa Gemini)
uv run rhq-ask "Toko mana yang EBITDA-nya negatif?"
uv run rhq-ask                                 # mode percakapan di Terminal
uv run rhq-bot                                 # jalankan bot Telegram (Ctrl+C untuk berhenti)
uv run rhq-eval                                # uji 13 pertanyaan berjawaban pasti (pola di answer key)
```

Isi `GEMINI_API_KEY` dan `TELEGRAM_BOT_TOKEN` di `.env`. Bot jalan selama Terminal terbuka (mode polling, tanpa server). Kuota gratis Gemini terbatas per menit; satu pertanyaan memakai beberapa panggilan model.

## Data dummy

- 50 toko (Denpasar 14, Badung 14, Gianyar 7, Tabanan 5, Buleleng 5, Klungkung 2, Karangasem 2, Bangli 1), 300 SKU, 25 supplier, 1 DC di Denpasar
- Periode 1 Nov 2024 s.d. 31 Okt 2026
- Musiman Bali: Nyepi (toko tutup, lonjakan H-1/H-2), Galungan/Kuningan (lonjakan Kebutuhan Upacara), high season Jul–Agu dan akhir tahun, efek kecil Lebaran dan Natal
- Konsisten: kategori harian = total toko harian; SKU mingguan = kategori per minggu (sampai rupiah)
- Tidak ada baris = toko tutup (Nyepi) atau belum buka
- Validasi otomatis sebelum file ditulis: primary key unik, foreign key, nilai negatif, rekonsiliasi total

Konvensi file: tanggal `YYYY-MM-DD`, waktu `YYYY-MM-DD HH:MM:SS`, uang dalam rupiah utuh, boolean `true/false`. Dua tabel besar (`fact_sales_sku_weekly`, `fact_stock_weekly`) ditulis sebagai `.csv.gz`.

Catatan ESG: karena Bali membatasi kantong plastik sekali pakai, `plastic_bags_used` = kantong plastik kecil untuk produk curah/fresh, `plastic_bags_sold` = tas belanja guna ulang yang terjual.

Data sengaja berisi beberapa pola untuk ditemukan agent. Kuncinya ada di `data/_answer_key.md` (tidak dimuat ke BigQuery).

Semua nama toko, orang, merek, dan supplier fiktif. Angka adalah asumsi simulasi, bukan data perusahaan mana pun.

## Layer data (BigQuery)

| Dataset | Isi | Dibuat oleh |
|---|---|---|
| `raw` | 32 tabel CSV apa adanya | `uv run load-bq` |
| `staging` | 32 view `stg_*` (kolom eksplisit) + seed `bali_calendar` | dbt |
| `mart` | Tabel siap analisa per department | dbt |

Mart utama:

| Tabel | Grain | Dipakai untuk |
|---|---|---|
| `mart_store_monthly` | bulan x toko | Sales, SPD, STD, AMB, achievement, YoY, opex, EBITDA, HR, OOS, shrink, IT, energi, display |
| `fct_sales_store_daily` | hari x toko | Tren harian, efek Nyepi/Galungan |
| `mart_category_monthly` | bulan x toko x kategori | Margin, kontribusi, YoY kategori |
| `mart_oos_weekly` | minggu x toko x SKU | OOS vs SOH 0 vs di bawah min stock, estimasi lost sales |
| `mart_supplier_monthly` | bulan x supplier | Fill rate, on-time, delay |
| `mart_dc_store_monthly` | bulan x toko | Fill rate dan biaya kirim DC |
| `mart_cashier_monthly` | bulan x kasir | Void, refund, selisih kas |
| `mart_member_monthly` | bulan x tipe member | Member aktif, retensi |
| `mart_campaign_performance` | campaign | Uplift (difference-in-differences) dan ROI |
| `mart_planogram_compliance_monthly` | bulan x toko | Kepatuhan facing, price tag, shelf talker |
| `mart_contract_status` | kontrak | Sisa hari sewa/izin/vendor |
| `mart_store_dev` | proyek capex | Payback toko baru |

Tes otomatis: primary key unik, foreign key, nilai yang diizinkan, rekonsiliasi kategori vs toko, total mart vs sumber, dan rentang rasio.
