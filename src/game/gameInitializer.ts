// Game Initializer - Sets up initial game state based on difficulty and configuration
import { GameState, GameConfig } from '../types';
import { generateMap } from './mapGenerator';

export class GameInitializer {
  /**
   * Initialize a new game with the given configuration
   */
  static initializeGame(config: GameConfig): GameState {
    // Generate map with all provinces and countries
    const { provinces, countries } = generateMap(
      config.map.width,
      config.map.height,
      config.map.seed
    );

    // Adjust starting conditions based on difficulty
    this.adjustDifficultySettings(countries, config.difficulty);

    // Set up initial technology trees (all empty at game start)
    countries.forEach(country => {
      country.technology = new Map();
    });

    // Create initial game state
    const gameState: GameState = {
      currentTurn: 1,
      currentPlayerCountryId: countries[0].id, // First country is always the player
      countries,
      provinces,
      units: countries.flatMap(c => c.units),
      gamePhase: 'diplomacy', // Game starts in diplomacy phase
      selectedUnit: null,
      selectedProvince: null,
      year: 1815, // Game starts in 1815
      militaryEra: 1, // Era I at start
      mapWidth: config.map.width,
      mapHeight: config.map.height,
      gameOver: false,
    };

    // Initialize naval units for each country (starting navies)
    countries.forEach(country => {
      // Each country starts with 2 naval units (for trade protection)
      country.navalUnits = [];
      for (let i = 0; i < 2; i++) {
        country.navalUnits.push({
          id: `navy_${country.id}_${i}`,
          type: 'frigate',
          countryId: country.id,
          seaZone: (countries.indexOf(country) + i) % 6,
          health: 100,
          firepower: 3,
          range: 5,
          armor: 10,
          hull: 35,
          speed: 4,
          experience: 0,
        });
      }
    });

    return gameState;
  }

  /**
   * Adjust game settings based on difficulty
   */
  private static adjustDifficultySettings(countries: any[], difficulty: 'easy' | 'normal' | 'hard'): void {
    const playerCountry = countries[0];

    switch (difficulty) {
      case 'easy':
        // Player starts with more resources and better initial conditions
        playerCountry.treasury = 50000;
        playerCountry.workers = 150;
        countries.forEach((country, index) => {
          if (index > 0) {
            // AI countries are weaker
            country.treasury = 15000;
            country.workers = 60;
          }
        });
        break;

      case 'normal':
        // Balanced game
        playerCountry.treasury = 30000;
        playerCountry.workers = 100;
        break;

      case 'hard':
        // Player starts at disadvantage, AI stronger
        playerCountry.treasury = 20000;
        playerCountry.workers = 80;
        countries.forEach((country, index) => {
          if (index > 0) {
            // AI countries are stronger
            country.treasury = 35000;
            country.workers = 120;
          }
        });
        break;
    }

    // Give all countries some starting infrastructure
    // Each gets 2-3 ports in coastal provinces
    countries.forEach(country => {
      let portsBuilt = 0;
      const targetPorts = 2 + Math.floor(Math.random() * 2);

      country.provinces.forEach((province: any) => {
        if (portsBuilt < targetPorts && Math.random() > 0.7) {
          province.infrastructure.hasPort = true;
          portsBuilt++;
        }
      });
    });
  }

  /**
   * Create a new game with default settings
   */
  static createNewGame(numCountries: number = 6, difficulty: 'easy' | 'normal' | 'hard' = 'normal'): GameState {
    const config: GameConfig = {
      map: {
        width: 30,
        height: 30,
        seed: Math.floor(Math.random() * 1000000),
      },
      numCountries,
      difficulty,
      gameSpeed: 'normal',
    };

    return this.initializeGame(config);
  }

  /**
   * Validate that game state is valid
   */
  static validateGameState(gameState: GameState): boolean {
    // Check that all required fields exist
    if (!gameState.countries || gameState.countries.length === 0) {
      console.error('Game state has no countries');
      return false;
    }

    if (!gameState.provinces || gameState.provinces.length === 0) {
      console.error('Game state has no provinces');
      return false;
    }

    if (!gameState.currentPlayerCountryId) {
      console.error('Game state has no player country');
      return false;
    }

    // Check that player country exists
    const playerCountry = gameState.countries.find(c => c.id === gameState.currentPlayerCountryId);
    if (!playerCountry) {
      console.error('Player country not found in game state');
      return false;
    }

    // Check that player country has provinces
    if (playerCountry.provinces.length === 0) {
      console.error('Player country has no provinces');
      return false;
    }

    // Check that all provinces have owners
    const unownedProvinces = gameState.provinces.filter(p => !p.owner);
    if (unownedProvinces.length > 0) {
      console.warn(`${unownedProvinces.length} unowned provinces found`);
    }

    return true;
  }
}
