import { Country, Province, Unit, UnitType, CountryType } from '@types/index';

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
    easy: { treasury: 5000, unitBonus: 0 },
    normal: { treasury: 3000, unitBonus: 2 },
    hard: { treasury: 2000, unitBonus: 4 },
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
        experience: 0,
      },
      {
        id: `${countryId}_unit_1`,
        type: UnitType.Cavalry,
        countryId,
        position: { x: baseProvince.position.x + 1, y: baseProvince.position.y },
        health: 100,
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
          experience: 0,
        });
      }
    }

    baseProvince.owner = countryId;
    baseProvince.garrisonUnits = [startingUnits[0]];

    const country: Country = {
      id: countryId,
      name: COUNTRY_NAMES[i],
      type: isPlayer ? CountryType.Player : CountryType.AI,
      treasury: isPlayer ? mod.treasury * 1.5 : mod.treasury,
      provinces: [baseProvince],
      units: startingUnits,
      technology: new Map<string, number>([
        ['agriculture', 1],
        ['military', 1],
        ['trade', 1],
      ]),
      diplomacy: new Map<string, any>(),
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
