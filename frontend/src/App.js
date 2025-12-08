import React, { useState } from 'react';
import axios from 'axios';
import './App.css';
import DecryptedText from './DecryptedText';
import Particles from './Particles';

function App() {
  const [videoUrl, setVideoUrl] = useState('');
  const [title, setTitle] = useState('');
  const [format, setFormat] = useState('mp4');
  const [videoQuality, setVideoQuality] = useState('720');
  const [audioQuality, setAudioQuality] = useState('128');
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [downloadedBytes, setDownloadedBytes] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  const [videoInfo, setVideoInfo] = useState(null);
  const [step, setStep] = useState('url'); // 'url' or 'download'

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

  const extractVideoId = (url) => {
    const regex = /(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
    const match = url.match(regex);
    return match ? match[1] : null;
  };

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    
    if (!videoUrl.trim()) {
      setMessage('Please enter a YouTube URL');
      setMessageType('error');
      return;
    }

    const videoId = extractVideoId(videoUrl);
    if (!videoId) {
      setMessage('Invalid YouTube URL. Please enter a valid URL.');
      setMessageType('error');
      return;
    }

    setProcessing(true);
    setProgressMessage('Fetching video info...');
    setMessage('');

    try {
      const response = await axios.get(`${API_URL}/video-info?video_id=${videoId}`);
      if (response.data.success) {
        setVideoInfo(response.data);
        setTitle(response.data.title);
        setStep('download');
      } else {
        setMessage('Could not fetch video information. Please try again.');
        setMessageType('error');
      }
    } catch (error) {
      console.error('Error fetching video info:', error);
      setMessage('Error: ' + (error.message || 'Could not fetch video info'));
      setMessageType('error');
    } finally {
      setProcessing(false);
      setProgressMessage('');
    }
  };

  const handleDownload = async (e) => {
    e.preventDefault();
    
    if (!title.trim()) {
      setMessage('Please enter a filename');
      setMessageType('error');
      return;
    }

    setLoading(true);
    setProgress(1);
    setDownloadedBytes(0);
    setTotalBytes(0);
    setProgressMessage('Processing');
    setMessage('');

    try {
      const videoId = extractVideoId(videoUrl);
      
      // Simulate progress during processing phase
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev < 30) return Math.floor(prev + Math.random() * 5);
          return prev;
        });
      }, 300);
      
      const response = await axios.post(`${API_URL}/download`, {
        video_id: videoId,
        title: title.trim(),
        format: format,
        video_quality: format === 'mp4' ? videoQuality : null,
        audio_quality: format === 'mp3' ? audioQuality : null,
        direct_download: true
      }, {
        responseType: 'blob',
        onDownloadProgress: (progressEvent) => {
          clearInterval(progressInterval);
          
          const downloaded = progressEvent.loaded;
          const total = progressEvent.total || 0;
          
          setDownloadedBytes(downloaded);
          setTotalBytes(total);
          
          if (total) {
            // Map download progress from 30% to 99%
            const downloadPercent = Math.round((downloaded * 100) / total);
            const mappedPercent = Math.floor(30 + (downloadPercent * 0.69));
            setProgress(Math.min(mappedPercent, 99));
            
            if (downloadPercent < 50) {
              setProgressMessage('Downloading...');
            } else {
              setProgressMessage('Finalizing...');
            }
          }
        }
      });

      clearInterval(progressInterval);
      setProgress(100);
      
      // Create a blob URL and trigger download
      const blob = new Blob([response.data], {
        type: format === 'mp3' ? 'audio/mpeg' : 'video/mp4'
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title.trim()}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setMessage(`Download complete! File: ${title.trim()}.${format}`);
      setMessageType('success');
      
      // Reset after a delay
      setTimeout(() => {
        setProgress(0);
        setProgressMessage('');
        setDownloadedBytes(0);
        setTotalBytes(0);
        setVideoUrl('');
        setTitle('');
        setFormat('mp4');
        setVideoInfo(null);
        setStep('url');
      }, 2000);
    } catch (error) {
      if (error.code === 'ERR_NETWORK') {
        setMessage('Cannot connect to server. Make sure the API server is running.');
      } else if (error.response?.status === 429) {
        setMessage('Too many requests. Please wait a moment and try again.');
        setMessageType('warning');
      } else {
        setMessage(`Error: ${error.response?.data?.error || error.message}`);
      }
      setMessageType('error');
    } finally {
      setLoading(false);
      setProgress(0);
      setProgressMessage('');
      setDownloadedBytes(0);
      setTotalBytes(0);
    }
  };

  const goBack = () => {
    setStep('url');
    setVideoInfo(null);
    setMessage('');
    setMessageType('');
  };

  return (
    <div className="app-wrapper">
      <div className="particles-background">
        <Particles
          particleCount={200}
          particleSpread={10}
          speed={0.1}
          particleColors={['#ffffff', '#ffffff']}
          moveParticlesOnHover={true}
          alphaParticles={false}
          particleBaseSize={100}
          sizeRandomness={1}
          disableRotation={false}
        />
      </div>
      <div className="container">
      <div className="card">
        <div className="header">
          <h1><DecryptedText text="Ambatudonlod" animateOn="both" revealDirection="start" /></h1>
          <p>Download videos as MP4 or extract audio as MP3</p>
        </div>

        {step === 'url' && (
          <form onSubmit={handleUrlSubmit} className="form">
            <div className="form-group">
              <label htmlFor="url">YouTube URL</label>
              <input
                id="url"
                type="text"
                placeholder="https://www.youtube.com/watch?v=..."
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                disabled={processing}
              />
            </div>

            <button type="submit" className="btn-download" disabled={processing}>
              {processing ? 'Fetching video...' : 'Next'}
            </button>
          </form>
        )}

        {step === 'download' && videoInfo && (
          <form onSubmit={handleDownload} className="form">
            <div className="download-preview-container">
              <div className="video-preview-card">
                {videoInfo.thumbnail && (
                  <img src={videoInfo.thumbnail} alt="Video thumbnail" className="video-thumbnail-large" />
                )}
                <div className="video-preview-details">
                  <h2 className="video-title-large">{videoInfo.title}</h2>
                  {videoInfo.duration && (
                    <p className="video-duration-large">
                      {Math.floor(videoInfo.duration / 60)}:{String(videoInfo.duration % 60).padStart(2, '0')}
                    </p>
                  )}
                </div>
              </div>

              <div className="download-form-section">
                <div className="form-group">
                  <label htmlFor="title">Filename</label>
                  <input
                    id="title"
                    type="text"
                    placeholder="Enter filename (without extension)"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    disabled={loading}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="format">Format</label>
                  <div className="format-options">
                    <label className={`radio-label ${format === 'mp4' ? 'selected' : ''}`}>
                      <input
                        type="radio"
                        value="mp4"
                        checked={format === 'mp4'}
                        onChange={(e) => setFormat(e.target.value)}
                        disabled={loading}
                      />
                      MP4 (Video)
                    </label>
                    <label className={`radio-label ${format === 'mp3' ? 'selected' : ''}`}>
                      <input
                        type="radio"
                        value="mp3"
                        checked={format === 'mp3'}
                        onChange={(e) => setFormat(e.target.value)}
                        disabled={loading}
                      />
                      MP3 (Audio)
                    </label>
                  </div>
                </div>

                {format === 'mp4' && (
                  <div className="form-group">
                    <label htmlFor="videoQuality">Quality</label>
                    <select
                      id="videoQuality"
                      value={videoQuality}
                      onChange={(e) => setVideoQuality(e.target.value)}
                      disabled={loading}
                      className="quality-select"
                    >
                      <option value="720">720p</option>
                      <option value="480">480p</option>
                      <option value="360">360p</option>
                    </select>
                  </div>
                )}

                {format === 'mp3' && (
                  <div className="form-group">
                    <label htmlFor="audioQuality">Quality</label>
                    <select
                      id="audioQuality"
                      value={audioQuality}
                      onChange={(e) => setAudioQuality(e.target.value)}
                      disabled={loading}
                      className="quality-select"
                    >
                      <option value="320">320 kb/s</option>
                      <option value="256">256 kb/s</option>
                      <option value="192">192 kb/s</option>
                      <option value="128">128 kb/s</option>
                    </select>
                  </div>
                )}
              </div>
            </div>

            <div className="button-group">
              <button type="button" className="btn-back" onClick={goBack} disabled={loading}>
                Back
              </button>
              <button type="submit" className="btn-download" disabled={loading}>
                {loading ? 'Downloading...' : 'Download'}
              </button>
            </div>
          </form>
        )}

        {loading && (
          <div className="progress-container">
            <div className="progress-bar-background">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${progress}%` }}
              ></div>
            </div>
            <div className="progress-info">
              <span className="progress-message">{progressMessage}</span>
              <span className="progress-bytes">{progress}%</span>
            </div>
          </div>
        )}

        {message && (
          <div className={`message ${messageType}`}>
            {message}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}

export default App;
