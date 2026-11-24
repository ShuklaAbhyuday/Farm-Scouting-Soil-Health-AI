import React from 'react';
import TimeSeriesChart from '../components/Charts/TimeSeriesChart';

const History: React.FC = () => {
  const dummyData = [
    { date: 'Jan', ndvi: 0.4, ndmi: 0.3, ndre: 0.2 },
    { date: 'Feb', ndvi: 0.5, ndmi: 0.4, ndre: 0.3 },
  ];

  return (
    <div>
      <h2>Historical Data</h2>
      <div className="card" style={{ marginTop: '2rem' }}>
        <TimeSeriesChart data={dummyData} />
      </div>
    </div>
  );
};

export default History;
