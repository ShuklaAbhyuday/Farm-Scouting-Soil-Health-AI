import React, { useState, useEffect } from 'react';
import StatsCard from '../components/Cards/StatsCard';
import FarmMap from '../components/Map/FarmMap';
import { getDashboard } from '../services/dashboardService';
import { analyzeField } from '../services/satelliteService';
import { DashboardSummary } from '../types';

const Dashboard: React.FC = () => {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  // Hardcoded fieldId for demo purposes, since we only created Field 1
  const fieldId = 1;

  const fetchDashboard = async () => {
    try {
      const response = await getDashboard(fieldId);
      setData(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [fieldId]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      await analyzeField(fieldId, { start_date: '2023-01-01', end_date: '2023-12-31' } as any);
      // Wait for 1s to allow DB updates then refresh
      setTimeout(() => {
        fetchDashboard();
        setAnalyzing(false);
      }, 1000);
    } catch (error) {
      console.error('Failed to analyze field', error);
      setAnalyzing(false);
    }
  };

  if (loading) return <div>Loading dashboard...</div>;

  return (
    <div className="dashboard-page">
      <h2>Field Overview {data?.field_name ? `- ${data.field_name}` : ''}</h2>
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <StatsCard 
          title="Health Score" 
          value={data?.health_score ? `${data.health_score}/100` : 'N/A'} 
          icon="❤️" 
          subtitle={data?.overall_health || 'Unknown'} 
        />
        <StatsCard 
          title="Total Hotspots" 
          value={data?.total_hotspots?.toString() || '0'} 
          icon="🔥" 
          trend={data?.ndvi_trend === 'declining' ? 'down' : 'up'} 
          trendValue={data?.critical_hotspots?.toString() || '0'} 
        />
        <StatsCard 
          title="Latest Observation" 
          value={data?.latest_observation_date ? new Date(data.latest_observation_date).toLocaleDateString() : 'None'} 
          icon="📡" 
        />
        <StatsCard 
          title="NDVI Trend" 
          value={data?.ndvi_trend || 'N/A'} 
          icon="📈" 
          subtitle={data?.ndvi_mean ? `Mean: ${data.ndvi_mean}` : ''}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
        <div>
          <h3>Field Map</h3>
          <FarmMap />
        </div>
        <div>
          <h3>Quick Actions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <button 
              className="btn btn-primary" 
              onClick={handleAnalyze} 
              disabled={analyzing}
            >
              {analyzing ? 'Analyzing...' : 'Analyze Field'}
            </button>
            <button className="btn btn-primary">Enter Soil Data</button>
            <button className="btn btn-primary">View History</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
