import { Country, Province, Unit, UnitType, GameState } from '../types/index';
import { TechnologyEngine } from './technologyEngine';
import { InfrastructureEngine, INFRASTRUCTURE_COSTS } from './infrastructureEngine';

export interface AIDecision {
  type: 'diplomacy' | 'military' | 'economic' | 'infrastructure' | 'research';
  action: string;
  target?: string;
  reason: string;
}

export interface AIAnalysis {
  threatLevel: number;
  economicStrength: number;
  diplomacyScore: number;
  militaryPower: number;
  techProgress: number;
  expansionPotential: number;
}

export class AIEngine {
  /* Main AI decision loop for a country */
  static makeDecisions(
    country: Country,
    allCountries: Country[],
    gameState: GameState
  ): AIDecision[] {
    const decisions: AIDecision[] = [];

    // Analyze current state
    const analysis = this.analyzeState(country, allCountries, gameState);

    // Determine overall strategy based on analysis
    const strategy = this.determineStrategy(country, analysis);

    // Make decisions based on strategy
    switch (strategy) {
      case 'aggressive':
        if (analysis.militaryPower > 60) {
          decisions.push(this.makeExpansionDecision(country, allCountries, analysis));
        }
        break;
      case 'defensive':
        decisions.push(this.makeDefensiveDecision(country, allCountries, analysis));
        break;
      case 'economic':
        decisions.push(this.makeDiplomaticDecision(country, allCountries, analysis));
        break;
    }

    // Always consider technology research
    const techDecision = this.makeResearchDecision(country);
    if (techDecision) decisions.push(techDecision);

    // Consider infrastructure improvements if economically strong
    if (analysis.economicStrength > 50) {
      const infraDecision = this.makeInfrastructureDecision(country);
      if (infraDecision) decisions.push(infraDecision);
    }

    // Consider military unit recruitment if strategically needed
    const militaryDecision = this.makeMilitaryDecision(country, analysis);
    if (militaryDecision) decisions.push(militaryDecision);

    return decisions;
  }

  /* Analyze current game state */
  private static analyzeState(
    country: Country,
    allCountries: Country[],
    gameState: GameState
  ): AIAnalysis {
    // Calculate threat level from enemies
    let threatLevel = 0;
    let hostileCount = 0;
    country.diplomacy.forEach((relation, otherId) => {
      if (relation.warState) {
        threatLevel += 50;
        hostileCount++;
      } else if (relation.trust < 30) {
        threatLevel += 15;
      }
    });

    // Calculate economic strength (relative to $100k target)
    const economicStrength = Math.min(100, (country.treasury / 100000) * 100);

    // Calculate diplomacy score (average trust)
    const avgTrust =
      Array.from(country.diplomacy.values()).reduce((sum, r) => sum + r.trust, 0) /
      Math.max(1, country.diplomacy.size);
    const diplomacyScore = avgTrust;

    // Calculate military power
    const unitCount = country.units.length;
    const avgHealth = unitCount > 0
      ? country.units.reduce((sum, u) => sum + u.health, 0) / unitCount
      : 100;
    const militaryPower = unitCount > 0 ? (unitCount * (avgHealth / 100)) * 10 : 0;

    // Calculate technology progress towards victory (12 techs needed)
    const techProgress = Math.min(100, (country.researchedTechnologies.size / 12) * 100);

    // Calculate expansion potential (how many provinces can be conquered)
    const totalProvinces = gameState.provinces.length;
    const ownedProvinces = country.provinces.length;
    const maxPossibleProvinces = Math.ceil(totalProvinces * 0.6);
    const expansionPotential = Math.min(100, (ownedProvinces / maxPossibleProvinces) * 100);

    return {
      threatLevel: Math.min(100, threatLevel),
      economicStrength,
      diplomacyScore,
      militaryPower,
      techProgress,
      expansionPotential,
    };
  }

  /* Determine overall AI strategy based on analysis */
  private static determineStrategy(country: Country, analysis: AIAnalysis): 'aggressive' | 'defensive' | 'economic' {
    // If under threat, go defensive
    if (analysis.threatLevel > 60) {
      return 'defensive';
    }

    // If economically strong and room to expand, go aggressive
    if (analysis.economicStrength > 70 && analysis.expansionPotential < 80) {
      return 'aggressive';
    }

    // If far from victory on any path, focus on economy
    if (analysis.economicStrength < 50 || analysis.techProgress < 30) {
      return 'economic';
    }

    // Default to balanced (defensive)
    return 'defensive';
  }

  /* Make defensive decisions when threatened */
  private static makeDefensiveDecision(
    country: Country,
    allCountries: Country[],
    analysis: any
  ): AIDecision {
    // Recruit more units
    if (country.treasury > 3000) {
      return {
        type: 'military',
        action: 'recruit_units',
        reason: 'Threat detected - building army',
      };
    }

    // Form defensive alliance
    const potentialAlly = allCountries.find(c => {
      const rel = country.diplomacy.get(c.id);
      return rel && rel.trust > 50 && !rel.warState;
    });

    if (potentialAlly) {
      return {
        type: 'diplomacy',
        action: 'propose_alliance',
        target: potentialAlly.id,
        reason: 'Seeking ally against threats',
      };
    }

    return {
      type: 'military',
      action: 'fortify_defenses',
      reason: 'Preparing defenses',
    };
  }

  /* Make expansion decisions when economically strong */
  private static makeExpansionDecision(
    country: Country,
    allCountries: Country[],
    analysis: any
  ): AIDecision {
    // Look for economically weak neighbors to attack
    const weakNeighbor = allCountries.find(c => {
      const rel = country.diplomacy.get(c.id);
      if (!rel || rel.warState) return false;
      return c.treasury < 20000 && c.units.length < 5;
    });

    if (weakNeighbor && country.units.length > 5) {
      return {
        type: 'military',
        action: 'declare_war',
        target: weakNeighbor.id,
        reason: 'Expansion opportunity',
      };
    }

    // Recruit more units for future expansion
    if (country.treasury > 4000) {
      return {
        type: 'military',
        action: 'recruit_units',
        reason: 'Preparing for expansion',
      };
    }

    return {
      type: 'economic',
      action: 'invest_in_growth',
      reason: 'Strengthening economy for expansion',
    };
  }

  /* Make diplomatic decisions */
  private static makeDiplomaticDecision(
    country: Country,
    allCountries: Country[],
    analysis: any
  ): AIDecision {
    // Propose trade agreement with friend
    const friend = allCountries.find(c => {
      const rel = country.diplomacy.get(c.id);
      return rel && rel.trust > 60 && !rel.tradeAgreement;
    });

    if (friend) {
      return {
        type: 'diplomacy',
        action: 'propose_trade',
        target: friend.id,
        reason: 'Expanding trade relations',
      };
    }

    // Send gift to improve relations with neutral power
    const neutral = allCountries.find(c => {
      const rel = country.diplomacy.get(c.id);
      return rel && rel.trust > 40 && rel.trust < 60;
    });

    if (neutral && country.treasury > 2000) {
      return {
        type: 'diplomacy',
        action: 'gift_money',
        target: neutral.id,
        reason: 'Improving relations',
      };
    }

    return {
      type: 'diplomacy',
      action: 'improve_relations',
      reason: 'Strengthening diplomatic position',
    };
  }

  /* Make research decisions */
  private static makeResearchDecision(country: Country): AIDecision | null {
    // Check if already researching something
    if (country.technology.size > 0) {
      return null; // Continue current research
    }

    // Get available technologies (not yet researched, prerequisites met)
    const availableTechs = TechnologyEngine.getAvailableTechnologies(country.researchedTechnologies);

    if (availableTechs.length === 0) return null;

    // Prioritize based on victory requirements
    // First, get the 12 victory technologies
    const victoryTechs = availableTechs.filter(t =>
      TechnologyEngine.VICTORY_TECHNOLOGIES.includes(t.id)
    );

    // Sort by era (lower era first for progression)
    const sortedTechs = (victoryTechs.length > 0 ? victoryTechs : availableTechs)
      .sort((a, b) => a.era - b.era);

    const techToResearch = sortedTechs[0];

    return {
      type: 'research',
      action: 'research_technology',
      target: techToResearch.id,
      reason: `Researching ${techToResearch.name}`,
    };
  }

  /* Make infrastructure decisions */
  private static makeInfrastructureDecision(country: Country): AIDecision | null {
    // Find province with most production potential
    let bestProvince: Province | undefined;
    let maxPotential = 0;

    country.provinces.forEach(province => {
      const potential = province.population + Object.values(province.resources).reduce((a, b) => a + b, 0);
      if (potential > maxPotential) {
        maxPotential = potential;
        bestProvince = province;
      }
    });

    if (!bestProvince) return null;

    // Build railroad first for production bonus
    if (!bestProvince.infrastructure.hasRailroad && country.treasury > INFRASTRUCTURE_COSTS.railroad) {
      return {
        type: 'infrastructure',
        action: 'build_railroad',
        target: bestProvince.id,
        reason: 'Improving production capacity',
      };
    }

    // Then industrialize for better output
    if (!bestProvince.infrastructure.industrialized && country.treasury > INFRASTRUCTURE_COSTS.industrialize) {
      return {
        type: 'infrastructure',
        action: 'industrialize',
        target: bestProvince.id,
        reason: 'Modernizing economy',
      };
    }

    return null;
  }

  /* Make military recruitment decisions */
  private static makeMilitaryDecision(country: Country, analysis: any): AIDecision | null {
    // Recruit units if economically strong and military weak
    if (analysis.economicStrength > 70 && analysis.militaryPower < 50) {
      const unitTypes = [UnitType.Infantry, UnitType.Cavalry, UnitType.Artillery];
      const unitType = unitTypes[Math.floor(Math.random() * unitTypes.length)];

      return {
        type: 'military',
        action: 'recruit_unit',
        target: unitType,
        reason: 'Building military strength',
      };
    }

    return null;
  }

  /* Calculate army strategy */
  static calculateArmyStrategy(
    country: Country,
    enemies: Country[]
  ): {
    defensiveStrength: number;
    offensiveStrength: number;
    recommendedStrategy: 'defensive' | 'balanced' | 'offensive';
  } {
    const defensiveStrength = country.units.filter(u => u.type === UnitType.Infantry).length * 10;
    const offensiveStrength = country.units.filter(u => u.type === UnitType.Cavalry).length * 12;

    let recommendedStrategy: 'defensive' | 'balanced' | 'offensive' = 'balanced';

    if (defensiveStrength > offensiveStrength * 1.5) {
      recommendedStrategy = 'defensive';
    } else if (offensiveStrength > defensiveStrength * 1.5) {
      recommendedStrategy = 'offensive';
    }

    return {
      defensiveStrength,
      offensiveStrength,
      recommendedStrategy,
    };
  }
}
