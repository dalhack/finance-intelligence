// Victory condition checking for Imperialism game

import { GameState, Country } from '../types/index';

export interface VictoryCondition {
  type: 'conquest' | 'economic' | 'technology' | 'time';
  name: string;
  description: string;
  met: boolean;
  progress: number; // 0-100
}

export interface VictoryStatus {
  gameOver: boolean;
  winner: Country | null;
  conditions: VictoryCondition[];
  reason: string;
}

export class VictoryEngine {
  /* Check all victory conditions */
  static checkVictory(gameState: GameState): VictoryStatus {
    const totalProvinces = gameState.provinces.length;
    const status: VictoryStatus = {
      gameOver: false,
      winner: null,
      conditions: [],
      reason: '',
    };

    gameState.countries.forEach(country => {
      // CONQUEST VICTORY: Control 60% of provinces
      const conquestCondition: VictoryCondition = {
        type: 'conquest',
        name: 'Territorial Conquest',
        description: 'Control 60% of all provinces',
        met: country.provinces.length >= (totalProvinces * 0.6),
        progress: Math.round((country.provinces.length / totalProvinces) * 100),
      };
      status.conditions.push(conquestCondition);

      if (conquestCondition.met) {
        status.gameOver = true;
        status.winner = country;
        status.reason = `${country.name} achieved territorial dominance`;
        return;
      }

      // ECONOMIC VICTORY: 100,000 treasury
      const economicCondition: VictoryCondition = {
        type: 'economic',
        name: 'Economic Dominance',
        description: 'Accumulate 100,000 in treasury',
        met: country.treasury >= 100000,
        progress: Math.min(100, Math.round((country.treasury / 100000) * 100)),
      };
      status.conditions.push(economicCondition);

      if (economicCondition.met) {
        status.gameOver = true;
        status.winner = country;
        status.reason = `${country.name} achieved economic supremacy`;
        return;
      }

      // TECHNOLOGY VICTORY: Research 12 unique technologies
      const techCount = country.technology.size;
      const technologyCondition: VictoryCondition = {
        type: 'technology',
        name: 'Technological Supremacy',
        description: 'Research 12 different technologies',
        met: techCount >= 12,
        progress: Math.min(100, Math.round((techCount / 12) * 100)),
      };
      status.conditions.push(technologyCondition);

      if (technologyCondition.met) {
        status.gameOver = true;
        status.winner = country;
        status.reason = `${country.name} achieved technological advancement`;
        return;
      }
    });

    // TIME VICTORY: Year 1920 reached (long game scenario)
    const timeCondition: VictoryCondition = {
      type: 'time',
      name: 'Time Limit',
      description: 'Reach year 1920',
      met: gameState.year >= 1920,
      progress: Math.min(100, Math.round(((gameState.year - 1815) / 105) * 100)),
    };
    status.conditions.push(timeCondition);

    if (timeCondition.met) {
      // Find the winner at year 1920 (player with most provinces)
      const leader = gameState.countries.reduce((best, current) => {
        return current.provinces.length > best.provinces.length ? current : best;
      });

      status.gameOver = true;
      status.winner = leader;
      status.reason = `Year ${gameState.year} reached. ${leader.name} declared winner!`;
    }

    return status;
  }

  /* Get victory progress for a country */
  static getCountryVictoryProgress(
    country: Country,
    gameState: GameState
  ): { type: string; progress: number }[] {
    const totalProvinces = gameState.provinces.length;

    return [
      {
        type: 'Conquest',
        progress: Math.min(100, Math.round((country.provinces.length / (totalProvinces * 0.6)) * 100)),
      },
      {
        type: 'Economic',
        progress: Math.min(100, Math.round((country.treasury / 100000) * 100)),
      },
      {
        type: 'Technology',
        progress: Math.min(100, Math.round((country.technology.size / 12) * 100)),
      },
    ];
  }

  /* Format victory information for display */
  static formatVictoryStatus(status: VictoryStatus): string[] {
    const lines: string[] = [];

    if (status.gameOver) {
      lines.push('═'.repeat(40));
      lines.push(`GAME OVER - ${status.reason}`);
      lines.push('═'.repeat(40));
    }

    lines.push('VICTORY PROGRESS:');
    status.conditions.forEach(condition => {
      const bar = this.createProgressBar(condition.progress);
      lines.push(`${condition.name}: ${bar} ${condition.progress}%`);
    });

    return lines;
  }

  /* Create a text-based progress bar */
  private static createProgressBar(progress: number, width: number = 20): string {
    const filled = Math.round((progress / 100) * width);
    const empty = width - filled;
    return '[' + '█'.repeat(filled) + '░'.repeat(empty) + ']';
  }
}
