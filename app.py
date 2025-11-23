import os
from flask import Flask, request, jsonify, abort, send_from_directory
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from dotenv import load_dotenv

# -----------------------------------------------------------
# Load variabel lingkungan dari file .env jika ada
# -----------------------------------------------------------
load_dotenv()

# -----------------------------------------------------------
# Inisialisasi aplikasi Flask
# static_folder : folder untuk frontend
# static_url_path : URL root untuk file static
# -----------------------------------------------------------
app = Flask(__name__, static_folder='frontend', static_url_path='/')

# -----------------------------------------------------------
# Mengambil konfigurasi database dari environment variable
# Hal ini membuat konfigurasi tidak hardcode di dalam kode
# -----------------------------------------------------------
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = int(os.environ.get('DB_PORT'))
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_NAME = os.environ.get('DB_NAME')

# Key kriptografi untuk stream XOR
XOR_KEY = os.environ.get('XOR_KEY', None)

# Jika key tidak ada, tampilkan peringatan saat aplikasi berjalan
if not XOR_KEY:
    print("WARNING: XOR_KEY not set. Set environment variable XOR_KEY before running.")


# -----------------------------------------------------------
# Fungsi untuk membuka koneksi ke database MySQL
# Koneksi dibuat setiap request dan ditutup setelah selesai
# -----------------------------------------------------------
def get_db_conn():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
        )

        # Aktifkan autocommit jika versi driver mendukung
        try:
            conn.autocommit = True
        except Exception:
            pass

        return conn

    except Error as e:
        print("DB connection error:", e)
        raise


# ===========================================================
#                KRIPTOGRAFI STREAM XOR
# ===========================================================

def xor_stream_bytes(data: bytes, key: bytes) -> bytes:
    """
    Fungsi XOR stream sederhana.
    Setiap byte plaintext di-XOR dengan byte key secara berulang (key modulo panjang).
    """
    if not key:
        raise ValueError('Empty key')

    out = bytearray(len(data))
    klen = len(key)

    # Loop tiap byte dan XOR-kan
    for i, b in enumerate(data):
        out[i] = b ^ key[i % klen]

    return bytes(out)


def encrypt_text(plaintext: str) -> bytes:
    """
    Mengubah plaintext menjadi byte lalu proses XOR.
    Output berupa byte cipher yang disimpan langsung ke database.
    """
    pt = plaintext.encode('utf-8')
    return xor_stream_bytes(pt, XOR_KEY.encode('utf-8'))


def decrypt_bytes(ct: bytes) -> str:
    """
    Dekripsi dilakukan dengan XOR lagi (XOR reversible).
    """
    pt = xor_stream_bytes(ct, XOR_KEY.encode('utf-8'))
    return pt.decode('utf-8', errors='replace')


# ===========================================================
#                     ENDPOINT CRUD API
# ===========================================================

# -----------------------------------------------------------
# GET /notes
# Mengambil daftar semua catatan (tanpa konten)
# -----------------------------------------------------------
@app.route("/notes", methods=["GET"])
def list_notes():
    conn = get_db_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, title, created_at, updated_at FROM notes ORDER BY id DESC")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(rows)


# -----------------------------------------------------------
# GET /notes/<id>
# Mengambil detail 1 catatan termasuk decrypt konten
# -----------------------------------------------------------
@app.route("/notes/<int:note_id>", methods=["GET"])
def get_note(note_id):
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, title, content, created_at, updated_at FROM notes WHERE id=%s", (note_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    # Jika tidak ditemukan -> 404
    if not row:
        abort(404)

    nid, title, content_blob, created_at, updated_at = row

    # Dekripsi content
    content = decrypt_bytes(content_blob)

    return jsonify({
        "id": nid,
        "title": title,
        "content": content,
        "created_at": str(created_at),
        "updated_at": str(updated_at),
    })


# -----------------------------------------------------------
# POST /notes
# Membuat catatan baru
# -----------------------------------------------------------
@app.route("/notes", methods=["POST"])
def create_note():
    data = request.json

    # Ambil data POST JSON
    title = data.get("title", "").strip()
    content = data.get("content", "")

    # Validasi wajib ada title
    if not title:
        return jsonify({"error": "Title is required"}), 400

    # Enkripsi konten sebelum disimpan
    cipher = encrypt_text(content)

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO notes(title, content) VALUES(%s, %s)",
        (title, cipher)
    )

    nid = cur.lastrowid

    cur.close()
    conn.close()

    # Kembalikan ID catatan baru
    return jsonify({"id": nid}), 201


# -----------------------------------------------------------
# PUT /notes/<id>
# Update judul atau isi catatan
# -----------------------------------------------------------
@app.route("/notes/<int:note_id>", methods=["PUT"])
def update_note(note_id):
    data = request.json
    title = data.get("title")
    content = data.get("content")

    conn = get_db_conn()
    cur = conn.cursor()

    # Cek apakah ID ada di database
    cur.execute("SELECT id FROM notes WHERE id=%s", (note_id,))
    exists = cur.fetchone()

    if not exists:
        abort(404)

    # Update sesuai request
    if title and content:
        cipher = encrypt_text(content)
        cur.execute("UPDATE notes SET title=%s, content=%s WHERE id=%s", (title, cipher, note_id))
    elif title:
        cur.execute("UPDATE notes SET title=%s WHERE id=%s", (title, note_id))
    elif content:
        cipher = encrypt_text(content)
        cur.execute("UPDATE notes SET content=%s WHERE id=%s", (cipher, note_id))

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"ok": True})


# -----------------------------------------------------------
# DELETE /notes/<id>
# Menghapus catatan berdasarkan ID
# -----------------------------------------------------------
@app.route("/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM notes WHERE id=%s", (note_id,))
    affected = cur.rowcount

    cur.close()
    conn.close()

    # Jika tidak ada baris yang terhapus → data tidak ditemukan
    if affected == 0:
        abort(404)

    return jsonify({"ok": True})


# -----------------------------------------------------------
# ROUTE FRONTEND
# Menampilkan halaman index.html di folder frontend
# -----------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


# -----------------------------------------------------------
# Main entry point aplikasi
# host=0.0.0.0 agar bisa diakses dari jaringan
# debug=True untuk memunculkan error detail
# -----------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
