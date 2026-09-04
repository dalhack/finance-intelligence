// Original Imperialism game type definitions
import { Resource } from './terrainData';

export interface Province {
  id: string;
  x: number;
  y: number;
  terrainId: string;
  ownerId: string | null;
  developmentLevel: 0 | 1 | 2 | 3;
  prospected: boolean;
  population: number;
  workers: number;

  // Resource production
  resources: Record<Resource, number>;
  productionQueues: ProductionQueue[];

  // Infrastructure
  buildings: string[];
  hasRailroad: boolean;
  hasPort: boolean;
  hasFort: number; // 0, 1, 2, or 3 (fort level)

  // Military presence
  units: MilitaryUnit[];
  fortifications: number; // Defense bonus from forts
}

export interface Country {
  id: string;
  name: string;
  type: 'human' | 'ai';
  color: string;

  // Core resources
  treasury: number;
  workers: number;

  // Territory & population
  provinces: Province[];
  population: number;

  // Military
  units: MilitaryUnit[];
  militaryEra: 1 | 2 | 3;

  // Naval
  navalUnits: NavalUnit[];
  merchantMarine: number;
  freightCars: number;

  // Infrastructure & buildings
  consulates: Set<string>; // IDs of countries with consulates
  embassies: Set<string>;

  // Technology
  technology: Set<string>;
  techQueuedTurns: number;

  // Diplomacy
  diplomacy: Map<string, DiplomaticRelation>;

  // Trade
  tradeRoutes: Map<string, TradeRoute>;
  imports: Record<string, number>;
  exports: Record<string, number>;

  // Victory tracking
  conquestProgress: number; // % of world conquered
  economicProgress: number; // Current treasury / target
  technologyProgress: number; // Techs researched / total needed
}

export interface MilitaryUnit {
  id: string;
  countryId: string;
  typeId: string; // References MILITARY_UNITS
  x: number;
  y: number;
  health: number; // 0-100
  morale: number; // 0-100
  experience: number; // 0-100
  veteranStatus: 'regular' | 'veteran' | 'elite';
}

export interface NavalUnit {
  id: string;
  countryId: string;
  typeId: string; // References NAVAL_UNITS
  seaZone: number;
  health: number;
  experience: number;
  veteranStatus: 'regular' | 'veteran' | 'elite';
}

export interface DiplomaticRelation {
  countryId: string;
  trust: number; // 0-100
  warState: boolean;
  allianceState: boolean;
  boycottingCountries: Set<string>;
  status: 'WAR' | 'ALLY' | 'FRIENDLY' | 'NEUTRAL' | 'HOSTILE';
  lastAction: 'trade' | 'subsidy' | 'embargo' | 'declaration' | null;
  lastActionTurn: number;
}

export interface TradeRoute {
  from: string; // Country ID
  to: string;
  resource: string;
  quantity: number;
  profitPerTurn: number;
}

export interface ProductionQueue {
  provinceId: string;
  unitType?: string; // Military/civilian unit to produce
  buildingType?: string; // Building to construct
  resourceType?: string; // Resource/good to produce
  progress: number; // 0-100
  turnsRemaining: number;
}

export interface GameState {
  currentTurn: number;
  year: number; // 1815-1920
  gamePhase: 'diplomacy' | 'movement' | 'combat' | 'research' | 'end-turn';

  countries: Country[];
  currentCountryId: string; // Human player's country

  mapWidth: number;
  mapHeight: number;

  // Game over state
  gameOver: boolean;
  winner?: string; // Country ID
  winCondition?: 'conquest' | 'economic' | 'technology' | 'time';

  // Victory engine
  victoryStatus?: any;
}

export interface TurnReport {
  turn: number;
  year: number;
  country: string;

  income: number;
  expenses: number;
  netChange: number;

  productionReport: Record<string, number>;
  militaryReport: string[];
  diplomaticEvents: string[];
  warnings: string[];

  victoryStatus?: any;
}

// Technology definitions
export interface Technology {
  id: string;
  name: string;
  description: string;
  researchTime: number;
  prerequisite?: string;
  bonus: {
    combatBonus?: number;
    productionBonus?: number;
    movementBonus?: number;
  };
}

export const TECHNOLOGIES: Record<string, Technology> = {
  musketry: {
    id: 'musketry',
    name: 'Musketry',
    description: 'Improves infantry combat effectiveness',
    researchTime: 2,
    bonus: { combatBonus: 10 },
  },
  horsemanship: {
    id: 'horsemanship',
    name: 'Horsemanship',
    description: 'Enhances cavalry units',
    researchTime: 2,
    bonus: { combatBonus: 8, movementBonus: 1 },
  },
  artilleryTactics: {
    id: 'artilleryTactics',
    name: 'Artillery Tactics',
    description: 'Improves artillery unit effectiveness',
    researchTime: 3,
    bonus: { combatBonus: 15 },
  },
  ironclads: {
    id: 'ironclads',
    name: 'Ironclads',
    description: 'Enables ironclad naval vessels',
    researchTime: 4,
    bonus: { combatBonus: 20 },
  },
  industrialization: {
    id: 'industrialization',
    name: 'Industrialization',
    description: 'Increases production capacity',
    researchTime: 5,
    bonus: { productionBonus: 25 },
  },
  railroads: {
    id: 'railroads',
    name: 'Railroads',
    description: 'Unlocks railroad infrastructure',
    researchTime: 4,
    bonus: { movementBonus: 2 },
  },
  steampower: {
    id: 'steampower',
    name: 'Steam Power',
    description: 'Enables steam-powered units and transport',
    researchTime: 5,
    prerequisite: 'railroads',
    bonus: { productionBonus: 15, movementBonus: 1 },
  },
  mechanization: {
    id: 'mechanization',
    name: 'Mechanization',
    description: 'Enables mechanized military units',
    researchTime: 6,
    prerequisite: 'steampower',
    bonus: { combatBonus: 25, movementBonus: 2 },
  },
  rifleInfantry: {
    id: 'rifleInfantry',
    name: 'Rifle Infantry',
    description: 'Improves infantry combat',
    researchTime: 3,
    bonus: { combatBonus: 12 },
  },
  navigation: {
    id: 'navigation',
    name: 'Navigation',
    description: 'Extends naval trading routes',
    researchTime: 3,
    bonus: {},
  },
};
