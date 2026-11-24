import api from './api';
import { DashboardSummary } from '../types';

export const getDashboard = (fieldId: number) => api.get<DashboardSummary>(`/fields/${fieldId}/dashboard`);
