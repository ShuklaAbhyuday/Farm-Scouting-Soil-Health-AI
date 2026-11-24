import React, { useCallback, useEffect, useState } from 'react';
import RecommendationCard from '../components/Cards/RecommendationCard';
import { generateRecommendations, getRecommendations } from '../services/recommendationService';
import { useFieldContext } from '../context/FieldContext';
import { Recommendation } from '../types';

const Recommendations: React.FC = () => {
  const { selectedFieldId } = useFieldContext();
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await getRecommendations(selectedFieldId);
      setRecs(res.data || []);
    } catch (err) {
      console.error('Failed to fetch recommendations:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedFieldId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await generateRecommendations(selectedFieldId);
      setRecs(res.data || []);
    } catch (err) {
      console.error('Failed to generate recommendations:', err);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>Actionable Recommendations</h2>
        <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
          {generating ? '⏳ Generating...' : '💡 Generate New Recommendations'}
        </button>
      </div>

      {loading ? (
        <p>Loading recommendations...</p>
      ) : recs.length === 0 ? (
        <div className="card">
          <p>No recommendations generated yet. Click <strong>Generate New Recommendations</strong> above (or run an analysis on the Dashboard).</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {recs.map((rec) => (
            <RecommendationCard key={rec.id} recommendation={rec} />
          ))}
        </div>
      )}
    </div>
  );
};

export default Recommendations;
