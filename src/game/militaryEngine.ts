import { Unit, UnitType } from '../types/index';
import { MILITARY_UNITS, NAVAL_UNITS } from './gameData';

export class MilitaryEngine {
  // Get available military units for current era
  static getAvailableUnits(era: number): Record<string, any> {
    switch (era) {
      case 1:
        return MILITARY_UNITS.era1;
      case 2:
        return MILITARY_UNITS.era2;
      case 3:
        return MILITARY_UNITS.era3;
      default:
        return MILITARY_UNITS.era1;
    }
  }

  // Get naval units
  static getNavalUnits(): Record<string, any> {
    return NAVAL_UNITS;
  }

  // Calculate combat damage with authentic game mechanics
  static calculateDamage(
    attacker: any, // Unit or Naval unit
    defender: any,
    terrain: string = 'plain'
  ): { damage: number; piercing: boolean } {
    // Get firepower from attacker
    const firepower = attacker.f || attacker.firepower || 0;

    // Get armor from defender
    const armor = defender.a || defender.armor || defender.d || defender.defense || 0;

    // Terrain bonuses (from original game reference)
    const terrainBonuses: Record<string, number> = {
      mountain: 0.3,
      forest: 0.2,
      hills: 0.15,
      plain: 0,
      water: -0.2,
    };

    const terrainBonus = 1 + (terrainBonuses[terrain] || 0);

    // Base damage calculation: firepower vs armor
    let damage = Math.max(1, firepower - Math.floor(armor / 10));
    damage = Math.floor(damage * terrainBonus);

    // Piercing determines if it penetrates armor
    const piercing = firepower > armor / 5;

    return { damage, piercing };
  }

  // Calculate unit morale loss from combat
  static calculateMoraleLoss(damageRatio: number): number {
    // If losing 30% or more of health, morale drops
    if (damageRatio > 0.3) {
      return Math.floor(damageRatio * 50); // Up to 50% morale loss
    }
    return 0;
  }

  // Determine if unit retreats based on morale
  static shouldRetreat(morale: number, health: number): boolean {
    // Unit retreats if morale drops below 30 or health below 20
    return morale < 30 || health < 20;
  }

  // Calculate experience gain from combat
  static calculateExperienceGain(damageDealt: number, oppositeDamage: number): number {
    // More damage dealt = more experience
    const baseExp = Math.floor(damageDealt / 10);
    // Surviving higher damage increases experience gain
    const survivalBonus = Math.floor(oppositeDamage / 20);
    return Math.min(100, baseExp + survivalBonus);
  }

  // Get unit cost for recruitment
  static getUnitCost(unitType: string, era: number): number {
    const units = this.getAvailableUnits(era);
    const unit = units[unitType];
    return unit?.cost || 500;
  }

  // Naval combat calculation
  static calculateNavalDamage(
    attacker: any, // Naval unit
    defender: any
  ): number {
    const firepower = attacker.f || 0;
    const armor = defender.a || 0;

    // Naval armor is more significant
    let damage = Math.max(1, firepower - Math.floor(armor / 15));

    // Range advantage
    if (attacker.r > (defender.r || 0)) {
      damage = Math.floor(damage * 1.2);
    }

    return damage;
  }

  // Calculate naval unit morale impact on combat
  static getNavalHullDamageThreshold(hull: number): { critical: number; destroyed: number } {
    return {
      critical: Math.floor(hull * 0.25),
      destroyed: 0,
    };
  }

  // Validate unit can move to location
  static canMove(unit: Unit, currentPos: any, targetPos: any, mapWidth: number, mapHeight: number, era: number = 1): boolean {
    // Check bounds
    if (targetPos.x < 0 || targetPos.x >= mapWidth || targetPos.y < 0 || targetPos.y >= mapHeight) {
      return false;
    }

    // Calculate distance
    const distance = Math.abs(targetPos.x - currentPos.x) + Math.abs(targetPos.y - currentPos.y);

    // Get unit movement stat based on type and era
    const units = this.getAvailableUnits(era);
    const unitStats = units[unit.type];
    const movement = unitStats?.mv || 4;

    return distance <= movement;
  }

  // Check if unit can attack another
  static canAttack(attacker: Unit, defender: Unit, distance: number): boolean {
    // Would need to reference attacker range stats
    // For now, basic check
    return distance > 0; // Can't attack same square
  }

  // Determine victor in combat
  static determineCombatWinner(
    attacker: Unit,
    defender: Unit,
    terrain: string = 'plain'
  ): { winner: 'attacker' | 'defender' | 'draw'; attackerDamage: number; defenderDamage: number } {
    const attackerDmg = this.calculateDamage(attacker, defender, terrain).damage;
    const defenderDmg = this.calculateDamage(defender, attacker, terrain).damage;

    if (attackerDmg > defenderDmg) {
      return { winner: 'attacker', attackerDamage: attackerDmg, defenderDamage: defenderDmg };
    } else if (defenderDmg > attackerDmg) {
      return { winner: 'defender', attackerDamage: attackerDmg, defenderDamage: defenderDmg };
    } else {
      return { winner: 'draw', attackerDamage: attackerDmg, defenderDamage: defenderDmg };
    }
  }
}
