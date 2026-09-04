import React, { useState } from 'react';
import { useGameStore } from '@game/store';
import { BattleScreen } from './BattleScreen';
import { TechnologyScreen } from './TechnologyScreen';
import '../styles/GameUI.css';

type ScreenType = 'map' | 'transport' | 'industry' | 'trade' | 'diplomacy' | 'battle' | 'research';

export const GameUI: React.FC = () => {
  const gameState = useGameStore(s => s.gameState);
  const nextTurn = useGameStore(s => s.nextTurn);
  const [currentScreen, setCurrentScreen] = useState<ScreenType>('map');

  if (!gameState) return null;

  const currentPlayer = gameState.countries.find(c => c.id === gameState.currentPlayerCountryId);
  const selectedProvince = gameState.selectedProvince;

  const screens: { id: ScreenType; label: string }[] = [
    { id: 'map', label: 'MAP' },
    { id: 'transport', label: 'TRANSPORT' },
    { id: 'industry', label: 'INDUSTRY' },
    { id: 'trade', label: 'TRADE' },
    { id: 'diplomacy', label: 'DIPLOMACY' },
    { id: 'research', label: 'RESEARCH' },
    { id: 'battle', label: 'BATTLE' },
  ];

  return (
    <aside className="game-ui">
      {/* Screen Tabs */}
      <div className="ui-panel">
        <div className="phase-buttons">
          {screens.map(screen => (
            <button
              key={screen.id}
              className={`phase-btn ${currentScreen === screen.id ? 'active' : ''}`}
              onClick={() => setCurrentScreen(screen.id)}
            >
              {screen.label}
            </button>
          ))}
        </div>
      </div>

      {/* MAP Screen */}
      {currentScreen === 'map' && (
        <>
          <div className="ui-panel">
            <h2>Empire</h2>
            {currentPlayer && (
              <div className="info-content">
                <p><strong>{currentPlayer.name}</strong></p>
                <p>Treasury: ${currentPlayer.treasury}</p>
                <p>Provinces: {currentPlayer.provinces.length}</p>
                <p>Units: {currentPlayer.units.length}</p>
                <p>Workers: 0</p>
              </div>
            )}
          </div>

          <div className="ui-panel">
            <h2>Selection</h2>
            {selectedProvince ? (
              <div className="info-content">
                <p><strong>{selectedProvince.name}</strong></p>
                <p>Owner: {selectedProvince.owner || 'Unclaimed'}</p>
                <p>Pop: {selectedProvince.population}</p>
                <p>Wheat: {selectedProvince.resources.wheat}</p>
                <p>Fish: {selectedProvince.resources.fish}</p>
                <p>Coal: {selectedProvince.resources.coal}</p>
              </div>
            ) : (
              <p className="empty-message">Select province</p>
            )}
          </div>
        </>
      )}

      {/* TRANSPORT Screen */}
      {currentScreen === 'transport' && (
        <>
          <div className="ui-panel">
            <h2>Transport</h2>
            {currentPlayer && (
              <div className="info-content">
                <p>Merchant Marine: {currentPlayer.merchantMarine}</p>
                <p>Freight Cars: {currentPlayer.freightCars}</p>
                <p>Consulates: {currentPlayer.consulates.size}</p>
              </div>
            )}
          </div>
          <div className="ui-panel">
            <div className="info-content">
              <button className="action-btn">View Routes</button>
              <button className="action-btn">Allocate</button>
              <button className="action-btn">Build Consulate</button>
            </div>
          </div>
        </>
      )}

      {/* INDUSTRY Screen */}
      {currentScreen === 'industry' && (
        <>
          <div className="ui-panel">
            <h2>Production</h2>
            {currentPlayer && (
              <div className="info-content">
                <p>Workers: {currentPlayer.workers}</p>
                <p>Productivity: Good</p>
              </div>
            )}
          </div>
          <div className="ui-panel">
            <h2>Raw Materials</h2>
            {selectedProvince ? (
              <div className="info-content">
                <p>Coal: {selectedProvince.resources.coal}</p>
                <p>Iron: {selectedProvince.resources.iron}</p>
                <p>Trees: {selectedProvince.resources.trees}</p>
                <p>Wheat: {selectedProvince.resources.wheat}</p>
              </div>
            ) : (
              <p className="empty-message">Select province</p>
            )}
          </div>
          <div className="ui-panel">
            <div className="info-content">
              <button className="action-btn">Allocate</button>
              <button className="action-btn">Train Workers</button>
            </div>
          </div>
        </>
      )}

      {/* TRADE Screen */}
      {currentScreen === 'trade' && (
        <div className="ui-panel">
          <h2>Trade</h2>
          <div className="info-content">
            <p>Trade Partners: {gameState.countries.length - 1}</p>
            <p>Consulates: 0</p>
            <p>Income: $0</p>
            <button className="action-btn">Give Orders</button>
            <button className="action-btn">Consulates</button>
          </div>
        </div>
      )}

      {/* DIPLOMACY Screen */}
      {currentScreen === 'diplomacy' && (
        <div className="ui-panel">
          <h2>Relations</h2>
          <div className="info-content">
            <p>Alliances: 0</p>
            <p>Wars: 0</p>
            <p>Treaties: 0</p>
            <button className="action-btn">Negotiate</button>
            <button className="action-btn">Declare War</button>
          </div>
        </div>
      )}

      {/* RESEARCH Screen */}
      {currentScreen === 'research' && currentPlayer && (
        <TechnologyScreen
          researchedTechs={new Set()}
          treasury={currentPlayer.treasury}
          onResearch={(techId) => console.log('Research:', techId)}
        />
      )}

      {/* BATTLE Screen */}
      {currentScreen === 'battle' && (
        <BattleScreen
          side1Units={[]}
          side2Units={[]}
          terrain="plain"
          turn={gameState.currentTurn}
          onClose={() => setCurrentScreen('map')}
        />
      )}

      {/* Footer */}
      <div className="ui-panel">
        <button className="next-turn-btn" onClick={nextTurn}>
          END TURN
        </button>
      </div>

      <div className="ui-panel">
        <div className="info-content">
          <p>Turn: {gameState.currentTurn}</p>
          <p>Era: Industrial</p>
        </div>
      </div>
    </aside>
  );
};
