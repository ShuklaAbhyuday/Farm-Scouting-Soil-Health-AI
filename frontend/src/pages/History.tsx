import React, { useEffect, useState } from 'react';
import TimeSeriesChart from '../components/Charts/TimeSeriesChart';
import api from '../services/api';
import { useFieldContext } from '../context/FieldContext';

interface ObservationRecord {
  observation_id: number;
  date: string;
  ndvi: number;
  ndmi: number;
  ndre: number;
  cloud_cover_pct: number;
  health_score: number;
  hotspot_count: number;
}

const History: React.FC = () => {
  const { selectedFieldId } = useFieldContext();
  const [chartData, setChartData] = useState<any[]>([]);
  const [observations, setObservations] = useState<ObservationRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/fields/${selectedFieldId}/history`);
        const obs: ObservationRecord[] = res.data?.observations || [];
        setObservations(obs);
        setChartData(
          obs.map((o) => ({
            date: o.date,
            ndvi: o.ndvi,
            ndmi: o.ndmi,
            ndre: o.ndre,
          }))
        );
      } catch (err) {
        console.error('Failed to fetch history:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [selectedFieldId]);

  return (
    <div>
      <h2>Historical Satellite Trends</h2>
      {loading ? (
        <p style={{ marginTop: '1rem' }}>Loading historical observations...</p>
      ) : chartData.length === 0 ? (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <p>No satellite observations recorded yet. Go to the Dashboard and click <strong>Analyze Field</strong> to log an observation.</p>
        </div>
      ) : (
        <>
          <div className="card" style={{ marginTop: '1.5rem' }}>
            <h3>NDVI / NDMI / NDRE Over Time</h3>
            <div style={{ marginTop: '1rem' }}>
              <TimeSeriesChart data={chartData} />
            </div>
          </div>

          <div className="card" style={{ marginTop: '1.5rem', overflowX: 'auto' }}>
            <h3>Observation Log ({observations.length})</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '0.5rem' }}>Date</th>
                  <th style={{ padding: '0.5rem' }}>NDVI</th>
                  <th style={{ padding: '0.5rem' }}>NDMI</th>
                  <th style={{ padding: '0.5rem' }}>NDRE</th>
                  <th style={{ padding: '0.5rem' }}>Cloud %</th>
                  <th style={{ padding: '0.5rem' }}>Health Score</th>
                  <th style={{ padding: '0.5rem' }}>Hotspots</th>
                </tr>
              </thead>
              <tbody>
                {observations.map((o) => (
                  <tr key={o.observation_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.5rem' }}>{o.date}</td>
                    <td style={{ padding: '0.5rem' }}>{o.ndvi}</td>
                    <td style={{ padding: '0.5rem' }}>{o.ndmi}</td>
                    <td style={{ padding: '0.5rem' }}>{o.ndre}</td>
                    <td style={{ padding: '0.5rem' }}>{o.cloud_cover_pct}%</td>
                    <td style={{ padding: '0.5rem' }}>{o.health_score}/100</td>
                    <td style={{ padding: '0.5rem' }}>{o.hotspot_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

export default History;
