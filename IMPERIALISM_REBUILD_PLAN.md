# Original Imperialism (1992) - Complete Rebuild Plan

## Project Overview
Complete reverse engineering and faithful recreation of the 1992 Strategic Simulations, Inc. Imperialism game for macOS using React + Electron + TypeScript.

**Source**: Analyzed original 1992 game documentation, quick reference cards, manual, and GOG distribution.

---

## Phase 1: Core Game Architecture ✅ (COMPLETED)

### 1.1 Data Structures ✅
- [x] Terrain system with 12+ terrain types
- [x] Military units for 3 eras + naval units
- [x] Building/infrastructure definitions
- [x] Production chains (raw → processed → finished)
- [x] Technology definitions
- [x] Type definitions for game entities

### 1.2 Economy Engine ✅ (PARTIAL)
- [x] Production chain implementation
- [x] Resource pricing system
- [x] Worker maintenance costs
- [x] Building maintenance costs
- [ ] Trade route calculations
- [ ] Merchant marine management

---

## Phase 2: Game Initialization & Map Generation

### 2.1 Map Generation
**Objectives:**
- Generate dynamic world map (1815-1920 timeframe)
- Distribute terrain types realistically
- Place provinces across continents
- Create sea zones for naval combat

**Implementation:**
- Create `mapGenerator.ts` with procedural generation
- Implement terrain distribution algorithm
- Initialize provinces with terrain, population, resources
- Create 6 countries with starting positions and provinces

### 2.2 Game Initialization
**Objectives:**
- Create initial game state with all countries
- Assign starting resources and treasury
- Set up diplomatic relations (all neutral at start)
- Initialize technology trees (no techs researched)

**Implementation:**
- Create `gameInitializer.ts`
- Distribute starting territories across map
- Set starting treasury ($10,000-$50,000 based on difficulty)
- Initialize empty military units
- Create initial worker allocation

---

## Phase 3: Turn System & Game Flow

### 3.1 Turn Engine Enhancement
**Objectives:**
- Complete turn processing cycle
- Execute all phases in correct order
- Handle AI turns
- Calculate victory conditions

**Implementation:**
- Update `turnEngine.ts` with complete cycle:
  1. Diplomacy phase
  2. Movement phase
  3. Combat resolution phase
  4. Research phase
  5. Economic calculations
  6. Victory check
  7. End turn

### 3.2 Game Phase Management
**Objectives:**
- Implement proper phase transitions
- Restrict player actions based on phase
- Show appropriate UI for each phase

**Implementation:**
- Create `phaseManager.ts`
- Implement diplomacy phase UI
- Implement movement phase UI
- Implement combat phase UI
- Implement research phase UI

---

## Phase 4: Military System

### 4.1 Unit Recruitment & Management
**Objectives:**
- Allow recruitment of military units
- Implement unit experience/morale system
- Create unit movement system

**Implementation:**
- Create `militaryEngine.ts` with:
  - Unit recruitment from finished goods
  - Unit health/morale/experience tracking
  - Unit experience gains in combat
  - Veteran status advancement
  - Unit disbanding/merge

### 4.2 Combat System
**Objectives:**
- Implement combat calculations
- Handle unit losses and retreats
- Track combat history

**Implementation:**
- Create `combatEngine.ts`:
  - Combat resolution algorithm from reference card stats
  - Random elements (morale affects retreat chance)
  - Terrain/fortification defense bonuses
  - Technology bonuses
  - Experience-based combat modifiers
  - Naval combat system
  - Siege mechanics (forts vs units)

### 4.3 Movement System
**Objectives:**
- Implement unit movement mechanics
- Enforce movement ranges based on terrain/era
- Handle stacking rules
- Create pathfinding

**Implementation:**
- Implement movement validation
- Calculate movement range based on unit type and era
- Handle terrain costs (railroad = faster movement)
- Restrict movement through enemy territories
- Show movement ranges in UI

---

## Phase 5: Economic System

### 5.1 Resource Management
**Objectives:**
- Production from provinces based on terrain
- Processing of raw materials
- Manufacturing of finished goods

**Implementation:**
- Enhance economy engine with:
  - Terrain-based raw material production
  - Industrial facility production chains
  - Worker allocation to different tasks
  - Technology bonuses to production

### 5.2 Trade System
**Objectives:**
- Establish trade routes between countries
- Calculate trade income
- Manage imports/exports

**Implementation:**
- Create `tradeEngine.ts`:
  - Trade route establishment costs
  - Trade income calculations
  - Trade route visibility/maintenance
  - Boycott mechanics (halt trade)
  - Merchant marine management (transport capacity)

### 5.3 Infrastructure Development
**Objectives:**
- Build railroads, ports, forts
- Calculate construction times and costs
- Implement infrastructure benefits

**Implementation:**
- Create `infrastructureEngine.ts`:
  - Construction queue management
  - Railroad connectivity for trade
  - Port for naval recruitment and trade
  - Forts for defense bonuses
  - Depots for production efficiency

---

## Phase 6: Diplomatic System

### 6.1 Diplomatic Relations
**Objectives:**
- Track trust levels with other countries
- Implement war/peace mechanics
- Handle alliances and pacts

**Implementation:**
- Enhance `diplomacyEngine.ts`:
  - Trust gain/loss mechanics
  - War declaration system
  - Automatic boycott on war declaration
  - Alliance formation and dissolution
  - Trust decay over time

### 6.2 Diplomatic Actions
**Objectives:**
- Establish trade consulates
- Build embassies
- Send subsidies to minor nations
- Negotiate pacts and alliances

**Implementation:**
- Trade consulate system ($800 cost, improves relations)
- Embassy system ($5,000 cost, enables alliances)
- Subsidy mechanics (pay other countries for favors)
- Minor nation colonization (establish control)
- Petition for military intervention

---

## Phase 7: Technology System

### 7.1 Technology Research
**Objectives:**
- Research technologies in sequence
- Apply technology bonuses
- Manage research queue

**Implementation:**
- Enhance `technologyEngine.ts`:
  - Research turn calculations
  - Technology prerequisites
  - Bonus application (combat, production, movement)
  - Technology unlock of new units/buildings
  - Player choice on which tech to research

### 7.2 Technology Effects
**Objectives:**
- Combat bonus technologies
- Production efficiency technologies
- Military era advancement

**Implementation:**
- Create technology bonus system:
  - Musketry → Infantry combat +10%
  - Industrialization → Production +25%
  - Steam Power → Naval bonuses
  - Mechanization → Enables Era III units
  - Railroads → Movement +2

---

## Phase 8: Victory System

### 8.1 Victory Conditions
**Objectives:**
- Implement 4 victory paths
- Track progress toward each victory
- Detect victory condition met

**Implementation:**
- Enhance `victoryEngine.ts` with:
  - **Conquest Victory**: Control 60% of world's provinces
  - **Economic Victory**: Accumulate $100,000+ treasury
  - **Technology Victory**: Research 12 key technologies
  - **Time Victory**: Reach year 1920 (game end)
  - Real-time progress tracking

### 8.2 Victory Display
**Objectives:**
- Show current progress on all victory conditions
- Display victory screen with final statistics
- Show AI country progress

**Implementation:**
- Update `VictoryDisplay.tsx` with:
  - Progress bars for all 4 conditions
  - Winner announcement screen
  - Final statistics display
  - Game over screen

---

## Phase 9: AI System

### 9.1 AI Decision Making
**Objectives:**
- Create intelligent AI strategies
- Handle resource management
- Plan military campaigns
- Manage diplomacy

**Implementation:**
- Enhance `aiEngine.ts`:
  - Victory condition prioritization (AI picks target condition)
  - Economic management (production planning)
  - Military planning (unit recruitment, movement, combat)
  - Diplomatic strategy (alliance forming, trades)
  - Technology research planning

### 9.2 AI Execution
**Objectives:**
- Execute AI decisions into game actions
- Handle unit movement and combat
- Process AI trades and diplomacy

**Implementation:**
- Enhance `aiExecutor.ts`:
  - Unit recruitment execution
  - Unit movement execution
  - Combat engagement execution
  - Trade route establishment
  - Diplomatic action execution

---

## Phase 10: UI System

### 10.1 Map Rendering
**Objectives:**
- Render game map with all provinces
- Show unit positions
- Display terrain types and development
- Show ownership/colors

**Implementation:**
- Enhance `GameMap.tsx`:
  - SVG-based map rendering
  - Terrain visualization
  - Unit position indicators
  - Province ownership colors
  - Sea zone representation
  - Province selection/inspection

### 10.2 Information Panels
**Objectives:**
- Show country statistics
- Display province details
- Show diplomatic status
- Show technology progress

**Implementation:**
- Create info panels:
  - `StatusPanel` - Current resources, treasury, workers
  - `ProvincePanel` - Selected province details
  - `DiplomacyPanel` - Relations with other countries
  - `TechnologyPanel` - Research progress
  - `MilitaryPanel` - Unit list and status

### 10.3 Action UI
**Objectives:**
- Allow player to execute actions
- Show available actions based on game state
- Provide feedback on action results

**Implementation:**
- Enhance `ActionPanel.tsx`:
  - Movement commands
  - Combat commands
  - Construction commands (buildings/units)
  - Research selection
  - Diplomatic actions
  - Trade establishment

### 10.4 Game Menu & Settings
**Objectives:**
- Provide game controls
- Allow save/load (future)
- Settings management

**Implementation:**
- Create menu system:
  - Main menu
  - Game pause/resume
  - Settings (music volume, etc.)
  - Game speed controls
  - End turn button

---

## Phase 11: Audio System

### 11.1 Music Management
**Objectives:**
- Play phase-appropriate music
- Handle music transitions
- Allow music control

**Implementation:**
- Integrate original soundtrack:
  - Menu music
  - Diplomacy phase music
  - Movement phase music
  - Combat phase music
  - Victory/defeat music
  - Ambient background music

### 11.2 Sound Effects
**Objectives:**
- Add combat sounds
- Add UI feedback sounds
- Add unit movement sounds

**Implementation:**
- Source original SFX or create faithful recreations

---

## Phase 12: Polish & Optimization

### 12.1 Performance Optimization
- Optimize map rendering
- Optimize turn calculations
- Optimize AI decision making

### 12.2 Bug Fixes & Balance
- Balance military unit stats
- Balance technology progression
- Balance resource availability
- Test all game mechanics

### 12.3 DOS-Style UI Recreation
- Recreate original game's visual style
- Implement retro color scheme (#000080 blue, #00aa00 green, #aaaa00 yellow)
- Create authentic font styling
- Add original UI elements

---

## Implementation Order (Priority)

### Critical Path (Required for playable game):
1. Map generation → Game initialization
2. Turn engine & phase management
3. Movement & combat systems
4. Military recruitment & basic production
5. Basic UI for map & actions
6. Victory condition checking

### High Priority (Core gameplay):
7. Complete economy system
8. Technology research system
9. Diplomatic system with war/peace
10. Infrastructure building

### Medium Priority (Game depth):
11. AI system
12. Trade routes
13. Advanced combat (fortifications, naval)
14. Province development system

### Polish (Final):
15. UI refinement
16. Audio integration
17. Game balance
18. Save/load functionality

---

## Technology Stack

- **Frontend**: React 18 + TypeScript
- **Desktop**: Electron
- **State Management**: Zustand
- **Rendering**: SVG for maps, Canvas for complex rendering
- **Build**: Vite

---

## File Structure to Create/Modify

```
src/
├── game/
│   ├── data/
│   │   ├── terrainData.ts ✅
│   │   ├── militaryData.ts ✅
│   │   ├── buildingsData.ts ✅
│   │   └── gameTypes.ts ✅
│   ├── economyEngine.ts ✅ (PARTIAL)
│   ├── mapGenerator.ts (TODO)
│   ├── gameInitializer.ts (TODO)
│   ├── phaseManager.ts (TODO)
│   ├── militaryEngine.ts (TODO)
│   ├── combatEngine.ts (TODO)
│   ├── tradeEngine.ts (TODO)
│   ├── infrastructureEngine.ts (TODO)
│   ├── diplomacyEngine.ts (PARTIAL)
│   ├── technologyEngine.ts (TODO)
│   ├── victoryEngine.ts (PARTIAL)
│   ├── aiEngine.ts (PARTIAL)
│   ├── aiExecutor.ts (PARTIAL)
│   ├── turnEngine.ts (PARTIAL)
│   └── store.ts ✅
├── components/
│   ├── GameMap.tsx (TODO: enhance)
│   ├── GameUI.tsx (TODO: enhance)
│   ├── ActionPanel.tsx (TODO: enhance)
│   ├── StatusPanel.tsx (TODO)
│   ├── ProvincePanel.tsx (TODO)
│   ├── DiplomacyPanel.tsx (PARTIAL)
│   ├── TechnologyPanel.tsx (TODO)
│   ├── MilitaryPanel.tsx (TODO)
│   ├── VictoryDisplay.tsx ✅
│   └── MusicPlayer.tsx ✅
└── styles/
    └── App.css (TODO: enhance)
```

---

## Estimated Effort

- **Phase 1 (Data)**: 2 hours ✅ DONE
- **Phase 2 (Initialization)**: 3 hours
- **Phase 3 (Turn System)**: 4 hours
- **Phase 4 (Military)**: 8 hours
- **Phase 5 (Economy)**: 6 hours
- **Phase 6 (Diplomacy)**: 5 hours
- **Phase 7 (Technology)**: 4 hours
- **Phase 8 (Victory)**: 3 hours
- **Phase 9 (AI)**: 6 hours
- **Phase 10 (UI)**: 8 hours
- **Phase 11 (Audio)**: 2 hours
- **Phase 12 (Polish)**: 4 hours

**Total Estimated**: ~55 hours of development

---

## Success Criteria

✅ Game can be launched and initialized
✅ Map is generated with 6 countries and provinces
✅ Players can move units, manage resources, and recruit armies
✅ Combat system works with realistic outcomes
✅ Trade routes generate income
✅ Technology research advances civilization
✅ Diplomacy allows alliances and wars
✅ Victory conditions are tracked and can be won
✅ AI opponents play competitively
✅ UI is functional and reflects original game's retro style
✅ Game loop runs smoothly without freezing
✅ All original game mechanics are faithfully recreated

---

## Notes

- All systems based on 1992 original game documentation
- Quick reference card provides exact unit stats and building costs
- Original game manual provides complete rule set
- Retro DOS aesthetic is core to the experience
- Game should feel authentic to original while running on modern hardware
