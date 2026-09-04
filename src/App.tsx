import React, { useEffect } from 'react';
import { useGameStore } from '@game/store';
import { GameMap } from '@components/GameMap';
import { GameUI } from '@components/GameUI';
import { MainMenu } from '@components/MainMenu';
import MusicPlayer from '@components/MusicPlayer';
import ReferenceViewer from '@components/ReferenceViewer';
import VictoryDisplay from '@components/VictoryDisplay';
import { getMusicManager } from '@game/musicManager';
import { GameStorage } from '@game/gameStorage';
import './styles/App.css';

function App() {
  const gameState = useGameStore(s => s.gameState);
  const lastTurnReport = useGameStore(s => s.lastTurnReport);
  const startNewGame = useGameStore(s => s.startNewGame);
  const isLoading = useGameStore(s => s.isLoading);
  const error = useGameStore(s => s.error);
  const musicManager = getMusicManager();

  useEffect(() => {
    if (gameState) {
      // Auto-save every 5 turns
      if (gameState.currentTurn % 5 === 0) {
        GameStorage.autoSave(gameState);
      }

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
  }, [gameState?.gamePhase, gameState?.currentTurn]);

  if (isLoading) {
    return <div className="app loading">Starting game...</div>;
  }

  if (error) {
    return <div className="app error">Error: {error}</div>;
  }

  if (!gameState) {
    return <MainMenu />;
  }

  const handleSaveGame = () => {
    const playerCountry = gameState.countries.find(c => c.id === gameState.currentPlayerCountryId);
    const saveName = playerCountry?.name ? `${playerCountry.name} - Turn ${gameState.currentTurn}` : `Save - Turn ${gameState.currentTurn}`;
    GameStorage.saveGame(gameState, saveName);
  };

  return (
    <div className="app">
      <header className="game-header">
        <h1>Imperialism</h1>
        <div className="header-info">
          <span>Turn {gameState.currentTurn}</span>
          <span>Phase: {gameState.gamePhase}</span>
          <button
            className="header-btn"
            onClick={handleSaveGame}
            title="Save game (Ctrl+S)"
          >
            SAVE
          </button>
        </div>
      </header>

      <div className="game-container">
        <GameMap />
        <GameUI />
      </div>

      <MusicPlayer visible={true} />
      <ReferenceViewer />
      <VictoryDisplay victoryStatus={lastTurnReport?.victoryStatus} />
    </div>
  );
}

export default App;
