// Original Imperialism military units from the game reference card
export interface MilitaryUnitType {
  id: string;
  name: string;
  era: 1 | 2 | 3;
  icon: string;
  isGeneral: boolean;
  stats: {
    firepower: number;
    melee: number;
    range: number;
    defense: number;
    movement: number;
  };
}

export const MILITARY_UNITS: Record<string, MilitaryUnitType> = {
  // ERA I (1815-1865)
  minuteman: {
    id: 'minuteman',
    name: 'Minuteman',
    era: 1,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 5, melee: 5, range: 5, defense: 4, movement: 4 },
  },
  regulars: {
    id: 'regulars',
    name: 'Regulars',
    era: 1,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 5, melee: 5, range: 5, defense: 7, movement: 4 },
  },
  hussars: {
    id: 'hussars',
    name: 'Hussars',
    era: 1,
    icon: '🐴',
    isGeneral: false,
    stats: { firepower: 10, melee: 12, range: 5, defense: 5, movement: 4 },
  },
  lightArtillery: {
    id: 'lightArtillery',
    name: 'Light Artillery',
    era: 1,
    icon: '🔫',
    isGeneral: false,
    stats: { firepower: 12, melee: 12, range: 5, defense: 5, movement: 4 },
  },
  sappers: {
    id: 'sappers',
    name: 'Sappers',
    era: 1,
    icon: '⚔️',
    isGeneral: false,
    stats: { firepower: 7, melee: 10, range: 3, defense: 7, movement: 11 },
  },
  skirmishers: {
    id: 'skirmishers',
    name: 'Skirmishers',
    era: 1,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 15, melee: 15, range: 9, defense: 3, movement: 5 },
  },
  grenadiers: {
    id: 'grenadiers',
    name: 'Grenadiers',
    era: 1,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 17, melee: 19, range: 11, defense: 2, movement: 3 },
  },
  cuirassiers: {
    id: 'cuirassiers',
    name: 'Cuirassiers',
    era: 1,
    icon: '🐴',
    isGeneral: false,
    stats: { firepower: 10, melee: 19, range: 3, defense: 5, movement: 9 },
  },
  artillery: {
    id: 'artillery',
    name: 'Artillery',
    era: 1,
    icon: '🔫',
    isGeneral: false,
    stats: { firepower: 16, melee: 4, range: 11, defense: 2, movement: 3 },
  },
  generalEra1: {
    id: 'generalEra1',
    name: 'General',
    era: 1,
    icon: '🎖️',
    isGeneral: true,
    stats: { firepower: 0, melee: 0, range: 5, defense: 5, movement: 7 },
  },

  // ERA II (1866-1918)
  militia: {
    id: 'militia',
    name: 'Militia',
    era: 2,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 7, melee: 7, range: 8, defense: 4, movement: 4 },
  },
  rifleInfantry: {
    id: 'rifleInfantry',
    name: 'Rifle Infantry',
    era: 2,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 10, melee: 10, range: 8, defense: 7, movement: 6 },
  },
  scouts: {
    id: 'scouts',
    name: 'Scouts',
    era: 2,
    icon: '🐴',
    isGeneral: false,
    stats: { firepower: 15, melee: 15, range: 8, defense: 7, movement: 4 },
  },
  fieldArtillery: {
    id: 'fieldArtillery',
    name: 'Field Artillery',
    era: 2,
    icon: '🔫',
    isGeneral: false,
    stats: { firepower: 17, melee: 17, range: 8, defense: 5, movement: 4 },
  },
  engineers: {
    id: 'engineers',
    name: 'Engineers',
    era: 2,
    icon: '⚙️',
    isGeneral: false,
    stats: { firepower: 10, melee: 13, range: 5, defense: 7, movement: 11 },
  },
  sharpshooters: {
    id: 'sharpshooters',
    name: 'Sharpshooters',
    era: 2,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 20, melee: 20, range: 12, defense: 3, movement: 4 },
  },
  guards: {
    id: 'guards',
    name: 'Guards',
    era: 2,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 26, melee: 26, range: 13, defense: 7, movement: 4 },
  },
  carabineers: {
    id: 'carabineers',
    name: 'Carabineers',
    era: 2,
    icon: '🐴',
    isGeneral: false,
    stats: { firepower: 20, melee: 26, range: 5, defense: 5, movement: 9 },
  },
  siegeArtillery: {
    id: 'siegeArtillery',
    name: 'Siege Artillery',
    era: 2,
    icon: '🔫',
    isGeneral: false,
    stats: { firepower: 30, melee: 30, range: 14, defense: 4, movement: 3 },
  },
  generalEra2: {
    id: 'generalEra2',
    name: 'General',
    era: 2,
    icon: '🎖️',
    isGeneral: true,
    stats: { firepower: 0, melee: 0, range: 8, defense: 7, movement: 9 },
  },

  // ERA III (1919-1920)
  conscripts: {
    id: 'conscripts',
    name: 'Conscripts',
    era: 3,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 10, melee: 10, range: 10, defense: 10, movement: 5 },
  },
  infantry: {
    id: 'infantry',
    name: 'Infantry',
    era: 3,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 15, melee: 15, range: 22, defense: 20, movement: 7 },
  },
  mechanized: {
    id: 'mechanized',
    name: 'Mechanized',
    era: 3,
    icon: '🚗',
    isGeneral: false,
    stats: { firepower: 25, melee: 25, range: 20, defense: 20, movement: 5 },
  },
  mobileArtillery: {
    id: 'mobileArtillery',
    name: 'Mobile Artillery',
    era: 3,
    icon: '🔫',
    isGeneral: false,
    stats: { firepower: 45, melee: 45, range: 12, defense: 20, movement: 4 },
  },
  saboteurs: {
    id: 'saboteurs',
    name: 'Saboteurs',
    era: 3,
    icon: '💣',
    isGeneral: false,
    stats: { firepower: 22, melee: 22, range: 10, defense: 10, movement: 11 },
  },
  rangers: {
    id: 'rangers',
    name: 'Rangers',
    era: 3,
    icon: '🪖',
    isGeneral: false,
    stats: { firepower: 25, melee: 25, range: 10, defense: 12, movement: 5 },
  },
  machineGunners: {
    id: 'machineGunners',
    name: 'Machine Gunners',
    era: 3,
    icon: '🔫',
    isGeneral: false,
    stats: { firepower: 50, melee: 50, range: 15, defense: 20, movement: 3 },
  },
  armor: {
    id: 'armor',
    name: 'Armor',
    era: 3,
    icon: '🚗',
    isGeneral: false,
    stats: { firepower: 50, melee: 50, range: 17, defense: 25, movement: 11 },
  },
  railroadGun: {
    id: 'railroadGun',
    name: 'Railroad Gun',
    era: 3,
    icon: '🚂',
    isGeneral: false,
    stats: { firepower: 25, melee: 12, range: 12, defense: 20, movement: 8 },
  },
  generalEra3: {
    id: 'generalEra3',
    name: 'General',
    era: 3,
    icon: '🎖️',
    isGeneral: true,
    stats: { firepower: 0, melee: 0, range: 10, defense: 20, movement: 11 },
  },
};

// Naval units
export interface NavalUnitType {
  id: string;
  name: string;
  icon: string;
  stats: {
    firepower: number;
    range: number;
    armor: number;
    hull: number;
    speed: number;
    seaZones: number;
  };
}

export const NAVAL_UNITS: Record<string, NavalUnitType> = {
  shipOfTheLine: {
    id: 'shipOfTheLine',
    name: 'Ship of the Line',
    icon: '⛵',
    stats: { firepower: 3, range: 5, armor: 10, hull: 35, speed: 4, seaZones: 3 },
  },
  ironclad: {
    id: 'ironclad',
    name: 'Ironclad',
    icon: '🚢',
    stats: { firepower: 6, range: 6, armor: 20, hull: 65, speed: 3, seaZones: 2 },
  },
  armoredCruiser: {
    id: 'armoredCruiser',
    name: 'Armored Cruiser',
    icon: '🚢',
    stats: { firepower: 3, range: 7, armor: 20, hull: 30, speed: 7, seaZones: 5 },
  },
  battlecruiser: {
    id: 'battlecruiser',
    name: 'Battlecruiser',
    icon: '🚢',
    stats: { firepower: 5, range: 8, armor: 55, hull: 50, speed: 5, seaZones: 3 },
  },
  frigate: {
    id: 'frigate',
    name: 'Frigate',
    icon: '⛵',
    stats: { firepower: 3, range: 5, armor: 10, hull: 35, speed: 4, seaZones: 3 },
  },
  raider: {
    id: 'raider',
    name: 'Raider',
    icon: '⛵',
    stats: { firepower: 6, range: 6, armor: 20, hull: 65, speed: 3, seaZones: 2 },
  },
  advancedIronclad: {
    id: 'advancedIronclad',
    name: 'Advanced Ironclad',
    icon: '🚢',
    stats: { firepower: 10, range: 9, armor: 50, hull: 70, speed: 6, seaZones: 4 },
  },
  dreadnought: {
    id: 'dreadnought',
    name: 'Dreadnought',
    icon: '🚢',
    stats: { firepower: 18, range: 13, armor: 55, hull: 90, speed: 9, seaZones: 6 },
  },
};
