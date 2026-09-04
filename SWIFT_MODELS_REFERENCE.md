# Swift Model Definitions Reference - Imperialism macOS

## Enums & Constants

### Types.swift - Complete Enum Definitions

```swift
// MARK: - Game Enums

enum GamePhase: String, Codable, CaseIterable {
    case diplomacy
    case movement
    case combat
    case research
    case ending
}

enum GameDifficulty: String, Codable, CaseIterable {
    case easy
    case normal
    case hard
    
    var aiBonus: Double {
        switch self {
        case .easy: return 0.8      // AI gets 80% resources
        case .normal: return 1.0    // Equal footing
        case .hard: return 1.2      // AI gets 120% resources
        }
    }
}

enum CountryType: String, Codable, CaseIterable {
    case player
    case ai
    case minor      // Can be colonized
}

enum Civilization: String, Codable, CaseIterable {
    case britain
    case france
    case spain
    case netherlands
    case portugal
    case russia
    case austria
    case prussia
    case ottoman
    case china
    case japan
    case usa
}

// MARK: - Terrain Types (12 types)

enum TerrainType: String, Codable, CaseIterable {
    case grassland      // 20% production, 100% movement
    case forest         // 15% production, 60% movement
    case mountain       // 10% production, 40% movement
    case desert         // 15% production, 80% movement
    case tundra         // 5% production, 50% movement
    case swamp          // 10% production, 40% movement
    case coast          // 30% production (fishing), 100% movement
    case ocean          // Naval only, varies by season
    case plains         // 25% production, 100% movement
    case jungle         // 12% production, 50% movement
    case steppe         // 18% production, 90% movement
    case island         // 20% production, 100% movement
    
    var productionModifier: Double {
        switch self {
        case .grassland: return 1.20
        case .forest: return 1.15
        case .mountain: return 1.10
        case .desert: return 1.15
        case .tundra: return 1.05
        case .swamp: return 1.10
        case .coast: return 1.30
        case .ocean: return 0.0
        case .plains: return 1.25
        case .jungle: return 1.12
        case .steppe: return 1.18
        case .island: return 1.20
        }
    }
    
    var movementModifier: Double {
        switch self {
        case .grassland, .plains, .coast, .island: return 1.0
        case .forest, .desert, .steppe: return 0.8
        case .mountain, .swamp, .jungle: return 0.5
        case .ocean, .tundra: return 0.6
        }
    }
}

// MARK: - Resource Types (15 total)

enum ResourceType: String, Codable, CaseIterable {
    // Raw materials
    case wheat
    case fish
    case coal
    case iron
    case wood
    case saltpeter  // Gunpowder ingredient
    
    // Processed goods
    case grain      // From wheat
    case steel      // From iron + coal
    case lumber     // From wood
    case gunpowder  // From saltpeter + coal
    
    // Finished goods
    case food
    case tools
    case textiles
    case weapons
    case irongoods
    
    var category: ResourceCategory {
        switch self {
        case .wheat, .fish, .coal, .iron, .wood, .saltpeter:
            return .raw
        case .grain, .steel, .lumber, .gunpowder:
            return .processed
        case .food, .tools, .textiles, .weapons, .irongoods:
            return .finished
        }
    }
}

enum ResourceCategory: String, Codable {
    case raw
    case processed
    case finished
}

// MARK: - Unit Types

enum UnitType: String, Codable, CaseIterable {
    // ERA 1: 1815-1850s
    case militia            // Weakest, fast recruitment
    case infantry
    case cavalry
    case artillery
    case frigate            // Naval
    
    // ERA 2: 1850s-1880s
    case regulars
    case guards
    case dragoons
    case ironclad            // Naval advancement
    
    // ERA 3: 1880s-1920s
    case riflemen
    case machinegunners
    case heavyartillery
    case battleship          // Naval peak
    
    var era: MilitaryEra {
        switch self {
        case .militia, .infantry, .cavalry, .artillery, .frigate:
            return .classical
        case .regulars, .guards, .dragoons, .ironclad:
            return .industrial
        case .riflemen, .machinegunners, .heavyartillery, .battleship:
            return .modern
        }
    }
    
    var baseCost: Int {
        switch self {
        case .militia: return 500
        case .infantry: return 800
        case .cavalry: return 1200
        case .artillery: return 1500
        case .frigate: return 2000
        case .regulars: return 1000
        case .guards: return 1500
        case .dragoons: return 1300
        case .ironclad: return 3000
        case .riflemen: return 1200
        case .machinegunners: return 1800
        case .heavyartillery: return 2500
        case .battleship: return 5000
        }
    }
}

enum MilitaryEra: String, Codable, CaseIterable {
    case classical   // 1815-1850s
    case industrial  // 1850s-1880s
    case modern      // 1880s-1920s
    
    var startYear: Int {
        switch self {
        case .classical: return 1815
        case .industrial: return 1855
        case .modern: return 1875
        }
    }
}

// MARK: - Building Types

enum BuildingType: String, Codable, CaseIterable {
    case railroad
    case port
    case depot
    case fort
    case factory
    case farm
    case mine
    
    var cost: Int {
        switch self {
        case .railroad: return 5000
        case .port: return 6000
        case .depot: return 3000
        case .fort: return 4000
        case .factory: return 8000
        case .farm: return 2000
        case .mine: return 3000
        }
    }
    
    var maintenanceCost: Int {
        switch self {
        case .railroad: return 10
        case .port: return 15
        case .depot: return 8
        case .fort: return 5
        case .factory: return 20
        case .farm: return 5
        case .mine: return 8
        }
    }
}

// MARK: - Technology Types

enum TechEra: String, Codable, CaseIterable {
    case classical
    case industrial
    case modern
    
    var startYear: Int {
        switch self {
        case .classical: return 1815
        case .industrial: return 1855
        case .modern: return 1875
        }
    }
}

// MARK: - Diplomacy Types

enum DiplomaticStatus: String, Codable, CaseIterable {
    case allied
    case neutral
    case hostile
    case war
    
    var trustRequirement: Int {
        switch self {
        case .allied: return 50
        case .neutral: return -49
        case .hostile: return -100
        case .war: return -50  // War state separate from trust
        }
    }
}

enum TradeStatus: String, Codable {
    case none
    case passive      // One-way trade
    case mutual       // Bidirectional agreement
}

// MARK: - Victory Types

enum VictoryType: String, Codable, CaseIterable {
    case conquest     // Control 60% of provinces
    case economic     // Treasury >= $100,000
    case technology   // Research 12 key technologies
    case timeout      // Reach year 1920
}

// MARK: - UI Types

enum ControlTab: String, CaseIterable {
    case map
    case transport
    case industry
    case trade
    case diplomacy
    case research
    case battle
}

enum GameAction: Codable {
    case moveUnit(unitId: String, toX: Int, toY: Int)
    case attackUnit(unitId: String, targetId: String)
    case recruitUnit(provinceId: String, unitType: UnitType)
    case buildInfra(provinceId: String, buildingType: BuildingType)
    case researchTech(techId: String)
    case establishTrade(countryId: String)
    case formAlliance(countryId: String)
    case declareWar(countryId: String)
    case makePeace(countryId: String)
}

// MARK: - GridPosition

struct GridPosition: Codable, Hashable, Equatable {
    let x: Int
    let y: Int
    
    func distance(to other: GridPosition) -> Int {
        return max(abs(x - other.x), abs(y - other.y))  // Chebyshev distance
    }
    
    func adjacent(to other: GridPosition) -> Bool {
        return distance(to: other) == 1
    }
}

```

## Core Data Models

### GameState.swift

```swift
struct GameState: Codable {
    // Game progress
    var currentTurn: Int
    var year: Int
    var gamePhase: GamePhase
    var difficulty: GameDifficulty
    
    // Map configuration
    var mapWidth: Int
    var mapHeight: Int
    var mapSeed: UInt64
    
    // Game entities
    var countries: [Country]
    var provinces: [Province]
    var units: [Unit]
    var buildings: [Building]
    
    // Game state
    var currentPlayerCountryId: String
    var selectedProvince: Province?
    var selectedUnit: Unit?
    
    // Victory tracking
    var victoryStatus: VictoryStatus?
    var isGameOver: Bool = false
    
    // Military era (changes with technology)
    var militaryEra: MilitaryEra = .classical
    
    var description: String {
        "Turn \(currentTurn) | Year \(year) | Phase: \(gamePhase.rawValue)"
    }
}

struct VictoryStatus: Codable {
    let winner: String        // Country ID
    let victoryType: VictoryType
    let reason: String
    let timestamp: Date
}
```

### Country.swift

```swift
struct Country: Codable, Identifiable {
    let id: String
    var name: String
    var type: CountryType
    var civilization: Civilization
    var color: CountryColor
    
    // Economy
    var treasury: Double
    var workers: Int
    var workerProductivity: Double = 1.0  // Modified by tech/buildings
    
    // Territory
    var provinces: [String]  // Province IDs owned
    var units: [String]      // Unit IDs owned
    
    // Military
    var navalUnits: [String] = []
    var militaryUpkeep: Double = 0
    
    // Technology
    var technology: Set<String> = []          // Technologies being researched
    var researchedTechnologies: Set<String> = []
    var researchInProgress: [String: ResearchProgress] = [:]
    
    // Diplomacy
    var diplomacy: [String: DiplomaticRelation] = [:]
    
    // Trade
    var merchantMarine: Int = 0
    var freightCars: Int = 0
    var tradeAgreements: Set<String> = []    // Country IDs
    var activeTradeRoutes: [TradeRoute] = []
    var tradeIncome: Double = 0
    
    // AI Personality (if type == .ai)
    var aiPersonality: AIPersonality?
    
    // Victory progress
    var victoryProgress: VictoryProgress = VictoryProgress()
    
    mutating func addProvince(_ id: String) {
        if !provinces.contains(id) {
            provinces.append(id)
        }
    }
    
    mutating func removeProvince(_ id: String) {
        provinces.removeAll { $0 == id }
    }
}

struct VictoryProgress: Codable {
    var conquestPercent: Double = 0    // 0-100
    var economicTreasury: Double = 0
    var technologyCount: Int = 0
    var yearsElapsed: Int = 0
}

struct CountryColor: Codable {
    let r: CGFloat
    let g: CGFloat
    let b: CGFloat
}

struct ResearchProgress: Codable {
    let techId: String
    var turnsRemaining: Int
    var startTurn: Int
    var lastUpdated: Date
}
```

### Province.swift

```swift
struct Province: Codable, Identifiable {
    let id: String
    var name: String
    let position: GridPosition
    var terrain: TerrainType
    
    // Ownership
    var owner: String?  // Country ID or nil if unclaimed
    var fortLevel: Int = 0
    var garrison: [String] = []  // Unit IDs stationed here
    
    // Population & workers
    var population: Int
    var workers: Int
    var growth: Double = 1.05  // Yearly growth rate
    
    // Resources
    var resources: [ResourceType: Int] = [:]  // Current stockpiles
    var resourceProduction: [ResourceType: Int] = [:]  // Per-turn production
    
    // Infrastructure
    var infrastructure: ProvinceInfrastructure = ProvinceInfrastructure()
    
    // Production tracking
    var rawMaterials: [ResourceType: Int] = [:]
    var processedGoods: [ResourceType: Int] = [:]
    var finishedGoods: [ResourceType: Int] = [:]
    
    var description: String {
        "\(name) [\(terrain.rawValue)] @ (\(position.x),\(position.y))"
    }
}

struct ProvinceInfrastructure: Codable {
    var hasRailroad: Bool = false
    var hasPort: Bool = false
    var hasDepot: Bool = false
    var industrialized: Bool = false
    var fort: Int = 0          // Fort level 0-3
    var farm: Bool = false
    var mine: Bool = false
    var factory: Bool = false
    
    var maintenanceCost: Int {
        var cost = 0
        if hasRailroad { cost += 10 }
        if hasPort { cost += 15 }
        if hasDepot { cost += 8 }
        if industrialized { cost += 20 }
        if farm { cost += 5 }
        if mine { cost += 8 }
        if factory { cost += 20 }
        cost += fort * 5
        return cost
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
    
    // Health & morale
    var health: Int = 100      // 0-100
    var morale: Int = 100      // 0-100, affects combat
    var experience: Int = 0    // 0-100, gives +0.5% per point in combat
    
    // Movement
    var movement: Int = 0      // Current turn movement points (reset each turn)
    var maxMovement: Int {
        let baseMoves = UnitMovement.getBaseMovement(for: type, era: type.era)
        return Int(Double(baseMoves) * (1.0 + Double(experience) * 0.005))
    }
    
    // Status
    var isNaval: Bool {
        type == .frigate || type == .ironclad || type == .battleship
    }
    
    var veterancy: Int {
        experience / 10  // 0-10 levels
    }
    
    var combatStrength: Double {
        let firepower = UnitMovement.getFirepower(for: type)
        let moraleBonus = Double(morale) / 100.0
        let experienceBonus = Double(experience) * 0.005
        return Double(firepower) * (1.0 + moraleBonus + experienceBonus)
    }
    
    var description: String {
        "\(type.rawValue) @ (\(position.x),\(position.y)) - HP:\(health) Morale:\(morale) XP:\(experience)"
    }
}

struct UnitMovement {
    static func getBaseMovement(for type: UnitType, era: MilitaryEra) -> Int {
        switch type {
        // ERA 1
        case .militia: return 5
        case .infantry: return 4
        case .cavalry: return 8
        case .artillery: return 3
        case .frigate: return 6
        // ERA 2
        case .regulars: return 5
        case .guards: return 5
        case .dragoons: return 9
        case .ironclad: return 7
        // ERA 3
        case .riflemen: return 4
        case .machinegunners: return 3
        case .heavyartillery: return 3
        case .battleship: return 8
        }
    }
    
    static func getFirepower(for type: UnitType) -> Int {
        switch type {
        case .militia: return 1
        case .infantry: return 3
        case .cavalry: return 4
        case .artillery: return 5
        case .frigate: return 4
        case .regulars: return 4
        case .guards: return 5
        case .dragoons: return 5
        case .ironclad: return 6
        case .riflemen: return 4
        case .machinegunners: return 6
        case .heavyartillery: return 7
        case .battleship: return 8
        }
    }
}
```

### DiplomaticRelation.swift

```swift
struct DiplomaticRelation: Codable {
    var countryId: String
    var status: DiplomaticStatus = .neutral
    var trust: Int = 0          // -100 to 100
    var warState: Bool = false  // Separate from status
    
    // Relations
    var tradeAgreement: Bool = false
    var allied: Bool = false
    var lastInteraction: Date = Date()
    
    var description: String {
        "\(status.rawValue) (Trust: \(trust))"
    }
    
    mutating func decayTrust() {
        // Each turn: -0.5 trust decay
        trust = max(-100, trust - 1)
    }
    
    mutating func gainTrust(_ amount: Int) {
        trust = min(100, trust + amount)
    }
    
    mutating func loseTrust(_ amount: Int) {
        trust = max(-100, trust - amount)
    }
}
```

### Technology.swift

```swift
struct Technology: Codable, Identifiable {
    let id: String
    let name: String
    let description: String
    let era: TechEra
    let cost: Int        // Turns to research
    let prerequisites: [String]  // Tech IDs required
    
    var isVictoryTech: Bool
    var bonuses: TechBonus
    
    struct TechBonus: Codable {
        var combatBonus: Int = 0       // % improvement to firepower
        var productionBonus: Int = 0   // % improvement to production
        var movementBonus: Int = 0     // Movement point increase
        var unlocksUnits: [UnitType] = []
        var unlocksBuildings: [BuildingType] = []
    }
}
```

### TradeRoute.swift

```swift
struct TradeRoute: Codable, Identifiable {
    let id: String
    let fromCountry: String
    let toCountry: String
    let fromProvince: String
    let toProvince: String
    
    var resources: [ResourceType: Int] = [:]  // Amount of each resource traded
    var income: Double  // Gold per turn
    var status: TradeStatus = .mutual
    var establishedTurn: Int
    
    var isActive: Bool {
        status == .mutual || status == .passive
    }
}
```

### Building.swift

```swift
struct Building: Codable, Identifiable {
    let id: String
    var type: BuildingType
    var provinceId: String
    var constructedTurn: Int
    var owner: String  // Country ID
    
    var isComplete: Bool {
        true  // Simplified: all buildings built in one turn
    }
    
    var maintenanceCost: Int {
        type.maintenanceCost
    }
}
```

## Persistence Models

### GameSave.swift

```swift
struct GameSave: Codable {
    let version: String = "1.0"
    let createdDate: Date
    let lastModified: Date
    let playerName: String
    let playerCivilization: Civilization
    let difficulty: GameDifficulty
    
    let gameState: GameState
    let metadata: SaveMetadata
    
    struct SaveMetadata: Codable {
        let totalTurns: Int
        let yearsElapsed: Int
        let countriesCount: Int
        let provincesCount: Int
    }
}
```

## AI Models

### AIPersonality.swift

```swift
struct AIPersonality: Codable {
    let aggressiveness: Double     // 0.0-1.0
    let diplomacy: Double          // 0.0-1.0 (peaceful vs aggressive)
    let expansion: Double          // 0.0-1.0 (expansionist vs defensive)
    let research: Double           // 0.0-1.0 (tech-focused vs military)
    let economy: Double            // 0.0-1.0 (money-focused vs spending)
    
    static let aggressive = AIPersonality(
        aggressiveness: 0.9,
        diplomacy: 0.2,
        expansion: 0.9,
        research: 0.4,
        economy: 0.3
    )
    
    static let balanced = AIPersonality(
        aggressiveness: 0.5,
        diplomacy: 0.5,
        expansion: 0.5,
        research: 0.5,
        economy: 0.5
    )
    
    static let diplomatic = AIPersonality(
        aggressiveness: 0.2,
        diplomacy: 0.9,
        expansion: 0.4,
        research: 0.7,
        economy: 0.7
    )
}
```

This reference provides the complete data model structure needed for Swift implementation in Days 6-8.
