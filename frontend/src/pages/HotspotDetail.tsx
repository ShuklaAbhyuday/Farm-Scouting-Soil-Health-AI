import React from 'react';
import FarmMap from '../components/Map/FarmMap';

const HotspotDetail: React.FC = () => {
  return (
    <div>
      <h2>Hotspot Details</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        <div className="card">
          <h3>Information</h3>
          <p>Detection Method: AI Model (Isolation Forest)</p>
          <p>Severity: Moderate</p>
        </div>
        <div>
          <FarmMap />
        </div>
      </div>
    </div>
  );
};

export default HotspotDetail;
