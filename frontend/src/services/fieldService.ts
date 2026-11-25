import api from './api';
import { Field, FieldCreate } from '../types';

export const getFields = (farmId: number) => api.get<Field[]>(`/farms/${farmId}/fields`);
export const createField = (farmId: number, data: FieldCreate) => api.post<Field>(`/farms/${farmId}/fields`, data);
export const getField = (id: number) => api.get<Field>(`/fields/${id}`);
export const updateField = (id: number, data: Partial<Field>) => api.put<Field>(`/fields/${id}`, data);
export const deleteField = (id: number) => api.delete(`/fields/${id}`);
