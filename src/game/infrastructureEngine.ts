import { Province } from '../types/index';

export interface Infrastructure {
  hasRailroad: boolean;
  hasPort: boolean;
  hasDepot: boolean;
  industrialized: boolean;
}

const INFRASTRUCTURE_COSTS = {
  railroad: 5000,
  port: 6000,
  depot: 3000,
  industrialize: 8000,
  fort_level_1: 3000,
  fort_level_2: 5000,
  fort_level_3: 8000,
};

const INFRASTRUCTURE_BONUSES = {
  railroad: {
    productionBonus: 1.3,
    transportCapacity: 100,
  },
  port: {
    productionBonus: 1.15,
    transportCapacity: 150,
    tradeBonus: 0.2,
  },
  depot: {
    productionBonus: 1.2,
    storageCapacity: 200,
  },
  industrialized: {
    productionBonus: 1.5,
    factoryOutput: 1.3,
  },
};

export class InfrastructureEngine {
  /* Check if infrastructure can be built */
  static canBuildInfrastructure(
    province: Province,
    infrastructure: keyof typeof INFRASTRUCTURE_COSTS,
    treasury: number
  ): { canBuild: boolean; reason?: string } {
    const cost = INFRASTRUCTURE_COSTS[infrastructure];

    if (treasury < cost) {
      return { canBuild: false, reason: `Insufficient funds (need ${cost})` };
    }

    // Check if already built
    if (infrastructure === 'railroad' && province.infrastructure.hasRailroad) {
      return { canBuild: false, reason: 'Railroad already exists' };
    }

    if (infrastructure === 'port') {
      // Port requires access to water (would need terrain type checking)
      if (province.infrastructure.hasPort) {
        return { canBuild: false, reason: 'Port already exists' };
      }
    }

    if (infrastructure === 'depot' && province.infrastructure.hasDepot) {
      return { canBuild: false, reason: 'Depot already exists' };
    }

    if (infrastructure === 'industrialize' && province.infrastructure.industrialized) {
      return { canBuild: false, reason: 'Already industrialized' };
    }

    return { canBuild: true };
  }

  /* Build infrastructure in a province */
  static buildInfrastructure(
    province: Province,
    infrastructure: keyof typeof INFRASTRUCTURE_COSTS,
    cost: number
  ): boolean {
    const check = this.canBuildInfrastructure(province, infrastructure, cost);
    if (!check.canBuild) return false;

    if (infrastructure === 'railroad') {
      province.infrastructure.hasRailroad = true;
    } else if (infrastructure === 'port') {
      province.infrastructure.hasPort = true;
    } else if (infrastructure === 'depot') {
      province.infrastructure.hasDepot = true;
    } else if (infrastructure === 'industrialize') {
      province.infrastructure.industrialized = true;
    }

    return true;
  }

  /* Get production multiplier for province */
  static getProductionMultiplier(infrastructure: Infrastructure, provinceType: string): number {
    let multiplier = 1.0;

    if (infrastructure.hasRailroad) {
      multiplier *= INFRASTRUCTURE_BONUSES.railroad.productionBonus;
    }

    if (infrastructure.hasPort) {
      multiplier *= INFRASTRUCTURE_BONUSES.port.productionBonus;
    }

    if (infrastructure.hasDepot) {
      multiplier *= INFRASTRUCTURE_BONUSES.depot.productionBonus;
    }

    if (infrastructure.industrialized) {
      multiplier *= INFRASTRUCTURE_BONUSES.industrialized.productionBonus;
    }

    return multiplier;
  }

  /* Get transport capacity for a province */
  static getTransportCapacity(infrastructure: Infrastructure): number {
    let capacity = 0;

    if (infrastructure.hasRailroad) {
      capacity += INFRASTRUCTURE_BONUSES.railroad.transportCapacity;
    }

    if (infrastructure.hasPort) {
      capacity += INFRASTRUCTURE_BONUSES.port.transportCapacity;
    }

    if (infrastructure.hasDepot) {
      capacity += INFRASTRUCTURE_BONUSES.depot.storageCapacity;
    }

    return capacity;
  }

  /* Get trade bonus for a province */
  static getTradeBonus(infrastructure: Infrastructure): number {
    let bonus = 0;

    if (infrastructure.hasPort) {
      bonus += INFRASTRUCTURE_BONUSES.port.tradeBonus;
    }

    return bonus;
  }

  /* Get total infrastructure cost for a province */
  static getTotalInfrastructureCost(province: Province): number {
    let total = 0;

    if (!province.infrastructure.hasRailroad) total += INFRASTRUCTURE_COSTS.railroad;
    if (!province.infrastructure.hasPort) total += INFRASTRUCTURE_COSTS.port;
    if (!province.infrastructure.hasDepot) total += INFRASTRUCTURE_COSTS.depot;
    if (!province.infrastructure.industrialized) total += INFRASTRUCTURE_COSTS.industrialize;

    return total;
  }

  /* Get infrastructure development progress */
  static getInfrastructureLevel(infrastructure: Infrastructure): {
    level: number;
    name: string;
    nextUpgrade?: string;
  } {
    let level = 0;
    let name = 'Undeveloped';

    if (infrastructure.hasRailroad) level++;
    if (infrastructure.hasPort) level++;
    if (infrastructure.hasDepot) level++;
    if (infrastructure.industrialized) level++;

    const names = [
      'Undeveloped',
      'Developed',
      'Modernized',
      'Industrialized',
      'Fully Developed',
    ];

    name = names[Math.min(level, names.length - 1)];

    const upgrades = [
      !infrastructure.hasRailroad ? 'Railroad' : null,
      !infrastructure.hasPort ? 'Port' : null,
      !infrastructure.hasDepot ? 'Depot' : null,
      !infrastructure.industrialized ? 'Industrialization' : null,
    ].filter(Boolean) as string[];

    return {
      level,
      name,
      nextUpgrade: upgrades.length > 0 ? upgrades[0] : undefined,
    };
  }

  /* Network connectivity check (for resource flow) */
  static isConnected(
    province: Province,
    neighborProvinces: Province[]
  ): {
    connectedByRail: boolean;
    connectedByPort: boolean;
    effective: boolean;
  } {
    let connectedByRail = province.infrastructure.hasRailroad;
    let connectedByPort = province.infrastructure.hasPort;

    if (!connectedByRail) {
      // Check if connected to adjacent rail network
      for (const neighbor of neighborProvinces) {
        if (neighbor.infrastructure.hasRailroad && neighbor.owner === province.owner) {
          connectedByRail = true;
          break;
        }
      }
    }

    if (!connectedByPort) {
      // Check if connected to adjacent port
      for (const neighbor of neighborProvinces) {
        if (neighbor.infrastructure.hasPort && neighbor.owner === province.owner) {
          connectedByPort = true;
          break;
        }
      }
    }

    return {
      connectedByRail,
      connectedByPort,
      effective: connectedByRail || connectedByPort,
    };
  }
}

export { INFRASTRUCTURE_COSTS, INFRASTRUCTURE_BONUSES };
