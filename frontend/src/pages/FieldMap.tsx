import React from 'react';
import FarmMap from '../components/Map/FarmMap';

const FieldMap: React.FC = () => {
  return (
    <div style={{ height: 'calc(100vh - 120px)' }}>
      <h2>Full Field Map</h2>
      <FarmMap />
    </div>
  );
};

export default FieldMap;
