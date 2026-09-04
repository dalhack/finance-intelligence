import { Country, Province, Resources, ProvinceType } from '../types/index';

const RESOURCE_PRICES = {
  coal: 50,
  iron: 70,
  trees: 40,
  sheep: 60,
  cotton: 80,
  wheat: 20,
  fish: 35,
  cloth: 120,
  lumber: 90,
  steel: 200,
  shirts: 250,
  chairs: 220,
  hammers: 280,
};

const WORKER_COST = 10; // $ per worker per turn
const UNIT_MAINTENANCE = 50; // $ per unit per turn
const CONSULATE_COST = 500; // $ one-time cost
const EMBASSY_COST = 5000; // $ one-time cost

export class EconomyEngine {
  /* Calculate raw material production for a province */
  static calculateRawProduction(province: Province): Resources {
    const production: Resources = {
      coal: 0, iron: 0, trees: 0, sheep: 0, cotton: 0, wheat: 0, fish: 0,
      cloth: 0, lumber: 0, steel: 0, shirts: 0, chairs: 0, hammers: 0,
    };

    if (!province.owner) return production;

    // Base production varies by province characteristics
    const baseMultiplier = this.getProductionMultiplier(province);

    // Determine what this province produces based on randomized resources
    // This is simplified - in full game, would have terrain-based resources
    const harvestedResources = this.harvestResources(province, baseMultiplier);

    return { ...production, ...harvestedResources };
  }

  /* Calculate processed goods from workers and raw materials */
  static calculateProcessedProduction(
    province: Province,
    availableWorkers: number
  ): Resources {
    const production: Resources = {
      coal: 0, iron: 0, trees: 0, sheep: 0, cotton: 0, wheat: 0, fish: 0,
      cloth: 0, lumber: 0, steel: 0, shirts: 0, chairs: 0, hammers: 0,
    };

    if (!province.owner || availableWorkers === 0) return production;

    const industrialBonus = province.infrastructure.industrialized ? 1.5 : 1.0;
    const depotBonus = province.infrastructure.hasDepot ? 1.2 : 1.0;
    const productionBonus = industrialBonus * depotBonus;

    // Allocate workers to production processes
    const workersPerProcess = Math.floor(availableWorkers / 4);

    // Cloth production: cotton or sheep
    if (province.resources.cotton > 0 || province.resources.sheep > 0) {
      const available = Math.min(province.resources.cotton * 2, province.resources.sheep);
      const clothOutput = Math.floor(Math.min(workersPerProcess * 6, available) * productionBonus);
      production.cloth = clothOutput;
    }

    // Lumber production: trees
    if (province.resources.trees > 0) {
      const lumberOutput = Math.floor(Math.min(workersPerProcess * 5, province.resources.trees) * productionBonus);
      production.lumber = lumberOutput;
    }

    // Steel production: coal + iron (1:1 ratio)
    if (province.resources.coal > 0 && province.resources.iron > 0) {
      const available = Math.min(province.resources.coal, province.resources.iron);
      const steelOutput = Math.floor(Math.min(workersPerProcess * 4, available) * productionBonus);
      production.steel = steelOutput;
    }

    return production;
  }

  /* Calculate finished goods from processed materials */
  static calculateFinishedGoods(province: Province, workers: number): Resources {
    const production: Resources = {
      coal: 0, iron: 0, trees: 0, sheep: 0, cotton: 0, wheat: 0, fish: 0,
      cloth: 0, lumber: 0, steel: 0, shirts: 0, chairs: 0, hammers: 0,
    };

    if (!province.owner || workers === 0) return production;

    const industrialBonus = province.infrastructure.industrialized ? 1.5 : 1.0;

    // Shirts: cloth → shirts (3:2 ratio)
    if (province.resources.cloth > 0) {
      production.shirts = Math.floor(Math.min(Math.floor(workers * 3), province.resources.cloth) * 0.67 * industrialBonus);
    }

    // Chairs: lumber → chairs (2:1 ratio)
    if (province.resources.lumber > 0) {
      production.chairs = Math.floor(Math.min(Math.floor(workers * 2), province.resources.lumber) * 0.5 * industrialBonus);
    }

    // Hammers: steel → hammers (1:1 ratio)
    if (province.resources.steel > 0) {
      production.hammers = Math.floor(Math.min(Math.floor(workers * 2), province.resources.steel) * industrialBonus);
    }

    return production;
  }

  /* Process turn economics for a country */
  static processCountryEconomics(country: Country): {
    income: number;
    expenses: number;
  } {
    let income = 0;
    let expenses = 0;

    // Worker costs
    expenses += country.workers * WORKER_COST;

    // Unit maintenance
    expenses += country.units.length * UNIT_MAINTENANCE;

    // Trade income (simplified - half of production value)
    country.provinces.forEach(province => {
      const totalValue = Object.entries(province.resources).reduce(
        (sum, [key, amount]) => sum + (amount * (RESOURCE_PRICES[key as keyof typeof RESOURCE_PRICES] || 0)),
        0
      );
      income += Math.floor(totalValue * 0.5); // Trade markup
    });

    return { income, expenses };
  }

  /* Calculate transport capacity usage */
  static calculateTransportUsage(
    country: Country,
    transportedGoods: Resources
  ): {
    maritime: number;
    terrestrial: number;
  } {
    const totalGoodWeight = Object.values(transportedGoods).reduce((a, b) => a + b, 0);

    return {
      maritime: Math.ceil(totalGoodWeight * 0.7), // Maritime carries 70% of weight
      terrestrial: Math.ceil(totalGoodWeight * 0.3), // Terrestrial 30%
    };
  }

  /* Check if resources are wasted (not transported/used) */
  static identifyWastedResources(province: Province): Resources {
    const wasted: Resources = {
      coal: 0, iron: 0, trees: 0, sheep: 0, cotton: 0, wheat: 0, fish: 0,
      cloth: 0, lumber: 0, steel: 0, shirts: 0, chairs: 0, hammers: 0,
    };

    // Resources are wasted if:
    // 1. Province has no railroad/port connection
    // 2. No depot nearby
    // 3. No merchant marine/freight capacity

    if (!province.infrastructure.hasRailroad && !province.infrastructure.hasPort) {
      // All raw materials are wasted
      wasted.coal = province.resources.coal;
      wasted.iron = province.resources.iron;
      wasted.trees = province.resources.trees;
      wasted.sheep = province.resources.sheep;
      wasted.cotton = province.resources.cotton;
      wasted.wheat = province.resources.wheat;
      wasted.fish = province.resources.fish;
    }

    return wasted;
  }

  private static getProductionMultiplier(province: Province): number {
    let multiplier = 1.0;

    if (province.type === ProvinceType.Capital) multiplier *= 1.5;
    if (province.type === ProvinceType.Town) multiplier *= 1.3;
    if (province.type === ProvinceType.Village) multiplier *= 1.1;

    if (province.infrastructure.industrialized) multiplier *= 1.5;
    if (province.infrastructure.hasDepot) multiplier *= 1.2;

    return multiplier;
  }

  private static harvestResources(province: Province, multiplier: number): Partial<Resources> {
    // Simplified resource harvesting based on province characteristics
    // In full game, this would be based on terrain type and discovered resources
    return {
      wheat: Math.floor(20 * multiplier),
      fish: Math.floor(15 * multiplier),
      coal: Math.floor(10 * multiplier),
      iron: Math.floor(8 * multiplier),
    };
  }
}
