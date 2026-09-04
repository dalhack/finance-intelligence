// Game action engine - processes all player and AI actions

import { Unit, Country, Province, GameState, UnitType } from '../types/index';
import { MilitaryEngine } from './militaryEngine';
import { EconomyEngine } from './economyEngine';
import { InfrastructureEngine } from './infrastructureEngine';
import { TechnologyEngine } from './technologyEngine';
import { DiplomacyEngine } from './diplomacyEngine';

export interface GameAction {
  type: 'moveUnit' | 'buildInfrastructure' | 'recruitUnit' | 'research' | 'diplomacy' | 'combat';
  playerId: string;
  timestamp: number;
  data: any;
  result?: any;
}

export interface ActionResult {
  success: boolean;
  message: string;
  cost?: number;
  reward?: any;
}

export class ActionEngine {
  // Move a unit to a new location
  static moveUnit(
    gameState: GameState,
    unitId: string,
    targetX: number,
    targetY: number
  ): ActionResult {
    const unit = gameState.units.find(u => u.id === unitId);
    if (!unit) {
      return { success: false, message: 'Unit not found' };
    }

    const currentPos = unit.position;
    const targetPos = { x: targetX, y: targetY };

    // Calculate map bounds from provinces
    const maxX = Math.max(...gameState.provinces.map(p => p.position.x), 100);
    const maxY = Math.max(...gameState.provinces.map(p => p.position.y), 100);

    // Check if movement is valid
    if (!MilitaryEngine.canMove(unit, currentPos, targetPos, maxX + 1, maxY + 1, gameState.militaryEra)) {
      return { success: false, message: 'Unit cannot move that far' };
    }

    // Check if target province is owned or neutral
    const targetProvince = gameState.provinces.find(
      p => p.position.x === targetX && p.position.y === targetY
    );

    if (targetProvince && targetProvince.owner && targetProvince.owner !== unit.countryId) {
      return { success: false, message: 'Enemy territory - combat required' };
    }

    // Move the unit
    unit.position = targetPos;
    unit.morale = Math.max(0, unit.morale - 5); // Movement costs morale

    return {
      success: true,
      message: `Unit moved to (${targetX}, ${targetY})`,
    };
  }

  // Recruit a new unit in a province
  static recruitUnit(
    gameState: GameState,
    countryId: string,
    provinceId: string,
    unitType: string
  ): ActionResult {
    const country = gameState.countries.find(c => c.id === countryId);
    if (!country) {
      return { success: false, message: 'Country not found' };
    }

    const province = gameState.provinces.find(p => p.id === provinceId);
    if (!province || province.owner !== countryId) {
      return { success: false, message: 'Province not owned by this country' };
    }

    // Get unit cost
    const cost = MilitaryEngine.getUnitCost(unitType, gameState.militaryEra);
    if (country.treasury < cost) {
      return { success: false, message: `Insufficient funds. Need ${cost}, have ${country.treasury}` };
    }

    // Create new unit
    const newUnit: Unit = {
      id: `unit_${Date.now()}_${Math.random()}`,
      type: UnitType.Infantry, // Would be based on unitType parameter
      countryId,
      position: { ...province.position },
      health: 100,
      morale: 100,
      experience: 0,
      era: gameState.militaryEra,
    };

    gameState.units.push(newUnit);
    country.units.push(newUnit);
    province.garrisonUnits.push(newUnit);
    country.treasury -= cost;

    return {
      success: true,
      message: `${unitType} recruited in ${province.name}`,
      cost,
    };
  }

  // Build infrastructure in a province
  static buildInfrastructure(
    gameState: GameState,
    countryId: string,
    provinceId: string,
    infrastructure: 'railroad' | 'port' | 'depot' | 'industrialize'
  ): ActionResult {
    const country = gameState.countries.find(c => c.id === countryId);
    if (!country) {
      return { success: false, message: 'Country not found' };
    }

    const province = gameState.provinces.find(p => p.id === provinceId);
    if (!province || province.owner !== countryId) {
      return { success: false, message: 'Province not owned by this country' };
    }

    // Check if can build
    const costs = { railroad: 5000, port: 6000, depot: 3000, industrialize: 8000 };
    const cost = costs[infrastructure];

    if (country.treasury < cost) {
      return { success: false, message: `Insufficient funds. Need ${cost}, have ${country.treasury}` };
    }

    // Build infrastructure
    const built = InfrastructureEngine.buildInfrastructure(province, infrastructure, cost);
    if (!built) {
      return { success: false, message: `Cannot build ${infrastructure} - already exists or invalid` };
    }

    country.treasury -= cost;

    return {
      success: true,
      message: `${infrastructure} built in ${province.name}`,
      cost,
    };
  }

  // Research a technology
  static researchTechnology(
    gameState: GameState,
    countryId: string,
    technologyId: string
  ): ActionResult {
    const country = gameState.countries.find(c => c.id === countryId);
    if (!country) {
      return { success: false, message: 'Country not found' };
    }

    // Check if can research
    const researchedTechs = new Set(country.technology.keys());
    const canResearch = TechnologyEngine.canResearch(technologyId, researchedTechs, country.treasury);
    if (!canResearch.canResearch) {
      return { success: false, message: canResearch.reason || 'Cannot research this technology' };
    }

    // Get technology details
    const tech = TechnologyEngine.getTechnology(technologyId);
    if (!tech) {
      return { success: false, message: 'Technology not found' };
    }

    if (country.treasury < tech.cost) {
      return { success: false, message: `Insufficient funds. Need ${tech.cost}, have ${country.treasury}` };
    }

    // Research the technology
    country.technology.set(technologyId, 1);
    country.treasury -= tech.cost;

    // Update military era if applicable
    if (['rifling', 'steam_power', 'railway'].includes(technologyId)) {
      gameState.militaryEra = Math.min(3, gameState.militaryEra + 1);
    }

    return {
      success: true,
      message: `Researched ${tech.name}`,
      cost: tech.cost,
    };
  }

  // Establish diplomatic relations
  static establishDiplomacy(
    gameState: GameState,
    countryId: string,
    targetCountryId: string,
    action: 'consulte' | 'embassy' | 'alliance' | 'trade' | 'war'
  ): ActionResult {
    const country = gameState.countries.find(c => c.id === countryId);
    if (!country) {
      return { success: false, message: 'Country not found' };
    }

    const targetCountry = gameState.countries.find(c => c.id === targetCountryId);
    if (!targetCountry) {
      return { success: false, message: 'Target country not found' };
    }

    const relation = country.diplomacy.get(targetCountryId);
    if (!relation) {
      return { success: false, message: 'No diplomatic relation exists' };
    }

    const costs = { consulte: 500, embassy: 5000, alliance: 2000, trade: 1000, war: 0 };
    const cost = costs[action];

    if (country.treasury < cost) {
      return { success: false, message: `Insufficient funds for ${action}` };
    }

    // Apply diplomatic action
    switch (action) {
      case 'consulte':
        country.consulates.add(targetCountryId);
        country.treasury -= cost;
        relation.trust += 5;
        break;

      case 'embassy':
        country.consulates.add(targetCountryId);
        country.treasury -= cost;
        relation.trust += 15;
        break;

      case 'alliance':
        country.treasury -= cost;
        relation.trust += 20;
        relation.tradeAgreement = true;
        break;

      case 'trade':
        country.treasury -= cost;
        country.tradeAgreements.set(targetCountryId, true);
        relation.trust += 10;
        break;

      case 'war':
        relation.warState = true;
        relation.trust = 0;
        break;

      default:
        return { success: false, message: 'Unknown diplomatic action' };
    }

    return {
      success: true,
      message: `${action} established with ${targetCountry.name}`,
      cost,
    };
  }

  // Attack an enemy unit
  static attackUnit(
    gameState: GameState,
    attackerUnitId: string,
    defenderUnitId: string,
    terrain: string = 'plain'
  ): ActionResult {
    const attacker = gameState.units.find(u => u.id === attackerUnitId);
    const defender = gameState.units.find(u => u.id === defenderUnitId);

    if (!attacker || !defender) {
      return { success: false, message: 'Unit not found' };
    }

    // Check if units belong to different countries
    if (attacker.countryId === defender.countryId) {
      return { success: false, message: 'Cannot attack own units' };
    }

    // Resolve combat
    const result = MilitaryEngine.determineCombatWinner(attacker, defender, terrain);

    // Apply damage
    if (result.winner === 'attacker') {
      defender.health = Math.max(0, defender.health - result.attackerDamage);
      attacker.health = Math.max(0, attacker.health - result.defenderDamage);
      attacker.experience += 10;

      if (defender.health === 0) {
        // Remove defeated unit
        const idx = gameState.units.indexOf(defender);
        if (idx > -1) gameState.units.splice(idx, 1);

        const country = gameState.countries.find(c => c.id === defender.countryId);
        if (country) {
          const unitIdx = country.units.indexOf(defender);
          if (unitIdx > -1) country.units.splice(unitIdx, 1);
        }

        return {
          success: true,
          message: `${attacker.countryId} defeated ${defender.countryId} unit`,
          reward: { experience: 20 },
        };
      }

      // Apply morale loss
      const moraleLoss = MilitaryEngine.calculateMoraleLoss(result.defenderDamage / defender.health);
      defender.morale = Math.max(0, defender.morale - moraleLoss);

      return {
        success: true,
        message: `Combat resolved - ${result.winner} wins`,
      };
    } else if (result.winner === 'defender') {
      attacker.health = Math.max(0, attacker.health - result.defenderDamage);
      defender.health = Math.max(0, defender.health - result.attackerDamage);
      defender.experience += 10;

      const moraleLoss = MilitaryEngine.calculateMoraleLoss(result.attackerDamage / attacker.health);
      attacker.morale = Math.max(0, attacker.morale - moraleLoss);

      return {
        success: true,
        message: `Combat resolved - ${result.winner} wins`,
      };
    } else {
      attacker.health = Math.max(0, attacker.health - result.defenderDamage);
      defender.health = Math.max(0, defender.health - result.attackerDamage);

      return {
        success: true,
        message: 'Combat resulted in a draw',
      };
    }
  }

  // Check if unit should retreat
  static checkRetreat(unit: Unit): boolean {
    return MilitaryEngine.shouldRetreat(unit.morale, unit.health);
  }

  // Get all valid actions for a unit
  static getValidUnitActions(
    gameState: GameState,
    unitId: string,
    countryId: string
  ): string[] {
    const unit = gameState.units.find(u => u.id === unitId);
    if (!unit || unit.countryId !== countryId) {
      return [];
    }

    const actions = ['move'];

    // Check for nearby enemies
    const enemies = gameState.units.filter(
      u => u.countryId !== countryId &&
      Math.abs(u.position.x - unit.position.x) <= 2 &&
      Math.abs(u.position.y - unit.position.y) <= 2
    );
    if (enemies.length > 0) {
      actions.push('attack');
    }

    // Check if in own province for building
    const province = gameState.provinces.find(
      p => p.position.x === unit.position.x && p.position.y === unit.position.y
    );
    if (province && province.owner === countryId) {
      actions.push('build');
    }

    return actions;
  }
}
