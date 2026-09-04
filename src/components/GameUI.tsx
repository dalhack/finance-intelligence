import React from 'react';
import { useGameStore } from '@game/store';
import '../styles/GameUI.css';

export const GameUI: React.FC = () => {
  const gameState = useGameStore(s => s.gameState);
  const nextTurn = useGameStore(s => s.nextTurn);
  const setGamePhase = useGameStore(s => s.setGamePhase);

  if (!gameState) return null;

  const currentPlayer = gameState.countries.find(c => c.id === gameState.currentPlayerCountryId);
  const selectedProvince = gameState.selectedProvince;

  const phaseOptions = ['diplomacy', 'movement', 'combat', 'research', 'end-turn'] as const;

  return (
    <aside className="game-ui">
      <div className="ui-panel">
        <h2>Country Info</h2>
        {currentPlayer && (
          <div className="info-content">
            <p><strong>{currentPlayer.name}</strong></p>
            <p>Treasury: {currentPlayer.treasury} gold</p>
            <p>Provinces: {currentPlayer.provinces.length}</p>
            <p>Units: {currentPlayer.units.length}</p>
          </div>
        )}
      </div>

      <div className="ui-panel">
        <h2>Province Info</h2>
        {selectedProvince ? (
          <div className="info-content">
            <p><strong>{selectedProvince.name}</strong></p>
            <p>Owner: {selectedProvince.owner ? `Country ${selectedProvince.owner}` : 'Unclaimed'}</p>
            <p>Population: {selectedProvince.population.toLocaleString()}</p>
            <p>Food: {selectedProvince.resources.food}</p>
            <p>Gold: {selectedProvince.resources.gold}</p>
            <p>Production: {selectedProvince.resources.production}</p>
          </div>
        ) : (
          <p className="empty-message">Click on a province to view details</p>
        )}
      </div>

      <div className="ui-panel">
        <h2>Game Phase</h2>
        <div className="phase-buttons">
          {phaseOptions.map(phase => (
            <button
              key={phase}
              className={`phase-btn ${gameState.gamePhase === phase ? 'active' : ''}`}
              onClick={() => setGamePhase(phase)}
            >
              {phase.charAt(0).toUpperCase() + phase.slice(1).replace('-', ' ')}
            </button>
          ))}
        </div>
      </div>

      <div className="ui-panel">
        <button className="next-turn-btn" onClick={nextTurn}>
          Next Turn →
        </button>
      </div>

      <div className="ui-panel">
        <h2>Actions</h2>
        <button className="action-btn">Build Unit</button>
        <button className="action-btn">Build Structure</button>
        <button className="action-btn">Diplomacy</button>
        <button className="action-btn">Trade</button>
        <button className="action-btn">Research</button>
      </div>
    </aside>
  );
};
