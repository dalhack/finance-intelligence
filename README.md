# Imperialism - macOS Edition

A complete reimplementation of the classic Imperialism strategy game for macOS, built with Electron and React.

## Project Status

🚀 **Early Development** - Core architecture in place, game mechanics being implemented

## Features (Planned)

- ✅ Game map generation with provinces
- ✅ Country initialization and diplomacy framework
- ✅ Turn-based game loop
- 🔄 Unit movement and combat system
- 🔄 Diplomatic relations and trade
- 🔄 Technology research tree
- 🔄 Economic simulation
- 🔄 AI opponents
- 🔄 Save/load system
- 🔄 Multiplayer support

## Tech Stack

- **Frontend**: React 18 + TypeScript
- **State Management**: Zustand
- **Desktop**: Electron (macOS native app)
- **Build**: Webpack + React Scripts

## Development

### Prerequisites

- Node.js 16+ 
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Start development (runs both Electron and React dev server)
npm run dev

# Build production app
npm run build

# Create macOS distribution
npm run dist
```

### Project Structure

```
src/
├── main/                 # Electron main process
│   ├── index.ts         # App entry point
│   └── preload.ts       # Context bridge for security
├── game/                # Game engine
│   ├── store.ts         # Zustand game state store
│   ├── mapGenerator.ts  # Procedural map generation
│   └── countryInitializer.ts  # Country/faction setup
├── types/               # TypeScript types
│   └── index.ts         # Shared game types
├── components/          # React components
│   ├── App.tsx
│   ├── GameMap.tsx      # Canvas-based map renderer
│   └── GameUI.tsx       # Side panel UI
├── styles/              # CSS stylesheets
└── index.tsx           # React root
public/
└── index.html          # HTML entry point
```

## References

This implementation is based on research of open-source Imperialism projects:

- **Imperialism Remake** (https://github.com/Trilarion/imperialism-remake) - Most complete Python implementation
- Original Imperialism game mechanics and design

## Game Mechanics Overview

### Core Systems

**Turn-Based Strategy**: Players and AI take turns managing their empires during diplomatic, movement, combat, and research phases.

**Provinces**: Map is divided into provinces with:
- Resources (food, gold, production)
- Population
- Ownership and garrison units
- Names generated procedurally

**Countries**: Each faction has:
- Treasury (gold management)
- Provinces and territories
- Military units
- Technology levels
- Diplomatic relations with other countries

**Military**: Different unit types with varying capabilities:
- Infantry, Cavalry, Artillery, Navy
- Health and experience tracking
- Movement and combat systems

**Diplomacy**: Complex relations between countries:
- Trust levels
- Trade agreements
- War declarations
- Alliance systems

## License

GPL-3.0 - This project respects the open-source nature of Imperialism

## Contributing

Contributions welcome! Areas needing work:
- Combat system implementation
- AI decision making
- Diplomatic negotiation UI
- Save/load functionality
- Multiplayer networking
