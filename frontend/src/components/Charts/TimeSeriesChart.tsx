import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface Props {
  data: any[];
}

const TimeSeriesChart: React.FC<Props> = ({ data }) => {
  return (
    <div style={{ width: '100%', height: 220 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 26, bottom: 5, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e3ddc9" />
          <XAxis dataKey="date" stroke="#545b4a" fontSize={11} />
          <YAxis stroke="#545b4a" fontSize={11} domain={[-0.5, 1]} />
          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e3ddc9', color: '#1a2116', borderRadius: '10px', fontSize: '12px' }} />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          <Line type="monotone" dataKey="ndvi" stroke="#4d7c16" strokeWidth={2.4} activeDot={{ r: 5 }} name="NDVI" />
          <Line type="monotone" dataKey="evi" stroke="#76b81c" strokeWidth={1.8} dot={false} name="EVI" />
          <Line type="monotone" dataKey="savi" stroke="#c88a04" strokeWidth={1.6} strokeDasharray="4 2" dot={false} name="SAVI" />
          <Line type="monotone" dataKey="ndmi" stroke="#0284c7" strokeWidth={1.8} name="NDMI" />
          <Line type="monotone" dataKey="ndre" stroke="#65a30d" strokeWidth={1.8} name="NDRE" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TimeSeriesChart;
