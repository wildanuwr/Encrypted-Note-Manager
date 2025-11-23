#!/usr/bin/env python3
"""
Encrypted Notes Manager
Flask API yang melakukan CRUD ke MySQL dan menyimpan `content` terenkripsi
menggunakan stream XOR sederhana.

Environment variables:
- DB_HOST (default 127.0.0.1)
- DB_PORT (default 3306)
- DB_USER
- DB_PASS
- DB_NAME (default encrypted_notes)
- XOR_KEY (required; untuk demo gunakan string yang cukup panjang)

Run: python app.py

Note: for demonstration/teaching only. XOR stream sederhana TIDAK aman untuk produksi.
"""

import os
from flask import Flask, request, jsonify, abort, send_from_directory
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, static_folder='frontend', static_url_path='/')

# Config from env
DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('DB_PORT', '3306'))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')
DB_NAME = os.environ.get('DB_NAME', 'encrypted_notes')
XOR_KEY = os.environ.get('XOR_KEY', None)

if not XOR_KEY:
    print("WARNING: XOR_KEY not set. Set environment variable XOR_KEY before running.")


def get_db_conn():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
        )
        # enable autocommit if desired
        try:
            conn.autocommit = True
        except Exception:
            # some connector versions use connection.autocommit attribute, ignore if not supported
            pass
        return conn
    except Error as e:
        print("DB connection error:", e)
        raise


# ---- XOR stream implementation ----

def xor_stream_bytes(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError('Empty key')
    out = bytearray(len(data))
    klen = len(key)
    for i, b in enumerate(data):
        out[i] = b ^ key[i % klen]
    return bytes(out)


def encrypt_text(plaintext: str) -> bytes:
    pt = plaintext.encode('utf-8')
    return xor_stream_bytes(pt, XOR_KEY.encode('utf-8'))


def decrypt_bytes(ct: bytes) -> str:
    pt = xor_stream_bytes(ct, XOR_KEY.encode('utf-8'))
    return pt.decode('utf-8', errors='replace')

@app.route("/notes", methods=["GET"])
def list_notes():
    conn = get_db_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, title, created_at, updated_at FROM notes ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/notes/<int:note_id>", methods=["GET"])
def get_note(note_id):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, content, created_at, updated_at FROM notes WHERE id=%s", (note_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        abort(404)

    nid, title, content_blob, created_at, updated_at = row
    content = decrypt_bytes(content_blob)

    return jsonify({
        "id": nid,
        "title": title,
        "content": content,
        "created_at": str(created_at),
        "updated_at": str(updated_at),
    })


@app.route("/notes", methods=["POST"])
def create_note():
    data = request.json
    title = data.get("title", "").strip()
    content = data.get("content", "")

    if not title:
        return jsonify({"error": "Title is required"}), 400

    cipher = encrypt_text(content)

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO notes(title, content) VALUES(%s, %s)", (title, cipher))
    nid = cur.lastrowid
    cur.close()
    conn.close()

    return jsonify({"id": nid}), 201


@app.route("/notes/<int:note_id>", methods=["PUT"])
def update_note(note_id):
    data = request.json

    title = data.get("title")
    content = data.get("content")

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM notes WHERE id=%s", (note_id,))
    exists = cur.fetchone()
    if not exists:
        abort(404)

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


@app.route("/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes WHERE id=%s", (note_id,))
    affected = cur.rowcount
    cur.close()
    conn.close()

    if affected == 0:
        abort(404)

    return jsonify({"ok": True})

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
