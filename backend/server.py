from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import time
import tempfile
from pathlib import Path
from google.cloud import secretmanager

app = Flask(__name__)
CORS(app)  # Mengizinkan akses dari Frontend manapun

# Gunakan folder temporary sistem (C:\Users\...\AppData\Local\Temp di Windows, atau /tmp di Linux)
OUTPUT_DIR = tempfile.gettempdir()

# [FIX] Tentukan path absolut ke cookies.txt (agar selalu ketemu)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")

# Function to fetch secret from Cloud Secret Manager
def get_secret(secret_id, version_id="latest"):
    """Fetch secret from Google Cloud Secret Manager"""
    try:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            return None
        
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching secret: {e}")
        return None

# Load cookies on startup
def load_cookies():
    """Load cookies from file or Cloud Secret Manager"""
    if os.path.exists(COOKIES_FILE):
        print(f"✅ Using local cookies file: {COOKIES_FILE}")
        return COOKIES_FILE
    
    # Try to fetch from Cloud Secret Manager
    print("🔄 Fetching cookies from Cloud Secret Manager...")
    cookies_data = get_secret("cookies")
    
    if cookies_data:
        with open(COOKIES_FILE, "w") as f:
            f.write(cookies_data)
        print(f"✅ Cookies loaded from Cloud Secret Manager")
        return COOKIES_FILE
    
    print("⚠️ No cookies found")
    return None

COOKIES_FILE = load_cookies()

@app.route("/", methods=["GET"])
def home():
    """Halaman depan untuk cek status server"""
    return jsonify({
        "status": "online",
        "message": "Server YouTube Downloader Berjalan! 🚀",
        "backend": "Flask + yt-dlp",
        "version": "1.0.0"
    })

@app.route("/video-info", methods=["GET"])
def get_video_info():
    """Mendapatkan metadata video (judul, thumbnail) tanpa download"""
    video_id = request.args.get("video_id")
    
    if not video_id:
        return jsonify(success=False, error="Missing video ID"), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True, # Hanya ambil info
            "socket_timeout": 15,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "nocheckcertificate": True,
            "noplaylist": True,
            "cachedir": False, # Disable cache to avoid permission/stale issues
        }

        # [FIX] Gunakan path absolut dan print debug log
        if os.path.exists(COOKIES_FILE):
            print(f"✅ Cookies found at: {COOKIES_FILE}")
            ydl_opts["cookiefile"] = COOKIES_FILE
        else:
            print(f"❌ Cookies NOT found at: {COOKIES_FILE}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # Ambil thumbnail resolusi tertinggi
        thumbnail_url = info.get("thumbnail", "")
        if info.get("thumbnails"):
            thumbnail_url = max(info["thumbnails"], key=lambda x: x.get("height", 0))["url"]
        
        return jsonify(
            success=True,
            title=info.get("title", "Unknown"),
            duration=info.get("duration", 0),
            thumbnail=thumbnail_url,
            author=info.get("uploader", "Unknown")
        )
    
    except Exception as e:
        print(f"Error fetching info: {e}")
        return jsonify(success=False, error=str(e)), 400

@app.route("/download", methods=["POST"])
def download_video():
    """Proses download dan streaming file ke user"""
    data = request.get_json()
    video_id = data.get("video_id")
    title = data.get("title", "video")
    format_type = data.get("format", "mp4").lower()
    video_quality = data.get("video_quality", "720")
    audio_quality = data.get("audio_quality", "128")

    if not video_id:
        return jsonify(success=False, error="Missing video ID"), 400

    url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Bersihkan nama file dari karakter aneh
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_title:
        safe_title = "video_download"
    
    # Template nama file sementara di folder /tmp
    # %(ext)s akan otomatis diganti oleh yt-dlp (mp4/mp3/webm)
    temp_filename_template = f"{safe_title}_{int(time.time())}.%(ext)s"
    temp_filepath = os.path.join(OUTPUT_DIR, temp_filename_template)
    
    try:
        ydl_opts = {
            "outtmpl": temp_filepath,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 60,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "nocheckcertificate": True,
            "noplaylist": True,
            "cachedir": False,
        }

        # [FIX] Gunakan path absolut untuk download juga
        if os.path.exists(COOKIES_FILE):
            print(f"✅ Cookies found at: {COOKIES_FILE}")
            ydl_opts["cookiefile"] = COOKIES_FILE
        else:
            print(f"❌ Cookies NOT found at: {COOKIES_FILE}")

        # Konfigurasi spesifik MP3 vs MP4
        if format_type == "mp3":
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(audio_quality),
                }],
            })
        else:
            # Format string untuk kualitas video
            if video_quality == "720":
                format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif video_quality == "480":
                format_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
            elif video_quality == "360":
                format_str = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
            else: # Best available (1080p+)
                format_str = "bestvideo+bestaudio/best"
            
            ydl_opts.update({
                "format": format_str,
                "merge_output_format": "mp4", # Force jadi MP4
            })

        print(f"Starting download: {video_id} [{format_type}]")
        
        # Eksekusi Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Cari file hasil download (karena ekstensi bisa berubah-ubah)
        # Kita cari file yang namanya diawali dengan safe_title dan timestamp tadi
        search_prefix = f"{safe_title}_{int(time.time())}"
        found_file = None
        
        for file in os.listdir(OUTPUT_DIR):
            if file.startswith(search_prefix):
                found_file = os.path.join(OUTPUT_DIR, file)
                break
        
        if not found_file or not os.path.exists(found_file):
            return jsonify(success=False, error="File not found after processing"), 500

        print(f"File ready: {found_file} ({os.path.getsize(found_file)} bytes)")

        # --- GENERATOR UNTUK STREAMING (HEMAT RAM) ---
        def generate_file_stream():
            try:
                with open(found_file, "rb") as f:
                    while True:
                        chunk = f.read(4096) # Baca 4KB per chunk
                        if not chunk:
                            break
                        yield chunk
            finally:
                # Hapus file setelah selesai streaming (Cleanup)
                try:
                    os.remove(found_file)
                    print(f"Cleaned up: {found_file}")
                except Exception as e:
                    print(f"Cleanup failed: {e}")

        # Tentukan nama file akhir untuk user
        final_filename = f"{safe_title}.{format_type}"
        mimetype = 'audio/mpeg' if format_type == 'mp3' else 'video/mp4'

        return Response(
            generate_file_stream(),
            mimetype=mimetype,
            headers={
                "Content-Disposition": f'attachment; filename="{final_filename}"',
                # "Content-Length": os.path.getsize(found_file) # Opsional, kadang bikin streaming putus di browser tertentu
            }
        )

    except Exception as e:
        print(f"Download Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify(success=False, error=str(e)), 500

if __name__ == "__main__":
    # Konfigurasi Port untuk Cloud Run
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)