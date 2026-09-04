import { Province, Coordinates, ProvinceType, Resources } from '../types/index';

// Simple seeded random number generator
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

export function generateMap(width: number, height: number, seed: number): Province[] {
  const rng = new SeededRandom(seed);
  const provinces: Province[] = [];

  // Create a grid of provinces
  const cellSize = 5; // Each province covers 5x5 squares
  const cols = Math.ceil(width / cellSize);
  const rows = Math.ceil(height / cellSize);

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const provinceId = `prov_${row}_${col}`;
      const baseX = col * cellSize;
      const baseY = row * cellSize;

      // Randomize position within cell
      const offsetX = rng.range(0, cellSize);
      const offsetY = rng.range(0, cellSize);

      const resources = getEmptyResources();
      resources.coal = rng.range(0, 50);
      resources.iron = rng.range(0, 40);
      resources.trees = rng.range(10, 80);
      resources.sheep = rng.range(5, 60);
      resources.cotton = rng.range(0, 50);
      resources.wheat = rng.range(20, 100);
      resources.fish = rng.range(0, 40);

      const province: Province = {
        id: provinceId,
        name: generateProvinceName(rng),
        position: {
          x: baseX + offsetX,
          y: baseY + offsetY,
        },
        type: ProvinceType.Hamlet,
        terrain: 'grassland',
        owner: null,
        population: rng.range(5000, 50000),
        workers: rng.range(20, 80),
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

const ADJECTIVES = [
  'Great', 'Ancient', 'New', 'Royal', 'Holy', 'Dark', 'Golden', 'Silver',
  'Northern', 'Southern', 'Eastern', 'Western', 'Central', 'Upper', 'Lower',
];

const NOUNS = [
  'Kingdom', 'Empire', 'Province', 'Territory', 'Valley', 'Plains', 'Mountain',
  'River', 'Bay', 'Port', 'City', 'Castle', 'Keep', 'Realm', 'Domain',
];

function generateProvinceName(rng: SeededRandom): string {
  const adj = ADJECTIVES[rng.range(0, ADJECTIVES.length)];
  const noun = NOUNS[rng.range(0, NOUNS.length)];
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
