import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

export interface ChartDataSeries {
  key: string;
  name: string;
  color: string;
}

interface LineChartComponentProps {
  data: any[];
  xAxisKey: string;
  series: ChartDataSeries[];
  yAxisDomain?: [number | string, number | string];
}

export const LineChartComponent: React.FC<LineChartComponentProps> = ({ data, xAxisKey, series, yAxisDomain }) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
        <XAxis 
          dataKey={xAxisKey} 
          stroke="#8b949e" 
          fontSize={12} 
          tickLine={false} 
          axisLine={false}
          dy={10}
        />
        <YAxis 
          stroke="#8b949e" 
          fontSize={12} 
          tickLine={false} 
          axisLine={false} 
          domain={yAxisDomain || ['auto', 'auto']}
          dx={-10}
        />
        <Tooltip 
          contentStyle={{ 
            backgroundColor: '#161b22', 
            borderColor: '#30363d',
            borderRadius: '0.375rem',
            color: '#c9d1d9'
          }}
          itemStyle={{ color: '#c9d1d9' }}
        />
        <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '12px', color: '#c9d1d9' }} />
        {series.map((s) => (
          <Line 
            key={s.key} 
            type="monotone" 
            dataKey={s.key} 
            name={s.name} 
            stroke={s.color} 
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
};
