# Tahap 2 — Spesifikasi dashboard Looker Studio (v1)

Cakupan v1: Ringkasan Eksekutif, Operation, Merchandise, Finance, Supply Chain.
Sumber: dataset `mart` di BigQuery (hasil `uv run dbt-rhq build`).

## 1. Aturan penting

- **Rasio selalu dihitung ulang dari jumlah**, jangan rata-rata kolom rasio. Contoh AMB = `SUM(net_sales) / SUM(std)`, bukan `AVG(amb)`. Kolom rasio di tabel (misal `amb`, `achievement`) hanya untuk tabel per toko per bulan.
- Dimensi tanggal: `month` (DATE), kecuali halaman harian memakai `sales_date`.
- Filter lintas halaman memakai nama kolom yang sama di semua sumber: `regency`, `am_name`, `ak_name`, `location_type`, `store_type`.
- Periode data: Nov 2024 s.d. Okt 2026. Default date range laporan: **Nov 2025 – Okt 2026**, perbandingan **Previous year**.

## 2. Data source

Buat dari **Create → Data source → BigQuery → My Projects → `<project>` → `mart` → tabel**. Ganti nama data source sesuai kolom pertama.

| Nama data source | Tabel | Dipakai di halaman |
|---|---|---|
| DS Store Monthly | `mart_store_monthly` | Ringkasan, Operation, Finance, Supply Chain |
| DS Sales Daily | `fct_sales_store_daily` | Operation |
| DS Category Monthly | `mart_category_monthly` | Merchandise |
| DS Campaign | `mart_campaign_performance` | Merchandise |
| DS Planogram | `mart_planogram_compliance_monthly` | Merchandise |
| DS OOS SKU | `mart_oos_sku_monthly` | Supply Chain |
| DS Supplier | `mart_supplier_monthly` | Supply Chain |
| DS DC | `mart_dc_store_monthly` | Supply Chain |

`fct_sales_store_daily` tidak punya `regency`/`am_name`; di halaman Operation pakai filter `store_code` untuk grafik harian.

## 3. Calculated field (dibuat di data source, tombol **Add a field**)

**DS Store Monthly**

| Nama | Formula | Format |
|---|---|---|
| Net Sales | `SUM(net_sales)` | Currency (IDR) |
| SPD | `SUM(net_sales) / SUM(open_days)` | Currency (IDR) |
| STD per Hari | `SUM(std) / SUM(open_days)` | Number |
| AMB | `SUM(net_sales) / SUM(std)` | Currency (IDR) |
| Achievement | `SUM(net_sales) / SUM(target_sales)` | Percent |
| GM % | `SUM(gross_profit) / SUM(net_sales)` | Percent |
| EBITDA | `SUM(ebitda)` | Currency (IDR) |
| EBITDA % | `SUM(ebitda) / SUM(net_sales)` | Percent |
| Rent % | `SUM(rent) / SUM(net_sales)` | Percent |
| Labor Cost % | `SUM(salary) / SUM(net_sales)` | Percent |
| Opex vs Budget | `SUM(total_opex) / SUM(budget_opex)` | Percent |
| OOS Rate | `SUM(oos_sku_weeks) / SUM(sku_weeks)` | Percent |
| SOH 0 Rate | `SUM(soh_zero_sku_weeks) / SUM(sku_weeks)` | Percent |
| Display Compliance | `SUM(compliant_items) / SUM(audited_items)` | Percent |
| Toko Capai Target | `CASE WHEN achievement >= 1 THEN 1 ELSE 0 END` | Number (dipakai dengan SUM) |

**DS Category Monthly**: Net Sales `SUM(net_sales)`, GM % `SUM(gross_profit) / SUM(net_sales)`.

**DS Planogram**: Facing Compliance `SUM(compliant_items) / SUM(audited_items)`.

**DS OOS SKU**: OOS Rate `SUM(oos_store_weeks) / SUM(store_weeks)`.

**DS Supplier**: Fill Rate `SUM(qty_received) / SUM(qty_ordered)`, On-time `SUM(on_time_lines) / SUM(po_lines)`.

**DS DC**: Fill Rate `SUM(qty_shipped) / SUM(qty_requested)`, On-time `SUM(on_time_shipments) / SUM(shipments)`, Biaya per Unit `SUM(delivery_cost) / SUM(qty_shipped)`.

## 4. Halaman

Header semua halaman: judul, **Date range control**, **Drop-down** `regency`, `am_name`, `location_type`, `store_type`. Saat membuat filter, set **"Report-level"** (klik kanan → Make report-level) supaya berlaku di semua halaman.

### Hal 1 — Ringkasan Eksekutif (DS Store Monthly)
1. Scorecard (8): Net Sales, SPD, STD per Hari, AMB, Achievement, GM %, EBITDA %, OOS Rate. Comparison date range: **Previous year**.
2. Time series: dimensi `month`; metrik Net Sales (bar) dan `SUM(target_sales)` (garis).
3. Tabel per `regency`: Net Sales, SPD, Achievement, EBITDA %, OOS Rate. Heatmap pada Achievement.
4. Bar horizontal: 10 toko Achievement terendah (dimensi `store_code`, sort Achievement naik, limit 10).

### Hal 2 — Operation
1. Scorecard: SPD, STD per Hari, AMB, Achievement, jumlah toko capai target (`SUM(Toko Capai Target)`) — DS Store Monthly.
2. Tabel per `am_name` dan `ak_name`: Net Sales, Achievement, SPD, Display Compliance; heatmap Achievement.
3. Time series harian (DS Sales Daily): dimensi `sales_date`, metrik `SUM(net_sales)`; tambahkan filter `store_code` di halaman ini. Lonjakan Nyepi H-1 dan Penampahan Galungan harus terlihat.
4. Tabel toko (dimensi `store_code`, `am_name`): Achievement, `spd_yoy_growth` (agregasi Average), Display Compliance. Sort Achievement naik.

### Hal 3 — Merchandise
1. Bar: Net Sales per `category` (DS Category Monthly), sort turun.
2. Bar: GM % per `category`.
3. Tabel campaign (DS Campaign): `campaign_id`, `campaign_name`, `target_category`, `cost`, `uplift_pct`, `roi`, `incremental_sales`. Sort `roi` naik; conditional formatting merah untuk `roi` < 0.
4. Bar: Facing Compliance per `am_name` (DS Planogram), garis referensi 90%.

### Hal 4 — Finance (DS Store Monthly)
1. Scorecard: Net Sales, EBITDA, EBITDA %, Rent %, Labor Cost %, Opex vs Budget.
2. Stacked column per `month`: `SUM(rent)`, `SUM(salary)`, `SUM(utilities)`, `SUM(maintenance)`, `SUM(promo_cost)`, `SUM(it_cost)`, `SUM(other_cost)`.
3. Tabel per `store_code` (+ `regency`, `location_type`): Net Sales, EBITDA, EBITDA %, Rent %, Labor Cost %. Sort EBITDA % naik; merah untuk < 0.

### Hal 5 — Supply Chain
1. Scorecard: OOS Rate, SOH 0 Rate (DS Store Monthly); Fill Rate supplier (DS Supplier); Fill Rate dan On-time DC (DS DC).
2. Time series OOS Rate per `month` (DS Store Monthly).
3. Tabel **Top SKU OOS berdasarkan jumlah toko** (DS OOS SKU): `sku`, `product_name`, `category`, `supplier_id`, `MAX(stores_oos)`, `MAX(stores_soh_zero)`, `SUM(est_lost_sales)`. Sort `stores_oos` turun, limit 20.
4. Time series Fill Rate per `supplier_name` (DS Supplier), filter supplier yang fill rate-nya pernah < 90%.
5. Tabel DC per `regency` (DS DC): Fill Rate, On-time, Biaya per Unit.

## 5. Cek setelah jadi

- Total Net Sales Hal 1 (semua periode, tanpa filter) = total `net_sales` di `mart_store_monthly`.
- Hal 3: campaign `CMP-2025-07` muncul di urutan ROI terendah.
- Hal 3: AM I Wayan Darmawan facing compliance sekitar 71%, AM lain sekitar 93%.
- Hal 5: fill rate SUP001 turun Agu–Des 2025.
- Data freshness data source: biarkan default 12 jam (hemat kuota BigQuery).

## 6. Catatan implementasi v1 (25 Nov 2026)

Laporan: "Retail HQ - Dashboard v1" — https://datastudio.google.com/reporting/9fa5a159-a084-49ec-b66c-40d05609ee4e

Status: 5 halaman selesai dibangun. Urutan halaman di editor saat ini: Ringkasan, Finance, Supply Chain, Operation, Merchandise. Nama halaman masih "Untitled Page"/"Copy of ..." dan perlu di-rename manual (Page → Manage pages).

Perbedaan dari spesifikasi di atas:
- Calculated field dibuat di level chart (bukan di data source).
- Hal 3: Net Sales dan GM % per `category` digabung jadi satu combo chart (bar Net Sales, garis GM % sumbu kanan).
- Hal 5 no. 4: dua garis "Fill Rate SUP001" vs "Fill Rate supplier lain" per bulan (Year Month). Hanya SUP001 yang fill rate bulanannya < 90% (Agu–Des 2025).
- Hal 5: kartu tambahan On-time DC; time series berisi OOS Rate dan SOH 0 Rate.
- "Toko Capai Target" menghitung **store-month** (bukan jumlah toko unik) karena dijumlah dari baris per toko per bulan.

Gotcha:
- **Format persen**: Display format "Percent" saja tidak cukup untuk calculated field rasio; set **Data type → Numeric → Percent** di editor field. Kolom `spd_yoy_growth` memang bernilai kecil (contoh 0,52%), bukan salah format.
- Date range default report-level (Fixed 1 Nov 2025 – 31 Okt 2026) menimpa semua chart. Akibatnya `CMP-2025-07` (14 Jul–6 Agu 2025) tidak tampil di tabel campaign, dan penurunan SUP001 hanya terlihat Nov–Des 2025. Untuk cek no. 5 di atas, perlebar date range ke Nov 2024.
- Chart (vega) dirender di iframe; klik otomatis langsung ke chart sering gagal — pilih komponen lewat panel/Arrange atau klik di tepi chart.
