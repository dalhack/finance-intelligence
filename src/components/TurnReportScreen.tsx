import React, { useState } from 'react';
import { TurnReport } from '@game/turnEngine';
import { AIDecision } from '@game/aiEngine';
import '../styles/TurnReportScreen.css';

interface TurnReportScreenProps {
  report: TurnReport;
  aiDecisions: Map<string, AIDecision[]>;
  previousBalance: number;
  currentBalance: number;
  onClose: () => void;
}

export const TurnReportScreen: React.FC<TurnReportScreenProps> = ({
  report,
  aiDecisions,
  previousBalance,
  currentBalance,
  onClose,
}) => {
  const [expandedCountry, setExpandedCountry] = useState<string | null>(null);

  const balanceChange = currentBalance - previousBalance;
  const balanceChangeColor = balanceChange >= 0 ? '#55ff55' : '#ff5555';

  return (
    <div className="turn-report-screen">
      <div className="report-header">
        <h2>TURN {report.turn} SUMMARY</h2>
        <p>Year {report.year}</p>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>

      <div className="report-container">
        {/* Summary Panel */}
        <div className="summary-panel">
          <h3>FINANCIAL SUMMARY</h3>
          <div className="summary-row">
            <span>Total Income:</span>
            <span style={{ color: '#55ff55' }}>${report.totalIncome}</span>
          </div>
          <div className="summary-row">
            <span>Total Expenses:</span>
            <span style={{ color: '#ff5555' }}>${report.totalExpenses}</span>
          </div>
          <div className="summary-row">
            <span>Net Change:</span>
            <span style={{ color: balanceChangeColor }}>
              {balanceChange >= 0 ? '+' : ''} ${balanceChange}
            </span>
          </div>
          <div className="summary-row">
            <span>New Balance:</span>
            <span style={{ color: '#ffff00' }}>${currentBalance}</span>
          </div>
        </div>

        {/* Events Panel */}
        <div className="events-panel">
          <h3>EVENTS</h3>
          {report.events.length > 0 ? (
            <ul className="events-list">
              {report.events.map((event, idx) => (
                <li key={idx} className="event-item">
                  {event}
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-message">No significant events this turn</p>
          )}
        </div>

        {/* Warnings Panel */}
        {report.warnings.length > 0 && (
          <div className="warnings-panel">
            <h3>WARNINGS</h3>
            <ul className="warnings-list">
              {report.warnings.map((warning, idx) => (
                <li key={idx} className="warning-item">
                  ⚠️ {warning}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* AI Decisions Panel */}
        {aiDecisions.size > 0 && (
          <div className="ai-decisions-panel">
            <h3>DIPLOMATIC INTELLIGENCE</h3>
            <div className="ai-countries">
              {Array.from(aiDecisions.entries()).map(([countryId, decisions]) => (
                <div key={countryId} className="ai-country">
                  <button
                    className={`country-header ${expandedCountry === countryId ? 'expanded' : ''}`}
                    onClick={() => setExpandedCountry(expandedCountry === countryId ? null : countryId)}
                  >
                    <span className="country-name">Country {countryId.slice(0, 8)}</span>
                    <span className="decision-count">{decisions.length} decision{decisions.length !== 1 ? 's' : ''}</span>
                    <span className="expand-icon">{expandedCountry === countryId ? '▼' : '▶'}</span>
                  </button>

                  {expandedCountry === countryId && (
                    <div className="decisions-list">
                      {decisions.map((decision, idx) => (
                        <div key={idx} className={`decision-item decision-${decision.type}`}>
                          <div className="decision-header">
                            <span className="decision-type">{decision.type.toUpperCase()}</span>
                            <span className="decision-action">{decision.action}</span>
                          </div>
                          <p className="decision-reason">{decision.reason}</p>
                          {decision.target && (
                            <p className="decision-target">Target: {decision.target}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="report-footer">
        <button className="continue-btn" onClick={onClose}>
          CONTINUE GAME
        </button>
      </div>
    </div>
  );
};
