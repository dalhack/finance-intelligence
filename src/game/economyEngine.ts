// Original Imperialism economy engine based on actual game mechanics
// Implements the complex industrial production chain from 1992 original
import { Country, Province, Resources, ProvinceType } from '../types/index';

const RESOURCE_PRICES: Record<string, number> = {
  // Raw materials (from terrain production)
  coal: 50,
  iron: 75,
  gold: 500,
  gems: 1000,
  oil: 100,
  livestock: 100,
  wool: 120,
  horses: 150,
  fruit: 80,
  cotton: 90,
  grain: 70,
  timber: 85,

  // Intermediate goods (from industrial processing)
  steel: 200,
  fabric: 150,
  lumber: 120,
  paper: 100,
  fuel: 125,

  // Finished goods (from factories)
  cannedFood: 250,
  clothing: 200,
  furniture: 300,
  hardware: 350,
  armaments: 500,

  // Legacy names for compatibility
  trees: 40,
  sheep: 60,
  wheat: 20,
  fish: 35,
  cloth: 120,
  shirts: 250,
  chairs: 220,
  hammers: 280,
  canned_food: 250,
  power: 0,
};

const getEmptyResources = (): Resources => ({
  coal: 0, iron: 0, trees: 0, sheep: 0, cotton: 0, wheat: 0, fish: 0,
  oil: 0, gold: 0, gems: 0, livestock: 0, wool: 0, fruit: 0, timber: 0, horses: 0, grain: 0,
  cloth: 0, lumber: 0, steel: 0, paper: 0, fabric: 0, fuel: 0,
  shirts: 0, chairs: 0, hammers: 0, canned_food: 0, clothing: 0, furniture: 0, hardware: 0, power: 0,
});

const WORKER_COST = 10; // $ per worker per turn
const UNIT_MAINTENANCE = 50; // $ per unit per turn
const CONSULATE_COST = 500; // $ one-time cost
const EMBASSY_COST = 5000; // $ one-time cost

export class EconomyEngine {
  /**
   * Calculate raw material production for a province based on terrain
   * This reflects the original game's terrain development system
   */
  static calculateRawProduction(province: Province): Resources {
    const production = getEmptyResources();

    if (!province.owner) return production;

    const baseMultiplier = this.getProductionMultiplier(province);
    const harvestedResources = this.harvestResources(province, baseMultiplier);

    return { ...production, ...harvestedResources };
  }

  /**
   * Process goods through industrial chain (raw → processed)
   * Based on the complex production chains in original Imperialism
   */
  static calculateProcessedProduction(
    province: Province,
    availableWorkers: number
  ): Resources {
    const production = getEmptyResources();

    if (!province.owner || availableWorkers === 0) return production;

    const industrialBonus = province.infrastructure.industrialized ? 1.5 : 1.0;
    const depotBonus = province.infrastructure.hasDepot ? 1.2 : 1.0;
    const productionBonus = industrialBonus * depotBonus;

    const workersPerProcess = Math.floor(availableWorkers / 4);

    // Original Imperialism production chains:
    // Cotton/Wool → Fabric → Clothing
    if ((province.resources.cotton > 0 || province.resources.wool > 0) && availableWorkers > 0) {
      const fabricInput = Math.min(province.resources.cotton, province.resources.wool);
      production.fabric = Math.floor(Math.min(workersPerProcess * 6, fabricInput) * productionBonus);
    }

    // Timber → Lumber → Furniture
    if (province.resources.timber > 0) {
      production.lumber = Math.floor(Math.min(workersPerProcess * 5, province.resources.timber) * productionBonus);
    }

    // Coal + Iron → Steel → Hardware/Armaments
    if (province.resources.coal > 0 && province.resources.iron > 0) {
      const steelInput = Math.min(province.resources.coal, province.resources.iron);
      production.steel = Math.floor(Math.min(workersPerProcess * 4, steelInput) * productionBonus);
    }

    // Paper production (from timber)
    if (province.resources.timber > 0) {
      production.paper = Math.floor(Math.min(workersPerProcess * 3, province.resources.timber) * 0.5 * productionBonus);
    }

    // Fuel production (from oil)
    if (province.resources.oil > 0) {
      production.fuel = Math.floor(Math.min(workersPerProcess * 4, province.resources.oil) * productionBonus);
    }

    return production;
  }

  /**
   * Calculate finished goods from processed materials
   * Grain/Livestock → Canned Food
   * Fabric → Clothing
   * Lumber → Furniture
   * Steel → Hardware/Armaments
   */
  static calculateFinishedGoods(province: Province, workers: number): Resources {
    const production = getEmptyResources();

    if (!province.owner || workers === 0) return production;

    const industrialBonus = province.infrastructure.industrialized ? 1.5 : 1.0;

    // Canned Food: Grain + Livestock → Canned Food
    if (province.resources.grain > 0 && province.resources.livestock > 0) {
      const foodInput = Math.min(province.resources.grain, province.resources.livestock);
      production.canned_food = Math.floor(Math.min(workers * 3, foodInput) * 0.67 * industrialBonus);
    }

    // Clothing: Fabric → Clothing
    if (province.resources.fabric > 0) {
      production.clothing = Math.floor(Math.min(workers * 4, province.resources.fabric) * 0.75 * industrialBonus);
    }

    // Furniture: Lumber → Furniture
    if (province.resources.lumber > 0) {
      production.furniture = Math.floor(Math.min(workers * 2, province.resources.lumber) * 0.5 * industrialBonus);
    }

    // Hardware/Armaments: Steel → Hardware/Armaments
    if (province.resources.steel > 0) {
      production.hardware = Math.floor(Math.min(workers * 3, province.resources.steel) * 0.8 * industrialBonus);
      // Some steel also goes to armaments (military units require this)
      const armaInput = Math.min(Math.floor(province.resources.steel * 0.3), workers);
      production.hammers = Math.floor(armaInput * industrialBonus);
    }

    return production;
  }

  /**
   * Process turn economics for a country
   * Implements original game's financial system
   */
  static processCountryEconomics(country: Country): {
    income: number;
    expenses: number;
  } {
    let income = 0;
    let expenses = 0;

    // Worker costs - must pay workers every turn
    expenses += country.workers * WORKER_COST;

    // Unit maintenance - every military unit has ongoing costs
    expenses += country.units.length * UNIT_MAINTENANCE;

    // Naval unit maintenance
    if (country.navalUnits) {
      expenses += country.navalUnits.length * 100; // Ships cost more to maintain
    }

    // Trade income from provincial resources
    country.provinces.forEach(province => {
      const totalValue = Object.entries(province.resources).reduce(
        (sum, [key, amount]) => sum + (amount * (RESOURCE_PRICES[key as keyof typeof RESOURCE_PRICES] || 0)),
        0
      );
      // In original game, you sell resources for income
      income += Math.floor(totalValue * 0.6); // Trade profit margin
    });

    // Consulate/Embassy income (trade bonuses)
    if (country.consulates) {
      income += country.consulates.size * 100; // Each consulate generates trade bonus
    }

    return { income, expenses };
  }

  /**
   * Calculate transport capacity usage for trade routes
   */
  static calculateTransportUsage(
    country: Country,
    transportedGoods: Resources
  ): {
    maritime: number;
    terrestrial: number;
  } {
    const totalGoodWeight = Object.values(transportedGoods).reduce((a, b) => a + b, 0);

    return {
      maritime: Math.ceil(totalGoodWeight * 0.7), // Merchant marines carry 70%
      terrestrial: Math.ceil(totalGoodWeight * 0.3), // Freight cars carry 30%
    };
  }

  /**
   * Identify resources that are wasted (not processed or transported)
   * In original game, unconnected provinces cannot export
   */
  static identifyWastedResources(province: Province): Resources {
    const wasted = getEmptyResources();

    // Resources are wasted if province has no railroad/port connection
    if (!province.infrastructure.hasRailroad && !province.infrastructure.hasPort) {
      // All raw materials are wasted and generate no income
      wasted.coal = province.resources.coal;
      wasted.iron = province.resources.iron;
      wasted.timber = province.resources.timber;
      wasted.oil = province.resources.oil;
      wasted.grain = province.resources.grain;
      wasted.livestock = province.resources.livestock;
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
    // Simplified resource harvesting - in full game this is based on terrain type
    // Each terrain type produces specific resources at specific development levels
    return {
      wheat: Math.floor(20 * multiplier),
      fish: Math.floor(15 * multiplier),
      coal: Math.floor(10 * multiplier),
      iron: Math.floor(8 * multiplier),
    };
  }
}
