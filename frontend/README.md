# YouTube Downloader Frontend

A React-based frontend for downloading YouTube videos as MP4 or extracting audio as MP3. **Optimized for Vercel hosting.**

## Features

- 🎥 Download YouTube videos as MP4
- 🎵 Extract audio as MP3
- 📥 Direct browser downloads (appears in download history)
- 🚀 Optimized for Vercel hosting
- 🎨 Modern, responsive UI
- ⚡ Fast and intuitive interface

## Quick Start (Local Development)

### Prerequisites
- Node.js 16+ and npm
- Python backend running

### Installation

```bash
# Install dependencies
npm install

# Create .env.local for local development
echo "REACT_APP_API_URL=http://localhost:5000" > .env.local

# Start the development server
npm start
```

The app opens at `http://localhost:3000`

## Backend Setup

In a separate terminal:

```bash
# Go to parent directory
cd ..

# Install Python dependencies
pip install flask flask-cors yt-dlp

# Start the server
python server.py
```

The backend runs at `http://localhost:5000`

## Deployment to Vercel

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions.

**Quick Deploy:**

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

**Set environment variable in Vercel:**
```
REACT_APP_API_URL=https://your-backend-api.com
```

## Build for Production

```bash
npm run build
```

Creates optimized build in `build/` directory.

## Environment Variables

### Development (`.env.local`)
```
REACT_APP_API_URL=http://localhost:5000
```

### Production (`.env.production`)
```
REACT_APP_API_URL=https://your-backend-api.com
```

## API Integration

The frontend communicates with Python Flask backend:

- **Endpoint**: `POST /download`
- **Request Format**: JSON
- **Response**: Blob (file data for download)

### Request Payload
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "My Video",
  "format": "mp4",
  "direct_download": true
}
```

## Project Structure

```
frontend/
├── public/
│   ├── index.html
│   └── _redirects          # Vercel routing config
├── src/
│   ├── App.js
│   ├── App.css
│   └── index.js
├── package.json
├── vercel.json             # Vercel build config
├── .env.example            # Environment template
├── .env.production         # Production environment
├── README.md
└── DEPLOYMENT.md           # Deployment guide
```

## Troubleshooting

### "Cannot connect to server"
- Verify backend URL in environment variables
- Ensure backend is running and CORS is enabled

### Downloads not working
- Check browser console for errors (F12)
- Verify API response is valid
- Check backend logs

### Build errors
- Run `npm install` again
- Clear cache: `rm -rf node_modules package-lock.json`
- Reinstall: `npm install`

## Technologies Used

- **React 18** - UI framework
- **Axios** - HTTP client
- **React Scripts** - Build tooling
- **Vercel** - Hosting platform

## Notes

- Files download directly to your browser's default download folder
- Large video files may take time to download
- Backend must support CORS for frontend communication
- YouTube ToS: Only download content you have permission to download

## Related Files

- **Backend**: `../server.py` - Flask API server
- **Deployment Guide**: `./DEPLOYMENT.md`
- **Example Env**: `./.env.example`

---

**Ready for production!** 🚀

For detailed deployment instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md)

