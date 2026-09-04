import { Country, CountryType } from '../types/index';

export interface MinorNation extends Country {
  ruler: string;
  preferredAlly: string | null;
}

const MINOR_NATIONS: Omit<MinorNation, 'id' | 'type' | 'provinces' | 'units' | 'diplomacy'>[] = [
  { name: 'Belgium', ruler: 'Leopold I', treasury: 5000, workers: 40, technology: new Map(), preferredAlly: null, merchantMarine: 1, freightCars: 2, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Greece', ruler: 'Otto of Bavaria', treasury: 4000, workers: 35, technology: new Map(), preferredAlly: null, merchantMarine: 2, freightCars: 1, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Portugal', ruler: 'King Miguel', treasury: 6000, workers: 45, technology: new Map(), preferredAlly: null, merchantMarine: 3, freightCars: 2, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Serbia', ruler: 'Milos Obrenovic', treasury: 3000, workers: 30, technology: new Map(), preferredAlly: null, merchantMarine: 0, freightCars: 1, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Romania', ruler: 'Alexandru Ghica', treasury: 3500, workers: 35, technology: new Map(), preferredAlly: null, merchantMarine: 0, freightCars: 2, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Bulgaria', ruler: 'Aleksandr Batenberg', treasury: 2500, workers: 25, technology: new Map(), preferredAlly: null, merchantMarine: 0, freightCars: 1, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Mexico', ruler: 'Benito Juarez', treasury: 7500, workers: 50, technology: new Map(), preferredAlly: null, merchantMarine: 2, freightCars: 3, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Brazil', ruler: 'Pedro II', treasury: 10000, workers: 60, technology: new Map(), preferredAlly: null, merchantMarine: 3, freightCars: 4, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Argentina', ruler: 'Sarmiento', treasury: 9000, workers: 55, technology: new Map(), preferredAlly: null, merchantMarine: 2, freightCars: 3, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Egypt', ruler: 'Ismail Pasha', treasury: 12500, workers: 70, technology: new Map(), preferredAlly: null, merchantMarine: 2, freightCars: 5, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Siam', ruler: 'Chulalongkorn', treasury: 8000, workers: 45, technology: new Map(), preferredAlly: null, merchantMarine: 1, freightCars: 2, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Japan', ruler: 'Meiji Emperor', treasury: 15000, workers: 80, technology: new Map(), preferredAlly: null, merchantMarine: 3, freightCars: 6, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'China', ruler: 'Empress Cixi', treasury: 25000, workers: 150, technology: new Map(), preferredAlly: null, merchantMarine: 5, freightCars: 10, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Persia', ruler: 'Nasir al-Din Shah', treasury: 7000, workers: 40, technology: new Map(), preferredAlly: null, merchantMarine: 1, freightCars: 2, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Afghanistan', ruler: 'Abdur Rahman Khan', treasury: 4500, workers: 30, technology: new Map(), preferredAlly: null, merchantMarine: 0, freightCars: 1, tradeAgreements: new Map(), consulates: new Set() },
  { name: 'Morocco', ruler: 'Hassan I', treasury: 5500, workers: 35, technology: new Map(), preferredAlly: null, merchantMarine: 1, freightCars: 2, tradeAgreements: new Map(), consulates: new Set() },
];

export class DiplomacyEngine {
  /* Check if Minor Nation should voluntarily join player */
  static shouldMinorNationJoin(minor: MinorNation, player: Country, trust: number): boolean {
    // Minor nations join if:
    // 1. Trust > 75
    // 2. Or if player is very powerful relative to others
    // 3. And player is "kind" (good diplomatic standing)

    if (trust < 50) return false;

    if (trust > 75) {
      // Will likely join if trust is high
      const joinChance = Math.min(0.8, (trust - 75) / 25);
      return Math.random() < joinChance;
    }

    // At medium trust (50-75), only join if circumstances are right
    if (trust > 60) {
      const joinChance = (trust - 60) / 15 * 0.4; // Max 40% chance
      return Math.random() < joinChance;
    }

    return false;
  }

  /* Process turn for minor nations - autonomy decisions */
  static processMinorNationTurn(minor: MinorNation, countries: Country[]): void {
    // Minor nations try to grow economically
    minor.workers = Math.min(minor.workers + 5, 200);

    // Adjust treasury based on simple economy
    const income = Math.floor(minor.workers * 2);
    const expenses = Math.floor(minor.workers * 0.5);
    minor.treasury += income - expenses;

    // Maintain minimum treasury
    if (minor.treasury < 0) {
      minor.treasury = 0;
    }
  }

  /* Calculate relationship change due to trade */
  static updateTrustFromTrade(currentTrust: number, tradeVolume: number): number {
    // Trading increases trust
    const tradeBonus = Math.min(tradeVolume * 0.01, 5); // Max 5 trust from trade
    return Math.min(100, currentTrust + tradeBonus);
  }

  /* Calculate relationship change due to shared enemy */
  static updateTrustFromSharedEnemy(currentTrust: number, hasSharedEnemy: boolean): number {
    if (hasSharedEnemy) {
      return Math.min(100, currentTrust + 3); // Shared enemy increases trust
    }
    return currentTrust;
  }

  /* Calculate relationship decay over time */
  static decayTrust(currentTrust: number): number {
    // Trust slowly decays without active diplomacy
    const decayRate = 0.02; // 2% decay per turn
    return currentTrust * (1 - decayRate);
  }

  /* Propose treaty - return if accepted */
  static proposeTreaty(
    proposer: Country,
    recipient: Country,
    trustLevel: number,
    treatyType: 'peace' | 'alliance' | 'trade'
  ): boolean {
    // Treaty acceptance based on trust and current relations
    const baseAcceptance: Record<string, number> = {
      peace: 0.3, // 30% base
      alliance: 0.2, // 20% base
      trade: 0.6, // 60% base (most appealing)
    };

    const trustModifier = trustLevel / 100;
    const acceptanceChance = baseAcceptance[treatyType] * (0.5 + trustModifier);

    return Math.random() < acceptanceChance;
  }

  /* Get diplomatic status description */
  static getDiplomaticStatus(trust: number, atWar: boolean): string {
    if (atWar) return 'At War';
    if (trust > 80) return 'Allies';
    if (trust > 60) return 'Friends';
    if (trust > 40) return 'Neutral';
    if (trust > 20) return 'Tense';
    return 'Hostile';
  }

  /* Calculate impact of war declaration on relationships */
  static declareWar(aggressor: Country, defender: Country, countries: Country[]): void {
    // War affects all diplomatic relationships
    countries.forEach(country => {
      if (country.id !== aggressor.id && country.id !== defender.id) {
        const aggressorRel = country.diplomacy.get(aggressor.id);
        const defenderRel = country.diplomacy.get(defender.id);

        if (aggressorRel) {
          aggressorRel.trust -= 10; // Declaring war hurts reputation
          aggressorRel.trust = Math.max(0, aggressorRel.trust);
        }

        if (defenderRel) {
          defenderRel.trust += 5; // Defending gains sympathy
        }
      }
    });
  }

  /* Gift money for diplomatic gain */
  static giftMoney(giver: Country, receiver: Country, amount: number): boolean {
    if (giver.treasury < amount) return false;

    giver.treasury -= amount;
    receiver.treasury += amount;

    // Increase trust - scaling with amount
    const trustIncrease = Math.min(amount / 1000, 15); // Max 15 trust per gift
    const rel = giver.diplomacy.get(receiver.id);
    if (rel) {
      rel.trust = Math.min(100, rel.trust + trustIncrease);
    }

    return true;
  }

  /* Establish consulate - costs $500, improves trade */
  static buildConsulate(builder: Country, target: Country): boolean {
    const CONSULATE_COST = 500;
    if (builder.treasury < CONSULATE_COST) return false;

    builder.treasury -= CONSULATE_COST;
    builder.consulates.add(target.id);

    // Consulate increases trade opportunity
    const rel = builder.diplomacy.get(target.id);
    if (rel) {
      rel.trust = Math.min(100, rel.trust + 2); // Small trust gain
    }

    return true;
  }

  /* Establish embassy - costs $5000, major diplomatic benefit */
  static buildEmbassy(builder: Country, target: Country): boolean {
    const EMBASSY_COST = 5000;
    if (builder.treasury < EMBASSY_COST) return false;

    builder.treasury -= EMBASSY_COST;
    builder.consulates.add(target.id);

    // Embassy significantly improves relations
    const rel = builder.diplomacy.get(target.id);
    if (rel) {
      rel.trust = Math.min(100, rel.trust + 10); // Major trust gain
    }

    return true;
  }

  /* Get list of available minor nations */
  static getAvailableMinorNations(): typeof MINOR_NATIONS {
    return MINOR_NATIONS;
  }
}
