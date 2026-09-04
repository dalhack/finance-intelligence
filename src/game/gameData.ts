// Original Imperialism game data extracted from reference card
// All statistics and mechanics are authentic to the 1997 game

export interface TerrainData {
  name: string;
  developedBy: string; // Unit type that develops it
  resource: string;
  developmentLevels: {
    level1: number;
    level2: number;
    level3: number;
  };
  prospect?: boolean; // Can be prospected (Barren Hills, Mountain)
  alwaysProduces?: number; // Minimum production if developed
}

export interface UnitStats {
  firepower: number;
  melee: number;
  range: number;
  defense: number; // format: "X(Y)" where Y is fortified
  movement: number;
  cost: number;
}

export interface ResourcePrice {
  raw: number;
  processed: number;
}

// Terrain types and their production - Page 1-3
export const TERRAIN_DATA: Record<string, TerrainData> = {
  // Mineral terrain
  'barren_hills': {
    name: 'Barren Hills',
    developedBy: 'Miner',
    resource: 'coal',
    developmentLevels: { level1: 2, level2: 4, level3: 6 },
    prospect: true,
  },
  'mountain': {
    name: 'Mountain',
    developedBy: 'Miner',
    resource: 'mixed_minerals', // Produces coal, iron, gold, or gems
    developmentLevels: { level1: 2, level2: 4, level3: 6 },
    prospect: true,
  },
  'swamp': {
    name: 'Swamp',
    developedBy: 'Driller',
    resource: 'oil',
    developmentLevels: { level1: 2, level2: 4, level3: 6 },
  },
  'desert': {
    name: 'Desert',
    developedBy: 'Driller',
    resource: 'oil',
    developmentLevels: { level1: 2, level2: 4, level3: 6 },
  },
  'tundra': {
    name: 'Tundra',
    developedBy: 'Driller',
    resource: 'oil',
    developmentLevels: { level1: 2, level2: 4, level3: 6 },
  },
  // Agricultural terrain
  'open_range': {
    name: 'Open Range',
    developedBy: 'Rancher',
    resource: 'livestock',
    developmentLevels: { level1: 1, level2: 2, level3: 3, },
  },
  'fertile_hills': {
    name: 'Fertile Hills',
    developedBy: 'Rancher',
    resource: 'wool',
    developmentLevels: { level1: 1, level2: 2, level3: 3 },
  },
  'orchard': {
    name: 'Orchard',
    developedBy: 'Farmer',
    resource: 'fruit',
    developmentLevels: { level1: 1, level2: 2, level3: 3 },
  },
  'plantation': {
    name: 'Plantation',
    developedBy: 'Farmer',
    resource: 'cotton',
    developmentLevels: { level1: 1, level2: 2, level3: 3 },
  },
  'farm': {
    name: 'Farm',
    developedBy: 'Farmer',
    resource: 'grain',
    developmentLevels: { level1: 1, level2: 2, level3: 3 },
  },
  'dry_plains': {
    name: 'Dry Plains',
    developedBy: 'Farmer',
    resource: 'grain',
    developmentLevels: { level1: 1, level2: 1, level3: 1 },
    alwaysProduces: 1,
  },
  // Forest terrain
  'hardwood_forest': {
    name: 'Hardwood Forest',
    developedBy: 'Forester',
    resource: 'timber',
    developmentLevels: { level1: 1, level2: 2, level3: 3 },
  },
  'scrub_forest': {
    name: 'Scrub Forest',
    developedBy: 'Forester',
    resource: 'timber',
    developmentLevels: { level1: 1, level2: 1, level3: 1 },
    alwaysProduces: 1,
  },
  // Special resources
  'horse_ranch': {
    name: 'Horse Ranch',
    developedBy: 'Rancher',
    resource: 'horses',
    developmentLevels: { level1: 1, level2: 1, level3: 1 },
    alwaysProduces: 1,
  },
};

// Production chain - industrial development (Page 4)
export const PRODUCTION_CHAIN = {
  canned_food: {
    inputs: { grain: 1, fruit: 1, fish: 1, livestock: 1 },
    output: 1,
    trainedWorkers: 1,
  },
  fabric: {
    inputs: { cotton: 1, wool: 1 },
    output: 1,
    trainedWorkers: 1,
  },
  clothing: {
    inputs: { fabric: 1 },
    output: 1,
    trainedWorkers: 1,
  },
  paper: {
    inputs: { timber: 1 },
    output: 1,
  },
  lumber: {
    inputs: { timber: 1 },
    output: 1,
  },
  furniture: {
    inputs: { lumber: 1 },
    output: 1,
    trainedWorkers: 1,
  },
  steel: {
    inputs: { coal: 1, iron: 1 },
    output: 1,
  },
  hardware: {
    inputs: { steel: 1 },
    output: 1, // For armaments
    trainedWorkers: 1,
  },
  fuel: {
    inputs: { oil: 1 },
    output: 1,
  },
  power: {
    inputs: { fuel: 1 },
    output: 1, // Industrial bonus
  },
};

// Resource prices (Page 4)
export const RESOURCE_PRICES: Record<string, ResourcePrice> = {
  gold: { raw: 200, processed: 200 },
  gems: { raw: 500, processed: 500 },
};

// Military units with authentic stats - Page 5
export const MILITARY_UNITS = {
  era1: {
    musketeers: { name: 'Musketeers', f: 5, m: 5, r: 5, d: 4, mv: 4, cost: 300 },
    regulars: { name: 'Regulars', f: 5, m: 5, r: 5, d: 7, mv: 6, cost: 350 },
    hussars: { name: 'Hussars', f: 10, m: 10, r: 5, d: 5, mv: 4, cost: 450 },
    light_artillery: { name: 'Light Artillery', f: 12, m: 12, r: 5, d: 5, mv: 4, cost: 500 },
    sappers: { name: 'Sappers', f: 7, m: 10, r: 3, d: 7, mv: 11, cost: 400 },
    skirmishers: { name: 'Skirmishers', f: 15, m: 19, r: 3, d: 5, mv: 9, cost: 400 },
    grenadiers: { name: 'Grenadiers', f: 10, m: 3, r: 9, d: 3, mv: 5, cost: 500 },
    cuirassiers: { name: 'Cuirassiers', f: 16, m: 4, r: 11, d: 2, mv: 3, cost: 600 },
    artillery: { name: 'Artillery', f: 16, m: 4, r: 11, d: 3, mv: 4, cost: 600 },
    general: { name: 'General', f: 0, m: 0, r: 5, d: 1, mv: 5, cost: 2000 },
  },
  era2: {
    militia: { name: 'Militia', f: 7, m: 7, r: 8, d: 4, mv: 4, cost: 400 },
    rifle_infantry: { name: 'Rifle Infantry', f: 10, m: 10, r: 8, d: 7, mv: 6, cost: 450 },
    scouts: { name: 'Scouts', f: 15, m: 15, r: 8, d: 7, mv: 4, cost: 400 },
    field_artillery: { name: 'Field Artillery', f: 17, m: 17, r: 8, d: 7, mv: 4, cost: 700 },
    engineers: { name: 'Engineers', f: 10, m: 13, r: 5, d: 5, mv: 11, cost: 550 },
    sharpshooters: { name: 'Sharpshooters', f: 20, m: 26, r: 5, d: 5, mv: 9, cost: 500 },
    guards: { name: 'Guards', f: 17, m: 13, r: 5, d: 5, mv: 6, cost: 600 },
    carbineers: { name: 'Carbineers', f: 30, m: 8, r: 12, d: 3, mv: 3, cost: 800 },
    siege_artillery: { name: 'Siege Artillery', f: 30, m: 14, r: 14, d: 3, mv: 3, cost: 1000 },
    general: { name: 'General', f: 0, m: 0, r: 8, d: 1, mv: 7, cost: 2500 },
  },
  era3: {
    conscripts: { name: 'Conscripts', f: 10, m: 10, r: 10, d: 10, mv: 5, cost: 500 },
    infantry: { name: 'Infantry', f: 15, m: 15, r: 10, d: 20, mv: 7, cost: 600 },
    mechanized: { name: 'Mechanized', f: 22, m: 22, r: 10, d: 20, mv: 5, cost: 1000 },
    mobile_artillery: { name: 'Mobile Artillery', f: 25, m: 25, r: 10, d: 20, mv: 4, cost: 1200 },
    saboteurs: { name: 'Saboteurs', f: 22, m: 28, r: 10, d: 10, mv: 11, cost: 700 },
    rangers: { name: 'Rangers', f: 45, m: 60, r: 12, d: 20, mv: 9, cost: 800 },
    machine_gunners: { name: 'Machine Gunners', f: 25, m: 8, r: 15, d: 20, mv: 8, cost: 1100 },
    armor: { name: 'Armor', f: 50, m: 12, r: 17, d: 20, mv: 3, cost: 2000 },
    railroad_gun: { name: 'Railroad Gun', f: 50, m: 12, r: 17, d: 20, mv: 5, cost: 1800 },
    general: { name: 'General', f: 0, m: 0, r: 10, d: 1, mv: 11, cost: 3500 },
  },
};

// Naval units with authentic stats - Page 6
export const NAVAL_UNITS = {
  ship_of_the_line: { name: 'Ship-of-the-Line', f: 3, r: 5, a: 10, h: 35, sp: 4, sz: 3, cost: 1500 },
  frigate: { name: 'Frigate', f: 3, r: 5, a: 10, h: 35, sp: 4, sz: 3, cost: 1200 },
  ironclad: { name: 'Ironclad', f: 6, r: 6, a: 20, h: 65, sp: 3, sz: 2, cost: 2000 },
  raider: { name: 'Raider', f: 6, r: 6, a: 20, h: 65, sp: 3, sz: 2, cost: 1800 },
  armored_cruiser: { name: 'Armored Cruiser', f: 3, r: 7, a: 20, h: 30, sp: 7, sz: 5, cost: 2200 },
  advanced_ironclad: { name: 'Advanced Ironclad', f: 5, r: 8, a: 55, h: 50, sp: 5, sz: 3, cost: 2500 },
  battlecruiser: { name: 'Battlecruiser', f: 20, r: 13, a: 70, h: 115, sp: 7, sz: 5, cost: 4000 },
  dreadnought: { name: 'Dreadnought', f: 18, r: 13, a: 55, h: 90, sp: 9, sz: 6, cost: 4500 },
};

// Diplomatic options and costs - Page 6
export const DIPLOMATIC_ACTIONS = {
  trade_consulte: {
    name: 'Trade Consulte',
    cost: 500,
    effects: {
      tradeBonus: 0.1,
      relationshipImprovement: 5,
    },
  },
  embassy: {
    name: 'Embassy',
    cost: 5000,
    effects: {
      tradeBonus: 0.2,
      relationshipImprovement: 10,
      overseasProfits: true,
    },
  },
};

// Civilian units (Page 3)
export const CIVILIAN_UNITS = {
  prospector: {
    name: 'Prospector',
    description: 'Searches in Barren Hills and Mountains for resources',
    searchableTerrain: ['barren_hills', 'mountain'],
    resources: ['coal', 'iron', 'gold', 'gems'],
    cost: 200,
  },
  engineer: {
    name: 'Engineer',
    description: 'Builds infrastructure',
    buildable: ['rr_track', 'rail_depot', 'port', 'fort'],
    cost: 400,
  },
  developer: {
    name: 'Developer',
    description: 'Purchases land in Minor Nations',
    cost: 600,
  },
};

// Infrastructure development levels (Page 3)
export const INFRASTRUCTURE_LEVELS = {
  fort: {
    level1: { name: 'Fort Level 1', defensiveBonus: 10 },
    level2: { name: 'Fort Level 2', defensiveBonus: 20 },
    level3: { name: 'Fort Level 3', defensiveBonus: 30 },
  },
};

// Game constants
export const GAME_CONSTANTS = {
  startYear: 1815,
  turnsPerYear: 4,
  maxEras: 3, // Era 1, 2, 3 for military units
  mapDefaultWidth: 100,
  mapDefaultHeight: 100,
};
