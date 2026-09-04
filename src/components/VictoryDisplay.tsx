import React from 'react';
import { useGameStore } from '../game/store';
import { VictoryStatus } from '../game/victoryEngine';
import './VictoryDisplay.css';

interface VictoryDisplayProps {
  victoryStatus?: VictoryStatus;
}

export const VictoryDisplay: React.FC<VictoryDisplayProps> = ({ victoryStatus }) => {
  if (!victoryStatus || !victoryStatus.gameOver) {
    return null;
  }

  return (
    <div className="victory-overlay">
      <div className="victory-modal">
        <div className="victory-header">
          <h1 className="victory-title">GAME OVER</h1>
        </div>

        <div className="victory-content">
          {victoryStatus.winner && (
            <>
              <div className="winner-info">
                <h2 className="winner-name">{victoryStatus.winner.name}</h2>
                <p className="winner-title">SUPREME RULER</p>
              </div>

              <div className="victory-reason">
                <p>{victoryStatus.reason}</p>
              </div>

              <div className="winner-stats">
                <div className="stat-row">
                  <span className="stat-label">Provinces Controlled:</span>
                  <span className="stat-value">{victoryStatus.winner.provinces.length}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Final Treasury:</span>
                  <span className="stat-value">${victoryStatus.winner.treasury}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Military Units:</span>
                  <span className="stat-value">{victoryStatus.winner.units.length}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-label">Technologies:</span>
                  <span className="stat-value">{victoryStatus.winner.technology.size}</span>
                </div>
              </div>

              <div className="victory-conditions">
                <h3>VICTORY CONDITIONS</h3>
                <div className="conditions-list">
                  {victoryStatus.conditions.map(condition => (
                    <div key={condition.type} className="condition-item">
                      <span className="condition-name">{condition.name}</span>
                      <div className="condition-bar">
                        <div
                          className={`condition-fill ${condition.met ? 'completed' : ''}`}
                          style={{ width: `${Math.min(100, condition.progress)}%` }}
                        />
                      </div>
                      <span className="condition-progress">{condition.progress}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="victory-actions">
          <button className="victory-btn" onClick={() => window.location.reload()}>
            NEW GAME
          </button>
        </div>
      </div>
    </div>
  );
};

export default VictoryDisplay;
