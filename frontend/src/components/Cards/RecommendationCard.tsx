import React from 'react';
import { Recommendation } from '../../types';

interface Props {
  recommendation: Recommendation;
}

const RecommendationCard: React.FC<Props> = ({ recommendation }) => {
  const getIcon = (category: string) => {
    switch (category) {
      case 'fertilizer': return '🌱';
      case 'irrigation': return '💧';
      case 'crop': return '🌾';
      case 'soil': return '🏔️';
      default: return '💡';
    }
  };

  return (
    <div className="card recommendation-card">
      <div className="rec-header">
        <span className="rec-icon">{getIcon(recommendation.category)}</span>
        <h4>{recommendation.title}</h4>
        <span className={`badge priority-${recommendation.priority}`}>{recommendation.priority}</span>
      </div>
      
      {recommendation.requires_ground_truth && (
        <div className="warning-banner" style={{ backgroundColor: 'rgba(234,179,8,0.2)', padding: '0.5rem', borderRadius: '4px', marginBottom: '1rem' }}>
          ⚠️ Ground soil testing recommended before applying
        </div>
      )}

      <p className="rec-description">{recommendation.description}</p>
      
      <details className="rec-reasoning">
        <summary>View Reasoning</summary>
        <p>{recommendation.reasoning}</p>
      </details>
    </div>
  );
};

export default RecommendationCard;
