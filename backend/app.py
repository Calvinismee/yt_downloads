import subprocess
import sys
import os

# Ensure yt-dlp is installed and up-to-date
def install_yt_dlp():
    try:
        import yt_dlp
        print("yt-dlp is already installed. Updating...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        print("yt-dlp updated successfully.")
    except ImportError:
        print("yt-dlp not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
        print("yt-dlp installed successfully.")

# Check if FFmpeg is installed
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("✓ FFmpeg is installed")
    except FileNotFoundError:
        print("✗ FFmpeg not found!")
        print("Please install FFmpeg:")
        print("  Windows: choco install ffmpeg  (or download from ffmpeg.org)")
        print("  Mac: brew install ffmpeg")
        print("  Linux: sudo apt-get install ffmpeg")
        sys.exit(1)

# Main download function
def download_youtube_content():
    install_yt_dlp()
    check_ffmpeg()

    print("\n--- YouTube Downloader ---")
    video_url = input("Enter YouTube video URL: ").strip()

    if not video_url.startswith("http"):
        print("Invalid URL. Please try again.")
        return

    while True:
        download_type = input("Download as MP4 (video) or MP3 (audio only)? [mp4/mp3]: ").lower().strip()
        if download_type in ["mp4", "mp3"]:
            break
        print("Invalid choice. Please enter 'mp4' or 'mp3'.")

    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)

    if download_type == "mp4":
        command = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
            video_url
        ]
        print(f"Downloading video to '{output_dir}'...")
    else:  # mp3
        command = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
            video_url
        ]
        print(f"Extracting audio to '{output_dir}'...")

    try:
        subprocess.run(command, check=True)
        print("\nDownload complete.")
    except subprocess.CalledProcessError as e:
        print(f"\nDownload failed: {e}")
    except FileNotFoundError:
        print("\nError: 'yt-dlp' not found. Make sure it’s installed and in PATH.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")

if __name__ == "__main__":
    download_youtube_content()
