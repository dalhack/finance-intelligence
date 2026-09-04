export interface Coordinates {
  x: number;
  y: number;
}

export enum UnitType {
  Infantry = 'infantry',
  Cavalry = 'cavalry',
  Artillery = 'artillery',
  Navy = 'navy',
}

export enum CountryType {
  Player = 'player',
  AI = 'ai',
}

export enum ResourceType {
  Coal = 'coal',
  Iron = 'iron',
  Trees = 'trees',
  Sheep = 'sheep',
  Cotton = 'cotton',
  Wheat = 'wheat',
  Fish = 'fish',
}

export enum ProvinceType {
  Hamlet = 'hamlet',
  Village = 'village',
  Town = 'town',
  Capital = 'capital',
}

export interface Unit {
  id: string;
  type: UnitType;
  countryId: string;
  position: Coordinates;
  health: number;
  experience: number;
}

export interface Resources {
  coal: number;
  iron: number;
  trees: number;
  sheep: number;
  cotton: number;
  wheat: number;
  fish: number;
  // Semi-finished goods
  cloth: number;
  lumber: number;
  steel: number;
  // Finished goods
  shirts: number;
  chairs: number;
  hammers: number;
}

export interface Province {
  id: string;
  name: string;
  position: Coordinates;
  type: ProvinceType;
  owner: string | null;
  population: number;
  workers: number;
  resources: Resources;
  production: {
    raw: Resources; // Raw material production per turn
    processed: Resources; // Processed goods per turn
  };
  infrastructure: {
    hasRailroad: boolean;
    hasPort: boolean;
    hasDepot: boolean;
    industrialized: boolean;
  };
  garrisonUnits: Unit[];
}

export interface Country {
  id: string;
  name: string;
  type: CountryType;
  treasury: number;
  provinces: Province[];
  units: Unit[];
  workers: number;
  technology: Map<string, number>;
  diplomacy: Map<string, DiplomaticRelation>;
  // Transport capacity
  merchantMarine: number;
  freightCars: number;
  // Trade
  tradeAgreements: Map<string, boolean>;
  consulates: Set<string>;
}

export interface DiplomaticRelation {
  countryId: string;
  trust: number;
  tradeAgreement: boolean;
  warState: boolean;
}

export interface GameState {
  currentTurn: number;
  currentPlayerCountryId: string;
  countries: Country[];
  provinces: Province[];
  units: Unit[];
  gamePhase: 'diplomacy' | 'movement' | 'combat' | 'research' | 'end-turn';
  selectedUnit: Unit | null;
  selectedProvince: Province | null;
  year: number;
}

export interface MapConfig {
  width: number;
  height: number;
  seed: number;
}

export interface GameConfig {
  map: MapConfig;
  numCountries: number;
  difficulty: 'easy' | 'normal' | 'hard';
  gameSpeed: 'slow' | 'normal' | 'fast';
}
