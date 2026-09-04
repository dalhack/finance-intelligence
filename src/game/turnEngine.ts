import { GameState, Country } from '../types/index';
import { MilitaryEngine } from './militaryEngine';
import { EconomyEngine } from './economyEngine';
import { TechnologyEngine } from './technologyEngine';
import { VictoryEngine, VictoryStatus } from './victoryEngine';
import { AIEngine } from './aiEngine';
import { AIActionExecutor } from './aiActionExecutor';

export interface TurnReport {
  turn: number;
  year: number;
  phase: string;
  totalIncome: number;
  totalExpenses: number;
  events: string[];
  warnings: string[];
  victoryStatus?: VictoryStatus;
}

export class TurnEngine {
  /**
   * Process complete game turn following exact 1992 Imperialism turn order:
   * 1. DIPLOMACY PHASE - Negotiate peace/war
   * 2. MOVEMENT PHASE - Move all units
   * 3. COMBAT PHASE - Resolve battles
   * 4. RESEARCH PHASE - Advance technology
   * 5. TURN ENDING - Economy, production, maintenance, victory check, year increment
   */
  static processTurn(gameState: GameState): TurnReport {
    const report: TurnReport = {
      turn: gameState.currentTurn,
      year: gameState.year,
      phase: 'start',
      totalIncome: 0,
      totalExpenses: 0,
      events: [],
      warnings: [],
    };

    // PHASE 0: AI DECISION MAKING & EXECUTION
    report.phase = 'ai-actions';
    this.processAIDecisions(gameState, report);

    // PHASE 1: DIPLOMACY
    report.phase = 'diplomacy';
    this.processDiplomacyPhase(gameState, report);

    // PHASE 2: MOVEMENT
    report.phase = 'movement';
    this.processMovementPhase(gameState, report);

    // PHASE 3: COMBAT
    report.phase = 'combat';
    this.processCombatPhase(gameState, report);

    // PHASE 4: RESEARCH
    report.phase = 'research';
    this.processResearchPhase(gameState, report);

    // PHASE 5: TURN ENDING (Economy, Production, Maintenance, Victory, Year)
    report.phase = 'ending';
    this.processTurnEnding(gameState, report);

    // Update turn counter
    gameState.currentTurn++;

    // Check year increment (4 turns per year)
    if ((gameState.currentTurn - 1) % 4 === 0) {
      gameState.year++;
      report.year = gameState.year;
      report.events.push(`Year ${gameState.year} started`);
    }

    // Set next phase
    gameState.gamePhase = 'diplomacy';

    return report;
  }

  /**
   * AI DECISION MAKING & EXECUTION: Get AI decisions and execute them
   */
  private static processAIDecisions(gameState: GameState, report: TurnReport): void {
    const aiDecisions = new Map<string, any[]>();

    gameState.countries.forEach(country => {
      if (country.type === 'ai') {
        const decisions = AIEngine.makeDecisions(country, gameState.countries, gameState);
        if (decisions.length > 0) {
          aiDecisions.set(country.id, decisions);
        }
      }
    });

    if (aiDecisions.size > 0) {
      const executionResult = AIActionExecutor.executeDecisions(gameState, aiDecisions);
      report.events.push(`AI actions executed: ${executionResult.success} successful, ${executionResult.failed} failed`);
      executionResult.messages.forEach(msg => report.events.push(msg));
    }
  }

  /**
   * DIPLOMACY PHASE: Countries declare war/peace, form alliances
   */
  private static processDiplomacyPhase(gameState: GameState, report: TurnReport): void {
    gameState.countries.forEach(country => {
      country.diplomacy.forEach((relation, otherId) => {
        // Apply trust decay per turn
        relation.trust = Math.max(0, relation.trust - 0.5);

        // Check if countries should be at war based on previous declarations
        if (relation.warState) {
          report.events.push(`${country.name} continues war with ${gameState.countries.find(c => c.id === otherId)?.name}`);
        }
      });
    });
  }

  /**
   * MOVEMENT PHASE: All units move according to their movement points
   */
  private static processMovementPhase(gameState: GameState, report: TurnReport): void {
    // AI units move automatically
    gameState.units.forEach(unit => {
      const country = gameState.countries.find(c => c.id === unit.countryId);
      if (country && country.type !== 'player') {
        // AI movement logic - simplified for now
        this.moveAIUnit(unit, gameState);
      }
    });

    report.events.push(`Movement phase: ${gameState.units.length} units processed`);
  }

  /**
   * COMBAT PHASE: Resolve all active combats
   */
  private static processCombatPhase(gameState: GameState, report: TurnReport): void {
    let combatsResolved = 0;

    gameState.units.forEach(attacker => {
      if (attacker.health <= 0) return;

      gameState.units.forEach(defender => {
        if (defender.health <= 0 || attacker.id === defender.id) return;
        if (attacker.countryId === defender.countryId) return;

        // Check if units are at same position
        if (
          attacker.position.x === defender.position.x &&
          attacker.position.y === defender.position.y
        ) {
          const defenderProvince = gameState.provinces.find(
            p => p.position.x === defender.position.x && p.position.y === defender.position.y
          );

          if (defenderProvince) {
            const result = MilitaryEngine.resolveCombat(attacker, defender, defenderProvince);
            combatsResolved++;

            if (result.attackerWins) {
              report.events.push(
                `${gameState.countries.find(c => c.id === attacker.countryId)?.name} defeated ${gameState.countries.find(c => c.id === defender.countryId)?.name} unit`
              );
            }

            // Remove dead units
            if (defender.health <= 0) {
              const idx = gameState.units.indexOf(defender);
              if (idx > -1) gameState.units.splice(idx, 1);
            }
          }
        }
      });
    });

    if (combatsResolved > 0) {
      report.events.push(`Combat phase: ${combatsResolved} battle(s) resolved`);
    }
  }

  /**
   * RESEARCH PHASE: Advance technology research for all countries
   */
  private static processResearchPhase(gameState: GameState, report: TurnReport): void {
    gameState.countries.forEach(country => {
      const techCount = country.technology.size;
      if (techCount > 0) {
        // Advance all research by 1 turn
        const completed = TechnologyEngine.advanceResearch(country.technology, country.researchedTechnologies);

        if (completed.length > 0) {
          completed.forEach(techId => {
            const tech = TechnologyEngine.getTechnology(techId);
            report.events.push(`${country.name} completed research: ${tech?.name}`);
          });
        } else {
          report.events.push(`${country.name} continues research (${techCount} technologies)`);
        }
      }
    });
  }

  /**
   * TURN ENDING: Economy, production, maintenance, victory check, year increment
   */
  private static processTurnEnding(gameState: GameState, report: TurnReport): void {
    gameState.countries.forEach(country => {
      // Calculate raw materials from provinces
      const rawProduction: Record<string, number> = {};
      country.provinces.forEach(province => {
        const pRaw = EconomyEngine.calculateRawProduction(province);
        Object.entries(pRaw).forEach(([key, value]) => {
          rawProduction[key] = (rawProduction[key] || 0) + (value as number);
        });
      });

      // Calculate processed goods (70% of workers)
      const processedProduction: Record<string, number> = {};
      country.provinces.forEach(province => {
        const workers = Math.floor(province.workers * 0.7);
        const pProcessed = EconomyEngine.calculateProcessedProduction(province, workers);
        Object.entries(pProcessed).forEach(([key, value]) => {
          processedProduction[key] = (processedProduction[key] || 0) + (value as number);
        });
      });

      // Calculate finished goods (30% of workers)
      const finishedProduction: Record<string, number> = {};
      country.provinces.forEach(province => {
        const workers = Math.floor(province.workers * 0.3);
        const pFinished = EconomyEngine.calculateFinishedGoods(province, workers);
        Object.entries(pFinished).forEach(([key, value]) => {
          finishedProduction[key] = (finishedProduction[key] || 0) + (value as number);
        });
      });

      // Calculate income from resources and trade
      const { income } = EconomyEngine.processCountryEconomics(country);
      report.totalIncome += income;
      country.treasury += income;

      // Calculate expenses
      const workerExpenses = country.workers * 10;
      const unitMaintenance = country.units.length * 50;
      const navalMaintenance = country.navalUnits?.length || 0 * 100;
      const infraMaintenance = this.calculateInfrastructureMaintenance(country);

      const totalExpenses = workerExpenses + unitMaintenance + navalMaintenance + infraMaintenance;
      report.totalExpenses += totalExpenses;
      country.treasury -= totalExpenses;

      // Prevent bankruptcy
      if (country.treasury < 0) {
        report.warnings.push(`${country.name} treasury deficit: $${country.treasury}`);
        country.treasury = 0;
      }

      // Update units (recovery)
      MilitaryEngine.updateUnitsPerTurn(gameState);
    });

    // Victory check
    report.victoryStatus = VictoryEngine.checkVictory(gameState);
    if (report.victoryStatus?.gameOver) {
      report.events.push(`GAME OVER: ${report.victoryStatus.reason}`);
      gameState.gamePhase = 'end-turn';
    }
  }

  /**
   * Calculate total infrastructure maintenance costs for a country
   */
  private static calculateInfrastructureMaintenance(country: Country): number {
    let cost = 0;

    country.provinces.forEach(province => {
      if (province.infrastructure.hasRailroad) cost += 10;
      if (province.infrastructure.hasPort) cost += 15;
      if (province.infrastructure.hasDepot) cost += 8;
      if (province.infrastructure.industrialized) cost += 20;

      // Fort maintenance
      if (province.infrastructure.fortLevel > 0) {
        cost += province.infrastructure.fortLevel * 5;
      }
    });

    return cost;
  }

  /**
   * Simple AI unit movement towards nearest enemy or random expansion
   */
  private static moveAIUnit(unit: any, gameState: GameState): void {
    const movePoints = MilitaryEngine.getMovementPoints(unit.type, gameState.militaryEra);

    // Find nearest enemy unit
    let nearestEnemy: any = null;
    let minDistance = Infinity;

    gameState.units.forEach(other => {
      if (other.countryId === unit.countryId) return;

      const distance = Math.max(
        Math.abs(other.position.x - unit.position.x),
        Math.abs(other.position.y - unit.position.y)
      );

      if (distance < minDistance) {
        minDistance = distance;
        nearestEnemy = other;
      }
    });

    // Move toward enemy if found and within range
    if (nearestEnemy && minDistance <= movePoints * 2) {
      const newX =
        unit.position.x + (nearestEnemy.position.x > unit.position.x ? 1 : nearestEnemy.position.x < unit.position.x ? -1 : 0);
      const newY =
        unit.position.y + (nearestEnemy.position.y > unit.position.y ? 1 : nearestEnemy.position.y < unit.position.y ? -1 : 0);

      if (
        MilitaryEngine.canMove(
          unit,
          unit.position,
          { x: newX, y: newY },
          gameState.mapWidth || 30,
          gameState.mapHeight || 30,
          gameState.militaryEra
        )
      ) {
        unit.position = { x: newX, y: newY };
      }
    }
  }

  /* Get turn summary for UI display */
  static formatTurnReport(report: TurnReport): string {
    const lines = [
      `=== TURN ${report.turn} (YEAR ${report.year}) ===`,
      `Income: $${report.totalIncome}`,
      `Expenses: $${report.totalExpenses}`,
      `Net: $${report.totalIncome - report.totalExpenses}`,
    ];

    if (report.events.length > 0) {
      lines.push('');
      lines.push('EVENTS:');
      report.events.forEach(e => lines.push(`  - ${e}`));
    }

    if (report.warnings.length > 0) {
      lines.push('');
      lines.push('WARNINGS:');
      report.warnings.forEach(w => lines.push(`  ⚠️ ${w}`));
    }

    return lines.join('\n');
  }
}
