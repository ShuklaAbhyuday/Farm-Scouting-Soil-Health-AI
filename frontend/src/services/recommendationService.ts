import api from './api';
import { CropRecommendationResponse, Recommendation } from '../types';

export const generateRecommendations = (fieldId: number) => api.post(`/fields/${fieldId}/recommendations/generate`);
export const getRecommendations = (fieldId: number) => api.get<Recommendation[]>(`/fields/${fieldId}/recommendations`);
export const getRecommendation = (id: number) => api.get<Recommendation>(`/recommendations/${id}`);

export const getCropRecommendations = (fieldId: number) =>
  api.get<CropRecommendationResponse>(`/fields/${fieldId}/crop-recommendation`);

export const computeCropRecommendations = (fieldId: number, params: Record<string, any>) =>
  api.post<CropRecommendationResponse>(`/fields/${fieldId}/crop-recommendation`, params);
