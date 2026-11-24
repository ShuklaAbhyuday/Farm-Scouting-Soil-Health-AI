import React from 'react';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon?: string;
  trend?: 'up' | 'down';
  trendValue?: string;
  subtitle?: string;
}

const StatsCard: React.FC<StatsCardProps> = ({ title, value, icon, trend, trendValue, subtitle }) => {
  return (
    <div className="card stats-card">
      <div className="stats-header">
        <span className="stats-title">{title}</span>
        {icon && <span className="stats-icon">{icon}</span>}
      </div>
      <div className="stats-body">
        <span className="stats-value">{value}</span>
        {trend && (
          <span className={`trend trend-${trend}`}>
            {trend === 'up' ? '↑' : '↓'} {trendValue}
          </span>
        )}
      </div>
      {subtitle && <div className="stats-footer">{subtitle}</div>}
    </div>
  );
};

export default StatsCard;
