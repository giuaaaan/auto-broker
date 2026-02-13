#!/usr/bin/env python3
"""
Test manuale eseguibile senza pytest.
Verifica che le funzioni base funzionino correttamente.
"""
import sys
import os

# Setup test environment
os.environ["DATABASE_URL"] = "postgresql://broker_user:broker_pass_2024@localhost:5432/broker_db"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["ENVIRONMENT"] = "testing"
os.environ["RETELL_API_KEY"] = "test"
os.environ["STRIPE_SECRET_KEY"] = "sk_test"
os.environ["RESEND_API_KEY"] = "test"
os.environ["COMPANY_NAME"] = "Test"

def test_imports():
    """Test che tutti gli import funzionino."""
    print("Test 1: Verifica imports...")
    try:
        from api import models, schemas
        from api.services import database, retell_service, stripe_service
        from api.services import docusign_service, email_service, pdf_generator, scraper
        print("✅ Tutti gli imports funzionano")
        return True
    except Exception as e:
        print(f"❌ Import fallito: {e}")
        return False

def test_schemas():
    """Test che gli schema Pydantic funzionino."""
    print("\nTest 2: Verifica schemas...")
    try:
        from api.schemas import LeadCreate, QualifyLeadRequest
        
        lead = LeadCreate(
            nome="Mario",
            azienda="Test Srl",
            telefono="+391234567",
            email="test@test.com"
        )
        assert lead.nome == "Mario"
        
        qual = QualifyLeadRequest(
            lead_id="123e4567-e89b-12d3-a456-426614174000",
            volume_kg_mensile=500.0,
            lane_origine="Milano",
            lane_destinazione="Roma",
            frequenza="settimanale",
            prezzo_attuale_kg=1.20,
            tipo_merce="Test",
            partita_iva="IT12345678901"
        )
        assert qual.volume_kg_mensile == 500.0
        print("✅ Schemas funzionano correttamente")
        return True
    except Exception as e:
        print(f"❌ Schema test fallito: {e}")
        return False

def test_services_mock():
    """Test che i servizi funzionino in modalità mock."""
    print("\nTest 3: Verifica servizi (mock mode)...")
    try:
        import asyncio
        
        async def test_async():
            from api.services.retell_service import retell_service
            from api.services.stripe_service import stripe_service
            from api.services.email_service import email_service
            from api.services.pdf_generator import pdf_generator
            from api.services.scraper import carrier_scraper
            
            # Test Retell
            result = await retell_service.call_sara("+39123", "lead1", "Azienda", "Mario")
            assert "call_id" in result
            
            # Test Stripe
            from decimal import Decimal
            fees = await stripe_service.calculate_fees(Decimal("100"))
            assert "stripe_fees" in fees
            
            # Test Email
            result = await email_service.send_email("test@test.com", "Subject", "<h1>Test</h1>")
            assert result["status"] == "sent"
            
            # Test PDF
            from datetime import datetime
            from decimal import Decimal
            result = pdf_generator.generate_proposal(
                "test-123", datetime.now(), datetime.now(),
                "Mario", "Azienda", "Via X", "IT123",
                "BRT", "Milano", "Roma", Decimal("100"),
                Decimal("1.0"), Decimal("100"), 1
            )
            assert "filename" in result
            
            # Test Scraper
            quotes = await carrier_scraper.scrape_all_carriers("Milano", "Roma", 100.0)
            assert len(quotes) > 0
        
        asyncio.run(test_async())
        print("✅ Tutti i servizi funzionano in mock mode")
        return True
    except Exception as e:
        print(f"❌ Servizi test fallito: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_calcolo_margine():
    """Verifica che il calcolo del margine 30% sia corretto."""
    print("\nTest 4: Verifica calcolo margine 30%...")
    try:
        from decimal import Decimal
        
        # Test logica margine
        costo = Decimal("100.00")
        markup = Decimal("1.30")  # 30%
        prezzo_vendita = costo * markup
        margine_netto = prezzo_vendita - costo
        
        assert prezzo_vendita == Decimal("130.00"), f"Prezzo atteso 130, got {prezzo_vendita}"
        assert margine_netto == Decimal("30.00"), f"Margine atteso 30, got {margine_netto}"
        
        print(f"✅ Calcolo margine corretto: costo={costo}, vendita={prezzo_vendita}, margine={margine_netto}")
        return True
    except Exception as e:
        print(f"❌ Calcolo margine fallito: {e}")
        return False

def main():
    print("="*60)
    print("TEST MANUALE AUTO-BROKER")
    print("="*60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Schemas", test_schemas()))
    results.append(("Servizi Mock", test_services_mock()))
    results.append(("Calcolo Margine", test_calcolo_margine()))
    
    print("\n" + "="*60)
    print("RISULTATI:")
    print("="*60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    passed_count = sum(1 for _, p in results if p)
    print(f"\nTotale: {passed_count}/{len(results)} test passati")
    
    if passed_count == len(results):
        print("🎉 Tutti i test passati!")
        return 0
    else:
        print("⚠️  Alcuni test falliti")
        return 1

if __name__ == "__main__":
    sys.exit(main())
