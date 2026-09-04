import { create } from 'zustand';
import { GameState, Country, Province, Unit, UnitType } from '@types/index';
import { generateMap } from './mapGenerator';
import { initializeCountries } from './countryInitializer';
import { EconomyEngine } from './economyEngine';

interface GameStore {
  gameState: GameState | null;
  isLoading: boolean;
  error: string | null;

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

      const updatedGameState = { ...state.gameState };
      updatedGameState.currentTurn++;

      // Advance year (4 turns per year)
      if (updatedGameState.currentTurn % 4 === 0) {
        updatedGameState.year++;
      }

      // Process economics for each country
      updatedGameState.countries.forEach(country => {
        // Calculate production
        country.provinces.forEach(province => {
          province.production.raw = EconomyEngine.calculateRawProduction(province);
          province.production.processed = EconomyEngine.calculateProcessedProduction(province, province.workers);
        });

        // Calculate income and expenses
        const { income, expenses } = EconomyEngine.processCountryEconomics(country);
        country.treasury += income - expenses;

        // Prevent bankruptcy (minimum 0)
        if (country.treasury < 0) {
          country.treasury = 0;
        }
      });

      updatedGameState.gamePhase = 'diplomacy';

      return { gameState: updatedGameState };
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
