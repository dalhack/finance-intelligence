import React, { useRef, useEffect, useState } from 'react';
import { useGameStore } from '@game/store';
import '../styles/GameMap.css';

export const GameMap: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const gameState = useGameStore(s => s.gameState);
  const selectProvince = useGameStore(s => s.selectProvince);
  const selectedProvince = gameState?.selectedProvince;

  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);

  useEffect(() => {
    if (!canvasRef.current || !gameState) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = '#2a5f3f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw provinces
    gameState.provinces.forEach(province => {
      const x = province.position.x * zoom + panX;
      const y = province.position.y * zoom + panY;
      const size = 15 * zoom;

      // Color based on owner
      if (province.owner) {
        const country = gameState.countries.find(c => c.id === province.owner);
        if (country) {
          ctx.fillStyle = getCountryColor(gameState.countries.indexOf(country));
        }
      } else {
        ctx.fillStyle = '#888888';
      }

      ctx.fillRect(x - size / 2, y - size / 2, size, size);

      // Highlight if selected
      if (selectedProvince?.id === province.id) {
        ctx.strokeStyle = '#ffff00';
        ctx.lineWidth = 3;
        ctx.strokeRect(x - size / 2, y - size / 2, size, size);
      }

      // Draw border
      ctx.strokeStyle = '#111111';
      ctx.lineWidth = 1;
      ctx.strokeRect(x - size / 2, y - size / 2, size, size);
    });

    // Draw units
    gameState.units.forEach(unit => {
      const x = unit.position.x * zoom + panX;
      const y = unit.position.y * zoom + panY;
      const country = gameState.countries.find(c => c.id === unit.countryId);

      if (country) {
        ctx.fillStyle = getCountryColor(gameState.countries.indexOf(country));
        ctx.beginPath();
        ctx.arc(x, y, 5 * zoom, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });
  }, [gameState, zoom, panX, panY, selectedProvince]);

  const handleCanvasClick = (e: React.MouseEvent) => {
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

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setZoom(z => Math.max(0.5, Math.min(3, z + (e.deltaY > 0 ? -0.1 : 0.1))));
  };

  return (
    <canvas
      ref={canvasRef}
      width={1000}
      height={700}
      onClick={handleCanvasClick}
      onWheel={handleWheel}
      className="game-map-canvas"
    />
  );
};

function getCountryColor(index: number): string {
  const colors = [
    '#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24',
    '#6c5ce7', '#a29bfe', '#74b9ff', '#81ecec',
    '#55efc4', '#fd79a8', '#fdcb6e', '#6c7a89',
  ];
  return colors[index % colors.length];
}
