export interface Technology {
  id: string;
  name: string;
  description: string;
  cost: number; // Gold cost to research
  era: number; // 1-4 (Industrial era progression)
  prerequisites: string[]; // Technology IDs required first
  effects: {
    unitAttackBonus?: number;
    unitDefenseBonus?: number;
    productionBonus?: number;
    tradeBonus?: number;
  };
}

const TECHNOLOGIES: Record<string, Technology> = {
  // Era 1 - Initial (1815)
  'musketry': {
    id: 'musketry',
    name: 'Advanced Musketry',
    description: 'Improve infantry combat effectiveness',
    cost: 2000,
    era: 1,
    prerequisites: [],
    effects: { unitAttackBonus: 1 },
  },
  'horsemanship': {
    id: 'horsemanship',
    name: 'Horsemanship',
    description: 'Cavalry mobility and training',
    cost: 2000,
    era: 1,
    prerequisites: [],
    effects: { unitAttackBonus: 1 },
  },
  'cannon_casting': {
    id: 'cannon_casting',
    name: 'Cannon Casting',
    description: 'Develop artillery units',
    cost: 3000,
    era: 1,
    prerequisites: [],
    effects: { unitAttackBonus: 2 },
  },
  'naval_tactics': {
    id: 'naval_tactics',
    name: 'Naval Tactics',
    description: 'Improve naval combat',
    cost: 2500,
    era: 1,
    prerequisites: [],
    effects: { unitAttackBonus: 1 },
  },

  // Era 2 - Industrial (1850)
  'rifling': {
    id: 'rifling',
    name: 'Rifled Infantry',
    description: 'Rifled muskets increase accuracy',
    cost: 3000,
    era: 2,
    prerequisites: ['musketry'],
    effects: { unitAttackBonus: 2, unitDefenseBonus: 1 },
  },
  'steel_production': {
    id: 'steel_production',
    name: 'Steel Production',
    description: 'Increased steel manufacturing',
    cost: 4000,
    era: 2,
    prerequisites: [],
    effects: { productionBonus: 0.2 },
  },
  'railway': {
    id: 'railway',
    name: 'Railway Technology',
    description: 'Build and operate railways for resource transport',
    cost: 5000,
    era: 2,
    prerequisites: ['steel_production'],
    effects: { tradeBonus: 0.3 },
  },
  'steam_power': {
    id: 'steam_power',
    name: 'Steam Power',
    description: 'Industrial steam engines for factories',
    cost: 4000,
    era: 2,
    prerequisites: [],
    effects: { productionBonus: 0.15 },
  },
  'ironclad_navy': {
    id: 'ironclad_navy',
    name: 'Ironclad Navy',
    description: 'Iron-hulled warships',
    cost: 5000,
    era: 2,
    prerequisites: ['naval_tactics', 'steel_production'],
    effects: { unitAttackBonus: 2, unitDefenseBonus: 3 },
  },

  // Era 3 - Late Industrial (1880)
  'breech_loading': {
    id: 'breech_loading',
    name: 'Breech-Loading Artillery',
    description: 'Faster-firing artillery pieces',
    cost: 4000,
    era: 3,
    prerequisites: ['cannon_casting', 'rifling'],
    effects: { unitAttackBonus: 3 },
  },
  'machine_guns': {
    id: 'machine_guns',
    name: 'Machine Guns',
    description: 'Rapid-fire small arms',
    cost: 4500,
    era: 3,
    prerequisites: ['rifling'],
    effects: { unitDefenseBonus: 3 },
  },
  'mass_production': {
    id: 'mass_production',
    name: 'Mass Production',
    description: 'Factory assembly line manufacturing',
    cost: 5000,
    era: 3,
    prerequisites: ['steam_power'],
    effects: { productionBonus: 0.25 },
  },
  'dreadnought': {
    id: 'dreadnought',
    name: 'Dreadnought Battleships',
    description: 'Advanced battleship design',
    cost: 6000,
    era: 3,
    prerequisites: ['ironclad_navy'],
    effects: { unitAttackBonus: 4, unitDefenseBonus: 4 },
  },

  // Era 4 - Modern (1900+)
  'smokeless_powder': {
    id: 'smokeless_powder',
    name: 'Smokeless Powder',
    description: 'Modern ammunition for all units',
    cost: 5000,
    era: 4,
    prerequisites: ['breech_loading', 'machine_guns'],
    effects: { unitAttackBonus: 4, unitDefenseBonus: 2 },
  },
  'logistics': {
    id: 'logistics',
    name: 'Supply Logistics',
    description: 'Improved military supply chains',
    cost: 4000,
    era: 4,
    prerequisites: ['railway'],
    effects: { tradeBonus: 0.5 },
  },
};

export class TechnologyEngine {
  /* Check if technology can be researched */
  static canResearch(
    technologyId: string,
    researchedTechs: Set<string>,
    treasury: number
  ): { canResearch: boolean; reason?: string } {
    const tech = TECHNOLOGIES[technologyId];
    if (!tech) {
      return { canResearch: false, reason: 'Technology not found' };
    }

    if (researchedTechs.has(technologyId)) {
      return { canResearch: false, reason: 'Already researched' };
    }

    if (treasury < tech.cost) {
      return { canResearch: false, reason: `Insufficient funds (need ${tech.cost})` };
    }

    for (const prereq of tech.prerequisites) {
      if (!researchedTechs.has(prereq)) {
        return { canResearch: false, reason: `Missing prerequisite: ${TECHNOLOGIES[prereq]?.name}` };
      }
    }

    return { canResearch: true };
  }

  /* Get technology details */
  static getTechnology(id: string): Technology | null {
    return TECHNOLOGIES[id] || null;
  }

  /* Get all technologies in an era */
  static getTechnologiesByEra(era: number): Technology[] {
    return Object.values(TECHNOLOGIES).filter(t => t.era === era);
  }

  /* Get available technologies (can be researched now) */
  static getAvailableTechnologies(researchedTechs: Set<string>): Technology[] {
    return Object.values(TECHNOLOGIES)
      .filter(t => !researchedTechs.has(t.id))
      .filter(t => t.prerequisites.every(p => researchedTechs.has(p)));
  }

  /* Get technology effect multiplier */
  static getEffectMultiplier(
    effect: keyof Technology['effects'],
    researchedTechs: Set<string>
  ): number {
    let multiplier = 1.0;

    Object.keys(TECHNOLOGIES).forEach(techId => {
      if (researchedTechs.has(techId)) {
        const tech = TECHNOLOGIES[techId];
        if (tech.effects[effect]) {
          multiplier += tech.effects[effect]!;
        }
      }
    });

    return multiplier;
  }

  /* Get all prerequisites for a technology (recursive) */
  static getAllPrerequisites(technologyId: string, resolved = new Set<string>()): Set<string> {
    const tech = TECHNOLOGIES[technologyId];
    if (!tech) return resolved;

    for (const prereq of tech.prerequisites) {
      if (!resolved.has(prereq)) {
        resolved.add(prereq);
        this.getAllPrerequisites(prereq, resolved);
      }
    }

    return resolved;
  }
}

export { TECHNOLOGIES };
