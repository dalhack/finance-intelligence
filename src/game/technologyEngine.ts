/**
 * Technology Engine - 1992 Imperialism Exact Mechanics
 * 12 Key technologies required for victory, exact research times from game reference
 */

export interface Technology {
  id: string;
  name: string;
  description: string;
  researchTime: number; // Turns to research (from EXACT_IMPLEMENTATION_PLAN.md)
  era: number; // 1-3 (game progression)
  level: number; // 1-3 (research level)
  prerequisites: string[]; // Technology IDs required first
  unlocksUnits?: string[]; // Unit types unlocked by this tech
  unlocksBuildings?: string[]; // Building types unlocked by this tech
  effects: {
    combatBonus?: number; // Combat effectiveness bonus (+%)
    productionBonus?: number; // Production bonus (+%)
    movementBonus?: number; // Movement bonus (+)
    tradeBonus?: number; // Trade bonus (+%)
  };
}

/**
 * 12 Key Technologies for Victory Condition (from EXACT_IMPLEMENTATION_PLAN.md)
 */
const TECHNOLOGIES: Record<string, Technology> = {
  // LEVEL 1 - Starting technologies
  'musketry': {
    id: 'musketry',
    name: 'Musketry',
    description: 'Infantry +10%',
    researchTime: 2,
    era: 1,
    level: 1,
    prerequisites: [],
    effects: { combatBonus: 10 },
  },
  'horsemanship': {
    id: 'horsemanship',
    name: 'Horsemanship',
    description: 'Cavalry +8%, Movement +1',
    researchTime: 2,
    era: 1,
    level: 1,
    prerequisites: [],
    effects: { combatBonus: 8, movementBonus: 1 },
  },
  'artillery_tactics': {
    id: 'artillery_tactics',
    name: 'Artillery Tactics',
    description: 'Artillery +15%',
    researchTime: 3,
    era: 1,
    level: 1,
    prerequisites: [],
    effects: { combatBonus: 15 },
  },
  'navigation': {
    id: 'navigation',
    name: 'Navigation',
    description: 'Naval trade routes enabled',
    researchTime: 3,
    era: 1,
    level: 1,
    prerequisites: [],
    effects: { tradeBonus: 20 },
  },
  'ironclads': {
    id: 'ironclads',
    name: 'Ironclads',
    description: 'Naval units unlocked',
    researchTime: 4,
    era: 1,
    level: 1,
    prerequisites: ['navigation'],
    unlocksUnits: ['ironclad', 'armored_cruiser'],
    effects: {},
  },

  // LEVEL 2 - Industrial era
  'industrialization': {
    id: 'industrialization',
    name: 'Industrialization',
    description: 'Production +25%',
    researchTime: 5,
    era: 2,
    level: 2,
    prerequisites: [],
    effects: { productionBonus: 25 },
  },
  'railroads': {
    id: 'railroads',
    name: 'Railroads',
    description: 'Movement +2, Infrastructure',
    researchTime: 4,
    era: 2,
    level: 2,
    prerequisites: [],
    unlocksBuildings: ['railroad', 'rail_depot'],
    effects: { movementBonus: 2 },
  },
  'steam_power': {
    id: 'steam_power',
    name: 'Steam Power',
    description: 'Naval +?, Production +15%',
    researchTime: 5,
    era: 2,
    level: 2,
    prerequisites: ['railroads'],
    effects: { productionBonus: 15, combatBonus: 5 },
  },
  'rifle_infantry': {
    id: 'rifle_infantry',
    name: 'Rifle Infantry',
    description: 'Infantry combat +12%',
    researchTime: 3,
    era: 2,
    level: 2,
    prerequisites: ['musketry'],
    unlocksUnits: ['rifle_infantry'],
    effects: { combatBonus: 12 },
  },

  // LEVEL 3 - Modern era
  'mechanization': {
    id: 'mechanization',
    name: 'Mechanization',
    description: 'Combat +25%, Movement +2',
    researchTime: 6,
    era: 3,
    level: 3,
    prerequisites: ['steam_power'],
    unlocksUnits: ['armor', 'mechanized'],
    effects: { combatBonus: 25, movementBonus: 2 },
  },
  'advanced_naval': {
    id: 'advanced_naval',
    name: 'Advanced Naval',
    description: 'Dreadnought unlocked',
    researchTime: 4,
    era: 3,
    level: 3,
    prerequisites: ['steam_power'],
    unlocksUnits: ['dreadnought'],
    effects: { combatBonus: 20 },
  },
  'industrial_dev': {
    id: 'industrial_dev',
    name: 'Industrial Development',
    description: 'Factory bonus +50%',
    researchTime: 5,
    era: 3,
    level: 3,
    prerequisites: ['industrialization'],
    unlocksBuildings: ['factory'],
    effects: { productionBonus: 50 },
  },
};

export class TechnologyEngine {
  /**
   * 12 key technologies required for technology victory (from EXACT_IMPLEMENTATION_PLAN.md)
   */
  static readonly VICTORY_TECHNOLOGIES = [
    'musketry',
    'horsemanship',
    'artillery_tactics',
    'navigation',
    'ironclads',
    'industrialization',
    'railroads',
    'steam_power',
    'mechanization',
    'advanced_naval',
    'industrial_dev',
    'rifle_infantry',
  ];

  /**
   * Start researching a technology (turn-based system)
   */
  static startResearch(
    countryTechnology: Map<string, number>,
    technologyId: string,
    researchedTechs: Set<string>,
    prereqOnly: boolean = false
  ): { success: boolean; message: string } {
    const tech = TECHNOLOGIES[technologyId];
    if (!tech) {
      return { success: false, message: 'Technology not found' };
    }

    if (researchedTechs.has(technologyId)) {
      return { success: false, message: 'Already researched' };
    }

    // Check prerequisites
    for (const prereq of tech.prerequisites) {
      if (!researchedTechs.has(prereq)) {
        return { success: false, message: `Missing prerequisite: ${TECHNOLOGIES[prereq]?.name}` };
      }
    }

    // Start research with 0 progress
    countryTechnology.set(technologyId, 0);
    return { success: true, message: `Started researching ${tech.name}` };
  }

  /**
   * Advance research progress for all technologies
   * Called once per turn, increments progress by 1
   */
  static advanceResearch(
    countryTechnology: Map<string, number>,
    researchedTechs: Set<string>
  ): string[] {
    const completedTechs: string[] = [];

    countryTechnology.forEach((progress, techId) => {
      const tech = TECHNOLOGIES[techId];
      if (!tech) return;

      // Already completed
      if (researchedTechs.has(techId)) {
        return;
      }

      // Increment progress
      const newProgress = progress + 1;

      // Check if completed
      if (newProgress >= tech.researchTime) {
        countryTechnology.delete(techId);
        researchedTechs.add(techId);
        completedTechs.push(techId);
      } else {
        countryTechnology.set(techId, newProgress);
      }
    });

    return completedTechs;
  }

  /**
   * Get current research progress (0 to researchTime)
   */
  static getResearchProgress(technologyId: string, countryTechnology: Map<string, number>): number {
    return countryTechnology.get(technologyId) || 0;
  }

  /**
   * Get technology details
   */
  static getTechnology(id: string): Technology | null {
    return TECHNOLOGIES[id] || null;
  }

  /**
   * Get technologies by era (for UI display)
   */
  static getTechnologiesByEra(era: number): Technology[] {
    return Object.values(TECHNOLOGIES).filter(t => t.era === era);
  }

  /**
   * Get technologies available to research now (prerequisites met)
   */
  static getAvailableTechnologies(researchedTechs: Set<string>): Technology[] {
    return Object.values(TECHNOLOGIES)
      .filter(t => !researchedTechs.has(t.id))
      .filter(t => t.prerequisites.every(p => researchedTechs.has(p)));
  }

  /**
   * Get total combat bonus from all researched technologies
   */
  static getCombatBonus(researchedTechs: Set<string>): number {
    let bonus = 0;

    researchedTechs.forEach(techId => {
      const tech = TECHNOLOGIES[techId];
      if (tech?.effects.combatBonus) {
        bonus += tech.effects.combatBonus;
      }
    });

    return bonus;
  }

  /**
   * Get total production bonus from all researched technologies
   */
  static getProductionBonus(researchedTechs: Set<string>): number {
    let bonus = 100; // Base 100%

    researchedTechs.forEach(techId => {
      const tech = TECHNOLOGIES[techId];
      if (tech?.effects.productionBonus) {
        bonus += tech.effects.productionBonus;
      }
    });

    return bonus / 100; // Return as multiplier (1.0 = 100%)
  }

  /**
   * Get total movement bonus from all researched technologies
   */
  static getMovementBonus(researchedTechs: Set<string>): number {
    let bonus = 0;

    researchedTechs.forEach(techId => {
      const tech = TECHNOLOGIES[techId];
      if (tech?.effects.movementBonus) {
        bonus += tech.effects.movementBonus;
      }
    });

    return bonus;
  }

  /**
   * Get total trade bonus from all researched technologies
   */
  static getTradeBonus(researchedTechs: Set<string>): number {
    let bonus = 100; // Base 100%

    researchedTechs.forEach(techId => {
      const tech = TECHNOLOGIES[techId];
      if (tech?.effects.tradeBonus) {
        bonus += tech.effects.tradeBonus;
      }
    });

    return bonus / 100; // Return as multiplier (1.0 = 100%)
  }

  /**
   * Get units unlocked by researched technologies
   */
  static getUnlockedUnits(researchedTechs: Set<string>): string[] {
    const units = new Set<string>();

    researchedTechs.forEach(techId => {
      const tech = TECHNOLOGIES[techId];
      if (tech?.unlocksUnits) {
        tech.unlocksUnits.forEach(unit => units.add(unit));
      }
    });

    return Array.from(units);
  }

  /**
   * Get buildings unlocked by researched technologies
   */
  static getUnlockedBuildings(researchedTechs: Set<string>): string[] {
    const buildings = new Set<string>();

    researchedTechs.forEach(techId => {
      const tech = TECHNOLOGIES[techId];
      if (tech?.unlocksBuildings) {
        tech.unlocksBuildings.forEach(building => buildings.add(building));
      }
    });

    return Array.from(buildings);
  }

  /**
   * Check if technology can be researched (for UI validation)
   * Returns true if prerequisites are met and not already researched
   */
  static canResearch(
    technologyId: string,
    researchedTechs: Set<string>,
    currentlyResearching?: string
  ): { canResearch: boolean; reason?: string } {
    const tech = TECHNOLOGIES[technologyId];
    if (!tech) {
      return { canResearch: false, reason: 'Technology not found' };
    }

    if (researchedTechs.has(technologyId)) {
      return { canResearch: false, reason: 'Already researched' };
    }

    // Check if already researching something else
    if (currentlyResearching && currentlyResearching !== technologyId) {
      return { canResearch: false, reason: 'Already researching another technology' };
    }

    // Check prerequisites
    for (const prereq of tech.prerequisites) {
      if (!researchedTechs.has(prereq)) {
        return { canResearch: false, reason: `Missing prerequisite: ${TECHNOLOGIES[prereq]?.name}` };
      }
    }

    return { canResearch: true };
  }
}

export { TECHNOLOGIES };
