export interface Coordinates {
  x: number;
  y: number;
}

export enum UnitType {
  Infantry = 'infantry',
  Cavalry = 'cavalry',
  Artillery = 'artillery',
  Navy = 'navy',
  // Civilian units
  Prospector = 'prospector',
  Engineer = 'engineer',
  Developer = 'developer',
  Miner = 'miner',
  Rancher = 'rancher',
  Farmer = 'farmer',
  Forester = 'forester',
  Driller = 'driller',
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
  Oil = 'oil',
  Gold = 'gold',
  Gems = 'gems',
  Livestock = 'livestock',
  Wool = 'wool',
  Fruit = 'fruit',
  Timber = 'timber',
  Horses = 'horses',
  Grain = 'grain',
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
  morale: number; // 0-100, units retreat when morale depletes
  experience: number;
  era?: number; // Military era (1-3)
}

export interface NavalUnit {
  id: string;
  type: string; // e.g., 'frigate', 'ironclad', 'dreadnought'
  countryId: string;
  seaZone: number; // Sea zone position
  health: number;
  firepower: number;
  range: number;
  armor: number;
  hull: number;
  speed: number;
  experience: number;
}

export interface Resources {
  // Raw materials
  coal: number;
  iron: number;
  trees: number;
  sheep: number;
  cotton: number;
  wheat: number;
  fish: number;
  oil: number;
  gold: number;
  gems: number;
  livestock: number;
  wool: number;
  fruit: number;
  timber: number;
  horses: number;
  grain: number;
  // Semi-finished goods
  cloth: number;
  lumber: number;
  steel: number;
  paper: number;
  fabric: number;
  fuel: number;
  // Finished goods
  shirts: number;
  chairs: number;
  hammers: number;
  canned_food: number;
  clothing: number;
  furniture: number;
  hardware: number;
  power: number;
}

export interface Province {
  id: string;
  name: string;
  position: Coordinates;
  type: ProvinceType;
  terrain: string; // Terrain type from TERRAIN_DATA
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
    fortLevel: number; // 0-3
  };
  garrisonUnits: Unit[];
  developmentLevel: number; // 0-3, for resource production scaling
}

export interface Country {
  id: string;
  name: string;
  type: CountryType;
  treasury: number;
  provinces: Province[];
  units: Unit[];
  navalUnits?: NavalUnit[];
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
  militaryEra: number; // 1-3, determines available military units

  // Original Imperialism game state
  mapWidth?: number;
  mapHeight?: number;
  gameOver?: boolean;
  winner?: string;
  winCondition?: 'conquest' | 'economic' | 'technology' | 'time';
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
