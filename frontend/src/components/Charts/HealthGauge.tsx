import React from 'react';
import { getHealthScoreColor } from '../../utils/helpers';

interface Props {
  score: number;
}

const HealthGauge: React.FC<Props> = ({ score }) => {
  const color = getHealthScoreColor(score);
  
  return (
    <div className="health-gauge" style={{ textAlign: 'center' }}>
      <div 
        className="gauge-circle" 
        style={{ 
          width: '120px', 
          height: '120px', 
          borderRadius: '50%', 
          border: `8px solid ${color}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto',
          fontSize: '2rem',
          fontWeight: 'bold'
        }}
      >
        {score}
      </div>
      <div style={{ marginTop: '0.5rem', color: color, fontWeight: 600 }}>
        {score >= 80 ? 'Healthy' : score >= 60 ? 'Mild Stress' : score >= 40 ? 'Moderate Stress' : 'Severe Stress'}
      </div>
    </div>
  );
};

export default HealthGauge;
