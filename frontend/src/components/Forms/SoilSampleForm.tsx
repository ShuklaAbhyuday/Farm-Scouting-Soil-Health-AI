import React, { useState } from 'react';
import { createSoilSample } from '../../services/soilService';
import { SOIL_TEXTURES } from '../../utils/constants';

interface Props {
  fieldId: number;
  onSaved?: () => void;
}

const SoilSampleForm: React.FC<Props> = ({ fieldId, onSaved }) => {
  const [formData, setFormData] = useState({
    nitrogen_level: 'low',
    nitrogen_value: '',
    phosphorus_level: 'medium',
    phosphorus_value: '',
    potassium_level: 'medium',
    potassium_value: '',
    ph_value: 6.8,
    moisture_level: 'medium',
    soil_texture: 'Loamy',
    source: 'lab',
    is_validated: true,
    notes: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '0.5rem',
    marginTop: '0.25rem',
    backgroundColor: 'var(--bg-secondary)',
    color: 'white',
    border: '1px solid var(--border)',
    borderRadius: '4px',
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setStatus(null);
    try {
      await createSoilSample(fieldId, {
        latitude: 23.0775,
        longitude: 76.8513,
        nitrogen_level: formData.nitrogen_level,
        nitrogen_value: formData.nitrogen_value ? parseFloat(formData.nitrogen_value) : undefined,
        phosphorus_level: formData.phosphorus_level,
        phosphorus_value: formData.phosphorus_value ? parseFloat(formData.phosphorus_value) : undefined,
        potassium_level: formData.potassium_level,
        potassium_value: formData.potassium_value ? parseFloat(formData.potassium_value) : undefined,
        ph_value: formData.ph_value,
        moisture_level: formData.moisture_level,
        soil_texture: formData.soil_texture,
        sample_date: new Date().toISOString(),
        source: formData.source,
        is_validated: formData.is_validated,
        notes: formData.notes,
      });
      setStatus('Soil sample saved! Recommendations will now use this ground-truth data.');
      if (onSaved) onSaved();
    } catch (err) {
      console.error('Failed to save soil sample:', err);
      setStatus('Error saving soil sample.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="card">
      <h3>⚡ Ground Truth Soil Entry</h3>
      {status && (
        <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', borderRadius: '6px', backgroundColor: 'rgba(34,197,94,0.15)', border: '1px solid #22c55e' }}>
          {status}
        </div>
      )}

      <div style={{ display: 'grid', gap: '0.85rem', marginTop: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <label>
            Nitrogen Level
            <select value={formData.nitrogen_level} onChange={(e) => setFormData({ ...formData, nitrogen_level: e.target.value })} style={inputStyle}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          <label>
            Nitrogen (mg/kg, optional)
            <input type="number" step="0.1" placeholder="e.g. 15" value={formData.nitrogen_value} onChange={(e) => setFormData({ ...formData, nitrogen_value: e.target.value })} style={inputStyle} />
          </label>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <label>
            Phosphorus Level
            <select value={formData.phosphorus_level} onChange={(e) => setFormData({ ...formData, phosphorus_level: e.target.value })} style={inputStyle}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          <label>
            Phosphorus (mg/kg, optional)
            <input type="number" step="0.1" placeholder="e.g. 12" value={formData.phosphorus_value} onChange={(e) => setFormData({ ...formData, phosphorus_value: e.target.value })} style={inputStyle} />
          </label>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <label>
            Potassium Level
            <select value={formData.potassium_level} onChange={(e) => setFormData({ ...formData, potassium_level: e.target.value })} style={inputStyle}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          <label>
            Potassium (mg/kg, optional)
            <input type="number" step="0.1" placeholder="e.g. 90" value={formData.potassium_value} onChange={(e) => setFormData({ ...formData, potassium_value: e.target.value })} style={inputStyle} />
          </label>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
          <label>
            pH Value
            <input type="number" step="0.1" value={formData.ph_value} onChange={(e) => setFormData({ ...formData, ph_value: parseFloat(e.target.value) })} style={inputStyle} />
          </label>
          <label>
            Soil Texture
            <select value={formData.soil_texture} onChange={(e) => setFormData({ ...formData, soil_texture: e.target.value })} style={inputStyle}>
              {SOIL_TEXTURES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>
            Source
            <select value={formData.source} onChange={(e) => setFormData({ ...formData, source: e.target.value })} style={inputStyle}>
              <option value="lab">Lab Test</option>
              <option value="sensor">IoT Sensor</option>
              <option value="manual">Manual Field Kit</option>
            </select>
          </label>
        </div>

        <label>
          Notes
          <input type="text" placeholder="Optional sample notes..." value={formData.notes} onChange={(e) => setFormData({ ...formData, notes: e.target.value })} style={inputStyle} />
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <input type="checkbox" checked={formData.is_validated} onChange={(e) => setFormData({ ...formData, is_validated: e.target.checked })} />
          I confirm these values are from verified lab/sensor testing
        </label>

        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving...' : '💾 Save Soil Data'}
        </button>
      </div>
    </form>
  );
};

export default SoilSampleForm;
