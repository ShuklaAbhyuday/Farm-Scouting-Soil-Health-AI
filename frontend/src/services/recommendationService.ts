import api from './api';
import { Recommendation } from '../types';

export const generateRecommendations = (fieldId: number) => api.post(`/fields/${fieldId}/recommendations/generate`);
export const getRecommendations = (fieldId: number) => api.get<Recommendation[]>(`/fields/${fieldId}/recommendations`);
export const getRecommendation = (id: number) => api.get<Recommendation>(`/recommendations/${id}`);
