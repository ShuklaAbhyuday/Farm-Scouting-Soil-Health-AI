import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SoilSampleForm from '../components/Forms/SoilSampleForm';
import { deleteSoilSample, getSoilSamples, updateSoilSample } from '../services/soilService';
import { useFieldContext } from '../context/FieldContext';
import { SoilSample } from '../types';

const SoilSamples: React.FC = () => {
  const navigate = useNavigate();
  const { selectedFieldId } = useFieldContext();
  const [samples, setSamples] = useState<SoilSample[]>([]);
  const [activeSample, setActiveSample] = useState<SoilSample | null>(null);
  const [loading, setLoading] = useState(true);

  const loadSamples = useCallback(async (preferredId?: number) => {
    try {
      const res = await getSoilSamples(selectedFieldId);
      const list: SoilSample[] = res.data || [];
      setSamples(list);
      if (preferredId) {
        setActiveSample(list.find((s) => s.id === preferredId) || list[0] || null);
      } else {
        setActiveSample((prev) => (prev ? list.find((s) => s.id === prev.id) || list[0] || null : list[0] || null));
      }
    } catch (err) {
      console.error('Failed to fetch soil samples:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedFieldId]);

  useEffect(() => {
    loadSamples();
  }, [loadSamples]);

  const handleSaved = async (created: SoilSample) => {
    setActiveSample(created);
    await loadSamples(created.id);
  };

  const handleToggleValidate = async (s: SoilSample) => {
    try {
      const res = await updateSoilSample(s.id, { is_validated: !s.is_validated });
      if (activeSample?.id === s.id) setActiveSample(res.data);
      await loadSamples(s.id);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteSoilSample(id);
      if (activeSample?.id === id) setActiveSample(null);
      await loadSamples();
    } catch (err) {
      console.error(err);
    }
  };

  const levelBadgeClass = (lvl: string) => {
    if (lvl === 'low') return 'badge-severe';
    if (lvl === 'medium') return 'badge-healthy';
    return 'badge-mild';
  };

  const analysis = activeSample?.analysis;

  return (
    <div>
      <h2>Soil Sample Submission & Results</h2>
      <div className="warning-banner" style={{ backgroundColor: 'rgba(59,130,246,0.2)', padding: '1rem', borderRadius: '8px', margin: '1rem 0 1.5rem' }}>
        📋 Ground Truth Data — Physical soil test inputs generate immediate fertility diagnostics, NPK treatment guidance, and matching crop suggestions.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.15fr', gap: '2rem', alignItems: 'start' }}>
        <SoilSampleForm fieldId={selectedFieldId} onSaved={handleSaved} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* SOIL SAMPLE RESULT PANEL */}
          <div className="card" style={{ borderColor: analysis ? 'var(--green-500)' : 'var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>📊 Soil Test Result</h3>
              {activeSample && (
                <span className={`badge ${activeSample.is_validated ? 'badge-healthy' : 'badge-mild'}`}>
                  {activeSample.is_validated ? 'Validated Lab/Sensor' : 'Unvalidated Entry'}
                </span>
              )}
            </div>

            {!activeSample || !analysis ? (
              <p style={{ color: 'var(--text-secondary)', marginTop: '0.75rem' }}>
                Submit a soil sample on the left (or select one below) to see the Soil Fertility Score, pH & NPK status, amendment actions, and best-fit crops.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.85rem', borderRadius: '8px', backgroundColor: 'var(--bg-secondary)' }}>
                  <div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>OVERALL VERDICT</div>
                    <strong style={{ fontSize: '1.05rem' }}>{analysis.verdict}</strong>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>FERTILITY SCORE</div>
                    <strong style={{ fontSize: '1.35rem', color: analysis.fertility_score >= 75 ? '#22c55e' : '#eab308' }}>
                      {analysis.fertility_score}/100
                    </strong>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                  <div style={{ padding: '0.6rem', borderRadius: '6px', backgroundColor: 'var(--bg-secondary)', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Nitrogen (N)</div>
                    <span className={`badge ${levelBadgeClass(analysis.nutrient_status.nitrogen.level)}`} style={{ marginTop: '0.25rem', display: 'inline-block' }}>
                      {analysis.nutrient_status.nitrogen.level.toUpperCase()}
                    </span>
                    {analysis.nutrient_status.nitrogen.is_measured && (
                      <div style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>{analysis.nutrient_status.nitrogen.value} mg/kg</div>
                    )}
                  </div>
                  <div style={{ padding: '0.6rem', borderRadius: '6px', backgroundColor: 'var(--bg-secondary)', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Phosphorus (P)</div>
                    <span className={`badge ${levelBadgeClass(analysis.nutrient_status.phosphorus.level)}`} style={{ marginTop: '0.25rem', display: 'inline-block' }}>
                      {analysis.nutrient_status.phosphorus.level.toUpperCase()}
                    </span>
                    {analysis.nutrient_status.phosphorus.is_measured && (
                      <div style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>{analysis.nutrient_status.phosphorus.value} mg/kg</div>
                    )}
                  </div>
                  <div style={{ padding: '0.6rem', borderRadius: '6px', backgroundColor: 'var(--bg-secondary)', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Potassium (K)</div>
                    <span className={`badge ${levelBadgeClass(analysis.nutrient_status.potassium.level)}`} style={{ marginTop: '0.25rem', display: 'inline-block' }}>
                      {analysis.nutrient_status.potassium.level.toUpperCase()}
                    </span>
                    {analysis.nutrient_status.potassium.is_measured && (
                      <div style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>{analysis.nutrient_status.potassium.value} mg/kg</div>
                    )}
                  </div>
                  <div style={{ padding: '0.6rem', borderRadius: '6px', backgroundColor: 'var(--bg-secondary)', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Soil pH</div>
                    <strong style={{ display: 'block', marginTop: '0.25rem' }}>{activeSample.ph_value ?? '7.0'}</strong>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{analysis.ph_status}</div>
                  </div>
                </div>

                <div>
                  <strong style={{ fontSize: '0.9rem' }}>Soil Treatment & Action Result</strong>
                  <ul style={{ marginTop: '0.4rem', paddingLeft: '1.25rem', display: 'grid', gap: '0.3rem', fontSize: '0.9rem' }}>
                    {analysis.actions.map((act, idx) => (
                      <li key={idx}>{act}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ fontSize: '0.9rem' }}>Top Crops for This Soil</strong>
                    <button
                      className="btn"
                      onClick={() => navigate('/crop-recommendation')}
                      style={{ fontSize: '0.8rem', padding: '0.25rem 0.6rem' }}
                    >
                      Open Crop Advisor →
                    </button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginTop: '0.5rem' }}>
                    {analysis.top_crops.map((c) => (
                      <div key={c.crop} style={{ padding: '0.6rem', borderRadius: '6px', backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                        <div style={{ fontWeight: 600 }}>{c.emoji} {c.crop}</div>
                        <div style={{ fontSize: '0.8rem', color: '#22c55e' }}>{c.suitability_score}% match</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{c.season}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* SUBMITTED SAMPLES HISTORY */}
          <div className="card">
            <h3>Submitted Soil Samples ({samples.length})</h3>
            {loading ? (
              <p>Loading samples...</p>
            ) : samples.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', marginTop: '0.75rem' }}>
                No samples recorded yet.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
                {samples.map((s) => (
                  <div
                    key={s.id}
                    style={{
                      padding: '0.75rem',
                      borderRadius: '8px',
                      border: activeSample?.id === s.id ? '1px solid var(--green-500)' : '1px solid var(--border)',
                      backgroundColor: 'var(--bg-secondary)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong>{s.source.toUpperCase()} — {new Date(s.sample_date).toLocaleDateString()}</strong>
                      <span className={`badge ${s.is_validated ? 'badge-healthy' : 'badge-mild'}`}>
                        {s.is_validated ? 'Validated' : 'Unvalidated'}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.9rem', marginTop: '0.4rem' }}>
                      N: {s.nitrogen_value ?? s.nitrogen_level} | P: {s.phosphorus_value ?? s.phosphorus_level} | K: {s.potassium_value ?? s.potassium_level} | pH: {s.ph_value} ({s.soil_texture})
                    </p>
                    {s.notes && <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{s.notes}</p>}
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                      <button className="btn btn-primary" onClick={() => setActiveSample(s)} style={{ fontSize: '0.8rem', padding: '0.25rem 0.6rem' }}>
                        View Result
                      </button>
                      <button className="btn" onClick={() => handleToggleValidate(s)} style={{ fontSize: '0.8rem', padding: '0.25rem 0.6rem' }}>
                        {s.is_validated ? 'Mark Unvalidated' : 'Validate'}
                      </button>
                      <button className="btn" onClick={() => handleDelete(s.id)} style={{ fontSize: '0.8rem', padding: '0.25rem 0.6rem', color: '#ef4444' }}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SoilSamples;
