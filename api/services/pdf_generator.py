"""
AUTO-BROKER: PDF Generator Service
"""
import os
import base64
from typing import Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False
    HTML = None

import structlog

logger = structlog.get_logger()

COMPANY_NAME = os.getenv("COMPANY_NAME", "Logistik AI")


class PDFGeneratorService:
    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "..", "generated")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_proposal(
        self,
        preventivo_id: str,
        data_preventivo: datetime,
        valido_fino: datetime,
        cliente_nome: str,
        cliente_azienda: str,
        cliente_indirizzo: str,
        cliente_piva: str,
        corriere_nome: str,
        lane_origine: str,
        lane_destinazione: str,
        peso_kg: Decimal,
        prezzo_kg: Decimal,
        prezzo_totale: Decimal,
        tempi_consegna: int
    ) -> Dict[str, Any]:
        filename = f"proposta_{preventivo_id}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                .header {{ text-align: center; border-bottom: 3px solid #0066cc; padding-bottom: 20px; }}
                .header h1 {{ color: #0066cc; margin: 0; }}
                .section {{ margin: 20px 0; }}
                .section h2 {{ color: #0066cc; border-bottom: 1px solid #ddd; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                td {{ padding: 8px; border: 1px solid #ddd; }}
                td:first-child {{ background-color: #f5f5f5; font-weight: bold; width: 30%; }}
                .price {{ font-size: 24px; color: #0066cc; text-align: center; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{COMPANY_NAME}</h1>
                <p>Soluzioni di Trasporto e Logistica</p>
            </div>
            
            <div class="section">
                <h2>PROPOSTA COMMERCIALE #{preventivo_id[:8]}</h2>
                <table>
                    <tr><td>Data</td><td>{data_preventivo.strftime('%d/%m/%Y')}</td></tr>
                    <tr><td>Valida fino al</td><td>{valido_fino.strftime('%d/%m/%Y')}</td></tr>
                </table>
            </div>
            
            <div class="section">
                <h2>CLIENTE</h2>
                <table>
                    <tr><td>Azienda</td><td>{cliente_azienda}</td></tr>
                    <tr><td>Referente</td><td>{cliente_nome}</td></tr>
                    <tr><td>Indirizzo</td><td>{cliente_indirizzo}</td></tr>
                    <tr><td>P.IVA</td><td>{cliente_piva}</td></tr>
                </table>
            </div>
            
            <div class="section">
                <h2>SERVIZIO</h2>
                <table>
                    <tr><td>Corriere</td><td>{corriere_nome}</td></tr>
                    <tr><td>Tratta</td><td>{lane_origine} → {lane_destinazione}</td></tr>
                    <tr><td>Peso</td><td>{peso_kg} kg</td></tr>
                    <tr><td>Tempi</td><td>{tempi_consegna} giorni</td></tr>
                </table>
            </div>
            
            <div class="price">
                € {prezzo_totale:.2f}
                <div style="font-size: 14px;">Totale stimato (IVA esclusa)</div>
            </div>
            
            <div style="margin-top: 60px;">
                <p>Firma cliente: _________________________</p>
                <p>Data: _________________________</p>
            </div>
        </body>
        </html>
        """
        
        if WEASYPRINT_AVAILABLE and HTML:
            HTML(string=html_content).write_pdf(filepath)
        else:
            # Fallback: create simple PDF with reportlab
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            
            c = canvas.Canvas(filepath, pagesize=A4)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(100, 800, f"{COMPANY_NAME}")
            c.setFont("Helvetica", 12)
            c.drawString(100, 780, "Proposta Commerciale")
            c.drawString(100, 760, f"Cliente: {cliente_azienda}")
            c.drawString(100, 740, f"Corriere: {corriere_nome}")
            c.drawString(100, 720, f"Tratta: {lane_origine} -> {lane_destinazione}")
            c.drawString(100, 700, f"Prezzo: € {prezzo_totale:.2f}")
            c.save()
        
        with open(filepath, "rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode()
        
        logger.info("Proposal PDF generated", preventivo_id=preventivo_id)
        
        return {
            "filename": filename,
            "filepath": filepath,
            "base64": pdf_base64
        }


pdf_generator = PDFGeneratorService()
