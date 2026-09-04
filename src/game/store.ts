import { create } from 'zustand';
import { GameState, Country, Province, Unit, UnitType, GameConfig } from '../types/index';
import { GameInitializer } from './gameInitializer';
import { TurnEngine, TurnReport } from './turnEngine';
import { ActionEngine, ActionResult } from './actionEngine';

interface GameStore {
  gameState: GameState | null;
  isLoading: boolean;
  error: string | null;
  lastTurnReport: TurnReport | null;

  // Game initialization
  startNewGame: (config: { numCountries: number; difficulty: 'easy' | 'normal' | 'hard' }) => void;
  loadGame: (saveData: GameState) => void;
  loadGameState: (gameState: GameState) => void;

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

  // Game actions
  executeAction: (action: () => ActionResult) => ActionResult;

  // Helpers
  getCurrentPlayer: () => Country | null;
  getProvinceAt: (x: number, y: number) => Province | null;
}

export const useGameStore = create<GameStore>((set, get) => ({
  gameState: null,
  isLoading: false,
  error: null,
  lastTurnReport: null,

  startNewGame: (config) => {
    set({ isLoading: true });
    try {
      const gameConfig: GameConfig = {
        map: {
          width: 30,
          height: 30,
          seed: Math.floor(Math.random() * 1000000),
        },
        numCountries: config.numCountries,
        difficulty: config.difficulty,
        gameSpeed: 'normal',
      };

      const gameState = GameInitializer.initializeGame(gameConfig);

      if (!GameInitializer.validateGameState(gameState)) {
        throw new Error('Game state validation failed');
      }

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

  loadGameState: (gameState) => {
    set({ gameState, isLoading: false, error: null });
  },

  nextTurn: () => {
    set((state) => {
      if (!state.gameState) return state;

      const turnReport = TurnEngine.processTurn(state.gameState);

      return {
        gameState: { ...state.gameState },
        lastTurnReport: turnReport,
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

  executeAction: (action) => {
    const result = action();
    // Force a state update to trigger re-renders
    set((state) => ({
      gameState: state.gameState ? { ...state.gameState } : null,
    }));
    return result;
  },
}));
