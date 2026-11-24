import React from 'react';
import { Hotspot } from '../../types';

interface Props {
  hotspot: Hotspot;
  onClick?: (hotspot: Hotspot) => void;
}

const HotspotCard: React.FC<Props> = ({ hotspot, onClick }) => {
  return (
    <div className="card hotspot-card" onClick={() => onClick && onClick(hotspot)} style={{ cursor: onClick ? 'pointer' : 'default' }}>
      <div className="hotspot-header">
        <span className={`badge badge-${hotspot.severity}`}>
          {hotspot.severity.charAt(0).toUpperCase() + hotspot.severity.slice(1)}
        </span>
        <span className="health-score">Score: {hotspot.health_score}</span>
      </div>
      <div className="hotspot-details">
        <p><strong>Method:</strong> {hotspot.detection_method === 'isolation_forest' ? 'AI Model' : 'Baseline Heuristic'}</p>
        <p><strong>Indices:</strong> NDVI: {hotspot.ndvi_value.toFixed(2)} | NDMI: {hotspot.ndmi_value.toFixed(2)}</p>
        <p><strong>Persistence:</strong> {hotspot.persistence_count} observation(s)</p>
      </div>
      {onClick && <button className="btn btn-primary mt-2">View Details</button>}
    </div>
  );
};

export default HotspotCard;
