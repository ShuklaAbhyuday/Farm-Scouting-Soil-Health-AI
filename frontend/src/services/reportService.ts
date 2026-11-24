import api from './api';

export const generateReport = (fieldId: number, params: any) => api.post(`/fields/${fieldId}/reports`, params);
export const getReports = (fieldId: number) => api.get(`/fields/${fieldId}/reports`);
export const downloadReport = (id: number) => api.get(`/reports/${id}/download`, { responseType: 'blob' });
