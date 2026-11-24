import React, { useState } from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import DrawingTools from '../Map/DrawingTools';
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM } from '../../utils/constants';

const FarmForm: React.FC = () => {
  const [name, setName] = useState('');
  const [boundary, setBoundary] = useState<any>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Create farm', { name, boundary });
  };

  return (
    <form onSubmit={handleSubmit} className="card">
      <h3>Create New Farm</h3>
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem' }}>Farm Name</label>
        <input 
          type="text" 
          value={name} 
          onChange={e => setName(e.target.value)} 
          required 
          style={{ width: '100%', padding: '0.5rem', backgroundColor: 'var(--bg-secondary)', color: 'white', border: '1px solid var(--border)', borderRadius: '4px' }}
        />
      </div>

      <div style={{ height: '300px', marginBottom: '1rem', border: '1px solid var(--border)', borderRadius: '4px', overflow: 'hidden' }}>
        <MapContainer center={DEFAULT_MAP_CENTER as any} zoom={DEFAULT_MAP_ZOOM} style={{ height: '100%', width: '100%' }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <DrawingTools onCreated={setBoundary} />
        </MapContainer>
      </div>

      <button type="submit" className="btn btn-primary">Create Farm</button>
    </form>
  );
};

export default FarmForm;
