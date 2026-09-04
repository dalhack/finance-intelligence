import { Unit, UnitType } from '../types/index';

export interface HexCoordinate {
  q: number; // Column
  r: number; // Row
}

export interface BattleUnit {
  unit: Unit;
  position: HexCoordinate;
  health: number;
  morale: number; // 0-100, units retreat when morale depletes
  experience: number;
}

export interface Battle {
  id: string;
  side1Units: BattleUnit[];
  side2Units: BattleUnit[];
  terrain: string; // Type of terrain (mountain, plain, forest, etc)
  currentTurn: number;
  victor: string | null; // country id of winner
}

export interface UnitStats {
  attack: number;
  defense: number;
  health: number;
  movement: number;
  range: number;
  morale: number;
  cost: number;
}

const UNIT_STATS: Record<string, UnitStats> = {
  [UnitType.Infantry]: {
    attack: 6,
    defense: 5,
    health: 8,
    movement: 2,
    range: 1,
    morale: 7,
    cost: 1000,
  },
  [UnitType.Cavalry]: {
    attack: 8,
    defense: 3,
    health: 6,
    movement: 4,
    range: 1,
    morale: 6,
    cost: 1500,
  },
  [UnitType.Artillery]: {
    attack: 10,
    defense: 2,
    health: 5,
    movement: 1,
    range: 4,
    morale: 5,
    cost: 2000,
  },
  [UnitType.Navy]: {
    attack: 8,
    defense: 6,
    health: 10,
    movement: 3,
    range: 3,
    morale: 7,
    cost: 3000,
  },
};

export class CombatEngine {
  /* Calculate hex distance between two coordinates */
  static hexDistance(a: HexCoordinate, b: HexCoordinate): number {
    return (Math.abs(a.q - b.q) + Math.abs(a.q + a.r - b.q - b.r) + Math.abs(a.r - b.r)) / 2;
  }

  /* Get neighboring hexes */
  static getNeighbors(hex: HexCoordinate): HexCoordinate[] {
    const directions = [
      { q: 1, r: 0 }, { q: 1, r: -1 }, { q: 0, r: -1 },
      { q: -1, r: 0 }, { q: -1, r: 1 }, { q: 0, r: 1 },
    ];
    return directions.map(d => ({ q: hex.q + d.q, r: hex.r + d.r }));
  }

  /* Check if unit can move to hex */
  static canMoveTo(
    unit: BattleUnit,
    targetHex: HexCoordinate,
    occupiedHexes: Set<string>,
    stats: UnitStats
  ): boolean {
    const distance = this.hexDistance(unit.position, targetHex);
    if (distance > stats.movement) return false;

    const hexKey = `${targetHex.q},${targetHex.r}`;
    if (occupiedHexes.has(hexKey)) return false;

    return true;
  }

  /* Resolve combat between two units */
  static resolveCombat(attacker: BattleUnit, defender: BattleUnit, terrain: string): {
    attackerDamage: number;
    defenderDamage: number;
  } {
    const attackerStats = UNIT_STATS[attacker.unit.type];
    const defenderStats = UNIT_STATS[defender.unit.type];

    // Base damage calculation
    let attackerDamage = attackerStats.attack + this.getExperienceBonus(attacker.experience);
    let defenderDamage = defenderStats.defense;

    // Range advantage
    const distance = this.hexDistance(attacker.position, defender.position);
    if (distance > 1 && attackerStats.range > distance) {
      attackerDamage *= 1.5; // Ranged advantage
    }

    // Terrain defense bonus
    if (terrain === 'mountain') {
      defenderDamage *= 1.3;
    } else if (terrain === 'forest') {
      defenderDamage *= 1.2;
    }

    // Morale affects damage
    const attackerMoraleMultiplier = attacker.morale / 100;
    const defenderMoraleMultiplier = defender.morale / 100;

    attackerDamage *= attackerMoraleMultiplier;
    defenderDamage *= defenderMoraleMultiplier;

    // Randomness
    const attackerVariance = 0.8 + Math.random() * 0.4;
    const defenderVariance = 0.8 + Math.random() * 0.4;

    return {
      attackerDamage: Math.floor(attackerDamage * attackerVariance),
      defenderDamage: Math.floor(defenderDamage * defenderVariance),
    };
  }

  /* Apply damage to unit */
  static applyDamage(unit: BattleUnit, damage: number): void {
    const actualDamage = Math.max(1, damage);
    unit.health -= actualDamage;

    // Morale damage (units can break before death)
    const moraleDamage = actualDamage * 0.5;
    unit.morale -= moraleDamage;
    unit.morale = Math.max(0, unit.morale);

    // Units retreat if morale depletes
    if (unit.morale === 0) {
      unit.health = 0; // Unit flees the battle
    }
  }

  /* Check if unit should retreat (morale < 25%) */
  static shouldRetreat(unit: BattleUnit): boolean {
    return unit.morale < 25;
  }

  /* Grant experience to unit for combat */
  static grantExperience(unit: BattleUnit, combatRounds: number): void {
    unit.experience += combatRounds * 5;
    // Max experience level
    if (unit.experience > 100) {
      unit.experience = 100; // 4 levels max (25 exp per level)
    }
  }

  /* Get experience bonus to combat */
  private static getExperienceBonus(experience: number): number {
    const level = Math.floor(experience / 25);
    return level * 2; // +2 attack per level
  }

  /* Get unit combat medals (visual indicator) */
  static getMedalCount(experience: number): number {
    return Math.floor(experience / 25);
  }

  /* Process battle turn - resolve all combats */
  static processBattleTurn(
    battle: Battle,
    side1Moves: Map<string, HexCoordinate>,
    side2Moves: Map<string, HexCoordinate>
  ): {
    side1Losses: number;
    side2Losses: number;
    battleOver: boolean;
  } {
    let side1Losses = 0;
    let side2Losses = 0;

    // Move units
    side1Moves.forEach((hex, unitId) => {
      const unit = battle.side1Units.find(u => u.unit.id === unitId);
      if (unit) {
        const stats = UNIT_STATS[unit.unit.type];
        if (this.canMoveTo(unit, hex, this.getOccupiedHexes(battle), stats)) {
          unit.position = hex;
        }
      }
    });

    side2Moves.forEach((hex, unitId) => {
      const unit = battle.side2Units.find(u => u.unit.id === unitId);
      if (unit) {
        const stats = UNIT_STATS[unit.unit.type];
        if (this.canMoveTo(unit, hex, this.getOccupiedHexes(battle), stats)) {
          unit.position = hex;
        }
      }
    });

    // Resolve combats (closest enemies)
    battle.side1Units.forEach(attacker => {
      const nearestEnemy = this.findNearestEnemy(attacker, battle.side2Units);
      if (nearestEnemy) {
        const { attackerDamage, defenderDamage } = this.resolveCombat(
          attacker,
          nearestEnemy,
          battle.terrain
        );

        this.applyDamage(attacker, defenderDamage);
        this.applyDamage(nearestEnemy, attackerDamage);

        if (nearestEnemy.health <= 0) side1Losses++;
        if (attacker.health <= 0) side2Losses++;
      }
    });

    // Check if battle is over
    const side1Active = battle.side1Units.filter(u => u.health > 0).length;
    const side2Active = battle.side2Units.filter(u => u.health > 0).length;

    const battleOver = side1Active === 0 || side2Active === 0;
    if (battleOver) {
      battle.victor = side1Active > 0 ? 'side1' : 'side2';
    }

    battle.currentTurn++;

    return {
      side1Losses,
      side2Losses,
      battleOver,
    };
  }

  private static findNearestEnemy(unit: BattleUnit, enemies: BattleUnit[]): BattleUnit | null {
    let nearest: BattleUnit | null = null;
    let minDistance = Infinity;

    enemies.forEach(enemy => {
      if (enemy.health > 0) {
        const distance = this.hexDistance(unit.position, enemy.position);
        if (distance < minDistance) {
          minDistance = distance;
          nearest = enemy;
        }
      }
    });

    return nearest;
  }

  private static getOccupiedHexes(battle: Battle): Set<string> {
    const occupied = new Set<string>();
    [...battle.side1Units, ...battle.side2Units].forEach(u => {
      occupied.add(`${u.position.q},${u.position.r}`);
    });
    return occupied;
  }

  /* Get battle summary */
  static getBattleSummary(battle: Battle): string {
    const side1Alive = battle.side1Units.filter(u => u.health > 0).length;
    const side2Alive = battle.side2Units.filter(u => u.health > 0).length;

    if (battle.victor === 'side1') {
      return `Battle Won! ${side1Alive} units remain. Turn ${battle.currentTurn}`;
    } else if (battle.victor === 'side2') {
      return `Battle Lost! ${side2Alive} enemy units remain. Turn ${battle.currentTurn}`;
    }

    return `Battle in progress. ${side1Alive} vs ${side2Alive}. Turn ${battle.currentTurn}`;
  }
}

export { UNIT_STATS };
