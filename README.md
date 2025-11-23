# Encrypted Notes Manager
![Tampilan Aplikasi](image/Screenshot_1.png)

Aplikasi sederhana yang melakukan operasi CRUD pada database MySQL sambil mengenkripsi field `content` menggunakan cipher Stream XOR . Proyek ini untuk tujuan pembelajaran — **jangan** gunakan cipher ini di lingkungan produksi.

## Fitur
- Buat, Baca, Perbarui, Hapus catatan
- Konten disimpan terenkripsi dengan stream XOR
- Frontend web sederhana

## Persyaratan
- Python 3.8+
- MySQL / MariaDB

## Persiapan
1. Buat database dan tabel:
    ```bash
    mysql -u root -p < sql/dump_notes.sql
    ```
2. Buat virtualenv dan install dependency:
    ```bash
    pip install -r requirements.txt
    ```
3. Export variabel lingkungan:
    ```bash
    export DB_HOST=127.0.0.1
    export DB_PORT=3306
    export DB_USER=root
    export DB_PASS=yourpassword
    export DB_NAME=encrypted_notes
    export XOR_KEY="kunci_rahasia"
    ```
    (Di Windows gunakan cara yang sesuai untuk mengatur environment variables)
4. Jalankan aplikasi:
    ```bash
    python app.py
    ```
5. Buka `http://127.0.0.1:5000/` untuk menggunakan frontend, atau gunakan curl/Postman untuk memanggil API.

## Endpoint API
- `GET /notes` — daftar catatan (metadata)
- `GET /notes/<id>` — ambil dan dekripsi isi catatan
- `POST /notes` — buat catatan `{title, content}`
- `PUT /notes/<id>` — perbarui (title dan/atau content)
- `DELETE /notes/<id>` — hapus catatan

## Catatan Keamanan
- Stream XOR pada repo ini sengaja dibuat sederhana untuk tujuan pengajaran. Kelemahan:
  - Menggunakan kembali kunci dapat membocorkan informasi
  - Tidak ada autentikasi / tidak ada pemeriksaan integritas
  - Panjang kunci berpengaruh pada keamanan
- Untuk sistem produksi, gunakan AES-GCM atau mode enkripsi terautentikasi lainnya.
