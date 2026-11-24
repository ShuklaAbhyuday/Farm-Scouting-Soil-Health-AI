import React, { useCallback, useEffect, useState } from 'react';
import SoilSampleForm from '../components/Forms/SoilSampleForm';
import { deleteSoilSample, getSoilSamples, updateSoilSample } from '../services/soilService';
import { useFieldContext } from '../context/FieldContext';
import { SoilSample } from '../types';

const SoilSamples: React.FC = () => {
  const { selectedFieldId } = useFieldContext();
  const [samples, setSamples] = useState<SoilSample[]>([]);
  const [loading, setLoading] = useState(true);

  const loadSamples = useCallback(async () => {
    try {
      const res = await getSoilSamples(selectedFieldId);
      setSamples(res.data || []);
    } catch (err) {
      console.error('Failed to fetch soil samples:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedFieldId]);

  useEffect(() => {
    loadSamples();
  }, [loadSamples]);

  const handleToggleValidate = async (s: SoilSample) => {
    try {
      await updateSoilSample(s.id, { is_validated: !s.is_validated });
      await loadSamples();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteSoilSample(id);
      await loadSamples();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div>
      <h2>Soil Data Management</h2>
      <div className="warning-banner" style={{ backgroundColor: 'rgba(59,130,246,0.2)', padding: '1rem', borderRadius: '8px', margin: '1rem 0 2rem' }}>
        📋 Ground Truth Data — These values are from physical soil testing, not satellite imagery.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', alignItems: 'start' }}>
        <SoilSampleForm fieldId={selectedFieldId} onSaved={loadSamples} />

        <div className="card">
          <h3>Recent Samples ({samples.length})</h3>
          {loading ? (
            <p>Loading samples...</p>
          ) : samples.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.75rem' }}>
              No samples recorded yet. Submit a sample on the left to unlock NPK-specific recommendations.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {samples.map((s) => (
                <div key={s.id} style={{ padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border)', backgroundColor: 'var(--bg-secondary)' }}>
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
  );
};

export default SoilSamples;
