import numpy as np

def extract_features(ndvi_array, ndmi_array, ndre_array, temporal_data=None):
    """
    Feature engineering for the ML model.
    Returns a feature matrix where each row is a pixel and columns are features.
    """
    features = []
    
    # Flatten arrays
    ndvi_flat = ndvi_array.flatten()
    ndmi_flat = ndmi_array.flatten()
    ndre_flat = ndre_array.flatten()
    
    for i in range(len(ndvi_flat)):
        pixel_features = [
            ndvi_flat[i],
            ndmi_flat[i],
            ndre_flat[i],
            # Example computed features
            ndvi_flat[i] - np.mean(ndvi_flat),
            ndmi_flat[i] - np.mean(ndmi_flat)
        ]
        
        if temporal_data is not None:
            temporal_flat = temporal_data.flatten()
            pixel_features.append(temporal_flat[i])
            
        features.append(pixel_features)
        
    return np.array(features)
