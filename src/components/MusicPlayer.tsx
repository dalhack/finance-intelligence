import React, { useState, useEffect } from 'react';
import { getMusicManager, SOUNDTRACK_TRACKS } from '../game/musicManager';
import './MusicPlayer.css';

interface MusicPlayerProps {
  visible?: boolean;
}

export const MusicPlayer: React.FC<MusicPlayerProps> = ({ visible = false }) => {
  const musicManager = getMusicManager();
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTrackId, setCurrentTrackId] = useState<string | null>(null);
  const [volume, setVolume] = useState(0.5);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    // Update state when music changes
    const interval = setInterval(() => {
      setIsPlaying(musicManager.isAudioPlaying());
      setCurrentTrackId(musicManager.getCurrentTrackId());
    }, 100);

    return () => clearInterval(interval);
  }, [musicManager]);

  const handlePlayPause = () => {
    if (isPlaying) {
      musicManager.pauseTrack();
    } else {
      musicManager.resumeTrack();
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = parseFloat(e.target.value);
    setVolume(vol);
    musicManager.setVolume(vol);
  };

  const handleTrackSelect = (trackId: string) => {
    const track = SOUNDTRACK_TRACKS.find(t => t.id === trackId);
    if (track) {
      musicManager.playTrack(track);
    }
  };

  const currentTrack = SOUNDTRACK_TRACKS.find(t => t.id === currentTrackId);

  if (!visible && !isPlaying) {
    return null;
  }

  return (
    <div className="music-player">
      <div className="music-player-header">
        <div className="music-player-title">
          {currentTrack ? (
            <>
              <span className="track-name">{currentTrack.name}</span>
              <span className="track-phase">[{currentTrack.phase}]</span>
            </>
          ) : (
            <span className="track-name">Imperialism Soundtrack</span>
          )}
        </div>
        <button
          className={`player-btn ${isPlaying ? 'playing' : ''}`}
          onClick={handlePlayPause}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
      </div>

      <div className="music-player-controls">
        <div className="volume-control">
          <span className="volume-icon">🔊</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={volume}
            onChange={handleVolumeChange}
            className="volume-slider"
            title="Volume"
          />
          <span className="volume-value">{Math.round(volume * 100)}%</span>
        </div>
      </div>

      {showDetails && (
        <div className="music-player-details">
          <div className="details-header">
            <h4>Soundtrack Tracks</h4>
            <button
              className="close-btn"
              onClick={() => setShowDetails(false)}
              title="Close"
            >
              ✕
            </button>
          </div>
          <div className="tracks-list">
            {SOUNDTRACK_TRACKS.map(track => (
              <button
                key={track.id}
                className={`track-item ${currentTrackId === track.id ? 'active' : ''}`}
                onClick={() => handleTrackSelect(track.id)}
                title={`${track.name} (${track.phase})`}
              >
                <span className="track-indicator">
                  {currentTrackId === track.id && isPlaying ? '♪' : '•'}
                </span>
                <span className="track-title">{track.name}</span>
                <span className="track-phase-small">{track.phase}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <button
        className="details-toggle"
        onClick={() => setShowDetails(!showDetails)}
        title={showDetails ? 'Hide tracks' : 'Show tracks'}
      >
        {showDetails ? '▲' : '▼'} Tracks
      </button>
    </div>
  );
};

export default MusicPlayer;
