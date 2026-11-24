export const SEVERITY_COLORS = {
  healthy: '#22c55e',
  mild: '#eab308',
  moderate: '#f97316',
  severe: '#ef4444',
};

export const INDEX_COLORS = {
  ndvi: { label: 'NDVI', color: '#22c55e', description: 'Vegetation Health' },
  ndmi: { label: 'NDMI', color: '#3b82f6', description: 'Moisture Stress' },
  ndre: { label: 'NDRE', color: '#a855f7', description: 'Chlorophyll / Nitrogen Proxy' },
};

export const NDVI_PALETTE = ['#d73027','#f46d43','#fdae61','#fee08b','#d9ef8b','#a6d96a','#66bd63','#1a9850'];
export const NDMI_PALETTE = ['#d73027','#f46d43','#fdae61','#fee08b','#d9ef8b','#a6d96a','#66bd63','#1a9850'];
export const NDRE_PALETTE = ['#d73027','#f46d43','#fdae61','#fee08b','#d9ef8b','#a6d96a','#66bd63','#1a9850'];

export const DEFAULT_MAP_CENTER: [number, number] = [23.2599, 77.4126]; // Bhopal
export const DEFAULT_MAP_ZOOM = 13;

export const CROP_TYPES = ['Wheat', 'Rice', 'Corn', 'Soybean', 'Cotton', 'Sugarcane', 'Pulses', 'Vegetables', 'Other'];
export const GROWTH_STAGES = ['Seedling', 'Vegetative', 'Flowering', 'Fruiting', 'Maturity', 'Harvest'];
export const SOIL_TEXTURES = ['Sandy', 'Loamy', 'Clay', 'Silt', 'Sandy Loam', 'Clay Loam', 'Silty Clay'];
