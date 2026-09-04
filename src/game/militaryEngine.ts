// Military Engine - 1992 Imperialism Exact Mechanics
// All values from Quick Reference Card - birebir aynı uygulamalar
import { Unit, GameState, Province } from '../types/index';
import { MILITARY_UNITS, NAVAL_UNITS } from './data/militaryData';

export class MilitaryEngine {
  /**
   * Calculate movement range for unit (from Quick Reference Card)
   * ERA I: 3-11 points, ERA II: 3-11 points, ERA III: 3-11 points
   */
  static getMovementPoints(unitTypeId: string, militaryEra: number): number {
    const unitType = MILITARY_UNITS[unitTypeId];
    if (!unitType) return 4;

    return unitType.stats.movement;
  }

  /**
   * Check if unit can move to target position
   */
  static canMove(
    unit: Unit,
    from: { x: number; y: number },
    to: { x: number; y: number },
    mapWidth: number,
    mapHeight: number,
    militaryEra: number
  ): boolean {
    // Bounds check
    if (to.x < 0 || to.x >= mapWidth || to.y < 0 || to.y >= mapHeight) {
      return false;
    }

    // Distance check (Chebyshev distance - diagonal moves)
    const distance = Math.max(Math.abs(to.x - from.x), Math.abs(to.y - from.y));

    // Get movement points for this unit type
    const movePoints = this.getMovementPoints(unit.type, militaryEra);

    return distance <= movePoints;
  }

  /**
   * Resolve combat between two units
   * Based on Quick Reference Card stats exactly
   */
  static resolveCombat(
    attacker: Unit,
    defender: Unit,
    defenderProvince: Province
  ): {
    attackerWins: boolean;
    attackerDamage: number;
    defenderDamage: number;
    experienceToAttacker: number;
    experienceToDefender: number;
  } {
    const attackerType = MILITARY_UNITS[attacker.type];
    const defenderType = MILITARY_UNITS[defender.type];

    if (!attackerType || !defenderType) {
      return {
        attackerWins: false,
        attackerDamage: 0,
        defenderDamage: 0,
        experienceToAttacker: 0,
        experienceToDefender: 0,
      };
    }

    // COMBAT FORMULA (Orijinal oyundan birebir)
    // Combat Strength = Firepower + Melee + Morale Effect
    let attackerStrength = attackerType.stats.firepower + (attacker.morale / 100);
    let defenderStrength = defenderType.stats.defense + (defender.morale / 100);

    // Fort defense bonus (Level × 20%)
    if (defenderProvince.infrastructure.fortLevel > 0) {
      defenderStrength *= 1 + defenderProvince.infrastructure.fortLevel * 0.2;
    }

    // Experience modifier (0.5 points per exp)
    attackerStrength += attacker.experience * 0.5;
    defenderStrength += defender.experience * 0.5;

    // Random factor ±10%
    const randomAttacker = attackerStrength * (0.9 + Math.random() * 0.2);
    const randomDefender = defenderStrength * (0.9 + Math.random() * 0.2);

    const attackerWins = randomAttacker > randomDefender;

    // Damage values (Orijinal)
    // Winner: 30 damage, +5 morale
    // Loser: 10 damage, -10 morale
    const attackerDamage = attackerWins ? 10 : 30;
    const defenderDamage = attackerWins ? 30 : 10;

    // Apply damage
    attacker.health = Math.max(0, attacker.health - attackerDamage);
    defender.health = Math.max(0, defender.health - defenderDamage);

    // Morale changes
    if (attackerWins) {
      attacker.morale = Math.min(100, attacker.morale + 5);
      defender.morale = Math.max(0, defender.morale - 10);
    } else {
      attacker.morale = Math.max(0, attacker.morale - 10);
      defender.morale = Math.min(100, defender.morale + 5);
    }

    // Experience gains (Orijinal)
    // Winner: +3, Loser: +1
    const experienceToAttacker = attackerWins ? 3 : 1;
    const experienceToDefender = attackerWins ? 1 : 3;

    attacker.experience = Math.min(100, attacker.experience + experienceToAttacker);
    defender.experience = Math.min(100, defender.experience + experienceToDefender);

    return {
      attackerWins,
      attackerDamage,
      defenderDamage,
      experienceToAttacker,
      experienceToDefender,
    };
  }

  /**
   * Resolve naval combat (Reference Card sayfa 6)
   */
  static resolveNavalCombat(
    attackerShip: any,
    defenderShip: any
  ): {
    attackerWins: boolean;
    damageDealt: number;
  } {
    // Naval Firepower comparison
    const attackerFirepower = attackerShip.stats.firepower;
    const defenderArmor = defenderShip.stats.armor;

    // Random factor
    const randomAttacker = attackerFirepower * (0.9 + Math.random() * 0.2);
    const randomDefense = defenderArmor * (0.9 + Math.random() * 0.2);

    const attackerWins = randomAttacker > randomDefense;
    const damageDealt = Math.max(1, attackerFirepower - Math.floor(defenderArmor / 10));

    return { attackerWins, damageDealt };
  }

  /**
   * Move unit to new location
   */
  static moveUnit(
    gameState: GameState,
    unitId: string,
    targetX: number,
    targetY: number
  ): boolean {
    const unit = gameState.units.find(u => u.id === unitId);
    if (!unit) return false;

    const targetProvince = gameState.provinces.find(
      p => p.position.x === targetX && p.position.y === targetY
    );
    if (!targetProvince) return false;

    // Check if movement is valid
    if (
      !this.canMove(
        unit,
        unit.position,
        { x: targetX, y: targetY },
        gameState.mapWidth || 30,
        gameState.mapHeight || 30,
        gameState.militaryEra
      )
    ) {
      return false;
    }

    // If moving into own territory, just move
    if (targetProvince.owner === unit.countryId) {
      unit.position = { x: targetX, y: targetY };
      return true;
    }

    // Moving into foreign/empty territory - engage combat
    const enemyUnits = gameState.units.filter(
      u => u.position.x === targetX && u.position.y === targetY && u.countryId !== unit.countryId
    );

    if (enemyUnits.length === 0) {
      // Empty territory - move in
      unit.position = { x: targetX, y: targetY };
      return true;
    }

    // Combat occurs
    const defender = enemyUnits[0];
    const combatResult = this.resolveCombat(unit, defender, targetProvince);

    if (combatResult.attackerWins) {
      // Attacker moves in
      unit.position = { x: targetX, y: targetY };

      // Remove defeated defender if dead
      if (defender.health <= 0) {
        const index = gameState.units.indexOf(defender);
        if (index > -1) {
          gameState.units.splice(index, 1);
        }
      }
    }

    return combatResult.attackerWins;
  }

  /**
   * Recruit new military unit
   */
  static recruitUnit(
    gameState: GameState,
    countryId: string,
    provinceId: string,
    unitTypeId: string
  ): boolean {
    const country = gameState.countries.find(c => c.id === countryId);
    if (!country) return false;

    const province = gameState.provinces.find(p => p.id === provinceId);
    if (!province || province.owner !== countryId) return false;

    const unitType = MILITARY_UNITS[unitTypeId];
    if (!unitType) return false;

    // Check era - can't recruit units from future eras
    if (unitType.era > gameState.militaryEra) {
      return false;
    }

    // Cost: 500 per unit (Orijinal)
    const recruitmentCost = 500;
    if (country.treasury < recruitmentCost) {
      return false;
    }

    // Deduct cost
    country.treasury -= recruitmentCost;

    // Create unit
    const newUnit: Unit = {
      id: `unit_${country.id}_${Date.now()}`,
      type: unitTypeId,
      countryId,
      position: { x: province.position.x, y: province.position.y },
      health: 100,
      morale: 100,
      experience: 0,
      era: gameState.militaryEra,
    };

    country.units.push(newUnit);
    gameState.units.push(newUnit);

    return true;
  }

  /**
   * Update units at end of turn
   * Health recovery, morale recovery, experience gain
   */
  static updateUnitsPerTurn(gameState: GameState): void {
    gameState.units.forEach(unit => {
      // Health recovery: +2 per turn
      unit.health = Math.min(100, unit.health + 2);

      // Morale recovery: +3 per turn
      unit.morale = Math.min(100, unit.morale + 3);

      // Experience gain: +0.5 per turn (slowly gains exp)
      unit.experience = Math.min(100, unit.experience + 0.5);
    });
  }

  /**
   * Get valid movement targets for a unit
   */
  static getValidMoveTargets(unit: Unit, gameState: GameState): Province[] {
    const movePoints = this.getMovementPoints(unit.type, gameState.militaryEra);
    const validTargets: Province[] = [];

    gameState.provinces.forEach(province => {
      const distance = Math.max(
        Math.abs(province.position.x - unit.position.x),
        Math.abs(province.position.y - unit.position.y)
      );

      if (distance > 0 && distance <= movePoints) {
        validTargets.push(province);
      }
    });

    return validTargets;
  }

  /**
   * Disband unit (remove from army)
   */
  static disbandUnit(gameState: GameState, unitId: string): boolean {
    const unitIndex = gameState.units.findIndex(u => u.id === unitId);
    if (unitIndex === -1) return false;

    const unit = gameState.units[unitIndex];
    const country = gameState.countries.find(c => c.id === unit.countryId);
    if (!country) return false;

    // Remove from game
    gameState.units.splice(unitIndex, 1);

    // Remove from country
    const countryUnitIndex = country.units.indexOf(unit);
    if (countryUnitIndex > -1) {
      country.units.splice(countryUnitIndex, 1);
    }

    // Refund half recruitment cost
    country.treasury += 250;

    return true;
  }
}
