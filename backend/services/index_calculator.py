import numpy as np

class IndexCalculator:
    """Calculates indices from raw band arrays (numpy) avoiding division by zero."""
    
    @staticmethod
    def calculate_ndvi(nir, red):
        """NDVI = (NIR - Red) / (NIR + Red)"""
        numerator = nir - red
        denominator = nir + red
        return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator!=0)
        
    @staticmethod
    def calculate_ndmi(nir, swir):
        """NDMI = (NIR - SWIR) / (NIR + SWIR)"""
        numerator = nir - swir
        denominator = nir + swir
        return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator!=0)
        
    @staticmethod
    def calculate_ndre(nir, red_edge):
        """NDRE = (NIR - RedEdge) / (NIR + RedEdge)"""
        numerator = nir - red_edge
        denominator = nir + red_edge
        return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator!=0)
