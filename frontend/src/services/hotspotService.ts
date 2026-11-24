import api from './api';
import { Hotspot } from '../types';

export const getHotspots = (fieldId: number) => api.get<Hotspot[]>(`/fields/${fieldId}/hotspots`);
export const getHotspot = (id: number) => api.get<Hotspot>(`/hotspots/${id}`);
export const getHotspotHistory = (id: number) => api.get<Hotspot[]>(`/hotspots/${id}/history`);
export const getHotspotSummary = (fieldId: number) => api.get(`/fields/${fieldId}/hotspots/summary`);
