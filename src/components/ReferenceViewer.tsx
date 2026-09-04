import React, { useState } from 'react';
import './ReferenceViewer.css';

interface ReferencePage {
  id: number;
  title: string;
  imagePath: string;
  description: string;
}

const REFERENCE_PAGES: ReferencePage[] = [
  {
    id: 1,
    title: 'Terrain & Resources',
    imagePath: '/assets/reference/page-1.png',
    description: 'Terrain types and their resource production. Shows how each terrain type generates resources with Miner, Driller, Forester, and Rancher units.',
  },
  {
    id: 2,
    title: 'Agricultural & Forest Production',
    imagePath: '/assets/reference/page-2.png',
    description: 'Agricultural terrain types (Open Range, Fertile Hills, Orchard, Plantation, Farm) and forest production with development levels.',
  },
  {
    id: 3,
    title: 'Civilian Units',
    imagePath: '/assets/reference/page-3.png',
    description: 'Civilian units including Prospector (searches for resources), Engineer (builds infrastructure), and Developer (purchases land in minor nations).',
  },
  {
    id: 4,
    title: 'Industrial Development',
    imagePath: '/assets/reference/page-4.png',
    description: 'Complete industrial production chain showing how raw materials are converted through factories into military and civilian units.',
  },
  {
    id: 5,
    title: 'Military Units',
    imagePath: '/assets/reference/page-5.png',
    description: 'All military units organized by era (I, II, III) with their stats: Firepower, Melee, Range, Defense, and Movement values.',
  },
  {
    id: 6,
    title: 'Diplomacy & Naval Units',
    imagePath: '/assets/reference/page-6.png',
    description: 'Diplomatic options (Consultes, Embassies) and naval units with their combat statistics and armor ratings.',
  },
];

export const ReferenceViewer: React.FC = () => {
  const [currentPage, setCurrentPage] = useState(0);
  const [isOpen, setIsOpen] = useState(false);

  const page = REFERENCE_PAGES[currentPage];

  const goToPage = (index: number) => {
    if (index >= 0 && index < REFERENCE_PAGES.length) {
      setCurrentPage(index);
    }
  };

  if (!isOpen) {
    return (
      <button
        className="reference-toggle"
        onClick={() => setIsOpen(true)}
        title="Open game reference"
      >
        📖 Reference
      </button>
    );
  }

  return (
    <div className="reference-viewer">
      <div className="reference-header">
        <h2>Imperialism Reference Card</h2>
        <button
          className="close-btn"
          onClick={() => setIsOpen(false)}
          title="Close reference"
        >
          ✕
        </button>
      </div>

      <div className="reference-content">
        <div className="reference-image-container">
          <img
            src={page.imagePath}
            alt={page.title}
            className="reference-image"
            onError={(e) => {
              (e.target as HTMLImageElement).src = '/assets/reference/page-1.png';
            }}
          />
        </div>

        <div className="reference-info">
          <h3>{page.title}</h3>
          <p>{page.description}</p>

          <div className="page-nav">
            <button
              className="nav-btn"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage === 0}
              title="Previous page"
            >
              ◄ Prev
            </button>

            <div className="page-indicator">
              Page {currentPage + 1} of {REFERENCE_PAGES.length}
            </div>

            <button
              className="nav-btn"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage === REFERENCE_PAGES.length - 1}
              title="Next page"
            >
              Next ►
            </button>
          </div>

          <div className="page-thumbnails">
            {REFERENCE_PAGES.map((p, idx) => (
              <button
                key={p.id}
                className={`thumbnail ${idx === currentPage ? 'active' : ''}`}
                onClick={() => goToPage(idx)}
                title={p.title}
              >
                {idx + 1}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="reference-footer">
        <small>
          Original game reference from 1997 Imperialism Quick Reference Card
        </small>
      </div>
    </div>
  );
};

export default ReferenceViewer;
