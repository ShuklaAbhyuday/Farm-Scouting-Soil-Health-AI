import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FarmMap from '../components/Map/FarmMap';
import { useFieldContext } from '../context/FieldContext';
import { createField, getField } from '../services/fieldService';
import { getHotspots } from '../services/hotspotService';
import { CROP_TYPES, GROWTH_STAGES } from '../utils/constants';
import { Field, Hotspot } from '../types';

const FieldMap: React.FC = () => {
  const navigate = useNavigate();
  const { selectedFarmId, selectedFieldId, refreshFarms } = useFieldContext();

  const [field, setField] = useState<Field | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [drawnBoundary, setDrawnBoundary] = useState<any>(null);
  const [newName, setNewName] = useState('');
  const [cropType, setCropType] = useState(CROP_TYPES[0]);
  const [growthStage, setGrowthStage] = useState(GROWTH_STAGES[1]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [fRes, hRes] = await Promise.all([
          getField(selectedFieldId),
          getHotspots(selectedFieldId).catch(() => ({ data: [] })),
        ]);
        setField(fRes.data);
        setHotspots(hRes.data || []);
      } catch (err) {
        console.error('Failed to load map data:', err);
      }
    };
    load();
  }, [selectedFieldId]);

  const handleSaveNewField = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!drawnBoundary || !newName.trim()) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await createField(selectedFarmId, {
        name: newName.trim(),
        boundary_geojson: drawnBoundary,
        crop_type: cropType,
        growth_stage: growthStage,
      });
      setDrawnBoundary(null);
      setNewName('');
      await refreshFarms(res.data.id);
      setMessage(`Saved field "${res.data.name}"! Switched active field to it.`);
    } catch (err) {
      console.error('Failed to save field:', err);
      setMessage('Error saving field. Please check backend connection.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2>Full Field Map {field ? `— ${field.name}` : ''}</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Use the polygon tool (top-right of map) to draw a new field boundary, or click a colored hotspot zone to inspect AI details.
          </p>
        </div>
      </div>

      {message && (
        <div style={{ backgroundColor: 'rgba(34,197,94,0.15)', border: '1px solid #22c55e', padding: '0.75rem 1rem', borderRadius: '8px' }}>
          ✅ {message}
        </div>
      )}

      {drawnBoundary && (
        <form onSubmit={handleSaveNewField} className="card" style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem' }}>New Field Name</label>
            <input
              type="text"
              placeholder="e.g. South Soybean Block"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              required
              style={{ width: '100%', padding: '0.5rem', backgroundColor: 'var(--bg-input)', color: 'white', border: '1px solid var(--border)', borderRadius: '6px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem' }}>Crop Type</label>
            <select
              value={cropType}
              onChange={(e) => setCropType(e.target.value)}
              style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', color: 'white', border: '1px solid var(--border)', borderRadius: '6px' }}
            >
              {CROP_TYPES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem' }}>Growth Stage</label>
            <select
              value={growthStage}
              onChange={(e) => setGrowthStage(e.target.value)}
              style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', color: 'white', border: '1px solid var(--border)', borderRadius: '6px' }}
            >
              {GROWTH_STAGES.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : '💾 Save Drawn Field'}
          </button>
          <button type="button" className="btn" onClick={() => setDrawnBoundary(null)}>
            Cancel
          </button>
        </form>
      )}

      <FarmMap
        boundary={field?.boundary_geojson}
        hotspots={hotspots}
        editable={true}
        onBoundaryCreated={(geo) => setDrawnBoundary(geo)}
        onHotspotClick={(h) => navigate(`/hotspots/${h.id}`)}
        height="calc(100vh - 230px)"
      />
    </div>
  );
};

export default FieldMap;
