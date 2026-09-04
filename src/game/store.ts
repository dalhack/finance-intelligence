import { create } from 'zustand';
import { GameState, Country, Province, Unit, UnitType } from '../types/index';
import { generateMap } from './mapGenerator';
import { initializeCountries } from './countryInitializer';
import { EconomyEngine } from './economyEngine';
import { DiplomacyEngine } from './diplomacyEngine';
import { TurnEngine, TurnReport } from './turnEngine';
import { AIEngine, AIDecision } from './aiEngine';

interface GameStore {
  gameState: GameState | null;
  isLoading: boolean;
  error: string | null;
  lastTurnReport: TurnReport | null;
  lastAIDecisions: Map<string, AIDecision[]> | null;

  // Game initialization
  startNewGame: (config: { numCountries: number; difficulty: 'easy' | 'normal' | 'hard' }) => void;
  loadGame: (saveData: GameState) => void;

  // Game state updates
  nextTurn: () => void;
  setGamePhase: (phase: GameState['gamePhase']) => void;
  selectUnit: (unit: Unit | null) => void;
  selectProvince: (province: Province | null) => void;

  // Unit operations
  moveUnit: (unitId: string, toX: number, toY: number) => boolean;
  createUnit: (type: UnitType, countryId: string, x: number, y: number) => void;

  // Country operations
  updateCountryTreasury: (countryId: string, amount: number) => void;

  // Helpers
  getCurrentPlayer: () => Country | null;
  getProvinceAt: (x: number, y: number) => Province | null;
}

export const useGameStore = create<GameStore>((set, get) => ({
  gameState: null,
  isLoading: false,
  error: null,
  lastTurnReport: null,
  lastAIDecisions: null,

  startNewGame: (config) => {
    set({ isLoading: true });
    try {
      const provinces = generateMap(100, 100, 42);
      const countries = initializeCountries(
        config.numCountries,
        provinces,
        config.difficulty
      );

      const gameState: GameState = {
        currentTurn: 1,
        year: 1815,
        currentPlayerCountryId: countries[0].id,
        countries,
        provinces,
        units: countries.flatMap(c => c.units),
        gamePhase: 'diplomacy',
        selectedUnit: null,
        selectedProvince: null,
      };

      set({ gameState, isLoading: false, error: null });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to start game',
        isLoading: false
      });
    }
  },

  loadGame: (saveData) => {
    set({ gameState: saveData });
  },

  nextTurn: () => {
    set((state) => {
      if (!state.gameState) return state;

      const previousBalance = state.gameState.countries.find(
        c => c.id === state.gameState!.currentPlayerCountryId
      )?.treasury || 0;

      // Use TurnEngine to process the turn
      const turnReport = TurnEngine.processTurn(state.gameState);

      // Get AI decisions from computer players
      const aiDecisions = new Map<string, AIDecision[]>();
      state.gameState.countries.forEach(country => {
        if (country.type === 'ai') {
          const decisions = AIEngine.makeDecisions(country, state.gameState!.countries, state.gameState);
          if (decisions.length > 0) {
            aiDecisions.set(country.id, decisions);
          }
        }
      });

      const currentBalance = state.gameState.countries.find(
        c => c.id === state.gameState!.currentPlayerCountryId
      )?.treasury || 0;

      return {
        gameState: { ...state.gameState },
        lastTurnReport: turnReport,
        lastAIDecisions: aiDecisions,
      };
    });
  },

  setGamePhase: (phase) => {
    set((state) => {
      if (!state.gameState) return state;
      return {
        gameState: { ...state.gameState, gamePhase: phase },
      };
    });
  },

  selectUnit: (unit) => {
    set((state) => {
      if (!state.gameState) return state;
      return {
        gameState: { ...state.gameState, selectedUnit: unit, selectedProvince: null },
      };
    });
  },

  selectProvince: (province) => {
    set((state) => {
      if (!state.gameState) return state;
      return {
        gameState: { ...state.gameState, selectedProvince: province, selectedUnit: null },
      };
    });
  },

  moveUnit: (unitId, toX, toY) => {
    set((state) => {
      if (!state.gameState) return state;

      const unit = state.gameState.units.find(u => u.id === unitId);
      if (!unit) return state;

      // TODO: Implement pathfinding and movement rules
      unit.position = { x: toX, y: toY };

      return { gameState: { ...state.gameState } };
    });
    return true;
  },

  createUnit: (type, countryId, x, y) => {
    set((state) => {
      if (!state.gameState) return state;

      const newUnit: Unit = {
        id: `unit_${Date.now()}`,
        type,
        countryId,
        position: { x, y },
        health: 100,
        morale: 100,
        experience: 0,
      };

      const updatedGameState = { ...state.gameState };
      updatedGameState.units.push(newUnit);

      const country = updatedGameState.countries.find(c => c.id === countryId);
      if (country) {
        country.units.push(newUnit);
      }

      return { gameState: updatedGameState };
    });
  },

  updateCountryTreasury: (countryId, amount) => {
    set((state) => {
      if (!state.gameState) return state;

      const country = state.gameState.countries.find(c => c.id === countryId);
      if (country) {
        country.treasury += amount;
      }

      return { gameState: { ...state.gameState } };
    });
  },

  getCurrentPlayer: () => {
    const { gameState } = get();
    if (!gameState) return null;
    return gameState.countries.find(c => c.id === gameState.currentPlayerCountryId) || null;
  },

  getProvinceAt: (x, y) => {
    const { gameState } = get();
    if (!gameState) return null;
    return gameState.provinces.find(p => p.position.x === x && p.position.y === y) || null;
  },
}));
