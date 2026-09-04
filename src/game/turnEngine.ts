import { GameState, Country } from '@types/index';
import { EconomyEngine } from './economyEngine';
import { DiplomacyEngine } from './diplomacyEngine';
import { TechnologyEngine } from './technologyEngine';
import { InfrastructureEngine } from './infrastructureEngine';

export interface TurnReport {
  turn: number;
  year: number;
  totalIncome: number;
  totalExpenses: number;
  events: string[];
  warnings: string[];
}

export class TurnEngine {
  /* Process a complete game turn */
  static processTurn(gameState: GameState): TurnReport {
    const report: TurnReport = {
      turn: gameState.currentTurn,
      year: gameState.year,
      totalIncome: 0,
      totalExpenses: 0,
      events: [],
      warnings: [],
    };

    // Process each country's turn
    gameState.countries.forEach(country => {
      this.processCountryTurn(country, gameState, report);
    });

    // Update game state
    gameState.currentTurn++;

    // Advance year (4 turns per year in Imperialism)
    if (gameState.currentTurn % 4 === 0) {
      gameState.year++;
      report.year = gameState.year;
      report.events.push(`Year ${gameState.year} reached`);
    }

    // Process diplomatic relationships
    this.processDiplomacy(gameState, report);

    // Set game phase
    gameState.gamePhase = 'diplomacy';

    return report;
  }

  /* Process a single country's turn */
  private static processCountryTurn(
    country: Country,
    gameState: GameState,
    report: TurnReport
  ): void {
    // Step 1: Calculate production from provinces
    const production = this.calculateProduction(country);

    // Step 2: Calculate income and expenses
    const { income, expenses } = this.calculateEconomics(country, production);
    report.totalIncome += income;
    report.totalExpenses += expenses;

    country.treasury += income - expenses;

    // Step 3: Apply technology bonuses
    this.applyTechnologyBonuses(country);

    // Step 4: Update unit morale and experience
    this.updateUnits(country);

    // Step 5: Check for bankruptcy
    if (country.treasury < 0) {
      country.treasury = 0;
      report.warnings.push(`${country.name} is bankrupt!`);
    }

    // Step 6: Update worker allocation
    this.updateWorkers(country);

    // Step 7: Check infrastructure maintenance
    this.checkInfrastructureMaintenance(country, report);
  }

  /* Calculate resource production for all provinces */
  private static calculateProduction(country: Country): any {
    const totalProduction = {
      raw: {} as any,
      processed: {} as any,
      finished: {} as any,
    };

    country.provinces.forEach(province => {
      if (!province.owner) return;

      // Calculate raw material production
      const rawProduction = EconomyEngine.calculateRawProduction(province);

      // Calculate processed production
      const workersForProduction = Math.floor(province.workers * 0.7);
      const processedProduction = EconomyEngine.calculateProcessedProduction(
        province,
        workersForProduction
      );

      // Calculate finished goods
      const workersForFinished = Math.floor(province.workers * 0.3);
      const finishedProduction = EconomyEngine.calculateFinishedGoods(
        province,
        workersForFinished
      );

      // Update province production
      province.production.raw = rawProduction;
      province.production.processed = processedProduction;

      // Aggregate totals
      Object.entries(rawProduction).forEach(([key, value]) => {
        totalProduction.raw[key] = (totalProduction.raw[key] || 0) + (value as number);
      });

      Object.entries(processedProduction).forEach(([key, value]) => {
        totalProduction.processed[key] = (totalProduction.processed[key] || 0) + (value as number);
      });

      Object.entries(finishedProduction).forEach(([key, value]) => {
        totalProduction.finished[key] = (totalProduction.finished[key] || 0) + (value as number);
      });
    });

    return totalProduction;
  }

  /* Calculate total income and expenses */
  private static calculateEconomics(
    country: Country,
    production: any
  ): { income: number; expenses: number } {
    let income = 0;
    let expenses = 0;

    // Income from trade (resource sales)
    const { income: tradeIncome } = EconomyEngine.processCountryEconomics(country);
    income += tradeIncome;

    // Expenses from workers
    expenses += country.workers * 10; // $10 per worker per turn

    // Expenses from unit maintenance
    expenses += country.units.length * 50; // $50 per unit per turn

    // Expenses from merchant marine operation
    expenses += country.merchantMarine * 20;

    // Expenses from freight cars operation
    expenses += country.freightCars * 5;

    // Income from consulates (trade bonuses)
    income += country.consulates.size * 100;

    return { income, expenses };
  }

  /* Apply technology bonuses to combat and production */
  private static applyTechnologyBonuses(country: Country): void {
    // Technology effects are applied in their respective engines
    // This is a placeholder for future tech effect application
  }

  /* Update unit health, morale, and experience */
  private static updateUnits(country: Country): void {
    country.units.forEach(unit => {
      // Recover small amount of health per turn (rest)
      unit.health = Math.min(100, unit.health + 2);

      // Recover morale per turn (unless at war)
      if (unit.morale < 100) {
        unit.morale = Math.min(100, unit.morale + 3);
      }

      // Veteran units slowly gain experience
      if (unit.experience < 100) {
        unit.experience = Math.min(100, unit.experience + 1);
      }
    });
  }

  /* Update worker distribution */
  private static updateWorkers(country: Country): void {
    // Redistribute workers if population grows
    const totalPopulation = country.provinces.reduce((sum, p) => sum + p.population, 0);
    const desiredWorkers = Math.floor(totalPopulation / 100);

    if (desiredWorkers > country.workers) {
      // Grow workforce by immigration/birth
      country.workers = Math.min(desiredWorkers, country.workers + Math.floor(desiredWorkers * 0.05));
    }

    // Allocate workers to provinces
    const avgWorkersPerProvince = Math.floor(country.workers / country.provinces.length);
    country.provinces.forEach(province => {
      province.workers = avgWorkersPerProvince;
    });
  }

  /* Check infrastructure maintenance costs */
  private static checkInfrastructureMaintenance(
    country: Country,
    report: TurnReport
  ): void {
    let maintenanceCost = 0;

    country.provinces.forEach(province => {
      if (province.infrastructure.hasRailroad) maintenanceCost += 10;
      if (province.infrastructure.hasPort) maintenanceCost += 15;
      if (province.infrastructure.hasDepot) maintenanceCost += 8;
      if (province.infrastructure.industrialized) maintenanceCost += 20;
    });

    if (maintenanceCost > 0) {
      country.treasury -= maintenanceCost;
      report.totalExpenses += maintenanceCost;

      if (maintenanceCost > 500) {
        report.warnings.push(`High infrastructure maintenance: $${maintenanceCost}`);
      }
    }
  }

  /* Process diplomatic relationships */
  private static processDiplomacy(gameState: GameState, report: TurnReport): void {
    gameState.countries.forEach(country => {
      country.diplomacy.forEach((relation, otherId) => {
        // Apply trust decay
        relation.trust = DiplomacyEngine.decayTrust(relation.trust);

        // Check for alliance benefits
        if (relation.trust > 75) {
          // Allies share small economic benefit
          const allyBonus = 100;
          country.treasury += allyBonus;
          report.totalIncome += allyBonus;
        }

        // Check for war status update
        if (relation.warState) {
          report.events.push(`${country.name} at war with country ${otherId}`);
        }
      });
    });
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
