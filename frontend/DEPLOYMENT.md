# YouTube Downloader - Vercel Deployment Guide

## Overview
This is a React frontend optimized for Vercel hosting. The frontend communicates with a Python Flask backend that handles YouTube downloads.

## Prerequisites
- Node.js 16+ installed
- Vercel account (free at vercel.com)
- Git repository for your project
- Python backend running somewhere (cloud server, VPS, or local machine)

## Local Development

### 1. Install dependencies
```bash
cd frontend
npm install
```

### 2. Set environment variables
Create a `.env.local` file:
```bash
REACT_APP_API_URL=http://localhost:5000
```

### 3. Start the development server
```bash
npm start
```

The app runs at `http://localhost:3000`

### 4. Backend Setup (Local)
In another terminal:
```bash
cd ..
python server.py
```

## Deployment to Vercel

### Option 1: Using Vercel CLI (Recommended)

1. **Install Vercel CLI:**
```bash
npm i -g vercel
```

2. **Login to Vercel:**
```bash
vercel login
```

3. **Deploy from frontend directory:**
```bash
cd frontend
vercel
```

4. **Follow prompts:**
   - Choose your project scope
   - Confirm project settings
   - Set environment variable `REACT_APP_API_URL` to your backend API URL

### Option 2: Connect GitHub Repository

1. **Push code to GitHub:**
```bash
git add .
git commit -m "Prepare for Vercel deployment"
git push origin main
```

2. **Go to Vercel Dashboard:**
   - Click "New Project"
   - Import your GitHub repository
   - Select the `frontend` folder as root directory
   - Add environment variable: `REACT_APP_API_URL`
   - Click Deploy

## Environment Variables

### Development (`.env.local`)
```
REACT_APP_API_URL=http://localhost:5000
```

### Production (Set in Vercel Dashboard)
```
REACT_APP_API_URL=https://your-backend-api.com
```

**To set in Vercel:**
1. Go to Project Settings
2. Navigate to Environment Variables
3. Add `REACT_APP_API_URL` with your backend URL
4. Redeploy

## Deploying Your Backend

Your Python Flask server needs to be hosted somewhere. Options:

### 1. **Render.com** (Recommended for Python)
- Free tier available
- Free PostgreSQL database
- Easy Flask deployment

### 2. **Railway.app**
- Pay-as-you-go pricing
- Good performance
- Easy deployment

### 3. **Heroku** (Paid - Free tier discontinued)
- Popular option
- Good documentation

### 4. **AWS/GCP/Azure**
- More complex setup
- Full control
- Scalable

## Backend Deployment Example (Render.com)

1. Create account at render.com
2. Create new Web Service
3. Connect GitHub repository
4. Select Python environment
5. Set start command: `pip install -r requirements.txt && python server.py`
6. Deploy
7. Copy your backend URL
8. Add to Vercel environment variables

## Building for Production

```bash
cd frontend
npm run build
```

This creates a production build in the `build/` directory.

## Vercel.json Configuration

The `vercel.json` file configures:
- Build command
- Output directory (where built files are)
- Environment variables

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "build",
  "env": {
    "REACT_APP_API_URL": "@api_url"
  }
}
```

## CORS Configuration

**Important:** Your Flask backend must have CORS enabled for Vercel:

```python
from flask_cors import CORS
app = Flask(__name__)
CORS(app)  # This allows requests from any origin
```

For production, you may want to restrict CORS:
```python
CORS(app, resources={r"/download": {"origins": ["https://your-vercel-domain.com"]}})
```

## Troubleshooting

### Error: "Cannot connect to server"
- Verify backend URL in `.env.production`
- Check CORS is enabled on backend
- Ensure backend is running and accessible

### Files not downloading
- Check browser console for errors
- Verify API response is a blob
- Check backend logs for processing errors

### Slow downloads
- Large video files (especially MP4) may take time
- Consider adding progress tracking
- Check if backend has size/timeout limits

## Performance Tips

1. **Enable Caching:**
   - Vercel automatically caches static assets
   - Add cache headers to your API responses

2. **Optimize Build Size:**
   - Check bundle size: `npm run build`
   - Use code splitting if needed

3. **Monitor Performance:**
   - Use Vercel Analytics
   - Check Real Experience Monitoring (RUM)

## Useful Links

- [Vercel Documentation](https://vercel.com/docs)
- [React Deployment](https://create-react-app.dev/deployment/)
- [Flask CORS](https://flask-cors.readthedocs.io/)
- [Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)

## Support

For issues:
1. Check Vercel deployment logs
2. Check browser console (F12)
3. Check backend server logs
4. Verify environment variables are set correctly

---

**Your app is now ready for production!** 🚀
