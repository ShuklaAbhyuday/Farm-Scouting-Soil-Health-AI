import React from 'react';
import { Link } from 'react-router-dom';

const FarmList: React.FC = () => {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h2>My Farms</h2>
        <Link to="/farms/new" className="btn btn-primary">Create New Farm</Link>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
        <div className="card">
          <h3>Demo Farm 1</h3>
          <p>Location: Bhopal, MP</p>
          <p>Fields: 2</p>
          <p>Area: 45.2 ha</p>
          <Link to="/" className="btn btn-primary" style={{ marginTop: '1rem' }}>View Dashboard</Link>
        </div>
      </div>
    </div>
  );
};

export default FarmList;
