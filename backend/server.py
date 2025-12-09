from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import time
import tempfile
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Mengizinkan akses dari Frontend manapun

# Gunakan folder temporary sistem (C:\Users\...\AppData\Local\Temp di Windows, atau /tmp di Linux)
OUTPUT_DIR = tempfile.gettempdir()

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
            "http_headers": {"User-Agent": "Mozilla/5.0"},
        }
        
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
            "http_headers": {"User-Agent": "Mozilla/5.0"},
        }

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