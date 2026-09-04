// Original Imperialism buildings and infrastructure
export interface BuildingType {
  id: string;
  name: string;
  icon: string;
  cost: number;
  buildTime: number;
  effects: string[];
}

export const BUILDINGS: Record<string, BuildingType> = {
  // Infrastructure
  railroadTrack: {
    id: 'railroadTrack',
    name: 'Railroad Track',
    icon: '🚂',
    cost: 5000,
    buildTime: 5,
    effects: ['Increases movement speed', 'Connects provinces for trade'],
  },
  railDepot: {
    id: 'railDepot',
    name: 'Rail Depot',
    icon: '🚂',
    cost: 8000,
    buildTime: 8,
    effects: ['Freight car storage', 'Increases military unit speed'],
  },
  port: {
    id: 'port',
    name: 'Port',
    icon: '⛵',
    cost: 10000,
    buildTime: 10,
    effects: ['Naval unit construction', 'Merchant marine storage', 'Trade enhancement'],
  },
  fortLevel1: {
    id: 'fortLevel1',
    name: 'Fort Level 1',
    icon: '🏰',
    cost: 5000,
    buildTime: 5,
    effects: ['Defense +50%'],
  },
  fortLevel2: {
    id: 'fortLevel2',
    name: 'Fort Level 2',
    icon: '🏰',
    cost: 10000,
    buildTime: 10,
    effects: ['Defense +75%'],
  },
  fortLevel3: {
    id: 'fortLevel3',
    name: 'Fort Level 3',
    icon: '🏰',
    cost: 15000,
    buildTime: 15,
    effects: ['Defense +100%'],
  },

  // Economic Buildings
  tradeConsulate: {
    id: 'tradeConsulate',
    name: 'Trade Consulate',
    icon: '🏛️',
    cost: 800,
    buildTime: 2,
    effects: ['Diplomatic relations +10%', 'Trade routes +25%'],
  },
  embassy: {
    id: 'embassy',
    name: 'Embassy',
    icon: '🏛️',
    cost: 5000,
    buildTime: 8,
    effects: ['Diplomatic relations +25%', 'Alliance support'],
  },

  // Industrial Buildings
  factory: {
    id: 'factory',
    name: 'Factory',
    icon: '🏭',
    cost: 12000,
    buildTime: 12,
    effects: ['Production efficiency +50%', 'Worker training'],
  },
  industrialDevelopment: {
    id: 'industrialDevelopment',
    name: 'Industrial Development',
    icon: '🏭',
    cost: 20000,
    buildTime: 15,
    effects: ['Production efficiency +100%', 'Advanced manufacturing'],
  },
};

// Civilian units that perform building construction
export interface CivilianUnitType {
  id: string;
  name: string;
  icon: string;
  description: string;
}

export const CIVILIAN_UNITS: Record<string, CivilianUnitType> = {
  prospector: {
    id: 'prospector',
    name: 'Prospector',
    icon: '🔍',
    description: 'Searches for coal, iron, gold, gems in Barren Hills and Mountains',
  },
  rancher: {
    id: 'rancher',
    name: 'Rancher',
    icon: '🤠',
    description: 'Develops livestock and wool production',
  },
  farmer: {
    id: 'farmer',
    name: 'Farmer',
    icon: '🚜',
    description: 'Develops fruit, cotton, and grain production',
  },
  forester: {
    id: 'forester',
    name: 'Forester',
    icon: '🌲',
    description: 'Develops timber production in forests',
  },
  driller: {
    id: 'driller',
    name: 'Driller',
    icon: '⛽',
    description: 'Searches for oil in deserts, swamps, and tundras',
  },
  engineer: {
    id: 'engineer',
    name: 'Engineer',
    icon: '⚙️',
    description: 'Builds infrastructure: railroads, ports, forts, depots',
  },
  developer: {
    id: 'developer',
    name: 'Developer',
    icon: '🏗️',
    description: 'Purchases land in Minor Nations for colonization',
  },
};

// Production chain for the industrial system
export interface ProductionChain {
  inputResources: Record<string, number>;
  outputResource: string;
  outputQuantity: number;
  buildingRequired?: string;
  time: number;
}

export const PRODUCTION_CHAINS: ProductionChain[] = [
  // Food processing
  {
    inputResources: { grain: 1, livestock: 1 },
    outputResource: 'cannedFood',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },
  {
    inputResources: { fruit: 1, livestock: 1 },
    outputResource: 'cannedFood',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },
  {
    inputResources: { fish: 1, livestock: 1 },
    outputResource: 'cannedFood',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },

  // Textile production
  {
    inputResources: { cotton: 1, wool: 1 },
    outputResource: 'fabric',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },
  {
    inputResources: { fabric: 1 },
    outputResource: 'clothing',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 1,
  },

  // Paper production
  {
    inputResources: { timber: 1 },
    outputResource: 'paper',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },

  // Wood products
  {
    inputResources: { timber: 1 },
    outputResource: 'lumber',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },
  {
    inputResources: { lumber: 1 },
    outputResource: 'furniture',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },

  // Steel production
  {
    inputResources: { coal: 1, iron: 1 },
    outputResource: 'steel',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 3,
  },

  // Hardware & Armaments
  {
    inputResources: { steel: 1 },
    outputResource: 'hardware',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },
  {
    inputResources: { steel: 1 },
    outputResource: 'armaments',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 3,
  },

  // Fuel production
  {
    inputResources: { oil: 1 },
    outputResource: 'fuel',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 2,
  },

  // Power generation
  {
    inputResources: { fuel: 1 },
    outputResource: 'power',
    outputQuantity: 1,
    buildingRequired: 'factory',
    time: 1,
  },

  // Finished products
  {
    inputResources: { horses: 1 },
    outputResource: 'transport',
    outputQuantity: 1,
    time: 2,
  },
];

export type ProductionResource =
  | 'cannedFood' | 'fabric' | 'clothing'
  | 'paper' | 'lumber' | 'furniture'
  | 'steel' | 'hardware' | 'armaments'
  | 'fuel' | 'power' | 'transport';

export const PRODUCTION_RESOURCES: Record<ProductionResource, { name: string; icon: string }> = {
  cannedFood: { name: 'Canned Food', icon: '🥫' },
  fabric: { name: 'Fabric', icon: '🧵' },
  clothing: { name: 'Clothing', icon: '👕' },
  paper: { name: 'Paper', icon: '📄' },
  lumber: { name: 'Lumber', icon: '🪵' },
  furniture: { name: 'Furniture', icon: '🪑' },
  steel: { name: 'Steel', icon: '⚙️' },
  hardware: { name: 'Hardware', icon: '🔧' },
  armaments: { name: 'Armaments', icon: '🔫' },
  fuel: { name: 'Fuel', icon: '⛽' },
  power: { name: 'Power', icon: '💡' },
  transport: { name: 'Transport', icon: '🐴' },
};
