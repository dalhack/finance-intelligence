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

export interface Unit {
  id: string;
  type: UnitType;
  countryId: string;
  position: Coordinates;
  health: number;
  experience: number;
}

export interface Province {
  id: string;
  name: string;
  position: Coordinates;
  owner: string | null;
  resources: {
    food: number;
    gold: number;
    production: number;
  };
  population: number;
  garrisonUnits: Unit[];
}

export interface Country {
  id: string;
  name: string;
  type: CountryType;
  treasury: number;
  provinces: Province[];
  units: Unit[];
  technology: Map<string, number>;
  diplomacy: Map<string, DiplomaticRelation>;
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
