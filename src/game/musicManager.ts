// Music manager for game soundtrack

export interface MusicTrack {
  id: string;
  name: string;
  phase: 'menu' | 'diplomacy' | 'movement' | 'combat' | 'victory' | 'defeat' | 'ambient';
  path: string;
  duration: number; // In seconds
}

// Categorize soundtrack tracks based on typical Imperialism music
export const SOUNDTRACK_TRACKS: MusicTrack[] = [
  {
    id: 'track_1',
    name: 'Main Theme',
    phase: 'menu',
    path: '/assets/music/Imperialism soundtrack - Track 1.mp3',
    duration: 45,
  },
  {
    id: 'track_2',
    name: 'Diplomacy',
    phase: 'diplomacy',
    path: '/assets/music/Imperialism soundtrack - Track 2.mp3',
    duration: 180,
  },
  {
    id: 'track_3',
    name: 'Movement Phase',
    phase: 'movement',
    path: '/assets/music/Imperialism soundtrack - Track 3.mp3',
    duration: 180,
  },
  {
    id: 'track_4',
    name: 'Combat',
    phase: 'combat',
    path: '/assets/music/Imperialism soundtrack - Track 4.mp3',
    duration: 180,
  },
  {
    id: 'track_5',
    name: 'Tension',
    phase: 'combat',
    path: '/assets/music/Imperialism soundtrack - Track 5.mp3',
    duration: 35,
  },
  {
    id: 'track_6',
    name: 'Ambient',
    phase: 'ambient',
    path: '/assets/music/Imperialism soundtrack - Track 6.mp3',
    duration: 45,
  },
  {
    id: 'track_7',
    name: 'Exploration',
    phase: 'movement',
    path: '/assets/music/Imperialism soundtrack - Track 7.mp3',
    duration: 65,
  },
  {
    id: 'track_8',
    name: 'Strategic',
    phase: 'diplomacy',
    path: '/assets/music/Imperialism soundtrack - Track 8.mp3',
    duration: 60,
  },
  {
    id: 'track_9',
    name: 'Battle',
    phase: 'combat',
    path: '/assets/music/Imperialism soundtrack - Track 9.mp3',
    duration: 180,
  },
  {
    id: 'track_10',
    name: 'Epic',
    phase: 'victory',
    path: '/assets/music/Imperialism soundtrack - Track 10.mp3',
    duration: 180,
  },
  {
    id: 'track_11',
    name: 'Theme Variation',
    phase: 'menu',
    path: '/assets/music/Imperialism soundtrack - Track 11.mp3',
    duration: 50,
  },
];

export class MusicManager {
  private currentTrack: HTMLAudioElement | null = null;
  private currentTrackId: string | null = null;
  private isPlaying: boolean = false;
  private volume: number = 0.5;
  private fadeOutDuration: number = 1000; // 1 second fade

  constructor() {
    this.volume = 0.5;
  }

  // Get tracks for a specific game phase
  static getTracksForPhase(phase: 'menu' | 'diplomacy' | 'movement' | 'combat' | 'victory' | 'defeat' | 'ambient'): MusicTrack[] {
    return SOUNDTRACK_TRACKS.filter(track => track.phase === phase);
  }

  // Play a specific track
  playTrack(track: MusicTrack, loop: boolean = true): void {
    // Stop current track if playing
    if (this.currentTrack) {
      this.stopTrack();
    }

    // Create new audio element
    const audio = new Audio(track.path);
    audio.volume = this.volume;
    audio.loop = loop;
    audio.crossOrigin = 'anonymous';

    audio.addEventListener('playing', () => {
      this.isPlaying = true;
    });

    audio.addEventListener('ended', () => {
      this.isPlaying = false;
    });

    audio.addEventListener('error', (e) => {
      console.error(`Failed to play track ${track.id}:`, e);
    });

    this.currentTrack = audio;
    this.currentTrackId = track.id;

    // Play the track
    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.catch(() => {
        console.warn('Audio autoplay prevented - user interaction required');
      });
    }
  }

  // Play a random track for a phase
  playPhaseMusic(phase: 'menu' | 'diplomacy' | 'movement' | 'combat' | 'victory' | 'defeat' | 'ambient'): void {
    const tracks = MusicManager.getTracksForPhase(phase);
    if (tracks.length === 0) return;

    const randomTrack = tracks[Math.floor(Math.random() * tracks.length)];
    this.playTrack(randomTrack);
  }

  // Stop current track with fade out
  stopTrack(fade: boolean = true): void {
    if (!this.currentTrack) return;

    if (fade) {
      this.fadeOut();
    } else {
      this.currentTrack.pause();
      this.currentTrack = null;
      this.currentTrackId = null;
      this.isPlaying = false;
    }
  }

  // Fade out current track
  private fadeOut(): void {
    if (!this.currentTrack) return;

    const startVolume = this.currentTrack.volume;
    const steps = 10;
    const stepDuration = this.fadeOutDuration / steps;
    let step = 0;

    const fadeInterval = setInterval(() => {
      step++;
      const progress = step / steps;
      this.currentTrack!.volume = startVolume * (1 - progress);

      if (step >= steps) {
        clearInterval(fadeInterval);
        this.currentTrack!.pause();
        this.currentTrack = null;
        this.currentTrackId = null;
        this.isPlaying = false;
      }
    }, stepDuration);
  }

  // Set volume (0-1)
  setVolume(vol: number): void {
    this.volume = Math.max(0, Math.min(1, vol));
    if (this.currentTrack) {
      this.currentTrack.volume = this.volume;
    }
  }

  // Get current volume
  getVolume(): number {
    return this.volume;
  }

  // Check if music is playing
  isAudioPlaying(): boolean {
    return this.isPlaying;
  }

  // Get current track ID
  getCurrentTrackId(): string | null {
    return this.currentTrackId;
  }

  // Pause current track
  pauseTrack(): void {
    if (this.currentTrack) {
      this.currentTrack.pause();
      this.isPlaying = false;
    }
  }

  // Resume current track
  resumeTrack(): void {
    if (this.currentTrack) {
      const playPromise = this.currentTrack.play();
      if (playPromise !== undefined) {
        playPromise.catch(() => {
          console.warn('Audio resume prevented');
        });
      }
      this.isPlaying = true;
    }
  }

  // Cleanup
  destroy(): void {
    if (this.currentTrack) {
      this.currentTrack.pause();
      this.currentTrack = null;
    }
  }
}

// Create singleton instance
let musicManagerInstance: MusicManager | null = null;

export function getMusicManager(): MusicManager {
  if (!musicManagerInstance) {
    musicManagerInstance = new MusicManager();
  }
  return musicManagerInstance;
}
