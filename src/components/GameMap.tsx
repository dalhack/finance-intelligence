import React, { useRef, useEffect, useState } from 'react';
import { useGameStore } from '@game/store';
import '../styles/GameMap.css';

/* DOS/Imperialism 1 Color Palette */
const DOS_PALETTE = {
  green: '#00aa00',
  lightGreen: '#55ff55',
  darkGreen: '#005500',
  brown: '#aa5500',
  lightBrown: '#ffaa55',
  gray: '#555555',
  lightGray: '#aaaaaa',
  white: '#ffffff',
  darkBlue: '#000055',
  blue: '#0000ff',
  cyan: '#00aaaa',
  yellow: '#ffff00',
};

const COUNTRY_COLORS = [
  '#aa00aa', // Magenta
  '#0000aa', // Blue
  '#00aaaa', // Cyan
  '#aa5500', // Brown
  '#aa00aa', // Purple
  '#005500', // Dark Green
];

export const GameMap: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const gameState = useGameStore(s => s.gameState);
  const selectProvince = useGameStore(s => s.selectProvince);
  const selectedProvince = gameState?.selectedProvince;

  const [zoom, setZoom] = useState(1.5);
  const [panX, setPanX] = useState(50);
  const [panY, setPanY] = useState(50);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!canvasRef.current || !gameState) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    // Clear with DOS dark green
    ctx.fillStyle = DOS_PALETTE.darkGreen;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid lines
    ctx.strokeStyle = DOS_PALETTE.darkBlue;
    ctx.lineWidth = 1;
    for (let i = 0; i < canvas.width; i += 20) {
      ctx.beginPath();
      ctx.moveTo(i + panX, 0);
      ctx.lineTo(i + panX, canvas.height);
      ctx.stroke();
    }
    for (let i = 0; i < canvas.height; i += 20) {
      ctx.beginPath();
      ctx.moveTo(0, i + panY);
      ctx.lineTo(canvas.width, i + panY);
      ctx.stroke();
    }

    // Draw provinces
    gameState.provinces.forEach(province => {
      const x = province.position.x * zoom + panX;
      const y = province.position.y * zoom + panY;
      const size = 20 * zoom;

      // Determine province color
      let fillColor = DOS_PALETTE.gray; // Unclaimed
      if (province.owner) {
        const countryIdx = gameState.countries.findIndex(c => c.id === province.owner);
        fillColor = COUNTRY_COLORS[countryIdx % COUNTRY_COLORS.length];
      }

      // Draw province square
      ctx.fillStyle = fillColor;
      ctx.fillRect(x - size / 2, y - size / 2, size, size);

      // Draw province border
      ctx.strokeStyle = DOS_PALETTE.lightGray;
      ctx.lineWidth = 1;
      ctx.strokeRect(x - size / 2, y - size / 2, size, size);

      // Highlight if selected
      if (selectedProvince?.id === province.id) {
        ctx.strokeStyle = DOS_PALETTE.yellow;
        ctx.lineWidth = 2;
        ctx.strokeRect(x - size / 2 - 2, y - size / 2 - 2, size + 4, size + 4);
      }

      // Draw infrastructure indicators
      if (zoom > 1.0 && province.owner) {
        let infraText = '';
        if (province.infrastructure.hasRailroad) infraText += 'R';
        if (province.infrastructure.hasPort) infraText += 'P';
        if (province.infrastructure.industrialized) infraText += 'I';
        if (infraText) {
          ctx.fillStyle = DOS_PALETTE.cyan;
          ctx.font = `bold 8px 'MS Sans Serif', Arial, monospace`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillText(infraText, x, y - size / 2 + 2);
        }
      }

      // Draw province name (if zoom allows)
      if (zoom > 0.8) {
        ctx.fillStyle = DOS_PALETTE.yellow;
        ctx.font = `bold 10px 'MS Sans Serif', Arial, monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const shortName = province.name.split(' ')[0].substring(0, 3);
        ctx.fillText(shortName, x, y);
      }

      // Draw garrison count if zoom in and has units
      if (zoom > 1.0) {
        const garrisonCount = province.garrisonUnits.length;
        if (garrisonCount > 0) {
          ctx.fillStyle = DOS_PALETTE.lightBrown;
          ctx.font = `bold 8px 'MS Sans Serif', Arial, monospace`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(`[${garrisonCount}]`, x, y + size / 2 - 1);
        }
      }
    });

    // Draw units
    gameState.units.forEach(unit => {
      const x = unit.position.x * zoom + panX;
      const y = unit.position.y * zoom + panY;
      const countryIdx = gameState.countries.findIndex(c => c.id === unit.countryId);
      const unitColor = COUNTRY_COLORS[countryIdx % COUNTRY_COLORS.length];

      // Draw unit as small circle with border
      ctx.fillStyle = unitColor;
      ctx.beginPath();
      ctx.arc(x, y, 4 * zoom, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = DOS_PALETTE.white;
      ctx.lineWidth = 1;
      ctx.stroke();
    });
  }, [gameState, zoom, panX, panY, selectedProvince]);

  const handleCanvasClick = (e: React.MouseEvent) => {
    if (isDragging) return;
    if (!canvasRef.current || !gameState) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const clickX = (e.clientX - rect.left - panX) / zoom;
    const clickY = (e.clientY - rect.top - panY) / zoom;

    // Find clicked province
    const clicked = gameState.provinces.find(p => {
      const dx = p.position.x - clickX;
      const dy = p.position.y - clickY;
      return Math.sqrt(dx * dx + dy * dy) < 10;
    });

    if (clicked) {
      selectProvince(clicked);
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 2 || e.ctrlKey) { // Right click or Ctrl+click for panning
      setIsDragging(true);
      setDragStart({ x: e.clientX - panX, y: e.clientY - panY });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPanX(e.clientX - dragStart.x);
      setPanY(e.clientY - dragStart.y);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.max(0.5, Math.min(4, z * zoomFactor)));
  };

  return (
    <canvas
      ref={canvasRef}
      width={1000}
      height={700}
      onClick={handleCanvasClick}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
      onContextMenu={e => e.preventDefault()}
      className="game-map-canvas"
      title="Left-click: select. Right-click/Ctrl+drag: pan. Wheel: zoom"
    />
  );
};
