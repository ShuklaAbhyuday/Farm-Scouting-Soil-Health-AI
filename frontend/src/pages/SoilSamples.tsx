import React from 'react';
import SoilSampleForm from '../components/Forms/SoilSampleForm';

const SoilSamples: React.FC = () => {
  return (
    <div>
      <h2>Soil Data Management</h2>
      <div className="warning-banner" style={{ backgroundColor: 'rgba(59,130,246,0.2)', padding: '1rem', borderRadius: '8px', marginBottom: '2rem' }}>
        📋 Ground Truth Data — These values are from physical soil testing, not satellite imagery
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        <SoilSampleForm />
        <div className="card">
          <h3>Recent Samples</h3>
          <p>No recent samples available.</p>
        </div>
      </div>
    </div>
  );
};

export default SoilSamples;
