import React, { useState } from 'react';
import { useGameStore } from '../game/store';
import { ActionEngine } from '../game/actionEngine';
import './ActionPanel.css';

type MessageType = 'success' | 'error' | 'info';

export const ActionPanel: React.FC = () => {
  const gameState = useGameStore(s => s.gameState);
  const executeAction = useGameStore(s => s.executeAction);
  const [message, setMessage] = useState<string>('');
  const [messageType, setMessageType] = useState<MessageType>('info');

  if (!gameState) return null;

  const selectedUnit = gameState.selectedUnit;
  const selectedProvince = gameState.selectedProvince;
  const currentPlayer = gameState.countries.find(c => c.id === gameState.currentPlayerCountryId);

  const showMessage = (msg: string, type: MessageType = 'info') => {
    setMessage(msg);
    setMessageType(type);
    setTimeout(() => setMessage(''), 4000);
  };

  const handleMoveUnit = () => {
    if (!selectedUnit || !gameState || !currentPlayer) {
      showMessage('No unit selected', 'error');
      return;
    }

    // Find nearby enemy units or unclaimed provinces to move towards
    const nearbyEnemies = gameState.units.filter(
      u => u.countryId !== selectedUnit.countryId &&
      Math.abs(u.position.x - selectedUnit.position.x) <= 5 &&
      Math.abs(u.position.y - selectedUnit.position.y) <= 5
    );

    let newX = selectedUnit.position.x;
    let newY = selectedUnit.position.y;

    if (nearbyEnemies.length > 0) {
      // Move towards nearest enemy
      const enemy = nearbyEnemies[0];
      if (enemy.position.x > selectedUnit.position.x) newX++;
      else if (enemy.position.x < selectedUnit.position.x) newX--;
      if (enemy.position.y > selectedUnit.position.y) newY++;
      else if (enemy.position.y < selectedUnit.position.y) newY--;
    } else {
      // Move towards unclaimed provinces or provinces to expand
      const unclaimedProvinces = gameState.provinces.filter(
        p => !p.owner ||
        (p.owner !== currentPlayer.id &&
         Math.abs(p.position.x - selectedUnit.position.x) <= 5 &&
         Math.abs(p.position.y - selectedUnit.position.y) <= 5)
      );

      if (unclaimedProvinces.length > 0) {
        const target = unclaimedProvinces[0];
        if (target.position.x > selectedUnit.position.x) newX++;
        else if (target.position.x < selectedUnit.position.x) newX--;
        if (target.position.y > selectedUnit.position.y) newY++;
        else if (target.position.y < selectedUnit.position.y) newY--;
      } else {
        // Random movement
        newX += Math.random() > 0.5 ? 1 : -1;
        newY += Math.random() > 0.5 ? 1 : -1;
      }
    }

    const result = executeAction(() =>
      ActionEngine.moveUnit(gameState, selectedUnit.id, newX, newY)
    );
    showMessage(result.message, result.success ? 'success' : 'error');
  };

  const handleRecruitUnit = () => {
    if (!selectedProvince || !currentPlayer || !gameState) {
      showMessage('Select a province first', 'error');
      return;
    }

    if (selectedProvince.owner !== currentPlayer.id) {
      showMessage('You do not own this province', 'error');
      return;
    }

    const result = executeAction(() =>
      ActionEngine.recruitUnit(
        gameState,
        currentPlayer.id,
        selectedProvince.id,
        'infantry'
      )
    );

    showMessage(result.message, result.success ? 'success' : 'error');
  };

  const handleBuildRailroad = () => {
    if (!selectedProvince || !currentPlayer || !gameState) {
      showMessage('Select a province first', 'error');
      return;
    }

    if (selectedProvince.owner !== currentPlayer.id) {
      showMessage('You do not own this province', 'error');
      return;
    }

    const result = executeAction(() =>
      ActionEngine.buildInfrastructure(
        gameState,
        currentPlayer.id,
        selectedProvince.id,
        'railroad'
      )
    );

    showMessage(result.message, result.success ? 'success' : 'error');
  };

  const handleBuildPort = () => {
    if (!selectedProvince || !currentPlayer || !gameState) {
      showMessage('Select a province first', 'error');
      return;
    }

    if (selectedProvince.owner !== currentPlayer.id) {
      showMessage('You do not own this province', 'error');
      return;
    }

    const result = executeAction(() =>
      ActionEngine.buildInfrastructure(
        gameState,
        currentPlayer.id,
        selectedProvince.id,
        'port'
      )
    );

    showMessage(result.message, result.success ? 'success' : 'error');
  };

  const handleIndustrialize = () => {
    if (!selectedProvince || !currentPlayer || !gameState) {
      showMessage('Select a province first', 'error');
      return;
    }

    if (selectedProvince.owner !== currentPlayer.id) {
      showMessage('You do not own this province', 'error');
      return;
    }

    const result = executeAction(() =>
      ActionEngine.buildInfrastructure(
        gameState,
        currentPlayer.id,
        selectedProvince.id,
        'industrialize'
      )
    );

    showMessage(result.message, result.success ? 'success' : 'error');
  };

  const handleTechnology = (techId: string) => {
    if (!currentPlayer || !gameState) return;

    const result = executeAction(() =>
      ActionEngine.researchTechnology(gameState, currentPlayer.id, techId)
    );
    showMessage(result.message, result.success ? 'success' : 'error');
  };

  const validUnitActions = selectedUnit
    ? ActionEngine.getValidUnitActions(gameState, selectedUnit.id, gameState.currentPlayerCountryId)
    : [];

  return (
    <div className="action-panel">
      {/* Message Display */}
      {message && (
        <div className={`action-message ${messageType}`}>
          {message}
        </div>
      )}

      {/* Unit Actions */}
      <div className="action-section">
        <h3>Unit Actions</h3>
        {selectedUnit ? (
          <div className="action-buttons">
            <div className="unit-info">
              <span>Type: {selectedUnit.type}</span>
              <span>Health: {selectedUnit.health}</span>
              <span>Morale: {selectedUnit.morale}</span>
            </div>
            {validUnitActions.includes('move') && (
              <button className="action-btn" onClick={handleMoveUnit}>
                Move Unit
              </button>
            )}
            {validUnitActions.includes('attack') && (
              <button className="action-btn attack">
                Attack Enemy
              </button>
            )}
          </div>
        ) : (
          <p className="empty-action">Select a unit</p>
        )}
      </div>

      {/* Province Actions */}
      <div className="action-section">
        <h3>Province Actions</h3>
        {selectedProvince ? (
          <div className="action-buttons">
            <div className="province-info">
              <span>{selectedProvince.name}</span>
              <span>Owner: {selectedProvince.owner ? 'Owned' : 'Unclaimed'}</span>
            </div>
            {selectedProvince.owner === gameState.currentPlayerCountryId && (
              <>
                {!selectedProvince.infrastructure.hasRailroad && (
                  <button className="action-btn" onClick={handleBuildRailroad}>
                    Build Railroad ($5000)
                  </button>
                )}
                {!selectedProvince.infrastructure.hasPort && (
                  <button className="action-btn" onClick={handleBuildPort}>
                    Build Port ($6000)
                  </button>
                )}
                {!selectedProvince.infrastructure.industrialized && (
                  <button className="action-btn" onClick={handleIndustrialize}>
                    Industrialize ($8000)
                  </button>
                )}
                <button className="action-btn" onClick={handleRecruitUnit}>
                  Recruit Unit ($1000)
                </button>
              </>
            )}
          </div>
        ) : (
          <p className="empty-action">Select a province</p>
        )}
      </div>

      {/* Research Actions */}
      <div className="action-section">
        <h3>Research</h3>
        <div className="action-buttons research-buttons">
          <button
            className="action-btn research"
            onClick={() => handleTechnology('rifling')}
            title="Cost: 2500"
          >
            Rifling ($2500)
          </button>
          <button
            className="action-btn research"
            onClick={() => handleTechnology('steam_power')}
            title="Cost: 3000"
          >
            Steam Power ($3000)
          </button>
          <button
            className="action-btn research"
            onClick={() => handleTechnology('railway')}
            title="Cost: 3500"
          >
            Railway ($3500)
          </button>
          <button
            className="action-btn research"
            onClick={() => handleTechnology('machine_guns')}
            title="Cost: 4000"
          >
            Machine Guns ($4000)
          </button>
        </div>
      </div>

      {/* Diplomatic Actions */}
      <div className="action-section">
        <h3>Diplomacy</h3>
        <div className="action-buttons">
          <button className="action-btn diplomacy">
            Trade Agreement
          </button>
          <button className="action-btn diplomacy">
            Alliance
          </button>
          <button className="action-btn diplomacy warning">
            Declare War
          </button>
        </div>
      </div>
    </div>
  );
};

export default ActionPanel;
