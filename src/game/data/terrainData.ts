// Original Imperialism (1992) terrain and resource definitions
export interface TerrainType {
  id: string;
  name: string;
  icon: string;
  baseProduction: Record<string, number>;
  developmentLevels: {
    level: 0 | 1 | 2 | 3;
    production: Record<string, number>;
  }[];
  requiredDeveloper: 'Prospector' | 'Rancher' | 'Farmer' | 'Forester' | 'Driller' | 'none';
  canProspect: boolean; // If true, must be prospected first
}

export const TERRAIN_DATA: Record<string, TerrainType> = {
  // Mineral Terrains (require Prospector)
  barrenHills: {
    id: 'barrenHills',
    name: 'Barren Hills',
    icon: '⛰️',
    baseProduction: {},
    requiredDeveloper: 'Prospector',
    canProspect: true,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { coal: 2, iron: 2 } },
      { level: 2, production: { coal: 4, iron: 4 } },
      { level: 3, production: { coal: 6, iron: 6 } },
    ],
  },
  mountain: {
    id: 'mountain',
    name: 'Mountain',
    icon: '⛰️',
    baseProduction: {},
    requiredDeveloper: 'Prospector',
    canProspect: true,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { coal: 2, iron: 2, gold: 1 } },
      { level: 2, production: { coal: 4, iron: 4, gold: 2, gems: 1 } },
      { level: 3, production: { coal: 6, iron: 6, gold: 3, gems: 1 } },
    ],
  },

  // Oil Terrains (require Driller)
  swamp: {
    id: 'swamp',
    name: 'Swamp',
    icon: '🌾',
    baseProduction: {},
    requiredDeveloper: 'Driller',
    canProspect: true,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { oil: 2 } },
      { level: 2, production: { oil: 4 } },
      { level: 3, production: { oil: 6 } },
    ],
  },
  desert: {
    id: 'desert',
    name: 'Desert',
    icon: '🏜️',
    baseProduction: {},
    requiredDeveloper: 'Driller',
    canProspect: true,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { oil: 2 } },
      { level: 2, production: { oil: 4 } },
      { level: 3, production: { oil: 6 } },
    ],
  },
  tundra: {
    id: 'tundra',
    name: 'Tundra',
    icon: '❄️',
    baseProduction: {},
    requiredDeveloper: 'Driller',
    canProspect: true,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { oil: 2 } },
      { level: 2, production: { oil: 4 } },
      { level: 3, production: { oil: 6 } },
    ],
  },

  // Livestock Terrains (require Rancher)
  openRange: {
    id: 'openRange',
    name: 'Open Range',
    icon: '🤠',
    baseProduction: { livestock: 1 },
    requiredDeveloper: 'Rancher',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: { livestock: 1 } },
      { level: 1, production: { livestock: 2 } },
      { level: 2, production: { livestock: 3 } },
      { level: 3, production: { livestock: 4 } },
    ],
  },
  fertileHills: {
    id: 'fertileHills',
    name: 'Fertile Hills',
    icon: '🐑',
    baseProduction: { wool: 1 },
    requiredDeveloper: 'Rancher',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: { wool: 1 } },
      { level: 1, production: { wool: 2 } },
      { level: 2, production: { wool: 3 } },
      { level: 3, production: { wool: 4 } },
    ],
  },
  horseRanch: {
    id: 'horseRanch',
    name: 'Horse Ranch',
    icon: '🐴',
    baseProduction: { horses: 1 },
    requiredDeveloper: 'none',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: { horses: 1 } },
      { level: 1, production: { horses: 1 } },
      { level: 2, production: { horses: 1 } },
      { level: 3, production: { horses: 1 } },
    ],
  },

  // Agriculture Terrains (require Farmer)
  orchard: {
    id: 'orchard',
    name: 'Orchard',
    icon: '🍎',
    baseProduction: {},
    requiredDeveloper: 'Farmer',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { fruit: 1 } },
      { level: 2, production: { fruit: 2 } },
      { level: 3, production: { fruit: 4 } },
    ],
  },
  plantation: {
    id: 'plantation',
    name: 'Plantation',
    icon: '🌾',
    baseProduction: {},
    requiredDeveloper: 'Farmer',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { cotton: 1 } },
      { level: 2, production: { cotton: 2 } },
      { level: 3, production: { cotton: 4 } },
    ],
  },
  farm: {
    id: 'farm',
    name: 'Farm',
    icon: '🚜',
    baseProduction: {},
    requiredDeveloper: 'Farmer',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { grain: 1 } },
      { level: 2, production: { grain: 2 } },
      { level: 3, production: { grain: 4 } },
    ],
  },
  dryPlains: {
    id: 'dryPlains',
    name: 'Dry Plains',
    icon: '🌾',
    baseProduction: { grain: 1 },
    requiredDeveloper: 'none',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: { grain: 1 } },
      { level: 1, production: { grain: 1 } },
      { level: 2, production: { grain: 1 } },
      { level: 3, production: { grain: 1 } },
    ],
  },

  // Forest Terrains (require Forester)
  hardwoodForest: {
    id: 'hardwoodForest',
    name: 'Hardwood Forest',
    icon: '🌲',
    baseProduction: {},
    requiredDeveloper: 'Forester',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: {} },
      { level: 1, production: { timber: 1 } },
      { level: 2, production: { timber: 2 } },
      { level: 3, production: { timber: 4 } },
    ],
  },
  scrubForest: {
    id: 'scrubForest',
    name: 'Scrub Forest',
    icon: '🌲',
    baseProduction: { timber: 1 },
    requiredDeveloper: 'none',
    canProspect: false,
    developmentLevels: [
      { level: 0, production: { timber: 1 } },
      { level: 1, production: { timber: 1 } },
      { level: 2, production: { timber: 1 } },
      { level: 3, production: { timber: 1 } },
    ],
  },
};

export type Resource =
  | 'coal' | 'iron' | 'gold' | 'gems' | 'oil'
  | 'livestock' | 'wool' | 'horses'
  | 'fruit' | 'cotton' | 'grain' | 'timber';

export const RESOURCES: Record<Resource, { name: string; icon: string }> = {
  coal: { name: 'Coal', icon: '🔨' },
  iron: { name: 'Iron', icon: '🔨' },
  gold: { name: 'Gold', icon: '🏆' },
  gems: { name: 'Gems', icon: '💎' },
  oil: { name: 'Oil', icon: '🛢️' },
  livestock: { name: 'Livestock', icon: '🐄' },
  wool: { name: 'Wool', icon: '🐑' },
  horses: { name: 'Horses', icon: '🐴' },
  fruit: { name: 'Fruit', icon: '🍎' },
  cotton: { name: 'Cotton', icon: '🌾' },
  grain: { name: 'Grain', icon: '🌾' },
  timber: { name: 'Timber', icon: '🌲' },
};
