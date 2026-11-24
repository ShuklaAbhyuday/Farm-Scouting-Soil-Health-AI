import React, { useState } from 'react';

const SoilSampleForm: React.FC = () => {
  const [formData, setFormData] = useState({
    nitrogen_level: 'medium',
    phosphorus_level: 'medium',
    potassium_level: 'medium',
    ph_value: 7.0,
    moisture_level: 'medium',
    soil_texture: 'Loamy',
    source: 'manual',
    is_validated: false,
    notes: ''
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Submit soil data', formData);
  };

  return (
    <form onSubmit={handleSubmit} className="card">
      <h3>⚡ Ground Truth Data — Not derived from satellite imagery</h3>
      
      <div style={{ display: 'grid', gap: '1rem', marginTop: '1rem' }}>
        <label>
          Nitrogen Level
          <select value={formData.nitrogen_level} onChange={e => setFormData({...formData, nitrogen_level: e.target.value})} style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem', backgroundColor: 'var(--bg-secondary)', color: 'white', border: '1px solid var(--border)', borderRadius: '4px' }}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>
        
        <label>
          pH Value
          <input type="number" step="0.1" value={formData.ph_value} onChange={e => setFormData({...formData, ph_value: parseFloat(e.target.value)})} style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem', backgroundColor: 'var(--bg-secondary)', color: 'white', border: '1px solid var(--border)', borderRadius: '4px' }} />
        </label>

        <label>
          <input type="checkbox" checked={formData.is_validated} onChange={e => setFormData({...formData, is_validated: e.target.checked})} />
          {' '}I confirm these values are from verified testing
        </label>

        <button type="submit" className="btn btn-primary">Save Soil Data</button>
      </div>
    </form>
  );
};

export default SoilSampleForm;
