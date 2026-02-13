"""
Unit tests for database models.
Tests model imports and basic structure without database connection.
"""
import pytest

# Import all models to ensure coverage
from api.models import (
    Lead, Qualificazione, Corriere, Preventivo, Contratto,
    Pagamento, Spedizione, ChiamataRetell, EmailInviata
)


class TestModelImports:
    """Test suite for model imports."""

    @pytest.mark.unit
    def test_all_models_imported(self):
        """Verify all expected models are imported."""
        assert Lead is not None
        assert Qualificazione is not None
        assert Corriere is not None
        assert Preventivo is not None
        assert Contratto is not None
        assert Pagamento is not None
        assert Spedizione is not None
        assert ChiamataRetell is not None
        assert EmailInviata is not None


class TestModelTableNames:
    """Test suite for model table names."""

    @pytest.mark.unit
    def test_lead_tablename(self):
        """Test Lead has correct table name."""
        assert Lead.__tablename__ == "leads"

    @pytest.mark.unit
    def test_qualificazione_tablename(self):
        """Test Qualificazione has correct table name."""
        assert Qualificazione.__tablename__ == "qualificazioni"

    @pytest.mark.unit
    def test_corriere_tablename(self):
        """Test Corriere has correct table name."""
        assert Corriere.__tablename__ == "corrieri"

    @pytest.mark.unit
    def test_preventivo_tablename(self):
        """Test Preventivo has correct table name."""
        assert Preventivo.__tablename__ == "preventivi"

    @pytest.mark.unit
    def test_contratto_tablename(self):
        """Test Contratto has correct table name."""
        assert Contratto.__tablename__ == "contratti"

    @pytest.mark.unit
    def test_pagamento_tablename(self):
        """Test Pagamento has correct table name."""
        assert Pagamento.__tablename__ == "pagamenti"

    @pytest.mark.unit
    def test_spedizione_tablename(self):
        """Test Spedizione has correct table name."""
        assert Spedizione.__tablename__ == "spedizioni"

    @pytest.mark.unit
    def test_chiamata_tablename(self):
        """Test ChiamataRetell has correct table name."""
        assert ChiamataRetell.__tablename__ == "chiamate_retell"

    @pytest.mark.unit
    def test_email_tablename(self):
        """Test EmailInviata has correct table name."""
        assert EmailInviata.__tablename__ == "email_inviate"
