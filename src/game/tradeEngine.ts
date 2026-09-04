import { Country, GameState } from '../types/index';
import { DiplomacyEngine } from './diplomacyEngine';

export interface TradeRoute {
  id: string;
  exporterId: string;
  importerId: string;
  goodType: string;
  income: number; // Income per turn
  capacity: number; // Units of goods per turn
  established: boolean;
  maintenanceCost: number;
}

export interface TradeMetrics {
  totalIncome: number;
  totalCost: number;
  netIncome: number;
  activeRoutes: number;
  capacity: number;
  utilization: number;
}

export class TradeEngine {
  /**
   * Base trade route income value from 1992 Imperialism
   * Trade routes generate $10-50 per turn depending on goods type and distance
   */
  static readonly BASE_TRADE_INCOME = 25;
  static readonly TRADE_ROUTE_MAINTENANCE = 100; // $ per turn per route

  /**
   * Establish trade route between two countries
   * Requires: consulate in importer's capital, peace/alliance, willing partners
   */
  static establishTradeRoute(
    exporter: Country,
    importer: Country,
    goodType: string,
    gameState: GameState
  ): { success: boolean; tradeRoute?: TradeRoute; message: string } {
    // Check if can trade
    if (!DiplomacyEngine.canTrade(exporter, importer)) {
      return { success: false, message: 'Cannot trade - at war or low trust' };
    }

    // Check if exporter has consulate/embassy in importer's capital
    const hasConsulate = exporter.consulates.has(importer.id);
    if (!hasConsulate) {
      return { success: false, message: 'Requires consulate in trading partner capital' };
    }

    // Calculate income based on good type
    const income = this.calculateTradeIncome(goodType, exporter, importer);
    const capacity = this.calculateTradeCapacity(exporter, importer);

    const tradeRoute: TradeRoute = {
      id: `trade_${exporter.id}_${importer.id}_${Date.now()}`,
      exporterId: exporter.id,
      importerId: importer.id,
      goodType,
      income,
      capacity,
      established: true,
      maintenanceCost: this.TRADE_ROUTE_MAINTENANCE,
    };

    return { success: true, tradeRoute, message: `Trade route established with ${importer.name}` };
  }

  /**
   * Calculate income from a trade route based on good type and partner strength
   */
  static calculateTradeIncome(
    goodType: string,
    exporter: Country,
    importer: Country
  ): number {
    let income = this.BASE_TRADE_INCOME;

    // Modifier based on good type (luxury goods worth more)
    const premiumGoods = ['gems', 'gold', 'armaments', 'hardware'];
    if (premiumGoods.includes(goodType)) {
      income *= 1.5;
    }

    // Modifier based on importer's wealth (wealthier importers pay more)
    const importerWealthBonus = Math.min(1.5, 1.0 + importer.treasury / 200000);
    income *= importerWealthBonus;

    // Distance factor (if we had map positions) would reduce income for distant traders
    // For now, assume established routes are optimized

    return Math.floor(income);
  }

  /**
   * Calculate trade capacity (how many units of goods can be transported per turn)
   * Limited by merchant marine, freight cars, and port/railroad infrastructure
   */
  static calculateTradeCapacity(exporter: Country, importer: Country): number {
    let capacity = 0;

    // Merchant marine capacity: 10 units per vessel
    capacity += exporter.merchantMarine * 10;

    // Freight car capacity: 5 units per car
    capacity += exporter.freightCars * 5;

    // Port/railroad network bonus (enables more trade)
    const portProvinces = exporter.provinces.filter(p => p.infrastructure.hasPort).length;
    const railProvinces = exporter.provinces.filter(p => p.infrastructure.hasRailroad).length;

    capacity += portProvinces * 20; // Ports increase capacity by 20 units each
    capacity += railProvinces * 15; // Railroads increase capacity by 15 units each

    return Math.max(capacity, 50); // Minimum 50 units capacity
  }

  /**
   * Process all trade routes for a country (calculate income/expenses)
   */
  static processTradeRoutes(country: Country, tradeRoutes: TradeRoute[]): TradeMetrics {
    let totalIncome = 0;
    let totalCost = 0;
    let activeRoutes = 0;

    tradeRoutes.forEach(route => {
      if (route.exporterId === country.id && route.established) {
        totalIncome += route.income;
        totalCost += route.maintenanceCost;
        activeRoutes++;
      }
    });

    const netIncome = totalIncome - totalCost;
    const totalCapacity = Math.max(
      country.merchantMarine * 10 + country.freightCars * 5,
      50
    );

    return {
      totalIncome,
      totalCost,
      netIncome,
      activeRoutes,
      capacity: totalCapacity,
      utilization: (activeRoutes * 20) / totalCapacity, // Rough utilization estimate
    };
  }

  /**
   * Calculate maximum number of trade routes a country can maintain
   * Limits prevent infinite scaling
   */
  static getMaxTradeRoutes(country: Country): number {
    let maxRoutes = 2; // Start with 2 base trade routes

    // Each consulate allows one additional trade route
    maxRoutes += country.consulates.size;

    // Technology bonuses would go here (Navigation +20%, Advanced Trade +40%)
    // For now, base implementation

    return maxRoutes;
  }

  /**
   * Check if country can establish another trade route
   */
  static canEstablishTradeRoute(country: Country, currentRoutes: TradeRoute[]): boolean {
    const maxRoutes = this.getMaxTradeRoutes(country);
    const activeRoutes = currentRoutes.filter(r => r.exporterId === country.id && r.established).length;
    return activeRoutes < maxRoutes;
  }

  /**
   * Get diplomatic bonus from trade relationships
   * Allies and trading partners trust each other more
   */
  static getTradeDiplomacyBonus(trader1: Country, trader2: Country): number {
    const rel = trader1.diplomacy.get(trader2.id);
    if (!rel) return 0;

    // Active trade routes improve trust slowly (+2 per year)
    if (rel.tradeAgreement) return 2;

    return 0;
  }

  /**
   * Calculate total trade bonus for a country from all active routes
   * Used for production and movement bonuses
   */
  static getTradeBonusMultiplier(country: Country, activeRoutes: number): number {
    const baseMultiplier = 1.0;

    // Each active trade route provides +5% bonus
    const routeBonus = Math.min(0.3, activeRoutes * 0.05); // Cap at +30%

    return baseMultiplier + routeBonus;
  }

  /**
   * Check trade route requirements are still met (for maintenance)
   */
  static validateTradeRoute(
    route: TradeRoute,
    exporter: Country,
    importer: Country
  ): boolean {
    // Check if still at peace/can trade
    if (!DiplomacyEngine.canTrade(exporter, importer)) {
      return false;
    }

    // Check if still have consulate
    if (!exporter.consulates.has(importer.id)) {
      return false;
    }

    // Check if still solvent (can afford maintenance)
    if (exporter.treasury < route.maintenanceCost) {
      return false;
    }

    return true;
  }

  /**
   * Dissolve a trade route (ends trade)
   */
  static dissolveTradeRoute(route: TradeRoute): void {
    route.established = false;
  }
}
