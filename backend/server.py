from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import time
import tempfile
from pathlib import Path
from google.cloud import secretmanager

app = Flask(__name__)
CORS(app)

# --- KONFIGURASI PATH ---
# [FIX] Gunakan /tmp untuk cookies karena folder app biasanya Read-Only di Cloud Run
OUTPUT_DIR = tempfile.gettempdir()
COOKIES_FILE = os.path.join(OUTPUT_DIR, "cookies.txt")


# Function to fetch secret from Cloud Secret Manager
def get_secret(secret_id, version_id="latest"):
    try:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            print("⚠️ GOOGLE_CLOUD_PROJECT not set. Skipping Secret Manager.")
            return None

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching secret: {e}")
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
    data = request.get_json()
    video_id = data.get("video_id")
    title = data.get("title", "video")
    format_type = data.get("format", "mp4").lower()
    video_quality = data.get("video_quality", "720")
    audio_quality = data.get("audio_quality", "128")

    if not video_id:
        return jsonify(success=False, error="Missing video ID"), 400

    url = f"https://www.youtube.com/watch?v={video_id}"

    safe_title = (
        "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        or "video"
    )
    temp_filename_template = f"{safe_title}_{int(time.time())}.%(ext)s"
    temp_filepath = os.path.join(OUTPUT_DIR, temp_filename_template)

    try:
        ydl_opts = {
            "outtmpl": temp_filepath,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 60,
            # [FIX] HAPUS 'cookies_from_browser'
            # [FIX] HAPUS 'User-Agent' manual (http_headers)
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            "nocheckcertificate": True,
            "noplaylist": True,
            "cachedir": False,
        }

        # Logika Kualitas (MP3/MP4) tetap sama
        if format_type == "mp3":
            ydl_opts.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": str(audio_quality),
                        }
                    ],
                }
            )
        else:
            if video_quality == "720":
                format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif video_quality == "480":
                format_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
            elif video_quality == "360":
                format_str = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
            else:
                format_str = "bestvideo+bestaudio/best"

            ydl_opts.update(
                {
                    "format": format_str,
                    "merge_output_format": "mp4",
                }
            )

        print(
            f"Starting download: {video_id} using cookies: {os.path.exists(COOKIES_FILE)}"
        )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Cari file hasil download
        search_prefix = f"{safe_title}_{int(time.time())}"
        found_file = None
        for file in os.listdir(OUTPUT_DIR):
            if file.startswith(search_prefix):
                found_file = os.path.join(OUTPUT_DIR, file)
                break

        if not found_file:
            return jsonify(success=False, error="File not found"), 500

        # Streaming Generator
        def generate_file_stream():
            try:
                with open(found_file, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        yield chunk
            finally:
                try:
                    os.remove(found_file)
                    print(f"Deleted: {found_file}")
                except:
                    pass

        final_filename = f"{safe_title}.{format_type}"
        mimetype = "audio/mpeg" if format_type == "mp3" else "video/mp4"

        return Response(
            generate_file_stream(),
            mimetype=mimetype,
            headers={"Content-Disposition": f'attachment; filename="{final_filename}"'},
        )

    except Exception as e:
        print(f"Download Error: {e}")
        return jsonify(success=False, error=str(e)), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
