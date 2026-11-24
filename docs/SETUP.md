# Tahap 1 — Setup akun & install (Mac, kompatibel Windows)

Target: semua gratis. Kerjakan berurutan. Perintah Mac di Terminal, perintah Windows di PowerShell.

## A. Akun (sekali saja)

| # | Akun | Untuk apa | Kartu kredit? |
|---|---|---|---|
| 1 | Google account (boleh Gmail pribadi) | BigQuery, Looker Studio, Gemini | Tidak |
| 2 | Google Cloud project + **BigQuery Sandbox** | Gudang data raw/staging/mart | Tidak |
| 3 | GitHub | Simpan kode, portfolio, GitHub Pages | Tidak |
| 4 | Telegram + BotFather | Bot agent (baru dipakai di Tahap 3) | Tidak |
| 5 | Google AI Studio (Gemini API key) | Otak agent (baru dipakai di Tahap 3) | Tidak |

### Langkah BigQuery Sandbox
1. Buka https://console.cloud.google.com/bigquery dan login.
2. Buat project baru, contoh nama `retail-hq`. Catat **Project ID** (bisa beda dari nama, misal `retail-hq-482113`).
3. Ikuti tawaran "BigQuery sandbox". Jangan masukkan kartu kredit.

**Batasan Sandbox yang perlu diketahui:**
- Tabel otomatis terhapus setelah 60 hari. Tidak masalah: data dummy bisa dibuat ulang dan dimuat ulang dengan satu perintah.
- Tidak bisa DML (INSERT/UPDATE/DELETE). Tahap 1–2 aman karena dbt membuat tabel dengan `CREATE TABLE AS`.
- Di Tahap 3, tabel `agent_actions` butuh INSERT/UPDATE. Pilihannya nanti: aktifkan billing (tetap Rp0 dalam free tier 10 GB storage + 1 TB query/bulan, wajib pasang budget alert) atau simpan `agent_actions` di luar BigQuery. Diputuskan saat masuk Tahap 3.

## B. Install di Mac

1. **Command Line Tools (berisi git)**
   ```bash
   xcode-select --install
   git --version
   ```
2. **uv** (sekaligus mengurus Python, tidak perlu install Python manual)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   Tutup Terminal, buka lagi, lalu cek: `uv --version`
3. **Google Cloud CLI (gcloud + bq)**: ikuti installer macOS di https://cloud.google.com/sdk/docs/install (pilih versi Intel/x86_64 atau Apple Silicon sesuai Mac). Lalu:
   ```bash
   gcloud init
   gcloud auth application-default login
   ```
4. **VS Code**: sudah ada di Mac. Pasang extension "Python" dan "Rainbow CSV".

## C. Install di Windows (untuk uji kompatibilitas, misalnya di Parallels)

```powershell
winget install --id Git.Git -e
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Tutup PowerShell, buka lagi, cek `git --version` dan `uv --version`. Google Cloud CLI: unduh installer Windows dari https://cloud.google.com/sdk/docs/install.

## D. Siapkan project & generate data

1. Ekstrak `retail-hq.zip` ke folder kerja, misalnya `~/Projects/retail-hq` (Mac) atau `C:\Users\<nama>\Projects\retail-hq` (Windows).
2. Di folder itu:
   ```bash
   uv sync
   uv run generate-data
   ```
   Pertama kali, uv mengunduh Python 3.12 dan library (sekitar 1–2 menit). Generate data sekitar 10–30 detik.
3. Salin `.env.example` menjadi `.env`, isi `GCP_PROJECT_ID`.
   - Mac: `cp .env.example .env`
   - Windows: `Copy-Item .env.example .env`
4. Hasil ada di `data/raw/` (32 tabel). `data/raw/_manifest.csv` berisi jumlah baris per tabel. Data dengan seed yang sama selalu identik di Mac dan Windows.

## E. Simpan ke GitHub

```bash
git init
git add .
git commit -m "Tahap 1: generator data dummy"
```
Buat repo baru di GitHub (boleh private dulu), lalu ikuti perintah `git remote add origin ...` dan `git push` yang ditampilkan GitHub. Folder `data/` dan file `.env` sudah dikecualikan lewat `.gitignore`.

## Cek berhasil

- [ ] `uv --version`, `git --version`, `gcloud --version` jalan
- [ ] `uv run generate-data` selesai dengan tulisan "validasi lolos"
- [ ] BigQuery console terbuka di project kamu (mode Sandbox)
- [ ] Repo GitHub berisi kode tanpa folder `data/`

## F. Muat ke BigQuery dan jalankan dbt

```bash
uv run load-bq            # 32 tabel ke dataset raw, cek jumlah baris
uv run dbt-rhq debug      # harus: All checks passed!
uv run dbt-rhq build      # seed + staging + mart + test (hasil 24 Nov 2026: PASS=202)
```
Di Sandbox tabel terhapus setelah 60 hari: jalankan ulang `uv run load-bq` lalu `uv run dbt-rhq build`.

## Masalah yang pernah muncul

| Gejala | Penyebab | Solusi |
|---|---|---|
| `gcloud: command not found` setelah install | Terminal pakai bash, installer menulis PATH ke file yang tidak dibaca | Tambahkan `source "$HOME/google-cloud-sdk/path.bash.inc"` ke `~/.bash_profile` |
| `tar: Unrecognized archive format` | Unduhan lewat browser tidak lengkap | Unduh dengan `curl -O ...` dari Terminal |
| `bq lscurl` / `shbq` | Dua perintah tertempel jadi satu baris | Tempel satu baris, tekan Enter, baru baris berikutnya |
| `Failed to build cryptography` | Versi 49+ tidak punya paket Mac Intel | Sudah dikunci ke 48.x di `pyproject.toml` |
| `Failed to build dbt-core-experimental-parser` (SSL) | dbt-core 1.12 mengunduh komponen dari GitHub | Sudah dikunci ke dbt-core 1.11.x |
