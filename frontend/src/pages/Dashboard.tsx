import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import StatsCard from '../components/Cards/StatsCard';
import RecommendationCard from '../components/Cards/RecommendationCard';
import FarmMap from '../components/Map/FarmMap';
import { getDashboard } from '../services/dashboardService';
import { analyzeField } from '../services/satelliteService';
import { getField } from '../services/fieldService';
import { getHotspots } from '../services/hotspotService';
import { useFieldContext } from '../context/FieldContext';
import { DashboardSummary, Hotspot } from '../types';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { selectedFieldId } = useFieldContext();

  const [data, setData] = useState<DashboardSummary | null>(null);
  const [boundary, setBoundary] = useState<any>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setErrorMsg(null);
    try {
      const [dashRes, fieldRes, hsRes] = await Promise.all([
        getDashboard(selectedFieldId),
        getField(selectedFieldId).catch(() => null),
        getHotspots(selectedFieldId).catch(() => ({ data: [] })),
      ]);
      setData(dashRes.data);
      if (fieldRes?.data?.boundary_geojson) {
        setBoundary(fieldRes.data.boundary_geojson);
      }
      setHotspots(hsRes.data || []);
    } catch (error) {
      console.error('Failed to fetch dashboard', error);
      setErrorMsg('Backend is waking up or unreachable. Please retry in a few seconds.');
    } finally {
      setLoading(false);
    }
  }, [selectedFieldId]);

  useEffect(() => {
    setLoading(true);
    fetchDashboard();
  }, [fetchDashboard]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setStatusMsg('Running Sentinel-2 analysis & Isolation Forest ML model...');
    setErrorMsg(null);
    try {
      const res: any = await analyzeField(selectedFieldId, {
        start_date: '2023-01-01',
        end_date: '2023-12-31',
      });
      await fetchDashboard();
      const count = res?.data?.hotspots_detected ?? 0;
      setStatusMsg(`Analysis complete! Detected ${count} hotspot zone(s) and updated recommendations.`);
    } catch (error) {
      console.error('Failed to analyze field', error);
      setErrorMsg('Analysis request failed. If Render just woke up, click Analyze Field again.');
      setStatusMsg(null);
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
        <p>Loading dashboard... (If the backend was idle, waking Render takes ~30–50s on first load.)</p>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <h2>Field Overview {data?.field_name ? `- ${data.field_name}` : ''}</h2>

      {statusMsg && (
        <div style={{ backgroundColor: 'rgba(34,197,94,0.15)', border: '1px solid #22c55e', padding: '0.75rem 1rem', borderRadius: '8px', margin: '1rem 0' }}>
          ✅ {statusMsg}
        </div>
      )}
      {errorMsg && (
        <div style={{ backgroundColor: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444', padding: '0.75rem 1rem', borderRadius: '8px', margin: '1rem 0' }}>
          ⚠️ {errorMsg}
        </div>
      )}

      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <StatsCard
          title="Health Score"
          value={data?.health_score != null ? `${data.health_score}/100` : 'N/A'}
          icon="❤️"
          subtitle={data?.overall_health || 'Unknown'}
        />
        <StatsCard
          title="Total Hotspots"
          value={data?.total_hotspots?.toString() || '0'}
          icon="🔥"
          trend={data?.ndvi_trend === 'declining' ? 'down' : 'up'}
          trendValue={`${data?.critical_hotspots ?? 0} severe`}
        />
        <StatsCard
          title="Latest Observation"
          value={data?.latest_observation_date ? new Date(data.latest_observation_date).toLocaleDateString() : 'None'}
          icon="📡"
          subtitle={data?.ndmi_mean != null ? `NDMI: ${data.ndmi_mean} | NDRE: ${data.ndre_mean}` : 'Run analysis'}
        />
        <StatsCard
          title="NDVI Trend"
          value={data?.ndvi_trend || 'N/A'}
          icon="📈"
          subtitle={data?.ndvi_mean != null ? `Mean: ${data.ndvi_mean}` : 'No scan yet'}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <h3>Field Map</h3>
            <button className="btn" onClick={() => navigate('/map')} style={{ fontSize: '0.85rem' }}>
              Open Full Map & Draw →
            </button>
          </div>
          <FarmMap
            boundary={boundary}
            hotspots={hotspots}
            onHotspotClick={(h) => navigate(`/hotspots/${h.id}`)}
          />
        </div>

        <div>
          <h3>Quick Actions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              className="btn btn-primary"
              onClick={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? '⏳ Analyzing Field...' : '🛰️ Analyze Field'}
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/soil')}>
              🧪 Submit Soil Sample &amp; Results
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/crop-recommendation')}>
              🌱 Crop Recommendation
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/history')}>
              📈 View History
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/recommendations')}>
              💡 View Recommendations
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/reports')}>
              📄 Generate PDF Report
            </button>
          </div>

          {data?.recent_recommendations && data.recent_recommendations.length > 0 && (
            <div style={{ marginTop: '1.5rem' }}>
              <h3>Latest Recommendation</h3>
              <div style={{ marginTop: '0.5rem' }}>
                <RecommendationCard recommendation={data.recent_recommendations[0]} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
