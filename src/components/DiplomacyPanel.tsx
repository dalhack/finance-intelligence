import React from 'react';
import { useGameStore } from '../game/store';
import './DiplomacyPanel.css';

export const DiplomacyPanel: React.FC = () => {
  const gameState = useGameStore(s => s.gameState);
  const currentPlayer = gameState?.countries.find(c => c.id === gameState?.currentPlayerCountryId);

  if (!gameState || !currentPlayer) return null;

  const getDiplomacyStatus = (trust: number, warState: boolean): string => {
    if (warState) return 'WAR';
    if (trust > 75) return 'ALLY';
    if (trust > 50) return 'FRIENDLY';
    if (trust > 25) return 'NEUTRAL';
    return 'HOSTILE';
  };

  const getDiplomacyColor = (status: string): string => {
    switch (status) {
      case 'WAR': return '#ff0000';
      case 'ALLY': return '#00ff00';
      case 'FRIENDLY': return '#00aa00';
      case 'NEUTRAL': return '#aaaa00';
      default: return '#ff6600';
    }
  };

  const otherCountries = gameState.countries.filter(c => c.id !== gameState.currentPlayerCountryId);

  return (
    <div className="diplomacy-panel">
      <div className="diplomacy-header">
        <h3>DIPLOMATIC RELATIONS</h3>
      </div>

      <div className="diplomacy-list">
        {otherCountries.length === 0 ? (
          <p className="no-diplomacy">No other countries</p>
        ) : (
          otherCountries.map(country => {
            const relation = currentPlayer.diplomacy.get(country.id);
            if (!relation) return null;

            const status = getDiplomacyStatus(relation.trust, relation.warState);
            const color = getDiplomacyColor(status);

            return (
              <div key={country.id} className="diplomacy-entry">
                <div className="country-row">
                  <span className="country-name">{country.name}</span>
                  <span className="status-badge" style={{ borderColor: color, color }}>
                    {status}
                  </span>
                </div>
                <div className="trust-bar-container">
                  <div className="trust-label">
                    <span>Trust:</span>
                    <span className="trust-value">{Math.round(relation.trust)}</span>
                  </div>
                  <div className="trust-bar">
                    <div
                      className="trust-fill"
                      style={{
                        width: `${Math.min(100, (relation.trust / 100) * 100)}%`,
                        backgroundColor: relation.trust > 50 ? '#00aa00' : '#ff6600',
                      }}
                    />
                  </div>
                </div>
                <div className="diplomacy-details">
                  {relation.tradeAgreement && (
                    <span className="agreement-badge">TRADE</span>
                  )}
                  <span className="unit-count">
                    Units: {gameState.units.filter(u => u.countryId === country.id).length}
                  </span>
                  <span className="province-count">
                    Provinces: {country.provinces.length}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default DiplomacyPanel;
