import React, { useState } from 'react';
import { TechnologyEngine, TECHNOLOGIES } from '@game/technologyEngine';
import '../styles/TechnologyScreen.css';

interface TechnologyScreenProps {
  researchedTechs: Set<string>;
  treasury: number;
  onResearch: (techId: string) => void;
}

export const TechnologyScreen: React.FC<TechnologyScreenProps> = ({
  researchedTechs,
  treasury,
  onResearch,
}) => {
  const [selectedTech, setSelectedTech] = useState<string | null>(null);

  const selectedTechData = selectedTech ? TECHNOLOGIES[selectedTech] : null;
  const canResearch = selectedTechData && selectedTech
    ? TechnologyEngine.canResearch(selectedTech, researchedTechs)
    : { canResearch: false };

  const eras = [1, 2, 3, 4];

  const handleResearch = () => {
    if (selectedTech && canResearch.canResearch) {
      onResearch(selectedTech);
    }
  };

  return (
    <div className="technology-screen">
      <div className="tech-header">
        <h2>RESEARCH & DEVELOPMENT</h2>
      </div>

      <div className="tech-container">
        <div className="tech-eras">
          {eras.map(era => (
            <div key={era} className={`tech-era era-${era}`}>
              <h3>ERA {era}</h3>
              <div className="tech-list">
                {TechnologyEngine.getTechnologiesByEra(era).map(tech => {
                  const isResearched = researchedTechs.has(tech.id);
                  const isSelected = selectedTech === tech.id;
                  const canRes = TechnologyEngine.canResearch(
                    tech.id,
                    researchedTechs
                  );

                  return (
                    <button
                      key={tech.id}
                      className={`tech-btn ${isResearched ? 'researched' : ''} ${
                        isSelected ? 'selected' : ''
                      } ${canRes.canResearch ? 'available' : 'unavailable'}`}
                      onClick={() => setSelectedTech(tech.id)}
                      disabled={isResearched}
                    >
                      <span className="tech-name">{tech.name}</span>
                      {isResearched && <span className="checkmark">✓</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {selectedTechData && (
          <div className="tech-details">
            <h3>{selectedTechData.name}</h3>

            <div className="tech-info">
              <p className="description">{selectedTechData.description}</p>

              <div className="cost-block">
                <span>Research Time:</span>
                <span className="cost-amount">{selectedTechData.researchTime} turns</span>
              </div>

              {selectedTechData.prerequisites.length > 0 && (
                <div className="prerequisites">
                  <h4>Prerequisites:</h4>
                  <ul>
                    {selectedTechData.prerequisites.map(prereqId => {
                      const prereq = TECHNOLOGIES[prereqId];
                      const isComplete = researchedTechs.has(prereqId);
                      return (
                        <li key={prereqId} className={isComplete ? 'complete' : 'incomplete'}>
                          {isComplete ? '✓' : '✗'} {prereq.name}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              <div className="effects">
                <h4>Effects:</h4>
                <ul>
                  {selectedTechData.effects.combatBonus && (
                    <li>+{selectedTechData.effects.combatBonus}% Combat</li>
                  )}
                  {selectedTechData.effects.productionBonus && (
                    <li>+{selectedTechData.effects.productionBonus}% Production</li>
                  )}
                  {selectedTechData.effects.movementBonus && (
                    <li>+{selectedTechData.effects.movementBonus} Movement</li>
                  )}
                  {selectedTechData.effects.tradeBonus && (
                    <li>+{selectedTechData.effects.tradeBonus}% Trade</li>
                  )}
                </ul>
              </div>

              {researchedTechs.has(selectedTech!) ? (
                <div className="status researched-status">RESEARCHED</div>
              ) : (
                <>
                  {canResearch.canResearch ? (
                    <button className="research-btn" onClick={handleResearch}>
                      START RESEARCH
                    </button>
                  ) : (
                    <div className="status blocked-status">
                      {canResearch.reason}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
