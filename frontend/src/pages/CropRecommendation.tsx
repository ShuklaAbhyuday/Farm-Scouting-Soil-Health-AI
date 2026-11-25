import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { computeCropRecommendations, getCropRecommendations } from '../services/recommendationService';
import { useFieldContext } from '../context/FieldContext';
import { SOIL_TEXTURES } from '../utils/constants';
import { CropRecommendationResponse } from '../types';

const CropRecommendation: React.FC = () => {
  const navigate = useNavigate();
  const { selectedFieldId } = useFieldContext();

  const [data, setData] = useState<CropRecommendationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);

  const [form, setForm] = useState({
    nitrogen_level: 'medium',
    nitrogen_value: '',
    phosphorus_level: 'medium',
    phosphorus_value: '',
    potassium_level: 'medium',
    potassium_value: '',
    ph_value: 6.8,
    moisture_level: 'medium',
    soil_texture: 'Loamy',
    season: 'All',
  });

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await getCropRecommendations(selectedFieldId);
        setData(res.data);
        const inp = res.data?.inputs_used;
        if (inp) {
          setForm({
            nitrogen_level: inp.nitrogen_level || 'medium',
            nitrogen_value: inp.nitrogen_value != null ? String(inp.nitrogen_value) : '',
            phosphorus_level: inp.phosphorus_level || 'medium',
            phosphorus_value: inp.phosphorus_value != null ? String(inp.phosphorus_value) : '',
            potassium_level: inp.potassium_level || 'medium',
            potassium_value: inp.potassium_value != null ? String(inp.potassium_value) : '',
            ph_value: inp.ph_value ?? 6.8,
            moisture_level: inp.moisture_level || 'medium',
            soil_texture: inp.soil_texture || 'Loamy',
            season: inp.season || 'All',
          });
        }
      } catch (err) {
        console.error('Failed to load crop recommendations:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [selectedFieldId]);

  const handleCalculate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCalculating(true);
    try {
      const res = await computeCropRecommendations(selectedFieldId, {
        nitrogen_level: form.nitrogen_level,
        nitrogen_value: form.nitrogen_value ? parseFloat(form.nitrogen_value) : null,
        phosphorus_level: form.phosphorus_level,
        phosphorus_value: form.phosphorus_value ? parseFloat(form.phosphorus_value) : null,
        potassium_level: form.potassium_level,
        potassium_value: form.potassium_value ? parseFloat(form.potassium_value) : null,
        ph_value: form.ph_value,
        moisture_level: form.moisture_level,
        soil_texture: form.soil_texture,
        season: form.season,
        use_latest_sample: false,
      });
      setData(res.data);
    } catch (err) {
      console.error('Failed to compute crop recommendations:', err);
    } finally {
      setCalculating(false);
    }
  };

  const handleSyncFromSoil = async () => {
    setCalculating(true);
    try {
      const res = await getCropRecommendations(selectedFieldId);
      setData(res.data);
      const inp = res.data?.inputs_used;
      if (inp) {
        setForm({
          nitrogen_level: inp.nitrogen_level || 'medium',
          nitrogen_value: inp.nitrogen_value != null ? String(inp.nitrogen_value) : '',
          phosphorus_level: inp.phosphorus_level || 'medium',
          phosphorus_value: inp.phosphorus_value != null ? String(inp.phosphorus_value) : '',
          potassium_level: inp.potassium_level || 'medium',
          potassium_value: inp.potassium_value != null ? String(inp.potassium_value) : '',
          ph_value: inp.ph_value ?? 6.8,
          moisture_level: inp.moisture_level || 'medium',
          soil_texture: inp.soil_texture || 'Loamy',
          season: inp.season || 'All',
        });
      }
    } finally {
      setCalculating(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '0.45rem',
    marginTop: '0.25rem',
    backgroundColor: 'var(--bg-secondary)',
    color: 'white',
    border: '1px solid var(--border)',
    borderRadius: '4px',
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <h2>🌱 Crop Recommendation Advisor {data?.field_name ? `— ${data.field_name}` : ''}</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Matches your soil NPK, pH, texture, and satellite moisture profile to the highest-suitability crops.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn" onClick={handleSyncFromSoil} disabled={calculating}>
            🔄 Sync Latest Soil Sample
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/soil')}>
            🧪 Submit Soil Sample
          </button>
        </div>
      </div>

      {data && (
        <div
          className="warning-banner"
          style={{
            backgroundColor: data.is_validated ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)',
            border: `1px solid ${data.is_validated ? '#22c55e' : '#eab308'}`,
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            marginBottom: '1.5rem',
          }}
        >
          {data.is_validated
            ? '✅ Using verified ground-truth soil test data combined with field conditions.'
            : data.has_soil_sample
              ? '⚠️ Using unvalidated soil sample entry — verify with lab values for best precision.'
              : 'ℹ️ No soil sample submitted yet for this field — showing estimates. Submit a soil sample or adjust values below.'}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '2rem', alignItems: 'start' }}>
        <form onSubmit={handleCalculate} className="card" style={{ display: 'grid', gap: '0.75rem' }}>
          <h3>Soil & Season Inputs</h3>

          <label>
            Cropping Season
            <select value={form.season} onChange={(e) => setForm({ ...form, season: e.target.value })} style={inputStyle}>
              <option value="All">All Seasons</option>
              <option value="Rabi">Rabi (Winter)</option>
              <option value="Kharif">Kharif (Monsoon)</option>
            </select>
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <label>
              Nitrogen
              <select value={form.nitrogen_level} onChange={(e) => setForm({ ...form, nitrogen_level: e.target.value })} style={inputStyle}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label>
              N (mg/kg)
              <input type="number" step="0.1" placeholder="Optional" value={form.nitrogen_value} onChange={(e) => setForm({ ...form, nitrogen_value: e.target.value })} style={inputStyle} />
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <label>
              Phosphorus
              <select value={form.phosphorus_level} onChange={(e) => setForm({ ...form, phosphorus_level: e.target.value })} style={inputStyle}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label>
              P (mg/kg)
              <input type="number" step="0.1" placeholder="Optional" value={form.phosphorus_value} onChange={(e) => setForm({ ...form, phosphorus_value: e.target.value })} style={inputStyle} />
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <label>
              Potassium
              <select value={form.potassium_level} onChange={(e) => setForm({ ...form, potassium_level: e.target.value })} style={inputStyle}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label>
              K (mg/kg)
              <input type="number" step="0.1" placeholder="Optional" value={form.potassium_value} onChange={(e) => setForm({ ...form, potassium_value: e.target.value })} style={inputStyle} />
            </label>
          </div>

          <label>
            Soil pH ({form.ph_value})
            <input type="number" step="0.1" min="3.5" max="9.5" value={form.ph_value} onChange={(e) => setForm({ ...form, ph_value: parseFloat(e.target.value) })} style={inputStyle} />
          </label>

          <label>
            Soil Texture
            <select value={form.soil_texture} onChange={(e) => setForm({ ...form, soil_texture: e.target.value })} style={inputStyle}>
              {SOIL_TEXTURES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>

          <label>
            Field Moisture
            <select value={form.moisture_level} onChange={(e) => setForm({ ...form, moisture_level: e.target.value })} style={inputStyle}>
              <option value="low">Low (Dry / Rainfed)</option>
              <option value="medium">Medium (Irrigated)</option>
              <option value="high">High (Water-Retentive)</option>
            </select>
          </label>

          <button type="submit" className="btn btn-primary" disabled={calculating}>
            {calculating ? 'Calculating...' : '🌱 Recommend Best Crops'}
          </button>
        </form>

        <div>
          {loading ? (
            <p>Loading crop recommendations...</p>
          ) : (
            <div style={{ display: 'grid', gap: '1rem' }}>
              {(data?.recommendations || []).map((item, idx) => (
                <div key={item.crop} className="card" style={{ borderLeft: `4px solid ${item.suitability_score >= 82 ? '#22c55e' : item.suitability_score >= 68 ? '#eab308' : '#64748b'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontSize: '1.5rem' }}>{item.emoji}</span>
                      <div>
                        <h3 style={{ margin: 0 }}>#{idx + 1} {item.crop}</h3>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          Season: {item.season} {item.nitrogen_fixer ? '• Nitrogen Fixer' : ''}
                        </span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span className={`badge ${item.suitability_score >= 82 ? 'badge-healthy' : item.suitability_score >= 68 ? 'badge-mild' : 'badge-moderate'}`}>
                        {item.suitability_score}% Match — {item.match_label}
                      </span>
                    </div>
                  </div>

                  <div style={{ marginTop: '0.75rem', height: '6px', borderRadius: '3px', backgroundColor: 'var(--bg-secondary)', overflow: 'hidden' }}>
                    <div style={{ width: `${item.suitability_score}%`, height: '100%', backgroundColor: item.suitability_score >= 82 ? '#22c55e' : item.suitability_score >= 68 ? '#eab308' : '#94a3b8' }} />
                  </div>

                  <ul style={{ marginTop: '0.75rem', paddingLeft: '1.2rem', fontSize: '0.9rem', display: 'grid', gap: '0.25rem' }}>
                    {item.reasons.map((r, rIdx) => <li key={rIdx}>{r}</li>)}
                  </ul>

                  <p style={{ marginTop: '0.6rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {item.care_notes}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CropRecommendation;
