import api from './api';
import { Farm, FarmCreate } from '../types';

export const getFarms = () => api.get<Farm[]>('/farms');
export const createFarm = (data: FarmCreate) => api.post<Farm>('/farms', data);
export const getFarm = (id: number) => api.get<Farm>(`/farms/${id}`);
export const updateFarm = (id: number, data: Partial<Farm>) => api.put<Farm>(`/farms/${id}`, data);
export const deleteFarm = (id: number) => api.delete(`/farms/${id}`);
