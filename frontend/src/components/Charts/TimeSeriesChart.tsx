import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface Props {
  data: any[];
}

const TimeSeriesChart: React.FC<Props> = ({ data }) => {
  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e3048" />
          <XAxis dataKey="date" stroke="#8899aa" />
          <YAxis stroke="#8899aa" />
          <Tooltip contentStyle={{ backgroundColor: '#162032', borderColor: '#1e3048', color: '#e8ecf1' }} />
          <Legend />
          <Line type="monotone" dataKey="ndvi" stroke="#22c55e" activeDot={{ r: 8 }} name="NDVI" />
          <Line type="monotone" dataKey="ndmi" stroke="#3b82f6" name="NDMI" />
          <Line type="monotone" dataKey="ndre" stroke="#a855f7" name="NDRE" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TimeSeriesChart;
