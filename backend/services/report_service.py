from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

class ReportService:
    def generate_pdf_report(self, field, observations, recommendations, file_path):
        """
        Generate PDF report using ReportLab.
        Clear labeling: "Satellite-Derived" vs "Ground-Truth".
        """
        c = canvas.Canvas(file_path, pagesize=letter)
        c.drawString(100, 750, f"Farm Scouting Report - Field: {field.name}")
        c.drawString(100, 730, "===============================================")
        
        y = 700
        c.drawString(100, y, "--- Satellite-Derived Data ---")
        y -= 20
        for obs in observations:
            c.drawString(100, y, f"Date: {obs.acquisition_date} | Cloud: {obs.cloud_cover_pct}%")
            y -= 20
            
        y -= 20
        c.drawString(100, y, "--- Ground-Truth Data & Recommendations ---")
        y -= 20
        for rec in recommendations:
            c.drawString(100, y, f"[{rec.category.upper()}] {rec.title}")
            y -= 20
            c.drawString(120, y, f"Reasoning: {rec.reasoning}")
            y -= 30
            
        c.save()
        return file_path
