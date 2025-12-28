from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import time
import tempfile
from pathlib import Path
from google.cloud import secretmanager

app = Flask(__name__)

CORS(app, resources={r"/*": {
    "origins": [
        "https://yt-downloads.vercel.app",  # Domain Frontend Vercel Kamu
        "http://localhost:3000",            # Localhost React/Nextjs
        "http://localhost:5173",            # Localhost Vite
        "*"                                 # Fallback (opsional, hapus jika mau strict)
    ]
}})

@app.after_request
def after_request(response):
    # Paksa header CORS di setiap response
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


# --- KONFIGURASI PATH ---

# --- DEFINISI PATH (TARUH SETELAH IMPORT) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = tempfile.gettempdir()


# Lokasi file di folder temp (untuk Cloud Run / Secret Manager)
TEMP_COOKIES_PATH = os.path.join(OUTPUT_DIR, "cookies.txt")

# Nama file di folder project (Prioritas 1 - Local Development)
LOCAL_COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")

SECRET_ID = "cookie"

def get_valid_cookies_path():
    """Logika pintar memilih cookies: Lokal -> Cache -> Secret Manager"""
    
    # 1. Cek Lokal (Prioritas Dev di Laptop)
    if os.path.exists(LOCAL_COOKIES_PATH) and os.path.getsize(LOCAL_COOKIES_PATH) > 0:
        print(f"🍪 [AUTH] Memakai Cookies LOKAL: {LOCAL_COOKIES_PATH}")
        return LOCAL_COOKIES_PATH

    # 2. Cek Cache di /tmp (Supaya gak panggil Secret Manager terus-terusan)
    if os.path.exists(TEMP_COOKIES_PATH) and os.path.getsize(TEMP_COOKIES_PATH) > 0:
        print(f"🍪 [AUTH] Memakai Cookies CACHE: {TEMP_COOKIES_PATH}")
        return TEMP_COOKIES_PATH

    # 3. Ambil dari Secret Manager (Khusus Cloud Run)
    print("🔄 [AUTH] Cookies tidak ada. Mengambil dari Secret Manager...")
    secret_data = get_secret(SECRET_ID)
    
    if secret_data:
        try:
            # Tulis ke /tmp agar bisa dibaca yt-dlp
            with open(TEMP_COOKIES_PATH, "w") as f:
                f.write(secret_data)
            print(f"✅ [AUTH] Cookies sukses didownload ke: {TEMP_COOKIES_PATH}")
            return TEMP_COOKIES_PATH
        except Exception as e:
            print(f"❌ Error menulis file cookies: {e}")
            return None
    
    print("⚠️ [AUTH] Gagal memuat Cookies. Download mungkin akan error 429/Sign-in.")
    return None

# Simpan path cookies yang ketemu ke variabel global
CURRENT_COOKIES_FILE = get_valid_cookies_path()

# Function to fetch secret from Cloud Secret Manager
def get_secret(secret_name):
    """Mengambil data dari Google Secret Manager"""
    try:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            print("⚠️ GOOGLE_CLOUD_PROJECT variable not set.")
            return None
            
        client = secretmanager.SecretManagerServiceClient()
        # Format path secret: projects/{id}/secrets/{name}/versions/latest
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Gagal ambil Secret: {e}")
        return None


# Load cookies logic
def setup_cookies():
    global COOKIES_FILE

    # 1. Cek apakah ada file cookies lokal (Prioritas Dev Lokal/Docker Copy)
    if os.path.exists(LOCAL_COOKIES_PATH) and os.path.getsize(LOCAL_COOKIES_PATH) > 0:
        print(f"✅ Found local cookies file: {LOCAL_COOKIES_PATH}")
        COOKIES_FILE = LOCAL_COOKIES_PATH
        return

    # 2. Cek apakah sudah ada di /tmp (Cache Cloud Run)
    if os.path.exists(TEMP_COOKIES_PATH) and os.path.getsize(TEMP_COOKIES_PATH) > 0:
        print(f"✅ Found cached cookies in temp: {TEMP_COOKIES_PATH}")
        COOKIES_FILE = TEMP_COOKIES_PATH
        return

    # 3. Ambil dari Secret Manager (Prioritas Utama untuk Production Cloud Run)
    print("🔄 Fetching cookies from Secret Manager...")
    secret_data = get_secret("youtube-cookies")

    if secret_data:
        try:
            with open(TEMP_COOKIES_PATH, "w") as f:
                f.write(secret_data)
            print(f"✅ Cookies loaded from Secret Manager into {TEMP_COOKIES_PATH}")
            COOKIES_FILE = TEMP_COOKIES_PATH
        except Exception as e:
            print(f"❌ Failed to write cookies file: {e}")
            COOKIES_FILE = None
    else:
        print("⚠️ No cookies found. App will try to run without auth.")
        COOKIES_FILE = None


# Jalankan setup cookies saat aplikasi start
setup_cookies()


@app.route("/", methods=["GET"])
def home():
    return jsonify(
        {
            "status": "online",
            "backend": "Flask + yt-dlp (Fixed)",
            "cookies_present": os.path.exists(COOKIES_FILE),
        }
    )


@app.route("/video-info", methods=["GET"])
def get_video_info():
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify(success=False, error="Missing video ID"), 400

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            # [FIX] HAPUS 'cookies_from_browser'
            # [FIX] Gunakan cookiefile jika ada
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            "cachedir": False,  # Disable cache agar tidak ada token kadaluwarsa
            "socket_timeout": 30,
            "nocheckcertificate": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        thumbnail_url = info.get("thumbnail", "")
        if info.get("thumbnails"):
            thumbnail_url = max(info["thumbnails"], key=lambda x: x.get("height", 0))[
                "url"
            ]

        return jsonify(
            success=True,
            title=info.get("title", "Unknown"),
            duration=info.get("duration", 0),
            thumbnail=thumbnail_url,
            author=info.get("uploader", "Unknown"),
        )

    except Exception as e:
        print(f"Error info: {e}")
        return jsonify(success=False, error=str(e)), 400


@app.route("/download", methods=["POST"])
def download_video():
    print("\n--- 🟢 REQUEST DOWNLOAD MASUK ---")
    try:
        data = request.get_json()
        video_id = data.get("video_id")
        title = data.get("title", "video")
        format_type = data.get("format", "mp4").lower()

        if not video_id:
            return jsonify(success=False, error="Missing video ID"), 400

        # Setup Path
        url = f"https://www.youtube.com/watch?v={video_id}"
        epoch_time = int(time.time())
        safe_title = (
            "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
            or "video"
        )
        filename_base = f"{safe_title}_{video_id}_{epoch_time}"
        temp_filepath_template = os.path.join(OUTPUT_DIR, f"{filename_base}.%(ext)s")

        print(f"📍 Target Folder: {OUTPUT_DIR}")
        print(f"📍 Filename Base: {filename_base}")

        # Cek FFmpeg (Khusus Windows Local)
        # Jika dijalankan lokal dan ffmpeg.exe ada di folder yang sama, tambahkan ke PATH sementara
        local_ffmpeg = os.path.join(BASE_DIR, "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            print(f"✅ FFmpeg lokal terdeteksi di: {local_ffmpeg}")
            os.environ["PATH"] += os.pathsep + BASE_DIR
        else:
            print(
                "⚠️ FFmpeg lokal tidak ditemukan di sebelah server.py (Semoga sudah ada di System PATH)"
            )

        cookie_path = get_valid_cookies_path()
        ydl_opts = {
            "outtmpl": temp_filepath_template,
            "quiet": False,  # Biarkan False biar errornya kelihatan
            "no_warnings": False,
            "socket_timeout": 60,
            # [PENTING] Ini kuncinya:
            "cookiefile": cookie_path,
            # Hapus user agent manual, biarkan yt-dlp yang atur
            # "http_headers": { ... },  <-- JANGAN DIPAKAI
            "nocheckcertificate": True,
            "noplaylist": True,
        }

        # Konfigurasi Format
        if format_type == "mp3":
            ydl_opts.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                        }
                    ],
                }
            )
        else:
            ydl_opts.update(
                {
                    "format": "bestvideo+bestaudio/best",  # Format paling aman
                    "merge_output_format": "mp4",
                }
            )

        print(f"⏳ Sedang mendownload: {video_id}...")

        # PROSES DOWNLOAD
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print("✅ Download yt-dlp selesai. Mencari file hasil...")

        # CARI FILE HASIL
        found_file = None
        files_in_dir = os.listdir(OUTPUT_DIR)  # List semua file buat debug

        for file in files_in_dir:
            if file.startswith(filename_base):
                found_file = os.path.join(OUTPUT_DIR, file)
                break

        if not found_file:
            print("❌ FILE TIDAK KETEMU!")
            print(f"   Dicari prefix: {filename_base}")
            print(f"   Isi folder {OUTPUT_DIR} (5 file pertama): {files_in_dir[:5]}")
            return (
                jsonify(
                    success=False,
                    error="File tidak ditemukan setelah download (Cek FFmpeg)",
                ),
                500,
            )

        print(f"✅ File ditemukan: {found_file}")

        # STREAMING RESPONSE
        final_filename = f"{safe_title}.{format_type}"
        mimetype = "audio/mpeg" if format_type == "mp3" else "video/mp4"

        def generate_file_stream(file_path):
            try:
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        yield chunk
            finally:
                try:
                    os.remove(file_path)
                    print(f"🧹 File dihapus: {file_path}")
                except:
                    pass

        return Response(
            generate_file_stream(found_file),
            mimetype=mimetype,
            headers={"Content-Disposition": f'attachment; filename="{final_filename}"'},
        )

    except Exception as e:
        print(f"\n❌ ERROR FATAL DI PYTHON:\n{str(e)}")
        import traceback

        traceback.print_exc()  # Print error lengkap merah-merah di terminal

        # Kirim pesan error asli ke Frontend biar tau salahnya apa
        return jsonify(success=False, error=f"Server Error: {str(e)}"), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
