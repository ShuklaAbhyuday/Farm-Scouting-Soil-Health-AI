import { SeverityLevel } from '../types';
import { SEVERITY_COLORS } from './constants';

export const formatDate = (date: string): string => {
  return new Date(date).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

export const getSeverityColor = (severity: SeverityLevel): string => {
  return SEVERITY_COLORS[severity] || SEVERITY_COLORS.healthy;
};

export const getSeverityLabel = (score: number): SeverityLevel => {
  if (score >= 80) return 'healthy';
  if (score >= 60) return 'mild';
  if (score >= 40) return 'moderate';
  return 'severe';
};

export const formatArea = (ha: number): string => {
  return `${ha.toFixed(2)} ha`;
};

export const formatIndex = (value: number): string => {
  return value.toFixed(2);
};

export const getHealthScoreColor = (score: number): string => {
  return getSeverityColor(getSeverityLabel(score));
};
