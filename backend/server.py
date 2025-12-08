from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp
import os
import io
from pathlib import Path
import threading
import time

app = Flask(__name__)
CORS(app)

OUTPUT_DIR = "downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def cleanup_file(filepath, delay=1):
    """Delete file after a delay to ensure streaming is complete"""
    def delete():
        time.sleep(delay)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    thread = threading.Thread(target=delete, daemon=True)
    thread.start()

def stream_file(file_obj, chunk_size=1024*1024):
    """Stream file in chunks"""
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk

@app.route("/video-info", methods=["GET"])
def get_video_info():
    """Get video metadata (title, thumbnail) without downloading"""
    video_id = request.args.get("video_id")
    
    if not video_id:
        return jsonify(success=False, error="Missing video ID"), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 30,
            "http_headers": {"User-Agent": "Mozilla/5.0"},
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # Get highest quality thumbnail
        thumbnail_url = info.get("thumbnail", "")
        if info.get("thumbnails"):
            # Use highest quality thumbnail available
            thumbnail_url = max(info["thumbnails"], key=lambda x: x.get("height", 0))["url"]
        
        return jsonify(
            success=True,
            title=info.get("title", "Unknown"),
            duration=info.get("duration", 0),
            thumbnail=thumbnail_url
        )
    
    except Exception as e:
        error_msg = str(e)
        print(f"Video info error: {error_msg}")
        return jsonify(success=False, error=f"Could not fetch video info: {error_msg}"), 400

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
    
    # Sanitize title
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_title:
        safe_title = "video"
    
    # Download to temporary file
    temp_filepath = os.path.join(OUTPUT_DIR, f"{safe_title}_temp.%(ext)s")
    
    try:
        if format_type == "mp3":
            # MP3: Extract audio with quality
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": temp_filepath,
                "quiet": False,
                "no_warnings": False,
                "socket_timeout": 30,
                "http_headers": {"User-Agent": "Mozilla/5.0"},
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(audio_quality),
                    "nopostoverwrites": False,
                }],
            }
        else:
            # MP4: Download with quality selection
            if video_quality == "720":
                format_str = "best[height<=720]/best[ext=mp4]/best"
            elif video_quality == "480":
                format_str = "best[height<=480]/best[ext=mp4]/best"
            elif video_quality == "360":
                format_str = "best[height<=360]/best[ext=mp4]/best"
            else:
                format_str = "best[ext=mp4]/best"
            
            ydl_opts = {
                "format": format_str,
                "outtmpl": temp_filepath,
                "quiet": False,
                "no_warnings": False,
                "socket_timeout": 30,
                "http_headers": {"User-Agent": "Mozilla/5.0"},
                "merge_output_format": "mp4",
            }
        
        # Download the video
        print(f"Starting download: {video_id} as {format_type}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Find the downloaded file
        temp_dir = Path(OUTPUT_DIR)
        downloaded_file = None
        for file in sorted(temp_dir.glob(f"{safe_title}_temp*"), key=os.path.getctime, reverse=True):
            if file.suffix in ['.mp3', '.mp4', '.m4a', '.webm']:
                downloaded_file = file
                break
        
        if not downloaded_file:
            return jsonify(success=False, error="File not found after download"), 500
        
        print(f"File found: {downloaded_file}, size: {os.path.getsize(downloaded_file)} bytes")
        
        # Read file into memory
        with open(str(downloaded_file), 'rb') as f:
            file_data = f.read()
        
        if not file_data:
            return jsonify(success=False, error="Downloaded file is empty"), 500
        
        # Create BytesIO object
        file_obj = io.BytesIO(file_data)
        
        # Schedule file cleanup
        cleanup_file(str(downloaded_file), delay=1)
        
        # Send file with streaming
        final_filename = f"{safe_title}.{format_type}"
        mimetype = 'audio/mpeg' if format_type == 'mp3' else 'video/mp4'
        
        print(f"Sending file: {final_filename}, size: {len(file_data)} bytes")
        
        # Use Response with streaming to enable progress tracking
        response = Response(
            stream_file(file_obj),
            mimetype=mimetype,
            headers={
                'Content-Length': len(file_data),
                'Content-Disposition': f'attachment; filename="{final_filename}"'
            }
        )
        return response
    
    except Exception as e:
        error_msg = str(e)
        print(f"Download error: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify(success=False, error=f"Download failed: {error_msg}"), 500

if __name__ == "__main__":
    # Get PORT from environment variable (Cloud Run sets this)
    # Default to 5000 for local testing
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
