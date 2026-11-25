import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface Props {
  data: any[];
}

const TimeSeriesChart: React.FC<Props> = ({ data }) => {
  return (
    <div style={{ width: '100%', height: 220 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 5, right: 16, bottom: 5, left: -12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#dfe3dc" />
          <XAxis dataKey="date" stroke="#535e58" fontSize={11} />
          <YAxis stroke="#535e58" fontSize={11} domain={[-0.5, 1]} />
          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#dfe3dc', color: '#111815', borderRadius: '8px', fontSize: '12px' }} />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          <Line type="monotone" dataKey="ndvi" stroke="#16a34a" strokeWidth={2} activeDot={{ r: 6 }} name="NDVI" />
          <Line type="monotone" dataKey="ndmi" stroke="#0284c7" strokeWidth={2} name="NDMI" />
          <Line type="monotone" dataKey="ndre" stroke="#7c3aed" strokeWidth={2} name="NDRE" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TimeSeriesChart;
