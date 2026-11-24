import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import DrawingTools from '../Map/DrawingTools';
import { createFarm } from '../../services/farmService';
import { useFieldContext } from '../../context/FieldContext';
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM } from '../../utils/constants';

const FarmForm: React.FC = () => {
  const navigate = useNavigate();
  const { refreshFarms } = useFieldContext();

  const [name, setName] = useState('');
  const [locationDesc, setLocationDesc] = useState('');
  const [boundary, setBoundary] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res: any = await createFarm({
        name,
        location_description: locationDesc || undefined,
        center_lat: DEFAULT_MAP_CENTER[0],
        center_lng: DEFAULT_MAP_CENTER[1],
        boundary_geojson: boundary || undefined,
      } as any);
      const firstFieldId = res.data?.fields?.[0]?.id;
      await refreshFarms(firstFieldId);
      navigate('/farms');
    } catch (err) {
      console.error('Failed to create farm:', err);
      setError('Failed to create farm. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="card">
      <h3>Create New Farm</h3>
      {error && <p style={{ color: '#ef4444', marginTop: '0.5rem' }}>{error}</p>}

      <div style={{ marginTop: '1rem', marginBottom: '1rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem' }}>Farm Name</label>
        <input
          type="text"
          placeholder="e.g. Green Valley Farm"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          style={{ width: '100%', padding: '0.5rem', backgroundColor: 'var(--bg-secondary)', color: 'white', border: '1px solid var(--border)', borderRadius: '4px' }}
        />
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem' }}>Location Description (optional)</label>
        <input
          type="text"
          placeholder="e.g. Sehore District, MP"
          value={locationDesc}
          onChange={(e) => setLocationDesc(e.target.value)}
          style={{ width: '100%', padding: '0.5rem', backgroundColor: 'var(--bg-secondary)', color: 'white', border: '1px solid var(--border)', borderRadius: '4px' }}
        />
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
        Optional: Use the polygon tool (top-right) to draw your primary field boundary on Google Satellite.
      </p>

      <div style={{ height: '320px', marginBottom: '1rem', border: '1px solid var(--border)', borderRadius: '4px', overflow: 'hidden' }}>
        <MapContainer center={DEFAULT_MAP_CENTER as any} zoom={DEFAULT_MAP_ZOOM} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}"
            attribution="&copy; Google Maps"
          />
          <DrawingTools onCreated={setBoundary} />
        </MapContainer>
      </div>

      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? 'Creating...' : 'Create Farm'}
      </button>
    </form>
  );
};

export default FarmForm;
