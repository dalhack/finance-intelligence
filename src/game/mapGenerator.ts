import { Province, Coordinates } from '@types/index';

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

      const province: Province = {
        id: provinceId,
        name: generateProvinceName(rng),
        position: {
          x: baseX + offsetX,
          y: baseY + offsetY,
        },
        owner: null,
        resources: {
          food: rng.range(50, 200),
          gold: rng.range(20, 100),
          production: rng.range(30, 150),
        },
        population: rng.range(5000, 50000),
        garrisonUnits: [],
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
