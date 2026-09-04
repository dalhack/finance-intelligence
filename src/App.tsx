import React, { useEffect } from 'react';
import { useGameStore } from '@game/store';
import { GameMap } from '@components/GameMap';
import { GameUI } from '@components/GameUI';
import './styles/App.css';

function App() {
  const gameState = useGameStore(s => s.gameState);
  const startNewGame = useGameStore(s => s.startNewGame);
  const isLoading = useGameStore(s => s.isLoading);
  const error = useGameStore(s => s.error);

  useEffect(() => {
    if (!gameState) {
      startNewGame({ numCountries: 6, difficulty: 'normal' });
    }
  }, []);

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
    </div>
  );
}

export default App;
