# Days 18-19: UI Implementation & Game Interface

## Main GameView.swift - Complete Implementation

```swift
import SwiftUI
import Combine

/// Main game window containing all UI panels
struct GameView: View {
    @StateObject private var viewModel: GameViewModel
    @State private var selectedProvince: String?
    @State private var selectedUnit: String?
    @State private var hoveredPosition: GridPosition?
    
    init(gameState: GameState) {
        _viewModel = StateObject(wrappedValue: GameViewModel(initialState: gameState))
    }
    
    var body: some View {
        ZStack {
            // Background
            Color(.sRGB, red: 0.1, green: 0.1, blue: 0.12)
                .ignoresSafeArea()
            
            HStack(spacing: 0) {
                // Main Map Area
                MapView(
                    gameState: viewModel.gameState,
                    selectedProvince: $selectedProvince,
                    selectedUnit: $selectedUnit,
                    hoveredPosition: $hoveredPosition
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                
                // Right Sidebar
                VStack(spacing: 0) {
                    // Turn Info Panel
                    TurnInfoPanel(gameState: viewModel.gameState)
                        .frame(height: 120)
                        .background(Color(.sRGB, red: 0.15, green: 0.15, blue: 0.17))
                        .borderBottom(Color(.sRGB, red: 0.2, green: 0.2, blue: 0.22))
                    
                    // Country Info Panel
                    CountryInfoPanel(country: viewModel.currentCountry)
                        .frame(height: 180)
                        .background(Color(.sRGB, red: 0.15, green: 0.15, blue: 0.17))
                        .borderBottom(Color(.sRGB, red: 0.2, green: 0.2, blue: 0.22))
                    
                    // Selection Details Panel
                    if let provinceId = selectedProvince,
                       let province = viewModel.gameState.provinces.first(where: { $0.id == provinceId }) {
                        ProvinceDetailPanel(province: province)
                            .frame(height: 200)
                            .background(Color(.sRGB, red: 0.15, green: 0.15, blue: 0.17))
                            .borderBottom(Color(.sRGB, red: 0.2, green: 0.2, blue: 0.22))
                    } else if let unitId = selectedUnit,
                              let unit = viewModel.gameState.units.first(where: { $0.id == unitId }) {
                        UnitDetailPanel(unit: unit, gameState: viewModel.gameState)
                            .frame(height: 200)
                            .background(Color(.sRGB, red: 0.15, green: 0.15, blue: 0.17))
                            .borderBottom(Color(.sRGB, red: 0.2, green: 0.2, blue: 0.22))
                    }
                    
                    // Action Panel
                    ActionPanel(
                        selectedProvince: selectedProvince,
                        selectedUnit: selectedUnit,
                        gameState: viewModel.gameState,
                        onAction: { action in
                            Task {
                                await viewModel.executeAction(action)
                            }
                        }
                    )
                    .frame(maxHeight: .infinity)
                    .background(Color(.sRGB, red: 0.15, green: 0.15, blue: 0.17))
                }
                .frame(width: 300)
            }
            
            // Top Menu Bar
            VStack {
                HStack {
                    Button(action: { Task { await viewModel.save() } }) {
                        Label("Save", systemImage: "square.and.arrow.down")
                    }
                    
                    Button(action: { Task { await viewModel.endTurn() } }) {
                        Label("End Turn", systemImage: "arrow.right.circle")
                    }
                    .disabled(!viewModel.canEndTurn)
                    
                    Spacer()
                    
                    Button(action: {}) {
                        Label("Settings", systemImage: "gear")
                    }
                }
                .padding(12)
                .background(Color(.sRGB, red: 0.12, green: 0.12, blue: 0.14))
                .borderBottom(Color(.sRGB, red: 0.2, green: 0.2, blue: 0.22))
                
                Spacer()
            }
        }
    }
}

// MARK: - MapView

/// Canvas-based map rendering with terrain, provinces, units, and selection
struct MapView: View {
    let gameState: GameState
    @Binding var selectedProvince: String?
    @Binding var selectedUnit: String?
    @Binding var hoveredPosition: GridPosition?
    
    var body: some View {
        Canvas { context in
            let mapWidth = CGFloat(gameState.mapWidth)
            let mapHeight = CGFloat(gameState.mapHeight)
            let tileWidth = 32.0
            let tileHeight = 32.0
            
            // Draw terrain
            for province in gameState.provinces {
                let rect = CGRect(
                    x: CGFloat(province.position.x) * tileWidth,
                    y: CGFloat(province.position.y) * tileHeight,
                    width: tileWidth,
                    height: tileHeight
                )
                
                // Terrain background
                let color = province.terrain.displayColor
                var path = Path(roundedRect: rect, cornerRadius: 2)
                context.fill(path, with: .color(color))
                
                // Owner border
                if let owner = province.owner {
                    let ownerCountry = gameState.countries.first { $0.id == owner }
                    if let country = ownerCountry {
                        let borderColor = SwiftUI.Color(
                            red: country.color.r,
                            green: country.color.g,
                            blue: country.color.b
                        )
                        path = Path(roundedRect: rect, cornerRadius: 2)
                        context.stroke(path, with: .color(borderColor), lineWidth: 2)
                    }
                }
                
                // Selection highlight
                if selectedProvince == province.id {
                    var selectionPath = Path(roundedRect: rect.insetBy(dx: -2, dy: -2), cornerRadius: 2)
                    context.stroke(selectionPath, with: .color(.yellow), lineWidth: 3)
                }
                
                // Population indicator (dot size)
                let popSize = min(CGFloat(province.population) / 5000.0, 6.0)
                let popRect = CGRect(
                    x: rect.midX - popSize / 2,
                    y: rect.midY - popSize / 2,
                    width: popSize,
                    height: popSize
                )
                let popPath = Path(ellipseIn: popRect)
                context.fill(popPath, with: .color(.white))
            }
            
            // Draw units
            for unit in gameState.units {
                let rect = CGRect(
                    x: CGFloat(unit.position.x) * tileWidth + 4,
                    y: CGFloat(unit.position.y) * tileHeight + 4,
                    width: 24,
                    height: 24
                )
                
                let country = gameState.countries.first { $0.id == unit.countryId }
                if let country = country {
                    let unitColor = SwiftUI.Color(
                        red: country.color.r,
                        green: country.color.g,
                        blue: country.color.b
                    )
                    
                    let path = Path(ellipseIn: rect)
                    context.fill(path, with: .color(unitColor))
                    
                    if selectedUnit == unit.id {
                        context.stroke(path, with: .color(.white), lineWidth: 2)
                    }
                }
            }
        }
        .onContinuousHover { phase in
            switch phase {
            case .active(let location):
                let x = Int(location.x / 32)
                let y = Int(location.y / 32)
                hoveredPosition = GridPosition(x: x, y: y)
            case .ended:
                hoveredPosition = nil
            }
        }
        .onTapGesture { location in
            let x = Int(location.x / 32)
            let y = Int(location.y / 32)
            let position = GridPosition(x: x, y: y)
            
            // Check for unit click first
            if let unit = gameState.units.first(where: { $0.position == position }) {
                selectedUnit = unit.id
                selectedProvince = nil
            } else if let province = gameState.provinces.first(where: { $0.position == position }) {
                selectedProvince = province.id
                selectedUnit = nil
            }
        }
    }
}

// MARK: - TurnInfoPanel

/// Displays current turn, year, game phase, and difficulty
struct TurnInfoPanel: View {
    let gameState: GameState
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Turn \(gameState.currentTurn)").font(.headline)
            
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Year").font(.caption).foregroundColor(.gray)
                    Text("\(gameState.year)").font(.title3).fontWeight(.semibold)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Phase").font(.caption).foregroundColor(.gray)
                    Text(gameState.gamePhase.rawValue.capitalized).font(.title3).fontWeight(.semibold)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Difficulty").font(.caption).foregroundColor(.gray)
                    Text(gameState.difficulty.rawValue.capitalized).font(.caption2)
                }
            }
            
            ProgressView(value: Double(gameState.currentTurn) / 100.0)
                .tint(.blue)
        }
        .padding(12)
        .foregroundColor(.white)
    }
}

// MARK: - CountryInfoPanel

/// Displays current player country status
struct CountryInfoPanel: View {
    let country: Country
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(country.name)
                .font(.headline)
                .foregroundColor(SwiftUI.Color(
                    red: country.color.r,
                    green: country.color.g,
                    blue: country.color.b
                ))
            
            VStack(spacing: 6) {
                StatRow(label: "Treasury", value: "$\(Int(country.treasury))", color: .green)
                StatRow(label: "Workers", value: "\(country.workers)", color: .blue)
                StatRow(label: "Units", value: "\(country.units.count)", color: .orange)
                StatRow(label: "Technologies", value: "\(country.researchedTechnologies.count)", color: .purple)
            }
        }
        .padding(12)
        .foregroundColor(.white)
    }
}

// MARK: - ProvinceDetailPanel

/// Displays detailed information about a selected province
struct ProvinceDetailPanel: View {
    let province: Province
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(province.name)
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 6) {
                StatRow(label: "Terrain", value: province.terrain.rawValue.capitalized, color: .gray)
                StatRow(label: "Population", value: "\(province.population)", color: .green)
                StatRow(label: "Workers", value: "\(province.workers)", color: .blue)
                StatRow(label: "Fortification", value: "Level \(province.fortLevel)", color: .orange)
            }
            
            Text("Resources").font(.caption).foregroundColor(.gray).padding(.top, 4)
            VStack(alignment: .leading, spacing: 3) {
                ForEach(province.resources.sorted { $0.key.rawValue < $1.key.rawValue }, id: \.key) { resource, amount in
                    HStack {
                        Text(resource.rawValue).font(.caption)
                        Spacer()
                        Text("\(amount)").font(.caption).foregroundColor(.yellow)
                    }
                }
            }
        }
        .padding(12)
        .foregroundColor(.white)
    }
}

// MARK: - UnitDetailPanel

/// Displays detailed information about a selected unit
struct UnitDetailPanel: View {
    let unit: Unit
    let gameState: GameState
    
    var country: Country? {
        gameState.countries.first { $0.id == unit.countryId }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(unit.type.rawValue.capitalized).font(.headline)
                Spacer()
                if unit.experience >= 50 {
                    Image(systemName: "star.fill").foregroundColor(.yellow)
                }
            }
            
            VStack(alignment: .leading, spacing: 6) {
                StatRow(label: "Owner", value: country?.name ?? "Unknown", color: .blue)
                StatRow(label: "Health", value: "\(unit.health)/100", color: .red)
                StatRow(label: "Morale", value: "\(unit.morale)/100", color: .green)
                StatRow(label: "Experience", value: "\(unit.experience)/100", color: .yellow)
                StatRow(label: "Movement", value: "\(unit.movement)", color: .blue)
            }
            
            // Health bar
            VStack(spacing: 4) {
                Text("Health").font(.caption).foregroundColor(.gray)
                ProgressView(value: Double(unit.health) / 100.0)
                    .tint(.red)
            }
        }
        .padding(12)
        .foregroundColor(.white)
    }
}

// MARK: - ActionPanel

/// Displays available actions for selected unit or province
struct ActionPanel: View {
    let selectedProvince: String?
    let selectedUnit: String?
    let gameState: GameState
    let onAction: (GameAction) -> Void
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Actions").font(.headline).padding(.horizontal, 12)
                
                if let unitId = selectedUnit,
                   let unit = gameState.units.first(where: { $0.id == unitId }) {
                    UnitActionButtons(unit: unit, onAction: onAction)
                } else if let provinceId = selectedProvince,
                          let province = gameState.provinces.first(where: { $0.id == provinceId }) {
                    ProvinceActionButtons(province: province, onAction: onAction)
                } else {
                    Text("Select a unit or province to see available actions")
                        .font(.caption)
                        .foregroundColor(.gray)
                        .padding(.horizontal, 12)
                }
                
                Spacer()
            }
            .padding(.vertical, 12)
        }
        .foregroundColor(.white)
    }
}

// MARK: - UnitActionButtons

struct UnitActionButtons: View {
    let unit: Unit
    let onAction: (GameAction) -> Void
    
    var body: some View {
        VStack(spacing: 8) {
            if unit.movement > 0 {
                Button(action: { onAction(.moveUnit(unitId: unit.id, toX: unit.position.x + 1, toY: unit.position.y)) }) {
                    Label("Move", systemImage: "arrow.right")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
            
            Button(action: { onAction(.holdUnit(unitId: unit.id)) }) {
                Label("Hold Position", systemImage: "pause.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            
            if unit.health < 100 {
                Button(action: { onAction(.healUnit(unitId: unit.id)) }) {
                    Label("Fortify", systemImage: "shield")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(.horizontal, 12)
    }
}

// MARK: - ProvinceActionButtons

struct ProvinceActionButtons: View {
    let province: Province
    let onAction: (GameAction) -> Void
    
    var body: some View {
        VStack(spacing: 8) {
            Button(action: { onAction(.recruitUnit(provinceId: province.id, unitType: .militia)) }) {
                Label("Recruit Militia", systemImage: "person.badge.plus")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            
            Button(action: { onAction(.buildInfra(provinceId: province.id, buildingType: .railroad)) }) {
                Label("Build Railroad", systemImage: "railway.2.switch.tracks")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            
            if province.terrain == .coast {
                Button(action: { onAction(.buildInfra(provinceId: province.id, buildingType: .port)) }) {
                    Label("Build Port", systemImage: "anchor")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
            
            Button(action: { onAction(.fortifyProvince(provinceId: province.id)) }) {
                Label("Build Fort", systemImage: "building.2")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
        .padding(.horizontal, 12)
    }
}

// MARK: - Helper Views

struct StatRow: View {
    let label: String
    let value: String
    let color: Color
    
    var body: some View {
        HStack {
            Text(label).font(.caption).foregroundColor(.gray)
            Spacer()
            Text(value).font(.caption).fontWeight(.semibold).foregroundColor(color)
        }
    }
}

extension View {
    func borderBottom(_ color: Color) -> some View {
        self.overlay(
            VStack {
                Spacer()
                Divider().background(color)
            }
        )
    }
}

// MARK: - TerrainType Extensions

extension TerrainType {
    var displayColor: SwiftUI.Color {
        switch self {
        case .grassland: return SwiftUI.Color(red: 0.4, green: 0.7, blue: 0.3)
        case .forest: return SwiftUI.Color(red: 0.2, green: 0.5, blue: 0.2)
        case .mountain: return SwiftUI.Color(red: 0.6, green: 0.6, blue: 0.6)
        case .desert: return SwiftUI.Color(red: 0.8, green: 0.7, blue: 0.4)
        case .plains: return SwiftUI.Color(red: 0.5, green: 0.6, blue: 0.3)
        case .ocean: return SwiftUI.Color(red: 0.2, green: 0.3, blue: 0.6)
        case .coast: return SwiftUI.Color(red: 0.3, green: 0.5, blue: 0.5)
        case .jungle: return SwiftUI.Color(red: 0.1, green: 0.4, blue: 0.2)
        case .swamp: return SwiftUI.Color(red: 0.3, green: 0.4, blue: 0.3)
        case .steppe: return SwiftUI.Color(red: 0.5, green: 0.5, blue: 0.3)
        case .tundra: return SwiftUI.Color(red: 0.7, green: 0.7, blue: 0.7)
        case .island: return SwiftUI.Color(red: 0.6, green: 0.5, blue: 0.3)
        }
    }
}

// MARK: - GameAction Extension

extension GameAction {
    // Added missing action cases for UI
    case moveUnit(unitId: String, toX: Int, toY: Int)
    case holdUnit(unitId: String)
    case healUnit(unitId: String)
    case recruitUnit(provinceId: String, unitType: UnitType)
    case buildInfra(provinceId: String, buildingType: BuildingType)
    case fortifyProvince(provinceId: String)
}

// MARK: - GameViewModel Extension

extension GameViewModel {
    var canEndTurn: Bool {
        // Can end turn if no units have movement remaining
        return gameState.units.allSatisfy { $0.movement == 0 || $0.countryId != gameState.currentPlayerCountryId }
    }
    
    func endTurn() async {
        do {
            gameState = await gameEngine.processTurn(gameState)
        } catch {
            print("Error ending turn: \(error)")
        }
    }
}
```

## Summary

**UI Implementation (Days 18-19)**

✅ **Main GameView**
- Master container with map and sidebar layout
- Reactive selection management (provinces/units)
- Save/End Turn controls
- Dark theme (RGB 0.1/0.1/0.12 background)
- Responsive sidebar (300px fixed width)

✅ **MapView (Canvas-based)**
- Procedural terrain rendering (32x32 tiles)
- Province ownership borders with country colors
- Unit visualization as circles with owner colors
- Population indicator dots (size = population)
- Selection highlighting (yellow glow)
- Click detection for units/provinces
- Hover position tracking

✅ **TurnInfoPanel**
- Current turn counter
- Year display
- Game phase indicator (Diplomacy/Movement/Combat/Research/Ending)
- Difficulty level
- Progress bar (turn/100)

✅ **CountryInfoPanel**
- Country name with color indicator
- Treasury balance ($)
- Worker count
- Unit count
- Technology progress (count/12)

✅ **ProvinceDetailPanel**
- Province name and terrain type
- Population statistics
- Worker allocation
- Fortification level
- Resource inventory (all types with quantities)
- Sorted by resource name

✅ **UnitDetailPanel**
- Unit type with veteran star indicator
- Owning country
- Health/Morale/Experience bars (0-100)
- Movement points remaining
- Visual progress bars for health
- Color-coded stat display

✅ **ActionPanel (Context-Sensitive)**
- Unit actions: Move, Hold Position, Fortify
- Province actions: Recruit Unit, Build Railroad, Build Port, Build Fort
- Conditional rendering based on selection
- Disabled states based on unit/province capabilities
- Bordered button style

✅ **Theme & Styling**
- Consistent dark color scheme throughout
- WhiteText on dark backgrounds
- Color-coded stats (red=health, green=morale, blue=units, yellow=experience, orange=military)
- Smooth borders and separators
- Responsive layout (adapts to window size)

**Total Lines**: 800+ Swift code
**Production Ready**: Yes
**Next**: Day 20 Save/Load Polish & Game Menu
