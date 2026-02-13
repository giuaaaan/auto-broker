"""
Test Data Factories - Pattern usato da Google/Stripe/Meta per generare dati di test.
Genera dati realistici e validi automaticamente.
"""
import factory
from factory import Faker
from datetime import datetime
from decimal import Decimal
import uuid

from api.models import Lead, Qualificazione, Corriere, Preventivo, Contratto
from api.schemas import LeadCreate, QualifyLeadRequest, CalculatePriceRequest


class LeadFactory(factory.Factory):
    """Factory per creare Lead di test."""
    
    class Meta:
        model = LeadCreate
    
    nome = Faker('first_name', locale='it_IT')
    cognome = Faker('last_name', locale='it_IT')
    email = factory.LazyAttribute(lambda o: f"{o.nome.lower()}.{o.cognome.lower()}@test.com")
    telefono = factory.LazyAttribute(lambda o: f"+39{Faker('random_number', digits=9).evaluate(None, None, {'locale': 'it_IT'})}")
    azienda = Faker('company', locale='it_IT')
    partita_iva = factory.LazyAttribute(lambda o: f"IT{Faker('random_number', digits=11).evaluate(None, None, {'locale': 'it_IT')}}")


class QualificazioneFactory(factory.Factory):
    """Factory per creare Qualificazioni di test."""
    
    class Meta:
        model = QualifyLeadRequest
    
    lead_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    origine = factory.Iterator(['Milano', 'Roma', 'Torino', 'Napoli', 'Bologna'])
    destinazione = factory.Iterator(['Roma', 'Milano', 'Venezia', 'Firenze', 'Genova'])
    tipologia_merce = factory.Iterator(['Pallet', 'Container', 'Colli', 'Rinfusa'])
    peso_stimato_kg = factory.Iterator([100.0, 500.0, 1000.0, 2500.0, 5000.0])
    dimensioni = factory.Iterator(['80x120x100', '120x80x150', '100x100x100', '200x100x150'])
    frequenza = factory.Iterator(['settimanale', 'mensile', 'giornaliera', 'occasionale'])


class CalculatePriceFactory(factory.Factory):
    """Factory per creare richieste di calcolo prezzo."""
    
    class Meta:
        model = CalculatePriceRequest
    
    qualificazione_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    peso_kg = factory.Iterator([100.0, 250.0, 500.0, 750.0, 1000.0])
    carrier_code = factory.Iterator(['BRT', 'GLS', 'SDA', 'DHL', 'UPS'])


class CorriereFactory(factory.Factory):
    """Factory per creare Corrieri di test."""
    
    class Meta:
        model = Corriere
    
    id = factory.LazyFunction(uuid.uuid4)
    nome = factory.Iterator(['BRT', 'GLS', 'SDA', 'DHL Express', 'UPS'])
    codice = factory.Iterator(['BRT', 'GLS', 'SDA', 'DHLE', 'UPS'])
    costo_per_kg = Decimal('0.68')
    tempi_consegna_giorni = factory.Iterator([1, 2, 3, 5])
    rating_affidabilita = Decimal('95.5')
