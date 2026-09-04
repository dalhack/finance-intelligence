import React, { useRef, useEffect, useState } from 'react';
import { BattleUnit, HexCoordinate, CombatEngine } from '@game/combatEngine';
import '../styles/BattleScreen.css';

interface BattleScreenProps {
  side1Units: BattleUnit[];
  side2Units: BattleUnit[];
  terrain: string;
  turn: number;
  onClose: () => void;
}

const TILE_SIZE = 40;
const HEX_HEIGHT = TILE_SIZE;
const HEX_WIDTH = (Math.sqrt(3) / 2) * HEX_HEIGHT;

interface HexPixel {
  x: number;
  y: number;
}

const hexToPixel = (hex: HexCoordinate): HexPixel => {
  const x = HEX_WIDTH * (3/2 * hex.q);
  const y = HEX_HEIGHT * (Math.sqrt(3)/2 * hex.q + Math.sqrt(3) * hex.r);
  return { x, y };
};

export const BattleScreen: React.FC<BattleScreenProps> = ({
  side1Units,
  side2Units,
  terrain,
  turn,
  onClose,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selectedUnit, setSelectedUnit] = useState<BattleUnit | null>(null);

  const getTerrainBonus = (terrainType: string): number => {
    if (terrainType === 'mountain') return 1.3;
    if (terrainType === 'forest') return 1.2;
    return 1.0;
  };

  const drawHexGrid = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number
  ) => {
    ctx.strokeStyle = '#00aa00';
    ctx.lineWidth = 1;

    const cols = Math.ceil(width / HEX_WIDTH);
    const rows = Math.ceil(height / HEX_HEIGHT);

    for (let q = 0; q < cols; q++) {
      for (let r = 0; r < rows; r++) {
        drawHex(ctx, { q, r });
      }
    }
  };

  const drawHex = (ctx: CanvasRenderingContext2D, hex: HexCoordinate) => {
    const pixel = hexToPixel(hex);
    ctx.beginPath();

    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 3) * i;
      const x = pixel.x + HEX_WIDTH / 2 * Math.cos(angle);
      const y = pixel.y + HEX_HEIGHT / 2 * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    ctx.closePath();
    ctx.stroke();
  };

  const drawUnit = (
    ctx: CanvasRenderingContext2D,
    unit: BattleUnit,
    isPlayer: boolean
  ) => {
    const pixel = hexToPixel(unit.position);

    ctx.fillStyle = isPlayer ? '#0055ff' : '#ff5500';
    ctx.beginPath();
    ctx.arc(pixel.x + HEX_WIDTH / 2, pixel.y + HEX_HEIGHT / 2, 12, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#ffff00';
    ctx.font = 'bold 8px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(
      Math.ceil(unit.health / 10).toString(),
      pixel.x + HEX_WIDTH / 2,
      pixel.y + HEX_HEIGHT / 2
    );
  };

  const drawBattle = () => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#001100';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    drawHexGrid(ctx, canvas.width, canvas.height);

    side1Units.forEach(unit => drawUnit(ctx, unit, true));
    side2Units.forEach(unit => drawUnit(ctx, unit, false));

    // Draw selection highlight
    if (selectedUnit) {
      const pixel = hexToPixel(selectedUnit.position);
      ctx.strokeStyle = '#ffff00';
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i;
        const x = pixel.x + HEX_WIDTH / 2 * Math.cos(angle);
        const y = pixel.y + HEX_HEIGHT / 2 * Math.sin(angle);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();

      // Draw range indicator
      ctx.strokeStyle = 'rgba(255, 255, 0, 0.3)';
      ctx.lineWidth = 1;
      const stats = selectedUnit.unit.type;
      for (let i = 0; i <= 4; i++) {
        ctx.beginPath();
        for (let j = 0; j < 6; j++) {
          const angle = (Math.PI / 3) * j;
          const x = pixel.x + (HEX_WIDTH / 2) * (i + 1) * Math.cos(angle);
          const y = pixel.y + (HEX_HEIGHT / 2) * (i + 1) * Math.sin(angle);
          if (j === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }
    }
  };

  useEffect(() => {
    drawBattle();
  }, [selectedUnit, side1Units, side2Units]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const allUnits = [...side1Units, ...side2Units];
    for (const unit of allUnits) {
      const pixel = hexToPixel(unit.position);
      const dist = Math.sqrt(
        Math.pow(x - (pixel.x + HEX_WIDTH / 2), 2) +
        Math.pow(y - (pixel.y + HEX_HEIGHT / 2), 2)
      );

      if (dist < 15) {
        setSelectedUnit(unit);
        return;
      }
    }

    setSelectedUnit(null);
  };

  const totalSide1Health = side1Units.reduce((sum, u) => sum + u.health, 0);
  const totalSide2Health = side2Units.reduce((sum, u) => sum + u.health, 0);
  const terrainBonus = getTerrainBonus(terrain);

  return (
    <div className="battle-screen">
      <div className="battle-header">
        <h2>Battle - {terrain.charAt(0).toUpperCase() + terrain.slice(1)}</h2>
        <p>Turn {turn}</p>
      </div>

      <div className="battle-container">
        <canvas
          ref={canvasRef}
          width={800}
          height={600}
          onClick={handleCanvasClick}
          className="battle-canvas"
        />

        <div className="battle-info">
          <div className="side side1">
            <h3>Your Forces</h3>
            <p>Units: {side1Units.filter(u => u.health > 0).length}</p>
            <p>Total Health: {totalSide1Health}</p>
          </div>

          <div className="side side2">
            <h3>Enemy Forces</h3>
            <p>Units: {side2Units.filter(u => u.health > 0).length}</p>
            <p>Total Health: {totalSide2Health}</p>
          </div>

          <div className="terrain-bonus">
            <p>Terrain Defense: {(terrainBonus * 100).toFixed(0)}%</p>
          </div>

          {selectedUnit && (
            <div className="unit-details">
              <h4>Selected Unit</h4>
              <p>Type: {selectedUnit.unit.type}</p>
              <p>Health: {selectedUnit.health}</p>
              <p>Morale: {selectedUnit.morale.toFixed(0)}</p>
              <p>Experience: {selectedUnit.experience}</p>
              <p>Medals: {CombatEngine.getMedalCount(selectedUnit.experience)}</p>
              {selectedUnit.morale < 25 && (
                <p className="warning">⚠️ Low morale - unit may retreat</p>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="battle-footer">
        <button className="close-btn" onClick={onClose}>
          Continue
        </button>
      </div>
    </div>
  );
};
