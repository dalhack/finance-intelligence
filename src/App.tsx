import React, { useEffect } from 'react';
import { useGameStore } from '@game/store';
import { GameMap } from '@components/GameMap';
import { GameUI } from '@components/GameUI';
import MusicPlayer from '@components/MusicPlayer';
import ReferenceViewer from '@components/ReferenceViewer';
import { getMusicManager } from '@game/musicManager';
import './styles/App.css';

function App() {
  const gameState = useGameStore(s => s.gameState);
  const startNewGame = useGameStore(s => s.startNewGame);
  const isLoading = useGameStore(s => s.isLoading);
  const error = useGameStore(s => s.error);
  const musicManager = getMusicManager();

  useEffect(() => {
    if (!gameState) {
      startNewGame({ numCountries: 6, difficulty: 'normal' });
    } else {
      // Map game phases to music phases
      const musicPhaseMap: Record<string, 'menu' | 'diplomacy' | 'movement' | 'combat' | 'victory' | 'defeat' | 'ambient'> = {
        diplomacy: 'diplomacy',
        movement: 'movement',
        combat: 'combat',
        research: 'ambient',
        'end-turn': 'ambient',
      };

      const musicPhase = musicPhaseMap[gameState.gamePhase] || 'ambient';
      musicManager.playPhaseMusic(musicPhase);
    }
  }, [gameState?.gamePhase]);

  if (isLoading) {
    return <div className="app loading">Starting game...</div>;
  }

  if (error) {
    return <div className="app error">Error: {error}</div>;
  }

  if (!gameState) {
    return <div className="app">Initializing...</div>;
  }

  return (
    <div className="app">
      <header className="game-header">
        <h1>Imperialism</h1>
        <div className="header-info">
          <span>Turn {gameState.currentTurn}</span>
          <span>Phase: {gameState.gamePhase}</span>
        </div>
      </header>

      <div className="game-container">
        <GameMap />
        <GameUI />
      </div>

      <MusicPlayer visible={true} />
      <ReferenceViewer />
    </div>
  );
}

export default App;
