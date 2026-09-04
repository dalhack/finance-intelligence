import { Country, Province, Unit, UnitType, CountryType, ProvinceType, Resources } from '../types/index';

const COUNTRY_NAMES = [
  'British Empire', 'French Republic', 'Germanic Confederation', 'Russian Empire',
  'Ottoman Empire', 'Spanish Monarchy', 'Italian States', 'Austrian Empire',
  'Prussian Kingdom', 'Dutch Republic', 'Swedish Kingdom', 'Danish Realm',
  'Polish-Lithuanian', 'Portuguese Kingdom', 'Belgian States', 'Swiss Confederation',
];

export function initializeCountries(
  numCountries: number,
  provinces: Province[],
  difficulty: 'easy' | 'normal' | 'hard'
): Country[] {
  const countries: Country[] = [];

  // Select random provinces for each country
  const selectedProvinces = selectRandomProvinces(provinces, numCountries);

  const difficultyMods = {
    easy: { treasury: 50000, workers: 100, unitBonus: 0, merchant: 5, freight: 10 },
    normal: { treasury: 30000, workers: 80, unitBonus: 2, merchant: 3, freight: 8 },
    hard: { treasury: 20000, workers: 60, unitBonus: 4, merchant: 2, freight: 6 },
  };

  const mod = difficultyMods[difficulty];

  for (let i = 0; i < numCountries; i++) {
    const isPlayer = i === 0;
    const countryId = `country_${i}`;
    const baseProvince = selectedProvinces[i];

    // Create starting units
    const startingUnits: Unit[] = [
      {
        id: `${countryId}_unit_0`,
        type: UnitType.Infantry,
        countryId,
        position: { ...baseProvince.position },
        health: 100,
        morale: 100,
        experience: 0,
      },
      {
        id: `${countryId}_unit_1`,
        type: UnitType.Cavalry,
        countryId,
        position: { x: baseProvince.position.x + 1, y: baseProvince.position.y },
        health: 100,
        morale: 100,
        experience: 0,
      },
    ];

    // AI countries get bonus units at higher difficulties
    if (!isPlayer && difficulty !== 'easy') {
      for (let j = 0; j < mod.unitBonus; j++) {
        startingUnits.push({
          id: `${countryId}_unit_${j + 2}`,
          type: j % 2 === 0 ? UnitType.Infantry : UnitType.Cavalry,
          countryId,
          position: {
            x: baseProvince.position.x + (j * 2),
            y: baseProvince.position.y + 1,
          },
          health: 100,
        morale: 100,
          experience: 0,
        });
      }
    }

    // Initialize province
    baseProvince.owner = countryId;
    baseProvince.type = isPlayer ? ProvinceType.Capital : ProvinceType.Village;
    baseProvince.garrisonUnits = [startingUnits[0]];
    baseProvince.workers = 30;
    baseProvince.infrastructure = {
      hasRailroad: isPlayer, // Player starts with a railroad
      hasPort: false,
      hasDepot: isPlayer,
      industrialized: false,
      fortLevel: 0,
    };
    baseProvince.developmentLevel = 0;
    baseProvince.production = {
      raw: getEmptyResources(),
      processed: getEmptyResources(),
    };

    const country: Country = {
      id: countryId,
      name: COUNTRY_NAMES[i],
      type: isPlayer ? CountryType.Player : CountryType.AI,
      treasury: isPlayer ? mod.treasury * 1.5 : mod.treasury,
      provinces: [baseProvince],
      units: startingUnits,
      navalUnits: [],
      workers: mod.workers,
      technology: new Map<string, number>([
        ['agriculture', 1],
        ['military', 1],
        ['trade', 1],
      ]),
      researchedTechnologies: new Set<string>(),
      diplomacy: new Map<string, any>(),
      merchantMarine: mod.merchant,
      freightCars: mod.freight,
      tradeAgreements: new Map<string, boolean>(),
      consulates: new Set<string>(),
    };

    countries.push(country);
  }

  // Initialize diplomatic relations
  for (let i = 0; i < countries.length; i++) {
    for (let j = 0; j < countries.length; j++) {
      if (i !== j) {
        countries[i].diplomacy.set(countries[j].id, {
          countryId: countries[j].id,
          trust: 50,
          tradeAgreement: false,
          warState: false,
        });
      }
    }
  }

  return countries;
}

function selectRandomProvinces(
  provinces: Province[],
  count: number
): Province[] {
  const selected: Province[] = [];
  const indices = new Set<number>();

  while (selected.length < Math.min(count, provinces.length)) {
    const idx = Math.floor(Math.random() * provinces.length);
    if (!indices.has(idx)) {
      indices.add(idx);
      selected.push(provinces[idx]);
    }
  }

  return selected;
}

function getEmptyResources(): Resources {
  return {
    // Raw materials
    coal: 0, iron: 0, trees: 0, sheep: 0, cotton: 0, wheat: 0, fish: 0,
    oil: 0, gold: 0, gems: 0, livestock: 0, wool: 0, fruit: 0, timber: 0, horses: 0, grain: 0,
    // Semi-finished goods
    cloth: 0, lumber: 0, steel: 0, paper: 0, fabric: 0, fuel: 0,
    // Finished goods
    shirts: 0, chairs: 0, hammers: 0, canned_food: 0, clothing: 0, furniture: 0, hardware: 0, power: 0,
  };
}
