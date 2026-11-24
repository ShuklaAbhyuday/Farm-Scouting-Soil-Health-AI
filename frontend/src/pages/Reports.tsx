import React from 'react';

const Reports: React.FC = () => {
  return (
    <div>
      <h2>Generate Reports</h2>
      <div className="card" style={{ marginTop: '2rem' }}>
        <button className="btn btn-primary">Generate PDF Report</button>
        <div style={{ marginTop: '2rem' }}>
          <h3>Recent Reports</h3>
          <p>No reports available.</p>
        </div>
      </div>
    </div>
  );
};

export default Reports;
