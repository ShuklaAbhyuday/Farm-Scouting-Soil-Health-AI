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
          <Line type="monotone" dataKey="ndvi" stroke="#16a34a" strokeWidth={2.2} activeDot={{ r: 5 }} name="NDVI" />
          <Line type="monotone" dataKey="evi" stroke="#0d9488" strokeWidth={1.8} dot={false} name="EVI" />
          <Line type="monotone" dataKey="savi" stroke="#ca8a04" strokeWidth={1.6} strokeDasharray="4 2" dot={false} name="SAVI" />
          <Line type="monotone" dataKey="ndmi" stroke="#0284c7" strokeWidth={1.8} name="NDMI" />
          <Line type="monotone" dataKey="ndre" stroke="#7c3aed" strokeWidth={1.8} name="NDRE" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TimeSeriesChart;
