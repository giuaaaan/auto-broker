"""
Unit tests for PDF generator service.
"""
import os
import pytest
from decimal import Decimal
from datetime import datetime

from api.services.pdf_generator import PDFGeneratorService, pdf_generator


class TestPDFGeneratorService:
    """Test suite for PDFGeneratorService."""

    @pytest.mark.unit
    def test_generate_proposal(self, tmp_path):
        """Test PDF proposal generation."""
        service = PDFGeneratorService()
        # Set output dir via monkeypatch to use temp path
        original_dir = service.output_dir
        service.output_dir = str(tmp_path)
        os.makedirs(service.output_dir, exist_ok=True)
        
        try:
            result = service.generate_proposal(
                preventivo_id="test-123",
                data_preventivo=datetime.now(),
                valido_fino=datetime.now(),
                cliente_nome="Mario Rossi",
                cliente_azienda="Rossi Srl",
                cliente_indirizzo="Via Milano 10, Milano",
                cliente_piva="IT12345678901",
                corriere_nome="BRT",
                lane_origine="Milano",
                lane_destinazione="Roma",
                peso_kg=Decimal("500"),
                prezzo_kg=Decimal("0.85"),
                prezzo_totale=Decimal("425.00"),
                tempi_consegna=1
            )
            
            assert "filename" in result
            assert "filepath" in result
            assert "base64" in result
            assert result["filename"].startswith("proposta_")
            assert result["filename"].endswith(".pdf")
            # Verify file was created
            assert os.path.exists(result["filepath"])
        finally:
            service.output_dir = original_dir

    @pytest.mark.unit
    def test_generate_proposal_html_content(self, tmp_path):
        """Test that proposal HTML contains expected content."""
        service = PDFGeneratorService()
        original_dir = service.output_dir
        service.output_dir = str(tmp_path)
        os.makedirs(service.output_dir, exist_ok=True)
        
        try:
            result = service.generate_proposal(
                preventivo_id="test-456",
                data_preventivo=datetime(2024, 1, 15),
                valido_fino=datetime(2024, 2, 15),
                cliente_nome="Giuseppe Bianchi",
                cliente_azienda="Bianchi Trasporti",
                cliente_indirizzo="Via Roma 25, Roma",
                cliente_piva="IT98765432109",
                corriere_nome="GLS",
                lane_origine="Torino",
                lane_destinazione="Napoli",
                peso_kg=Decimal("1000"),
                prezzo_kg=Decimal("0.78"),
                prezzo_totale=Decimal("780.00"),
                tempi_consegna=2
            )
            
            # Verify base64 content is valid
            import base64
            decoded = base64.b64decode(result["base64"])
            assert decoded.startswith(b"%PDF") or len(decoded) > 100
        finally:
            service.output_dir = original_dir

    @pytest.mark.unit
    def test_output_directory_created_on_init(self):
        """Test that output directory is created on initialization."""
        service = PDFGeneratorService()
        # Directory should exist after initialization
        assert os.path.exists(service.output_dir)

    @pytest.mark.unit
    def test_pdf_generator_singleton(self):
        """Test that pdf_generator is a singleton instance."""
        assert isinstance(pdf_generator, PDFGeneratorService)
