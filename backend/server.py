from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import time
import tempfile
from google.cloud import secretmanager

app = Flask(__name__)

# --- KONFIGURASI CORS ---
# Izinkan domain spesifik agar lebih aman, tapi tetap fleksibel
CORS(app, resources={r"/*": {
    "origins": [
        "https://yt-downloads.vercel.app",  # Domain Production
        "http://localhost:3000",            # React Local
        "http://localhost:5173",            # Vite Local
        "*"                                 # Fallback (bisa dihapus nanti jika sudah stable)
    ]
}})

# --- KONFIGURASI PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = tempfile.gettempdir() # /tmp di Linux atau %TEMP% di Windows

# Path File Cookies
LOCAL_COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")
TEMP_COOKIES_PATH = os.path.join(OUTPUT_DIR, "cookies.txt")

# Nama Secret di Google Cloud (Pastikan SAMA PERSIS dengan di Console)
SECRET_ID = "cookie"  # <-- Pastikan nama secret di GCP adalah 'cookie' atau 'youtube-cookies'

# ==========================================
# 1. DEFINISI FUNGSI HELPER (WAJIB DI ATAS)
# ==========================================

def get_secret(secret_name):
    """Mengambil data dari Google Secret Manager"""
    try:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            # Jika running lokal tanpa env var project, skip secret manager
            return None
            
        client = secretmanager.SecretManagerServiceClient()
        # Format path: projects/{id}/secrets/{name}/versions/latest
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Gagal ambil Secret '{secret_name}': {e}")
        return None

def get_valid_cookies_path():
    """
    Logika pintar memilih cookies: 
    1. Prioritas Lokal (Dev)
    2. Cache /tmp (Supaya cepat)
    3. Secret Manager (Cloud Run Production)
    """
    
    # 1. Cek Lokal (Prioritas Dev di Laptop)
    if os.path.exists(LOCAL_COOKIES_PATH) and os.path.getsize(LOCAL_COOKIES_PATH) > 0:
        print(f"🍪 [AUTH] Memakai Cookies LOKAL: {LOCAL_COOKIES_PATH}")
        return LOCAL_COOKIES_PATH

    # 2. Cek Cache di /tmp (Supaya gak panggil Secret Manager terus-terusan)
    if os.path.exists(TEMP_COOKIES_PATH) and os.path.getsize(TEMP_COOKIES_PATH) > 0:
        print(f"🍪 [AUTH] Memakai Cookies CACHE: {TEMP_COOKIES_PATH}")
        return TEMP_COOKIES_PATH

    # 3. Ambil dari Secret Manager (Khusus Cloud Run)
    print("🔄 [AUTH] Cookies tidak ada di cache. Mengambil dari Secret Manager...")
    secret_data = get_secret(SECRET_ID)
    
    if secret_data:
        try:
            # Tulis ke /tmp agar bisa dibaca yt-dlp
            with open(TEMP_COOKIES_PATH, "w") as f:
                f.write(secret_data)
            print(f"✅ [AUTH] Cookies sukses didownload ke: {TEMP_COOKIES_PATH}")
            return TEMP_COOKIES_PATH
        except Exception as e:
            print(f"❌ Error menulis file cookies ke temp: {e}")
            return None
    
    print("⚠️ [AUTH] Gagal memuat Cookies. Download mungkin akan error 429/Sign-in.")
    return None

# ==========================================
# 2. INITIALIZATION (JALAN SAAT STARTUP)
# ==========================================

# Variable Global untuk menyimpan path cookies yang valid
CURRENT_COOKIES_FILE = get_valid_cookies_path()
print(f"🚀 SERVER STARTUP - Cookies Path: {CURRENT_COOKIES_FILE}")


# ==========================================
# 3. ROUTES
# ==========================================

@app.route("/", methods=["GET"])
def home():
    """Endpoint untuk health check"""
    cookies_status = False
    if CURRENT_COOKIES_FILE and os.path.exists(CURRENT_COOKIES_FILE):
        cookies_status = True
        
    return jsonify({
        "status": "online",
        "backend": "Flask + yt-dlp",
        "cookies_loaded": cookies_status,
        "cookies_source": CURRENT_COOKIES_FILE if cookies_status else "None"
    })

@app.route("/video-info", methods=["GET"])
def get_video_info():
    """Mengambil metadata video"""
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify(success=False, error="Missing video ID"), 400

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        # Cek ulang cookies siapa tau baru ada update/terhapus dari cache
        cookie_path = get_valid_cookies_path()
        # Update ydl_opts dengan trik "Android Client"
        ydl_opts = {
            "quiet": False,
            "no_warnings": False,
            "cookiefile": cookie_path,
            "socket_timeout": 30,
            
            # [TRIK JITU] Memaksa yt-dlp berpura-pura jadi HP Android / TV
            # Ini seringkali membypass cek "Sign in to confirm you're not a bot"
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"],
                    "player_skip": ["webpage", "configs", "js"],
                    "include_ssl_logs": [False] 
                }
            },
            
            # Hapus cache user agent, gunakan yang dibuat yt-dlp
            "cachedir": False,
            "nocheckcertificate": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Ambil thumbnail terbaik
        thumbnail_url = info.get("thumbnail", "")
        if info.get("thumbnails"):
            thumbnail_url = max(info["thumbnails"], key=lambda x: x.get("height", 0))["url"]

        return jsonify(
            success=True,
            title=info.get("title", "Unknown"),
            duration=info.get("duration", 0),
            thumbnail=thumbnail_url,
            author=info.get("uploader", "Unknown"),
        )

    except Exception as e:
        print(f"Error fetching info: {e}")
        return jsonify(success=False, error=str(e)), 400


@app.route("/download", methods=["POST"])
def download_video():
    """Proses download dan streaming"""
    print("\n--- 🟢 REQUEST DOWNLOAD MASUK ---")
    try:
        data = request.get_json()
        video_id = data.get("video_id")
        title = data.get("title", "video")
        format_type = data.get("format", "mp4").lower()

        if not video_id:
            return jsonify(success=False, error="Missing video ID"), 400

        # --- SETUP PATH & FILENAME ---
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Timestamp dibuat SEKALI di sini agar konsisten
        epoch_time = int(time.time())
        
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip() or "video"
        
        # Base name yang unik
        filename_base = f"{safe_title}_{video_id}_{epoch_time}"
        temp_filepath_template = os.path.join(OUTPUT_DIR, f"{filename_base}.%(ext)s")

        print(f"📍 Target Folder: {OUTPUT_DIR}")
        print(f"📍 Filename Pattern: {filename_base}")

        # --- CEK FFMPEG (KHUSUS WINDOWS LOCAL) ---
        local_ffmpeg = os.path.join(BASE_DIR, "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            print(f"✅ FFmpeg lokal terdeteksi di: {local_ffmpeg}")
            # Tambahkan ke PATH environment sementara process ini berjalan
            os.environ["PATH"] += os.pathsep + BASE_DIR
        
        # --- KONFIGURASI YT-DLP ---
        cookie_path = get_valid_cookies_path()
        
     # Update ydl_opts dengan trik "Android Client"
        ydl_opts = {
            "quiet": False,
            "no_warnings": False,
            "cookiefile": cookie_path,
            "socket_timeout": 30,
            
            # [TRIK JITU] Memaksa yt-dlp berpura-pura jadi HP Android / TV
            # Ini seringkali membypass cek "Sign in to confirm you're not a bot"
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"],
                    "player_skip": ["webpage", "configs", "js"],
                    "include_ssl_logs": [False] 
                }
            },
            
            # Hapus cache user agent, gunakan yang dibuat yt-dlp
            "cachedir": False,
            "nocheckcertificate": True,
            "noplaylist": True,
        }
        
        if format_type == "mp3":
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                }],
            })
        else:
            ydl_opts.update({
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
            })

        print(f"⏳ Sedang mendownload: {video_id}...")

        # --- EKSEKUSI DOWNLOAD ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print("✅ Download yt-dlp selesai. Mencari file hasil...")

        # --- CARI FILE HASIL ---
        found_file = None
        # Cari file yang diawali dengan filename_base yang kita buat tadi
        for file in os.listdir(OUTPUT_DIR):
            if file.startswith(filename_base):
                found_file = os.path.join(OUTPUT_DIR, file)
                break

        if not found_file:
            print("❌ FILE TIDAK KETEMU!")
            print(f"   Dicari prefix: {filename_base}")
            try:
                print(f"   Isi folder {OUTPUT_DIR}: {os.listdir(OUTPUT_DIR)[:5]}...")
            except: pass
            
            return jsonify(
                success=False, 
                error="File berhasil didownload tapi gagal ditemukan (Cek FFmpeg Merge)"
            ), 500

        print(f"✅ File ditemukan: {found_file}")

        # --- STREAMING RESPONSE ---
        final_filename = f"{safe_title}.{format_type}"
        mimetype = "audio/mpeg" if format_type == "mp3" else "video/mp4"

        def generate_file_stream(file_path):
            try:
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk: break
                        yield chunk
            finally:
                # Cleanup: Hapus file setelah selesai dikirim ke user
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"🧹 File dihapus: {file_path}")
                except Exception as e:
                    print(f"⚠️ Gagal menghapus file temp: {e}")

        return Response(
            generate_file_stream(found_file),
            mimetype=mimetype,
            headers={"Content-Disposition": f'attachment; filename="{final_filename}"'},
        )

    except Exception as e:
        print(f"\n❌ ERROR FATAL DI PYTHON:\n{str(e)}")
        import traceback
        traceback.print_exc()

        return jsonify(success=False, error=f"Server Error: {str(e)}"), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)