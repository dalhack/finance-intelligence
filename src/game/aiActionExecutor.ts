import { GameState, Country } from '../types/index';
import { AIDecision } from './aiEngine';
import { ActionEngine } from './actionEngine';
import { DiplomacyEngine } from './diplomacyEngine';
import { INFRASTRUCTURE_COSTS } from './infrastructureEngine';

export class AIActionExecutor {
  static executeDecisions(
    gameState: GameState,
    aiDecisions: Map<string, AIDecision[]>
  ): { success: number; failed: number; messages: string[] } {
    const messages: string[] = [];
    let success = 0;
    let failed = 0;

    aiDecisions.forEach((decisions, countryId) => {
      const country = gameState.countries.find(c => c.id === countryId);
      if (!country) {
        failed++;
        return;
      }

      decisions.forEach(decision => {
        const result = this.executeDecision(gameState, country, decision);
        if (result.success) {
          success++;
          messages.push(`${country.name}: ${result.message}`);
        } else {
          failed++;
        }
      });
    });

    return { success, failed, messages };
  }

  private static executeDecision(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): { success: boolean; message: string } {
    switch (decision.type) {
      case 'research':
        return this.executeResearch(gameState, country, decision);
      case 'military':
        return this.executeMilitary(gameState, country, decision);
      case 'diplomacy':
        return this.executeDiplomacy(gameState, country, decision);
      case 'infrastructure':
        return this.executeInfrastructure(gameState, country, decision);
      case 'economic':
        return this.executeEconomic(gameState, country, decision);
      default:
        return { success: false, message: 'Unknown decision type' };
    }
  }

  private static executeResearch(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): { success: boolean; message: string } {
    if (decision.action === 'research_technology' && decision.target) {
      const result = ActionEngine.researchTechnology(gameState, country.id, decision.target);
      return {
        success: result.success,
        message: result.success ? `Starting research: ${decision.target}` : result.message,
      };
    }
    return { success: false, message: 'Invalid research decision' };
  }

  private static executeMilitary(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): { success: boolean; message: string } {
    switch (decision.action) {
      case 'recruit_units':
        if (country.treasury > 1000) {
          const province = country.provinces[0];
          if (province) {
            const result = ActionEngine.recruitUnit(gameState, country.id, province.id, 'infantry');
            return {
              success: result.success,
              message: result.success ? 'Unit recruited' : result.message,
            };
          }
        }
        return { success: false, message: 'Insufficient funds' };

      case 'declare_war':
        if (decision.target) {
          const targetCountry = gameState.countries.find(c => c.id === decision.target);
          if (targetCountry) {
            DiplomacyEngine.declareWar(country, targetCountry);
            return { success: true, message: `War declared on ${targetCountry.name}` };
          }
        }
        return { success: false, message: 'Target not found' };

      case 'fortify_defenses':
        return { success: true, message: 'Fortifying defenses' };

      default:
        return { success: false, message: 'Unknown military action' };
    }
  }

  private static executeDiplomacy(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): { success: boolean; message: string } {
    if (!decision.target) {
      return { success: false, message: 'No target specified' };
    }

    const targetCountry = gameState.countries.find(c => c.id === decision.target);
    if (!targetCountry) {
      return { success: false, message: 'Target country not found' };
    }

    switch (decision.action) {
      case 'propose_alliance':
        const canAlliance = DiplomacyEngine.formAlliance(country, targetCountry);
        return {
          success: canAlliance,
          message: canAlliance ? `Alliance formed with ${targetCountry.name}` : 'Cannot form alliance',
        };

      case 'propose_trade':
        if (country.treasury >= 500) {
          const rel = country.diplomacy.get(targetCountry.id);
          if (rel) {
            rel.tradeAgreement = true;
            return { success: true, message: `Trade agreement with ${targetCountry.name}` };
          }
        }
        return { success: false, message: 'Cannot establish trade' };

      case 'gift_money':
        const amount = Math.min(1000, country.treasury / 10);
        if (amount > 0) {
          DiplomacyEngine.giveSubsidy(country, targetCountry, amount);
          return { success: true, message: `Sent $${amount} to ${targetCountry.name}` };
        }
        return { success: false, message: 'Insufficient funds' };

      case 'improve_relations':
        if (country.treasury > 500) {
          const rel = country.diplomacy.get(targetCountry.id);
          if (rel) {
            rel.trust = Math.min(100, rel.trust + 5);
            country.treasury -= 500;
            return { success: true, message: `Relations improved with ${targetCountry.name}` };
          }
        }
        return { success: false, message: 'Cannot improve relations' };

      default:
        return { success: false, message: 'Unknown diplomacy action' };
    }
  }

  private static executeInfrastructure(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): { success: boolean; message: string } {
    if (!decision.target) {
      return { success: false, message: 'No target province' };
    }

    const targetProvince = country.provinces.find(p => p.id === decision.target);
    if (!targetProvince) {
      return { success: false, message: 'Target province not found' };
    }

    switch (decision.action) {
      case 'build_railroad':
        if (country.treasury >= INFRASTRUCTURE_COSTS.railroad) {
          const result = ActionEngine.buildInfrastructure(
            gameState,
            country.id,
            targetProvince.id,
            'railroad'
          );
          return {
            success: result.success,
            message: result.success ? 'Railroad built' : result.message,
          };
        }
        return { success: false, message: 'Insufficient funds' };

      case 'industrialize':
        if (country.treasury >= INFRASTRUCTURE_COSTS.industrialize) {
          const result = ActionEngine.buildInfrastructure(
            gameState,
            country.id,
            targetProvince.id,
            'industrialize'
          );
          return {
            success: result.success,
            message: result.success ? 'Industrialized' : result.message,
          };
        }
        return { success: false, message: 'Insufficient funds' };

      default:
        return { success: false, message: 'Unknown infrastructure action' };
    }
  }

  private static executeEconomic(
    gameState: GameState,
    country: Country,
    decision: AIDecision
  ): { success: boolean; message: string } {
    switch (decision.action) {
      case 'invest_in_growth':
        if (country.treasury > 5000) {
          country.workers = Math.min(country.workers + 10, 500);
          country.treasury -= 5000;
          return { success: true, message: 'Invested in growth' };
        }
        return { success: false, message: 'Insufficient funds' };

      default:
        return { success: false, message: 'Unknown economic action' };
    }
  }
}
