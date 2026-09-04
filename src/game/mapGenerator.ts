// Original Imperialism Map Generator
// Generates 1815-era world map with proper terrain distribution and countries

import { Province, Country, CountryType, ProvinceType, Resources, Coordinates } from '../types/index';
import { TERRAIN_DATA } from './data/terrainData';

const COUNTRY_COLORS = [
  '#aa00aa', // Magenta - Player
  '#0000aa', // Blue
  '#00aa00', // Green
  '#aa0000', // Red
  '#aaaa00', // Yellow
  '#00aaaa', // Cyan
];

const COUNTRY_NAMES = [
  'Ottoman Empire',
  'British Empire',
  'French Republic',
  'Russian Empire',
  'German States',
  'Spanish Kingdom',
];

// Seeded random number generator
class SeededRandom {
  private seed: number;

  constructor(seed: number) {
    this.seed = seed;
  }

  next(): number {
    this.seed = (this.seed * 9301 + 49297) % 233280;
    return this.seed / 233280;
  }

  range(min: number, max: number): number {
    return Math.floor(this.next() * (max - min) + min);
  }
}

export function generateMap(width: number, height: number, seed: number): { provinces: Province[]; countries: Country[] } {
  const rng = new SeededRandom(seed);
  const numCountries = 6;

  // Step 1: Generate terrain map
  const terrainMap = generateTerrainMap(width, height, rng);

  // Step 2: Create provinces from terrain
  const provinces = createProvinces(terrainMap, width, height, rng);

  // Step 3: Create countries
  const countries = createCountries(numCountries);

  // Step 4: Assign provinces to countries
  assignProvincesToCountries(provinces, countries, width, height, rng);

  return { provinces, countries };
}

/**
 * Generate terrain map using noise-based algorithm
 * Uses terrain types from original Imperialism game
 */
function generateTerrainMap(width: number, height: number, rng: SeededRandom): string[][] {
  const map: string[][] = [];
  const terrainKeys = Object.keys(TERRAIN_DATA);

  // Create base terrain with random distribution
  for (let y = 0; y < height; y++) {
    map[y] = [];
    for (let x = 0; x < width; x++) {
      const rand = rng.next();

      // Terrain distribution weighted toward playable/resource areas
      let terrain: string;
      if (rand < 0.12) terrain = 'mountain';
      else if (rand < 0.22) terrain = 'barrenHills';
      else if (rand < 0.30) terrain = 'swamp';
      else if (rand < 0.36) terrain = 'desert';
      else if (rand < 0.42) terrain = 'tundra';
      else if (rand < 0.50) terrain = 'openRange';
      else if (rand < 0.56) terrain = 'fertileHills';
      else if (rand < 0.61) terrain = 'horseRanch';
      else if (rand < 0.66) terrain = 'orchard';
      else if (rand < 0.71) terrain = 'plantation';
      else if (rand < 0.76) terrain = 'farm';
      else if (rand < 0.79) terrain = 'dryPlains';
      else if (rand < 0.85) terrain = 'hardwoodForest';
      else if (rand < 0.91) terrain = 'scrubForest';
      else terrain = 'scrubForest';

      map[y][x] = terrain;
    }
  }

  // Smooth terrain to create coherent regions
  return smoothTerrainMap(map, width, height);
}

/**
 * Smooth terrain map to create more coherent geographic regions
 */
function smoothTerrainMap(map: string[][], width: number, height: number): string[][] {
  const smoothed: string[][] = map.map(row => [...row]);

  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const neighbors = [
        map[y - 1][x],
        map[y + 1][x],
        map[y][x - 1],
        map[y][x + 1],
      ];

      // Find most common neighbor terrain
      const terrainCount: Record<string, number> = {};
      neighbors.forEach(t => {
        terrainCount[t] = (terrainCount[t] || 0) + 1;
      });

      // If current terrain is minority, change it
      const currentTerrain = map[y][x];
      const currentCount = terrainCount[currentTerrain] || 0;
      if (currentCount < 2) {
        const mostCommon = Object.entries(terrainCount)
          .sort(([, a], [, b]) => b - a)[0];
        if (mostCommon) {
          smoothed[y][x] = mostCommon[0];
        }
      }
    }
  }

  return smoothed;
}

/**
 * Create Province objects from terrain map
 */
function createProvinces(terrainMap: string[][], width: number, height: number, rng: SeededRandom): Province[] {
  const provinces: Province[] = [];
  const cellSize = 3; // Group cells into provinces
  const cols = Math.ceil(width / cellSize);
  const rows = Math.ceil(height / cellSize);

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const x = col * cellSize;
      const y = row * cellSize;

      // Find dominant terrain in this region
      let terrainCount: Record<string, number> = {};
      for (let dy = 0; dy < cellSize && y + dy < height; dy++) {
        for (let dx = 0; dx < cellSize && x + dx < width; dx++) {
          const terrain = terrainMap[y + dy][x + dx];
          terrainCount[terrain] = (terrainCount[terrain] || 0) + 1;
        }
      }

      const dominantTerrain = Object.entries(terrainCount)
        .sort(([, a], [, b]) => b - a)[0]?.[0] || 'farm';

      const terrainData = TERRAIN_DATA[dominantTerrain as keyof typeof TERRAIN_DATA];
      if (!terrainData) continue;

      const resources = getEmptyResources();
      const developmentResources = terrainData.developmentLevels[1]?.production || {};
      Object.assign(resources, developmentResources);

      const province: Province = {
        id: `prov_${col}_${row}`,
        name: generateProvinceName(rng),
        position: { x: col, y: row },
        type: ProvinceType.Hamlet,
        terrain: dominantTerrain,
        owner: null,
        population: rng.range(8000, 25000),
        workers: rng.range(40, 100),
        resources,
        production: {
          raw: getEmptyResources(),
          processed: getEmptyResources(),
        },
        infrastructure: {
          hasRailroad: false,
          hasPort: false,
          hasDepot: false,
          industrialized: false,
          fortLevel: 0,
        },
        garrisonUnits: [],
        developmentLevel: 0,
      };

      provinces.push(province);
    }
  }

  return provinces;
}

/**
 * Create Country objects for players and AI
 */
function createCountries(numCountries: number): Country[] {
  const countries: Country[] = [];

  for (let i = 0; i < numCountries; i++) {
    const country: Country = {
      id: `country_${i}`,
      name: COUNTRY_NAMES[i] || `Country ${i}`,
      type: i === 0 ? CountryType.Player : CountryType.AI,
      treasury: 25000 + Math.random() * 15000,
      provinces: [],
      units: [],
      navalUnits: [],
      workers: 100,
      technology: new Map(),
      diplomacy: new Map(),
      merchantMarine: 2,
      freightCars: 5,
      tradeAgreements: new Map(),
      consulates: new Set(),
    };

    countries.push(country);
  }

  return countries;
}

/**
 * Assign provinces to countries using flood fill algorithm
 */
function assignProvincesToCountries(
  provinces: Province[],
  countries: Country[],
  width: number,
  height: number,
  rng: SeededRandom
): void {
  // Create starting positions for each country
  const startPositions: Array<{ col: number; row: number; countryId: string }> = [];
  const step = Math.floor(Math.ceil(width / 3) / countries.length);

  countries.forEach((country, index) => {
    const startCol = index * step + rng.range(0, Math.max(1, step / 2));
    const startRow = rng.range(0, Math.ceil(height / 3));

    startPositions.push({
      col: startCol,
      row: startRow,
      countryId: country.id,
    });
  });

  // Assign provinces to countries
  const assigned = new Set<string>();
  const provincesPerCountry = Math.floor(provinces.length / countries.length);

  startPositions.forEach(start => {
    const queue: Array<{ col: number; row: number; countryId: string }> = [start];
    let assignedCount = 0;

    while (queue.length > 0 && assignedCount < provincesPerCountry) {
      const { col, row, countryId } = queue.shift()!;
      const key = `${col}_${row}`;

      if (assigned.has(key)) continue;
      assigned.add(key);

      const province = provinces.find(p => p.position.x === col && p.position.y === row);
      if (province) {
        province.owner = countryId;
        const country = countries.find(c => c.id === countryId);
        if (country) {
          country.provinces.push(province);
          assignedCount++;
        }
      }

      // Add neighbors with probability
      const neighbors = [
        { col: col + 1, row },
        { col: col - 1, row },
        { col, row: row + 1 },
        { col, row: row - 1 },
      ];

      neighbors.forEach(neighbor => {
        if (!assigned.has(`${neighbor.col}_${neighbor.row}`) && rng.next() > 0.4) {
          queue.push({ ...neighbor, countryId });
        }
      });
    }
  });

  // Assign remaining provinces to closest country
  provinces.forEach(province => {
    if (!province.owner) {
      let closestCountry = countries[0];
      let closestDist = Infinity;

      countries.forEach(country => {
        if (country.provinces.length > 0) {
          const avgPos = {
            x: country.provinces.reduce((sum, p) => sum + p.position.x, 0) / country.provinces.length,
            y: country.provinces.reduce((sum, p) => sum + p.position.y, 0) / country.provinces.length,
          };

          const dist = Math.sqrt(
            Math.pow(province.position.x - avgPos.x, 2) +
            Math.pow(province.position.y - avgPos.y, 2)
          );

          if (dist < closestDist) {
            closestDist = dist;
            closestCountry = country;
          }
        }
      });

      province.owner = closestCountry.id;
      closestCountry.provinces.push(province);
    }
  });

  // Initialize diplomatic relations
  countries.forEach(country1 => {
    countries.forEach(country2 => {
      if (country1.id !== country2.id && !country1.diplomacy.has(country2.id)) {
        country1.diplomacy.set(country2.id, {
          countryId: country2.id,
          trust: 50,
          tradeAgreement: false,
          warState: false,
        });
      }
    });
  });
}

const PROVINCE_ADJECTIVES = [
  'Great', 'Ancient', 'New', 'Royal', 'Holy', 'Dark', 'Golden', 'Silver',
  'Northern', 'Southern', 'Eastern', 'Western', 'Central', 'Upper', 'Lower',
  'Wild', 'Rich', 'Fair', 'Deep', 'High',
];

const PROVINCE_NOUNS = [
  'Kingdom', 'Empire', 'Province', 'Territory', 'Valley', 'Plains', 'Mountain',
  'River', 'Bay', 'Port', 'City', 'Castle', 'Keep', 'Realm', 'Domain',
  'Heights', 'Shire', 'Reach', 'March', 'Field',
];

function generateProvinceName(rng: SeededRandom): string {
  const adj = PROVINCE_ADJECTIVES[rng.range(0, PROVINCE_ADJECTIVES.length)];
  const noun = PROVINCE_NOUNS[rng.range(0, PROVINCE_NOUNS.length)];
  return `${adj} ${noun}`;
}

function getEmptyResources(): Resources {
  return {
    coal: 0, iron: 0, trees: 0, sheep: 0, cotton: 0, wheat: 0, fish: 0,
    oil: 0, gold: 0, gems: 0, livestock: 0, wool: 0, fruit: 0, timber: 0, horses: 0, grain: 0,
    cloth: 0, lumber: 0, steel: 0, paper: 0, fabric: 0, fuel: 0,
    shirts: 0, chairs: 0, hammers: 0, canned_food: 0, clothing: 0, furniture: 0, hardware: 0, power: 0,
  };
}
