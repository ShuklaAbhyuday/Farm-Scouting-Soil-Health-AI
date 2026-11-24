import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import FarmMap from '../components/Map/FarmMap';
import HotspotCard from '../components/Cards/HotspotCard';
import { getHotspot, getHotspots } from '../services/hotspotService';
import { getField } from '../services/fieldService';
import { useFieldContext } from '../context/FieldContext';
import { Hotspot } from '../types';

const HotspotDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { selectedFieldId } = useFieldContext();

  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [selected, setSelected] = useState<Hotspot | null>(null);
  const [boundary, setBoundary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [listRes, fieldRes] = await Promise.all([
          getHotspots(selectedFieldId),
          getField(selectedFieldId).catch(() => null),
        ]);
        const list = listRes.data || [];
        setHotspots(list);
        if (fieldRes?.data?.boundary_geojson) {
          setBoundary(fieldRes.data.boundary_geojson);
        }

        if (id) {
          const single = await getHotspot(Number(id)).catch(() => null);
          setSelected(single?.data || list[0] || null);
        } else {
          setSelected(list[0] || null);
        }
      } catch (err) {
        console.error('Failed to load hotspots:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, selectedFieldId]);

  if (loading) return <div>Loading hotspots...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Detected Stress Hotspots ({hotspots.length})</h2>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          ← Back to Dashboard
        </button>
      </div>

      {hotspots.length === 0 ? (
        <div className="card">
          <p>No hotspots detected yet for this field. Go to the Dashboard and click <strong>Analyze Field</strong> first.</p>
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '1.5rem' }}>
            <div className="card">
              <h3>{selected?.likely_issue || 'Hotspot Details'}</h3>
              {selected && (
                <div style={{ display: 'grid', gap: '0.6rem', marginTop: '1rem' }}>
                  <p>
                    <strong>Severity:</strong>{' '}
                    <span className={`badge badge-${selected.severity}`}>{selected.severity.toUpperCase()}</span>
                  </p>
                  <p><strong>Health Score:</strong> {selected.health_score} / 100</p>
                  <p><strong>Area:</strong> {selected.area_ha} ha</p>
                  <p>
                    <strong>Detection Method:</strong>{' '}
                    {selected.detection_method === 'isolation_forest'
                      ? 'AI Model (Isolation Forest)'
                      : 'Baseline Weighted Heuristic'}
                  </p>
                  <p>
                    <strong>Indices:</strong> NDVI {selected.ndvi_value?.toFixed(3)} ({selected.ndvi_deviation >= 0 ? '+' : ''}{selected.ndvi_deviation?.toFixed(3)}) | NDMI {selected.ndmi_value?.toFixed(3)} | NDRE {selected.ndre_value?.toFixed(3)}
                  </p>
                  <p><strong>AI Explanation:</strong> {selected.explanation}</p>
                </div>
              )}
            </div>

            <FarmMap
              boundary={boundary}
              hotspots={hotspots}
              onHotspotClick={(h) => {
                setSelected(h);
                navigate(`/hotspots/${h.id}`);
              }}
            />
          </div>

          <div>
            <h3>All Zones in Field</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem', marginTop: '0.75rem' }}>
              {hotspots.map((hs) => (
                <HotspotCard
                  key={hs.id}
                  hotspot={hs}
                  onClick={(h) => {
                    setSelected(h);
                    navigate(`/hotspots/${h.id}`);
                  }}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default HotspotDetail;
