import api from './api';
import { SoilPdfParseResponse, SoilSample, SoilSampleCreate } from '../types';

export const getSoilSamples = (fieldId: number) => api.get<SoilSample[]>(`/fields/${fieldId}/soil-samples`);
export const createSoilSample = (fieldId: number, data: SoilSampleCreate) => api.post<SoilSample>(`/fields/${fieldId}/soil-samples`, data);
export const updateSoilSample = (id: number, data: Partial<SoilSample>) => api.put<SoilSample>(`/soil-samples/${id}`, data);
export const deleteSoilSample = (id: number) => api.delete(`/soil-samples/${id}`);

export const parseSoilReportPdf = async (file: File): Promise<{ data: SoilPdfParseResponse }> => {
  const formData = new FormData();
  formData.append('file', file);
  const baseUrl = (api.defaults.baseURL || 'http://localhost:8000/api').replace(/\/$/, '');
  const response = await fetch(`${baseUrl}/soil-samples/parse-pdf`, {
    method: 'POST',
    body: formData,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw { response: { data: payload, status: response.status } };
  }
  return { data: payload as SoilPdfParseResponse };
};
