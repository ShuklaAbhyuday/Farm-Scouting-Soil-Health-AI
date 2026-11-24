import api from './api';
import { SoilSample, SoilSampleCreate } from '../types';

export const getSoilSamples = (fieldId: number) => api.get<SoilSample[]>(`/fields/${fieldId}/soil-samples`);
export const createSoilSample = (fieldId: number, data: SoilSampleCreate) => api.post<SoilSample>(`/fields/${fieldId}/soil-samples`, data);
export const updateSoilSample = (id: number, data: Partial<SoilSample>) => api.put<SoilSample>(`/soil-samples/${id}`, data);
export const deleteSoilSample = (id: number) => api.delete(`/soil-samples/${id}`);
