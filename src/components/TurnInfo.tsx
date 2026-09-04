import React from 'react';
import { useGameStore } from '../game/store';
import './TurnInfo.css';

export const TurnInfo: React.FC = () => {
  const gameState = useGameStore(s => s.gameState);
  const lastTurnReport = useGameStore(s => s.lastTurnReport);
  const currentPlayer = gameState?.countries.find(c => c.id === gameState?.currentPlayerCountryId);

  if (!gameState || !currentPlayer) return null;

  return (
    <div className="turn-info-panel">
      <div className="turn-header">
        <h3>TURN {gameState.currentTurn} (YEAR {gameState.year})</h3>
      </div>

      <div className="player-info">
        <div className="info-row">
          <span className="label">Empire:</span>
          <span className="value">{currentPlayer.name}</span>
        </div>
        <div className="info-row">
          <span className="label">Treasury:</span>
          <span className="value treasury">${currentPlayer.treasury}</span>
        </div>
        <div className="info-row">
          <span className="label">Provinces:</span>
          <span className="value">{currentPlayer.provinces.length}</span>
        </div>
        <div className="info-row">
          <span className="label">Units:</span>
          <span className="value">{currentPlayer.units.length}</span>
        </div>
        <div className="info-row">
          <span className="label">Workers:</span>
          <span className="value">{currentPlayer.workers}</span>
        </div>
        <div className="info-row">
          <span className="label">Military Era:</span>
          <span className="value">{gameState.militaryEra}</span>
        </div>
      </div>

      {lastTurnReport && (
        <div className="turn-report">
          <h4>LAST TURN SUMMARY</h4>
          <div className="report-item">
            <span>Income:</span>
            <span className="income">${lastTurnReport.totalIncome}</span>
          </div>
          <div className="report-item">
            <span>Expenses:</span>
            <span className="expense">${lastTurnReport.totalExpenses}</span>
          </div>
          <div className="report-item">
            <span>Net:</span>
            <span className={lastTurnReport.totalIncome - lastTurnReport.totalExpenses >= 0 ? 'income' : 'expense'}>
              ${lastTurnReport.totalIncome - lastTurnReport.totalExpenses}
            </span>
          </div>

          {lastTurnReport.events.length > 0 && (
            <div className="events-section">
              <h5>EVENTS</h5>
              {lastTurnReport.events.map((event, idx) => (
                <div key={idx} className="event-item">{event}</div>
              ))}
            </div>
          )}

          {lastTurnReport.warnings.length > 0 && (
            <div className="warnings-section">
              <h5>WARNINGS</h5>
              {lastTurnReport.warnings.map((warning, idx) => (
                <div key={idx} className="warning-item">⚠️ {warning}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TurnInfo;
