import api from './api';
import { SatelliteObservation, AnalysisRequest, HistoricalData } from '../types';

export const analyzeField = (fieldId: number, data: AnalysisRequest) => api.post(`/fields/${fieldId}/analyze`, null, { params: data });
export const getObservations = (fieldId: number) => api.get<SatelliteObservation[]>(`/fields/${fieldId}/observations`);
export const getObservation = (id: number) => api.get<SatelliteObservation>(`/observations/${id}`);
export const getIndexHistory = (fieldId: number) => api.get<HistoricalData>(`/fields/${fieldId}/history`);
