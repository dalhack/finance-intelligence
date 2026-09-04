// Executes AI decisions using the ActionEngine

import { GameState, Country } from '../types/index';
import { AIDecision } from './aiEngine';
import { ActionEngine } from './actionEngine';
import { TechnologyEngine } from './technologyEngine';

export class AIExecutor {
  /* Execute all AI decisions for a country */
  static executeDecisions(
    gameState: GameState,
    country: Country,
    decisions: AIDecision[]
  ): void {
    decisions.forEach(decision => {
      this.executeDecision(gameState, country, decision);
    });
  }

  /* Execute a single AI decision */
  private static executeDecision(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): void {
    switch (decision.type) {
      case 'military':
        this.executeMilitaryDecision(gameState, country, decision);
        break;

      case 'research':
        this.executeResearchDecision(gameState, country, decision);
        break;

      case 'infrastructure':
        this.executeInfrastructureDecision(gameState, country, decision);
        break;

      case 'diplomacy':
        this.executeDiplomacyDecision(gameState, country, decision);
        break;

      case 'economic':
        this.executeEconomicDecision(gameState, country, decision);
        break;
    }
  }

  /* Execute military decisions (recruit units, move units, attack) */
  private static executeMilitaryDecision(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): void {
    if (decision.action === 'recruit') {
      // Recruit unit in a random friendly province
      const friendlyProvinces = country.provinces.filter(p => p.owner === country.id);
      if (friendlyProvinces.length > 0) {
        const targetProvince = friendlyProvinces[Math.floor(Math.random() * friendlyProvinces.length)];
        ActionEngine.recruitUnit(gameState, country.id, targetProvince.id, 'infantry');
      }
    } else if (decision.action === 'move') {
      // Move all units towards enemies or unclaimed territories
      country.units.forEach(unit => {
        const enemies = gameState.units.filter(
          u => u.countryId !== country.id &&
          Math.abs(u.position.x - unit.position.x) <= 10 &&
          Math.abs(u.position.y - unit.position.y) <= 10
        );

        if (enemies.length > 0) {
          const target = enemies[0];
          const newX = unit.position.x + (target.position.x > unit.position.x ? 1 : -1);
          const newY = unit.position.y + (target.position.y > unit.position.y ? 1 : -1);
          ActionEngine.moveUnit(gameState, unit.id, newX, newY);
        }
      });
    }
  }

  /* Execute research decisions */
  private static executeResearchDecision(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): void {
    if (decision.action === 'research' && decision.target) {
      ActionEngine.researchTechnology(gameState, country.id, decision.target);
    }
  }

  /* Execute infrastructure decisions */
  private static executeInfrastructureDecision(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): void {
    const infrastructure = decision.action as 'railroad' | 'port' | 'depot' | 'industrialize';
    const targetProvinceId = decision.target;

    if (targetProvinceId) {
      ActionEngine.buildInfrastructure(gameState, country.id, targetProvinceId, infrastructure);
    }
  }

  /* Execute diplomatic decisions */
  private static executeDiplomacyDecision(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): void {
    if (!decision.target) return;

    const action = decision.action as 'consulte' | 'embassy' | 'alliance' | 'trade' | 'war';
    ActionEngine.establishDiplomacy(gameState, country.id, decision.target, action);
  }

  /* Execute economic decisions (currently placeholder) */
  private static executeEconomicDecision(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): void {
    // Economic decisions would involve resource allocation and trade
    // For now, this is handled through infrastructure and other decisions
  }
}
