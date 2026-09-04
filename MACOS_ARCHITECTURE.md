# Imperialism 1992 macOS - Swift/SwiftUI Architecture Design

## Overview
Native macOS application built with Swift and SwiftUI, targeting macOS 12.0+. Uses modern Swift concurrency (async/await) and SwiftUI reactive patterns with Combine for state management.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    SwiftUI Views (Presentation)         │
│  (GameView, MapView, UIPanel, TurnInfo, etc.)          │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              ViewModel Layer (MVVM Pattern)             │
│  (GameViewModel, MapViewModel, DiplomacyViewModel)      │
│  Uses @StateObject, @ObservedObject, @EnvironmentObject│
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│           Game Engine Layer (Business Logic)             │
│  ┌────────────────────────────────────────────────┐     │
│  │ GameEngine (Main coordinator)                  │     │
│  │ ├── MapSystem                                  │     │
│  │ ├── MilitaryEngine                             │     │
│  │ ├── EconomyEngine                              │     │
│  │ ├── TechnologyEngine                           │     │
│  │ ├── DiplomacyEngine                            │     │
│  │ ├── TradeEngine                                │     │
│  │ ├── AIEngine                                   │     │
│  │ └── TurnEngine                                 │     │
│  └────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              Data Model Layer (Entities)                 │
│  ┌────────────────────────────────────────────────┐     │
│  │ GameState, Country, Province, Unit, etc.       │     │
│  │ (Codable for serialization)                    │     │
│  └────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│           Persistence Layer (Storage)                    │
│  ├── FileManager (game saves)                           │
│  └── Codable JSON serialization                         │
└─────────────────────────────────────────────────────────┘
```

## File Structure

```
Imperialism-macOS/
├── ImperialismApp.swift                    # App entry point
├── Assets.xcassets/                        # Graphics, colors
├── Localizable.strings                     # i18n (Turkish support)
│
├── Views/                                  # SwiftUI Views
│   ├── ContentView.swift                   # Main game container
│   ├── GameView.swift                      # Game board + panels
│   ├── MapView.swift                       # Map rendering (Canvas)
│   ├── UIPanel.swift                       # Right control panel
│   ├── TurnInfo.swift                      # Turn/era/year display
│   ├── ActionPanel.swift                   # Unit/province actions
│   ├── DiplomacyPanel.swift                # Relations display
│   ├── TechnologyPanel.swift               # Research display
│   ├── TradePanel.swift                    # Trade routes display
│   ├── BattleView.swift                    # Combat resolution
│   └── MainMenu.swift                      # Start/load/settings
│
├── ViewModels/                             # MVVM State Management
│   ├── GameViewModel.swift                 # Game state coordinator
│   ├── MapViewModel.swift                  # Map rendering logic
│   ├── ActionViewModel.swift               # Unit/province actions
│   ├── DiplomacyViewModel.swift            # Diplomacy state
│   └── TurnReportViewModel.swift           # Turn summary display
│
├── Models/                                 # Data Entities (Codable)
│   ├── GameState.swift                     # Main game state
│   ├── GameConfig.swift                    # Game settings/difficulty
│   ├── Country.swift                       # Player/AI countries
│   ├── Province.swift                      # Map provinces
│   ├── Unit.swift                          # Military units
│   ├── Building.swift                      # Infrastructure
│   ├── Technology.swift                    # Tech tree definitions
│   ├── DiplomaticRelation.swift            # Diplomacy state
│   ├── TradeRoute.swift                    # Trade connections
│   └── Types.swift                         # Enums & constants
│
├── Engines/                                # Game Logic
│   ├── GameEngine.swift                    # Main engine coordinator
│   ├── MapSystem.swift                     # Map generation & provinces
│   ├── MilitaryEngine.swift                # Units, combat, movement
│   ├── EconomyEngine.swift                 # Production, resources
│   ├── TechnologyEngine.swift              # Research progression
│   ├── DiplomacyEngine.swift               # Diplomacy mechanics
│   ├── TradeEngine.swift                   # Trade routes, income
│   ├── AIEngine.swift                      # AI decision making
│   ├── AIActionExecutor.swift              # AI action execution
│   ├── TurnEngine.swift                    # Turn processing pipeline
│   ├── VictoryEngine.swift                 # Victory condition checking
│   └── CombatResolver.swift                # Combat calculation
│
├── Services/                               # Utility Services
│   ├── GameStorageService.swift            # Save/load games
│   ├── RandomNumberGenerator.swift         # Seeded RNG
│   └── Logger.swift                        # Debug logging
│
└── Resources/                              # Game Data
    ├── TerrainData.swift                   # 12 terrain types
    ├── MilitaryData.swift                  # 3 eras of units
    ├── BuildingData.swift                  # Infrastructure types
    ├── TechnologyData.swift                # 12 victory techs
    └── GameConstants.swift                 # Magic numbers
```

## Core Model Definitions

### GameState.swift
```swift
struct GameState: Codable {
    var currentTurn: Int
    var year: Int
    var gamePhase: GamePhase
    var mapWidth: Int
    var mapHeight: Int
    
    var countries: [Country]
    var provinces: [Province]
    var units: [Unit]
    var buildings: [Building]
    
    var currentPlayerCountryId: String
    var selectedProvince: Province?
    var selectedUnit: Unit?
    
    enum GamePhase: String, Codable {
        case diplomacy, movement, combat, research, ending
    }
}
```

### Country.swift
```swift
struct Country: Codable, Identifiable {
    let id: String
    var name: String
    var type: CountryType  // player, ai, minor
    var civilization: Civilization
    
    var treasury: Double
    var workers: Int
    var provinces: [String]  // Province IDs
    var units: [String]      // Unit IDs
    var diplomacy: [String: DiplomaticRelation]
    
    var technology: Set<String>
    var researchedTechnologies: Set<String>
    var researchInProgress: [String: ResearchProgress]
    
    var merchantMarine: Int
    var freightCars: Int
    var consulates: Set<String>  // Country IDs
    
    enum CountryType: String, Codable {
        case player, ai, minor
    }
}
```

### Province.swift
```swift
struct Province: Codable, Identifiable {
    let id: String
    var name: String
    var position: GridPosition
    var terrain: TerrainType
    var owner: String?  // Country ID
    
    var population: Int
    var workers: Int
    var fortLevel: Int
    
    var resources: [ResourceType: Int]
    var infrastructure: Infrastructure
    var garrison: [String]  // Unit IDs
    
    struct Infrastructure: Codable {
        var hasRailroad: Bool
        var hasPort: Bool
        var hasDepot: Bool
        var industrialized: Bool
    }
}
```

### Unit.swift
```swift
struct Unit: Codable, Identifiable {
    let id: String
    var type: UnitType
    var countryId: String
    var position: GridPosition
    
    var health: Int      // 0-100
    var morale: Int      // 0-100
    var experience: Int  // 0-100
    var veterancy: Int   // 0-10 levels
    
    var movement: Int    // Current turn movement
    var maxMovement: Int
}
```

### Technology.swift
```swift
struct Technology: Codable, Identifiable {
    let id: String
    var name: String
    var era: TechEra
    var cost: Int        // Research turns
    var prerequisites: Set<String>
    var bonuses: TechBonus
    
    struct TechBonus: Codable {
        var combatBonus: Int?
        var productionBonus: Int?
        var movementBonus: Int?
        var unlocksUnits: [String]
        var unlocksBuildings: [String]
    }
}
```

## State Management Strategy

### Using @StateObject & @EnvironmentObject
```swift
@main
struct ImperialismApp: App {
    @StateObject private var gameViewModel = GameViewModel()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(gameViewModel)
        }
    }
}
```

### ViewModel Pattern
```swift
class GameViewModel: NSObject, ObservableObject {
    @Published var gameState: GameState?
    @Published var isProcessingTurn = false
    @Published var selectedProvince: Province?
    @Published var selectedUnit: Unit?
    
    private let gameEngine = GameEngine()
    private let storageService = GameStorageService()
    
    func startNewGame(config: GameConfig) async {
        // Initialize game state
        let state = await gameEngine.initialize(config: config)
        DispatchQueue.main.async {
            self.gameState = state
        }
    }
    
    func nextTurn() async {
        guard let state = gameState else { return }
        DispatchQueue.main.async { self.isProcessingTurn = true }
        
        // Process turn asynchronously
        let updatedState = await gameEngine.processTurn(state)
        
        DispatchQueue.main.async {
            self.gameState = updatedState
            self.isProcessingTurn = false
        }
    }
}
```

## Threading Strategy

- **Main Thread**: All UI updates, SwiftUI renders
- **Background Queue**: Heavy computation (map generation, AI decisions, combat calculations)
- **Async/Await**: Coordinate async tasks (save/load, turn processing)

```swift
// Example: AI turn processing off main thread
func processAITurn() async {
    let aiDecisions = await Task.detached(priority: .userInitiated) {
        // Heavy AI computation
        return self.gameEngine.getAIDecisions(gameState)
    }.value
    
    // Update UI on main thread
    DispatchQueue.main.async {
        self.gameState.countries[index].executeDecisions(aiDecisions)
    }
}
```

## Data Persistence

### Save Format (JSON with Codable)
```swift
// User's home directory: ~/Library/Application Support/Imperialism/
// Saves directory: saves/
// Autosave: saves/autosave.imperialism
// Manual saves: saves/game_name_timestamp.imperialism

struct GameSave: Codable {
    let version: String = "1.0"
    let createdDate: Date
    let playerName: String
    let difficulty: GameDifficulty
    let gameState: GameState
}
```

### Storage Service
```swift
class GameStorageService {
    private let fileManager = FileManager.default
    private var savesDirectory: URL {
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let appDir = appSupport.appendingPathComponent("Imperialism")
        return appDir.appendingPathComponent("saves")
    }
    
    func saveGame(_ state: GameState, name: String) async throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(GameSave(gameState: state))
        
        let url = savesDirectory.appendingPathComponent("\(name)_\(Date().timeIntervalSince1970).imperialism")
        try data.write(to: url)
    }
    
    func loadGame(from url: URL) async throws -> GameState {
        let data = try Data(contentsOf: url)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let save = try decoder.decode(GameSave.self, from: data)
        return save.gameState
    }
}
```

## Engine Coordination

### GameEngine (Coordinator)
```swift
class GameEngine {
    let mapSystem: MapSystem
    let militaryEngine: MilitaryEngine
    let economyEngine: EconomyEngine
    let technologyEngine: TechnologyEngine
    let diplomacyEngine: DiplomacyEngine
    let tradeEngine: TradeEngine
    let aiEngine: AIEngine
    let turnEngine: TurnEngine
    let victoryEngine: VictoryEngine
    
    init() {
        mapSystem = MapSystem()
        militaryEngine = MilitaryEngine()
        // ... initialize all engines
    }
    
    func initialize(config: GameConfig) async -> GameState {
        // 1. Generate map
        // 2. Create provinces
        // 3. Initialize countries
        // 4. Setup diplomacy
        // 5. Return initial state
    }
    
    func processTurn(_ state: GameState) async -> GameState {
        return await turnEngine.processTurn(state)
    }
    
    func executePlayerAction(_ action: GameAction, state: GameState) async -> GameState {
        // Validate and execute action
        // Return updated state
    }
}
```

## View Architecture

### MapView (Canvas-based rendering)
```swift
struct MapView: View {
    @EnvironmentObject var viewModel: GameViewModel
    @StateObject private var mapViewModel = MapViewModel()
    
    var body: some View {
        Canvas { context in
            // Draw terrain
            // Draw provinces with ownership colors
            // Draw units
            // Draw fortifications
        }
        .gesture(mapGestures)
    }
}
```

### UIPanel (Right-side control panel)
```swift
struct UIPanel: View {
    @EnvironmentObject var viewModel: GameViewModel
    @State private var currentTab: ControlTab = .map
    
    var body: some View {
        VStack(spacing: 0) {
            TurnInfo()
            
            Picker("Screen", selection: $currentTab) {
                // Tab buttons
            }
            
            TabView(selection: $currentTab) {
                MapInfoView()
                TechnologyPanel()
                DiplomacyPanel()
                TradePanel()
            }
            
            ActionPanel()
            
            Button("END TURN") {
                Task {
                    await viewModel.nextTurn()
                }
            }
        }
    }
}
```

## Performance Considerations

1. **Map Rendering**: Use Canvas with visible rect clipping to render only viewport
2. **AI Calculations**: Run on background queue with priority levels
3. **Unit Updates**: Batch update units in groups to reduce re-renders
4. **Memory**: Lazy load province details, cache frequently accessed data
5. **Async I/O**: All file operations async to prevent UI blocking

## Deployment Strategy

### macOS Target
- Minimum: macOS 12.0 (Monterey)
- Recommended: macOS 13.0+ (Ventura)
- ARM64 + x86_64 universal binary

### App Signing & Notarization
- Self-signed certificate for development
- Developer ID certificate for distribution
- Notarization with Apple services

### Bundle Configuration
- Bundle ID: `com.imperialism.macos`
- Version: 1.0.0
- Category: Games
- Capabilities: File Access (saves directory), optional Network (future multiplayer)

## Next Steps (Days 5-6)

1. **Day 5**: Complete Swift data model definitions + storage service
2. **Day 6**: Create Xcode project structure and basic Combine patterns
3. **Day 7-8**: Implement MapSystem and province generation
4. **Day 9-10**: Implement MilitaryEngine and unit movement
