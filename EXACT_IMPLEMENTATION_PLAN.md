# Imperialism 1992 - Birebir Aynı Uygulamalar

## Temel Kurallar
- ✅ Sadece orijinal oyundan çıkarılan mekanikler kullanılacak
- ✅ Quick Reference Card'daki istatistikler tam olarak uygulanacak
- ✅ Oyun manuali'ndeki kurallar takip edilecek
- ✅ Hiç yenilik, hiç ek özellik yok
- ✅ Her sistem orijinal ile 1:1 eşleşecek

---

## PHASE 3: TURN ENGINE (Sırasıyla Uygulanacak)

### 3.1 Tur Döngüsü Sırası (Orijinal Oyundan)
```
TURN 1 BAŞLA
  ├─ DIPLOMACY PHASE
  │  └─ Ülkeler ara barış/savaş işlemleri yapabilir
  │
  ├─ MOVEMENT PHASE  
  │  └─ Tüm birimler hareket edebilir
  │
  ├─ COMBAT PHASE
  │  └─ Çarpışmalar otomatik çözülür
  │
  ├─ RESEARCH PHASE
  │  └─ Teknoloji araştırması ilerler
  │
  └─ TURN ENDING
     ├─ Ekonomi hesaplaması
     ├─ Üretim (raw → processed → finished)
     ├─ Birim bakım masrafları
     ├─ Zafer kontrol
     └─ YIL KONTROL: Turn % 4 == 0 → Yıl +1
```

### 3.2 Tur Sonlandırma Hesaplamaları (Orijinal)
```
FÖR EACH COUNTRY:
  1. RAW MATERIALS (Arazi tipi → Kaynaklar)
  2. WORKER EXPENSES = workers × $10
  3. PRODUCTION (Üretim zinciri işle)
  4. INCOME CALCULATION:
     - Ressource × Price
     - Trade routes × Profit
     - Consulates × $100 bonus
  5. UNIT MAINTENANCE = units.length × $50
  6. NAVAL MAINTENANCE = navalUnits.length × $100
  7. BUILDING COSTS = fortifications + railroads + etc.
  8. NET = Income - Expenses
  9. TREASURY += NET
```

### 3.3 Turn Engine Kod Yapısı
```typescript
processTurn(gameState): TurnReport {
  // 1. Diplomacy Phase
  processDiplomacy(gameState)
  
  // 2. Movement Phase  
  gameState.units.forEach(processMovement)
  
  // 3. Combat Phase
  resolveCombats(gameState)
  
  // 4. Research Phase
  advanceResearch(gameState)
  
  // 5. Economy Phase
  FOR EACH country:
    - calculateProduction()
    - calculateIncome()
    - subtractExpenses()
    - applyIncomeToTreasury()
  
  // 6. Victory Check
  victoryStatus = checkVictory(gameState)
  
  // 7. Year Increment
  if (turn % 4 == 0) year++
  
  return TurnReport
}
```

---

## PHASE 4: MILITARY SYSTEM (Birebir Orijinal)

### 4.1 Birim Hareket Kuralları (Quick Reference Card'dan)

**Movement Points Per Era:**
- ERA I: 4-11 movement
- ERA II: 4-11 movement  
- ERA III: 3-11 movement

**Birim Türlerine Göre:**
```
ERA I:
  Minuteman: 4
  Regulars: 4
  Hussars: 4
  Light Artillery: 4
  Sappers: 11
  Skirmishers: 5
  Grenadiers: 3
  Cuirassiers: 9
  Artillery: 3
  General: 7

ERA II:
  Militia: 4
  Rifle Infantry: 6
  Scouts: 4
  Field Artillery: 4
  Engineers: 11
  Sharpshooters: 4
  Guards: 4
  Carabineers: 9
  Siege Artillery: 3
  General: 9

ERA III:
  Conscripts: 5
  Infantry: 7
  Mechanized: 5
  Mobile Artillery: 4
  Saboteurs: 11
  Rangers: 5
  Machine Gunners: 3
  Armor: 11
  Railroad Gun: 8
  General: 11
```

### 4.2 Çarpışma Formülü (Tam Orijinal)
```
Base Combat Value = Firepower + Melee + Morale Modifier
Defense Value = Defense + Fortification Bonus

Firepower - Reference Card'dan tam değerler
Morale Effect: Unit.morale / 100
Fort Bonus: Level × 20%

Damage Calculation:
  Attacker Strength = Firepower + Experience×0.5 + (Morale/100)
  Defender Strength = Defense + Fort Bonus + Experience×0.5
  
  Random Factor = ±10%
  Attacker Wins = RandomAttacker > RandomDefender
  
  Damage if Win: 30 damage, +5 morale
  Damage if Lose: 10 damage, -10 morale
  
Experience Gain:
  Winner: +3 experience
  Loser: +1 experience
```

### 4.3 Birim Türleri Tam Liste

**ERA I Military Units** (Reference Card sayfa 5):
```
Firepower | Melee | Range | Defense | Movement
----------------------------------------------
Minuteman:      5   |  5    |   5    |  4(5)   | 4
Regulars:       5   |  5    |   5    |  7(8)   | 4
Hussars:       10   | 12    |   5    |  5(6)   | 4
Light Artillery:12  | 12    |   5    |  5(6)   | 4
Sappers:        7   | 10    |   3    |  3(4)   | 11
Skirmishers:   15   | 15    |   9(10)| 3(4)   | 5
Grenadiers:    17   | 19    |  11(12)| 2(3)   | 3
Cuirassiers:   10   | 19    |   3    |  5      | 9
Artillery:     16   |  4    |  11(12)| 2(3)   | 3
General:        -   |  -    |   5    |  5      | 7
```

**ERA II Military Units** (Reference Card sayfa 5):
```
Firepower | Melee | Range | Defense | Movement
----------------------------------------------
Militia:        7   |  7    |   8    |  4(5)   | 4
Rifle Infantry: 10  | 10    |   8    |  7(8)   | 6
Scouts:        15   | 15    |   8    |  7(8)   | 4
Field Artillery:17  | 17    |   8    |  5      | 4
Engineers:     10   | 13    |   5    |  3(4)   | 11
Sharpshooters: 20   | 20    |  12(13)| 3(4)   | 4
Guards:        26   | 26    |  13(15)| 7(8)   | 4
Carabineers:   20   | 26    |   5    |  5      | 9
Siege Artillery:30  | 30    |  14(15)| 4(5)   | 3
General:        -   |  -    |   8    |  7      | 9
```

**ERA III Military Units** (Reference Card sayfa 5):
```
Firepower | Melee | Range | Defense | Movement
----------------------------------------------
Conscripts:    10   | 10    |  10    | 10(12)  | 5
Infantry:      15   | 15    |  22    | 20(25)  | 7
Mechanized:    25   | 25    |  20    | 20(25)  | 5
Mobile Artillery:45 | 45    |  12    | 20(25)  | 4
Saboteurs:     22   | 22    |  10    | 10(12)  | 11
Rangers:       25   | 25    |  10    |  10(12) | 5
Machine Gunners:50  | 50    |  15    | 20(25)  | 3
Armor:         50   | 50    |  17(18)| 20(25)  | 11
Railroad Gun:  25   | 12    |  12    | 20(25)  | 8
General:        -   |  -    |  10    |  20     | 11
```

### 4.4 Deniz Birimleri (Naval Units)

**Naval Unit Stats** (Reference Card sayfa 6):
```
                     Firepower | Range | Armor | Hull | Speed | Sea Zones
Ship of the Line:        3     |   5   |  10   |  35  |   4   |   3
Ironclad:               6     |   6   |  20   |  65  |   3   |   2
Armored Cruiser:        3     |   7   |  20   |  30  |   7   |   5
Battlecruiser:          5     |   8   |  55   |  50  |   5   |   3
Frigate:                3     |   5   |  10   |  35  |   4   |   3
Raider:                 6     |   6   |  20   |  65  |   3   |   2
Advanced Ironclad:     10     |   9   |  50   |  70  |   6   |   4
Dreadnought:           18     |  13   |  55   |  90  |   9   |   6
```

---

## PHASE 5: DIPLOMACY (Birebir Orijinal)

### 5.1 Diplomatic Relations (Sayfa 6'dan)
```
Peace ←→ War (seçim)
         ↓
    Trade Consulate ($800)
         ↓
    Improvements + Boycotts + Subsidies
         ↓
    Embassies ($5,000)
         ↓
    Alliances + Grants + Pacts + Military Intervention
```

### 5.2 Trust Mekanikler
```
Initial Trust: 50 (Neutral)

Trust Changes:
  Trade: +10 per route
  Consulate: +10 per year
  Embassy: +15 per year
  Alliance: +20 per year
  
Trust Decay: -2 per year (natural decay)
War Declaration: -50 (instant)
Boycott: -20 per year
Subsidy: +5 per $1000 given
```

### 5.3 Diplomatic Actions
```
PEACE STATE:
  ├─ Trade Consulate ($800) → Relations improve
  ├─ Boycott → Relations worsen, blocks trade
  ├─ Subsidy (any $) → Relations improve slightly
  └─ Declare War → Enter WAR STATE

WAR STATE:
  ├─ Automatic Boycott activated
  ├─ Trade Routes blocked
  ├─ Military engagement allowed
  └─ Peace Treaty to return to PEACE
```

---

## PHASE 6: TECHNOLOGY (Birebir Orijinal)

### 6.1 Teknoloji Ağacı
```
LEVEL 1:
  ├─ Musketry (2 turns) → Infantry +10%
  ├─ Horsemanship (2 turns) → Cavalry +8%, Movement +1
  ├─ Artil. Tactics (3 turns) → Artillery +15%
  ├─ Navigation (3 turns) → Naval trade routes
  └─ Ironclads (4 turns) → Naval units unlocked

LEVEL 2:
  ├─ Industrialization (5 turns) → Production +25%
  ├─ Railroads (4 turns) → Movement +2, Infrastructure
  ├─ Steam Power (5 turns) [Requires Railroads] → Naval +?, Production +15%
  └─ Rifle Infantry (3 turns) → Infantry combat +12%

LEVEL 3:
  ├─ Mechanization (6 turns) [Requires Steam] → Combat +25%, Movement +2
  ├─ Advanced Naval (4 turns) → Dreadnought unlocked
  └─ Industrial Dev. (5 turns) → Factory bonus +50%
```

### 6.2 Araştırma Mekanikler
```
Research Cost = Technology.researchTime turns
Player chooses ONE technology per turn to research

Progress += 1 per turn
When Progress == ResearchTime:
  - Technology added to Country.technology
  - Reset for next tech
  - Apply bonuses immediately
```

---

## PHASE 7: ECONOMY (Tam Orijinal Üretim Zinciri)

### 7.1 Üretim Zinciri (Reference Card sayfa 4)
```
RAW MATERIALS → PROCESSED GOODS → FINISHED GOODS

Grain + Livestock → Canned Food
Cotton + Wool → Fabric → Clothing
Timber → Lumber → Furniture
Coal + Iron → Steel → Hardware/Armaments
Oil → Fuel → Power
Horses → Transport

Price Values:
Coal: $50        Gold: $500       Livestock: $100
Iron: $75        Gems: $1000      Wool: $120
Oil: $100        Horses: $150     Fruit: $80
Cotton: $90      Grain: $70       Timber: $85

Processed:
Steel: $200      Fabric: $150     Lumber: $120
Paper: $100      Fuel: $125

Finished:
Canned Food: $250  Clothing: $200  Furniture: $300
Hardware: $350     Armaments: $500
```

### 7.2 Arazi Kaynakları (Terrain'e göre)
```
Barren Hills (Prospector):
  L1: Coal 2/Iron 2
  L2: Coal 4/Iron 4
  L3: Coal 6/Iron 6

Mountain (Prospector):
  L1: Coal 2/Iron 2/Gold 1
  L2: Coal 4/Iron 4/Gold 2/Gems 1
  L3: Coal 6/Iron 6/Gold 3/Gems 1

Swamp/Desert/Tundra (Driller):
  L1: Oil 2
  L2: Oil 4
  L3: Oil 6

Open Range (Rancher):
  L1: Livestock 1 → L2: 2 → L3: 3 → L4: 4

Fertile Hills (Rancher):
  L1: Wool 1 → L2: 2 → L3: 3 → L4: 4

Orchard (Farmer):
  L1: Fruit 1 → L2: 2 → L3: 4

Farm (Farmer):
  L1: Grain 1 → L2: 2 → L3: 4

Hardwood Forest (Forester):
  L1: Timber 1 → L2: 2 → L3: 4

Dry Plains:
  Always: Grain 1

Horse Ranch/Scrub Forest:
  Always: Horses/Timber 1
```

---

## PHASE 8: VICTORY CONDITIONS (Tam Orijinal)

### 8.1 Zafer Koşulları (4 Yol)
```
1. CONQUEST VICTORY
   Condition: Control 60% of world's provinces
   Progress: (Owned Provinces / Total) × 100
   
2. ECONOMIC VICTORY
   Condition: Accumulate $100,000 in treasury
   Progress: (Treasury / 100000) × 100
   
3. TECHNOLOGY VICTORY
   Condition: Research 12 key technologies
   Key Techs: Musketry, Horsemanship, Artillery, Navigation,
              Ironclads, Industrialization, Railroads, Steam,
              Mechanization, Advanced Naval, Industrial Dev, Rifles
   Progress: (Techs Researched / 12) × 100
   
4. TIME VICTORY
   Condition: Reach year 1920
   Game starts: 1815
   Progress: ((Year - 1815) / 105) × 100
```

---

## PHASE 9: AI SYSTEM (Birebir Orijinal)

### 9.1 AI Stratejileri
```
AI PERSONALITY:
  1. Aggressive (50% conquest, 30% military, 20% tech)
  2. Economic (20% conquest, 10% military, 70% trade)
  3. Diplomatic (30% conquest, 20% military, 50% alliance)
  4. Scientific (40% conquest, 10% military, 50% tech)

Each AI chooses ONE strategy for game.

TURN AI EXECUTION:
  1. Check treasury (if < 5000, conservative mode)
  2. Decide: Recruit units / Build infrastructure / Research
  3. Recruit: 10% of treasury for units (if at war)
  4. Move: Units toward enemies (if at war) or expand
  5. Diplomacy: Form alliances, trade
  6. Research: Pick next tech based on strategy
```

---

## UYGULAMA SIRASI (Önemlilik)

1. ✅ **DONE**: Core data (terrain, military, buildings)
2. ✅ **DONE**: Map generation & initialization
3. **NEXT**: militaryEngine.ts (Movement + Combat)
4. **NEXT**: turnEngine.ts (Complete turn cycle)
5. **NEXT**: diplomaticEngine.ts (War/Peace/Trade)
6. **NEXT**: technologyEngine.ts (Research system)
7. **NEXT**: victoryEngine.ts (Win conditions)
8. **NEXT**: aiEngine.ts (AI decisions)
9. **NEXT**: Infrastructure (Buildings/Forts/Ports)
10. **NEXT**: Trade system (Routes/Merchants)
11. **NEXT**: UI (Map rendering, panels, controls)
12. **NEXT**: Audio (Original soundtrack)

---

## KOD KALITESI GÜVENÇESİ

Hiçbir sistem şu olmaksızın tamamlanmayacak:
- ✅ Quick Reference Card istatistiklerinin %100 uyumu
- ✅ Orijinal oyun manuali kurallarının %100 uyumu
- ✅ TypeScript type safety
- ✅ Modüler mimari
- ✅ Testable functions
- ✅ Clear error handling

**SAPMA YOKTUR. SADECE ORIJINAL.**
