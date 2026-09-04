import React, { useState } from 'react';
import { useGameStore } from '@game/store';
import { GameStorage } from '@game/gameStorage';
import '../styles/MainMenu.css';

type MenuScreen = 'main' | 'newGame' | 'loadGame' | 'settings';

export const MainMenu: React.FC = () => {
  const startNewGame = useGameStore(s => s.startNewGame);
  const [currentScreen, setCurrentScreen] = useState<MenuScreen>('main');
  const [difficulty, setDifficulty] = useState<'easy' | 'normal' | 'hard'>('normal');
  const [numCountries, setNumCountries] = useState(6);
  const [saves, setSaves] = useState<Record<string, any>>(GameStorage.getSaveSlots());

  const handleStartNewGame = () => {
    startNewGame({ numCountries, difficulty });
  };

  const handleLoadGame = (slotName: string) => {
    const gameState = GameStorage.loadGame(slotName);
    if (gameState) {
      const store = useGameStore.getState();
      store.loadGameState(gameState);
    }
  };

  const handleDeleteSave = (slotName: string) => {
    GameStorage.deleteSave(slotName);
    setSaves(GameStorage.getSaveSlots());
  };

  return (
    <div className="main-menu">
      <div className="menu-container">
        <header className="menu-header">
          <h1>IMPERIALISM</h1>
          <p className="menu-subtitle">1992 Exact Recreation</p>
        </header>

        {currentScreen === 'main' && (
          <div className="menu-content">
            <div className="menu-buttons">
              <button
                className="menu-btn large"
                onClick={() => setCurrentScreen('newGame')}
              >
                NEW GAME
              </button>
              <button
                className="menu-btn large"
                onClick={() => setCurrentScreen('loadGame')}
              >
                LOAD GAME
              </button>
              <button
                className="menu-btn large"
                onClick={() => setCurrentScreen('settings')}
              >
                SETTINGS
              </button>
              <button
                className="menu-btn large danger"
                onClick={() => window.close()}
              >
                EXIT
              </button>
            </div>
          </div>
        )}

        {currentScreen === 'newGame' && (
          <div className="menu-content">
            <h2>New Game</h2>
            <div className="menu-form">
              <div className="form-group">
                <label>Difficulty:</label>
                <select
                  value={difficulty}
                  onChange={e => setDifficulty(e.target.value as any)}
                  className="form-input"
                >
                  <option value="easy">Easy</option>
                  <option value="normal">Normal</option>
                  <option value="hard">Hard</option>
                </select>
              </div>

              <div className="form-group">
                <label>Number of Countries:</label>
                <input
                  type="number"
                  min="2"
                  max="8"
                  value={numCountries}
                  onChange={e => setNumCountries(parseInt(e.target.value))}
                  className="form-input"
                />
              </div>

              <div className="form-buttons">
                <button
                  className="menu-btn"
                  onClick={handleStartNewGame}
                >
                  START
                </button>
                <button
                  className="menu-btn"
                  onClick={() => setCurrentScreen('main')}
                >
                  BACK
                </button>
              </div>
            </div>
          </div>
        )}

        {currentScreen === 'loadGame' && (
          <div className="menu-content">
            <h2>Load Game</h2>
            <div className="saves-list">
              {Object.entries(saves).length > 0 ? (
                Object.entries(saves).map(([slotName, save]) => (
                  <div key={slotName} className="save-item">
                    <div className="save-info">
                      <span className="save-name">{save.name}</span>
                      <span className="save-details">
                        Turn {save.turn} | Year {save.year}
                      </span>
                      <span className="save-time">
                        {new Date(save.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="save-buttons">
                      <button
                        className="menu-btn small"
                        onClick={() => handleLoadGame(slotName)}
                      >
                        LOAD
                      </button>
                      <button
                        className="menu-btn small danger"
                        onClick={() => handleDeleteSave(slotName)}
                      >
                        DELETE
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="empty-message">No saves found</p>
              )}
            </div>
            <button
              className="menu-btn"
              onClick={() => setCurrentScreen('main')}
            >
              BACK
            </button>
          </div>
        )}

        {currentScreen === 'settings' && (
          <div className="menu-content">
            <h2>Settings</h2>
            <div className="menu-form">
              <div className="form-group">
                <label>Graphics:</label>
                <select className="form-input">
                  <option>Low (800x600)</option>
                  <option>Medium (1024x768)</option>
                  <option selected>High (1280x1024)</option>
                </select>
              </div>

              <div className="form-group">
                <label>Sound:</label>
                <input type="checkbox" defaultChecked />
              </div>

              <div className="form-group">
                <label>Auto-save interval:</label>
                <select className="form-input">
                  <option>Never</option>
                  <option>Every Turn</option>
                  <option selected>Every 5 Turns</option>
                </select>
              </div>

              <div className="form-buttons">
                <button
                  className="menu-btn"
                  onClick={() => setCurrentScreen('main')}
                >
                  BACK
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
