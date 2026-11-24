import React from 'react';

const Recommendations: React.FC = () => {
  return (
    <div>
      <h2>Actionable Recommendations</h2>
      <div style={{ marginTop: '2rem' }}>
        <p>No recommendations generated yet. Run an analysis first.</p>
        <button className="btn btn-primary mt-4">Generate New Recommendations</button>
      </div>
    </div>
  );
};

export default Recommendations;
