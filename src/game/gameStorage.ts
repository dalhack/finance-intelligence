import { GameState } from '../types/index';

const STORAGE_KEY = 'imperialism_game_state';
const AUTOSAVE_KEY = 'imperialism_autosave';
const SAVE_SLOTS_KEY = 'imperialism_save_slots';

export interface GameSave {
  id: string;
  name: string;
  timestamp: number;
  turn: number;
  year: number;
  gameState: GameState;
}

export class GameStorage {
  static saveGame(gameState: GameState, slotName: string): boolean {
    try {
      const save: GameSave = {
        id: `save_${Date.now()}`,
        name: slotName,
        timestamp: Date.now(),
        turn: gameState.currentTurn,
        year: gameState.year,
        gameState: JSON.parse(JSON.stringify(gameState)),
      };

      const slots = this.getSaveSlots();
      slots[slotName] = save;
      localStorage.setItem(SAVE_SLOTS_KEY, JSON.stringify(slots));
      localStorage.setItem(`${STORAGE_KEY}_${slotName}`, JSON.stringify(save));

      return true;
    } catch (error) {
      console.error('Failed to save game:', error);
      return false;
    }
  }

  static loadGame(slotName: string): GameState | null {
    try {
      const saveData = localStorage.getItem(`${STORAGE_KEY}_${slotName}`);
      if (!saveData) return null;

      const save: GameSave = JSON.parse(saveData);
      return save.gameState;
    } catch (error) {
      console.error('Failed to load game:', error);
      return null;
    }
  }

  static autoSave(gameState: GameState): boolean {
    return this.saveGame(gameState, 'autosave');
  }

  static loadAutoSave(): GameState | null {
    return this.loadGame('autosave');
  }

  static getSaveSlots(): Record<string, GameSave> {
    try {
      const slotsData = localStorage.getItem(SAVE_SLOTS_KEY);
      return slotsData ? JSON.parse(slotsData) : {};
    } catch {
      return {};
    }
  }

  static deleteSave(slotName: string): boolean {
    try {
      const slots = this.getSaveSlots();
      delete slots[slotName];
      localStorage.setItem(SAVE_SLOTS_KEY, JSON.stringify(slots));
      localStorage.removeItem(`${STORAGE_KEY}_${slotName}`);
      return true;
    } catch (error) {
      console.error('Failed to delete save:', error);
      return false;
    }
  }

  static clearAllSaves(): boolean {
    try {
      const slots = this.getSaveSlots();
      Object.keys(slots).forEach(slot => {
        localStorage.removeItem(`${STORAGE_KEY}_${slot}`);
      });
      localStorage.removeItem(SAVE_SLOTS_KEY);
      return true;
    } catch (error) {
      console.error('Failed to clear saves:', error);
      return false;
    }
  }

  static exportSave(slotName: string): string | null {
    try {
      const saveData = localStorage.getItem(`${STORAGE_KEY}_${slotName}`);
      return saveData ? saveData : null;
    } catch (error) {
      console.error('Failed to export save:', error);
      return null;
    }
  }

  static importSave(slotName: string, saveData: string): boolean {
    try {
      const save: GameSave = JSON.parse(saveData);
      localStorage.setItem(`${STORAGE_KEY}_${slotName}`, JSON.stringify(save));

      const slots = this.getSaveSlots();
      slots[slotName] = save;
      localStorage.setItem(SAVE_SLOTS_KEY, JSON.stringify(slots));

      return true;
    } catch (error) {
      console.error('Failed to import save:', error);
      return false;
    }
  }
}
