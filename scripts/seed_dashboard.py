"""
AUTO-BROKER: Dashboard Database Seeder
Populates database with realistic demo data for testing Mission Control Center.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from sqlalchemy.ext.asyncio import AsyncSession
from services.database import get_db_session, init_db
from models import Spedizione, Corriere, Pagamento, Lead


# Demo data
CARRIERS_DATA = [
    {
        "nome": "Bartolini",
        "tipo": "nazionale",
        "rating": 4.5,
        "prezzo_per_km": Decimal("0.85"),
        "telefono": "+39 02 1234567",
        "email": "booking@bartolini.it"
    },
    {
        "nome": "DHL Express",
        "tipo": "internazionale",
        "rating": 4.8,
        "prezzo_per_km": Decimal("1.20"),
        "telefono": "+39 02 7654321",
        "email": "italy@dhl.com"
    },
    {
        "nome": "SDA",
        "tipo": "nazionale",
        "rating": 4.2,
        "prezzo_per_km": Decimal("0.75"),
        "telefono": "+39 02 9876543",
        "email": "book@sda.it"
    },
    {
        "nome": "TNT",
        "tipo": "internazionale",
        "rating": 4.3,
        "prezzo_per_km": Decimal("0.95"),
        "telefono": "+39 02 4567890",
        "email": "italia@tnt.com"
    },
]

SHIPMENTS_DATA = [
    {
        "tracking": "AB20260214001",
        "origin": "Via Roma 100, Milano",
        "destination": "Via Napoli 50, Roma",
        "city_origin": "Milano",
        "city_dest": "Roma",
        "stato": "in_transit",
        "peso": 150.5,
        "valore": Decimal("5000"),
        "carrier_idx": 0,
        "days_ago": 2
    },
    {
        "tracking": "AB20260214002",
        "origin": "Via Torino 45, Torino",
        "destination": "Via Palermo 23, Palermo",
        "city_origin": "Torino",
        "city_dest": "Palermo",
        "stato": "pending",
        "peso": 320.0,
        "valore": Decimal("8500"),
        "carrier_idx": 1,
        "days_ago": 0
    },
    {
        "tracking": "AB20260214003",
        "origin": "Via Firenze 12, Firenze",
        "destination": "Via Bologna 78, Bologna",
        "city_origin": "Firenze",
        "city_dest": "Bologna",
        "stato": "delivered",
        "peso": 45.0,
        "valore": Decimal("1200"),
        "carrier_idx": 2,
        "days_ago": 5
    },
    {
        "tracking": "AB20260214004",
        "origin": "Via Genova 33, Genova",
        "destination": "Via Venezia 90, Venezia",
        "city_origin": "Genova",
        "city_dest": "Venezia",
        "stato": "in_transit",
        "peso": 210.0,
        "valore": Decimal("6700"),
        "carrier_idx": 3,
        "days_ago": 1
    },
    {
        "tracking": "AB20260214005",
        "origin": "Via Bari 67, Bari",
        "destination": "Via Verona 34, Verona",
        "city_origin": "Bari",
        "city_dest": "Verona",
        "stato": "confirmed",
        "peso": 89.5,
        "valore": Decimal("3400"),
        "carrier_idx": 0,
        "days_ago": 1
    },
    {
        "tracking": "AB20260214006",
        "origin": "Via Padova 89, Padova",
        "destination": "Via Catania 12, Catania",
        "city_origin": "Padova",
        "city_dest": "Catania",
        "stato": "disputed",
        "peso": 175.0,
        "valore": Decimal("4200"),
        "carrier_idx": 2,
        "days_ago": 3
    },
    {
        "tracking": "AB20260214007",
        "origin": "Via Trieste 56, Trieste",
        "destination": "Via Brescia 45, Brescia",
        "city_origin": "Trieste",
        "city_dest": "Brescia",
        "stato": "in_transit",
        "peso": 130.0,
        "valore": Decimal("2800"),
        "carrier_idx": 1,
        "days_ago": 2
    },
    {
        "tracking": "AB20260214008",
        "origin": "Via Parma 23, Parma",
        "destination": "Via Modena 67, Modena",
        "city_origin": "Parma",
        "city_dest": "Modena",
        "stato": "pending",
        "peso": 55.0,
        "valore": Decimal("1800"),
        "carrier_idx": 3,
        "days_ago": 0
    },
]

PAYMENTS_DATA = [
    {"importo": Decimal("500"), "days_ago": 0},
    {"importo": Decimal("750"), "days_ago": 1},
    {"importo": Decimal("1200"), "days_ago": 2},
    {"importo": Decimal("890"), "days_ago": 3},
    {"importo": Decimal("1100"), "days_ago": 4},
    {"importo": Decimal("650"), "days_ago": 5},
    {"importo": Decimal("950"), "days_ago": 6},
    {"importo": Decimal("1400"), "days_ago": 7},
    {"importo": Decimal("720"), "days_ago": 8},
    {"importo": Decimal("880"), "days_ago": 9},
    {"importo": Decimal("1050"), "days_ago": 10},
    {"importo": Decimal("600"), "days_ago": 11},
    {"importo": Decimal("1300"), "days_ago": 12},
    {"importo": Decimal("780"), "days_ago": 13},
    {"importo": Decimal("920"), "days_ago": 14},
]


async def seed_carriers(db: AsyncSession) -> list:
    """Create carrier records."""
    print("🚛 Creating carriers...")
    carriers = []
    
    for data in CARRIERS_DATA:
        carrier = Corriere(
            id=uuid4(),
            nome=data["nome"],
            tipo=data["tipo"],
            rating=data["rating"],
            prezzo_per_km=data["prezzo_per_km"],
            telefono=data["telefono"],
            email=data["email"],
            disponibile=True
        )
        db.add(carrier)
        carriers.append(carrier)
    
    await db.commit()
    print(f"✅ Created {len(carriers)} carriers")
    return carriers


async def seed_shipments(db: AsyncSession, carriers: list) -> list:
    """Create shipment records."""
    print("📦 Creating shipments...")
    shipments = []
    
    for data in SHIPMENTS_DATA:
        carrier = carriers[data["carrier_idx"]]
        created_at = datetime.utcnow() - timedelta(days=data["days_ago"])
        
        # Calculate estimated delivery
        if data["stato"] == "delivered":
            est_delivery = created_at + timedelta(days=2)
            act_delivery = created_at + timedelta(days=2)
        else:
            est_delivery = created_at + timedelta(days=3)
            act_delivery = None
        
        shipment = Spedizione(
            id=uuid4(),
            codice_tracking=data["tracking"],
            corriere_id=carrier.id,
            origine=data["origin"],
            destinazione=data["destination"],
            stato=data["stato"],
            peso_kg=data["peso"],
            valore_merce=data["valore"],
            data_consegna_stimata=est_delivery,
            data_consegna_effettiva=act_delivery,
            created_at=created_at,
            updated_at=created_at
        )
        db.add(shipment)
        shipments.append(shipment)
    
    await db.commit()
    print(f"✅ Created {len(shipments)} shipments")
    return shipments


async def seed_payments(db: AsyncSession) -> list:
    """Create payment records for revenue simulation."""
    print("💰 Creating payments...")
    payments = []
    
    for data in PAYMENTS_DATA:
        created_at = datetime.utcnow() - timedelta(days=data["days_ago"])
        
        payment = Pagamento(
            id=uuid4(),
            importo=data["importo"],
            stripe_payment_status="completed",
            created_at=created_at
        )
        db.add(payment)
        payments.append(payment)
    
    await db.commit()
    print(f"✅ Created {len(payments)} payments")
    return payments


async def print_summary(db: AsyncSession):
    """Print summary of seeded data."""
    from sqlalchemy import select, func
    
    # Count shipments by status
    result = await db.execute(
        select(Spedizione.stato, func.count(Spedizione.id))
        .group_by(Spedizione.stato)
    )
    status_counts = dict(result.all())
    
    # Calculate total revenue
    result = await db.execute(
        select(func.sum(Pagamento.importo))
        .where(Pagamento.stripe_payment_status == "completed")
    )
    total_revenue = result.scalar() or Decimal("0")
    
    print("\n" + "="*50)
    print("📊 SEED SUMMARY")
    print("="*50)
    print(f"\n🚛 Carriers: {len(CARRIERS_DATA)}")
    print(f"📦 Shipments by status:")
    for status, count in status_counts.items():
        print(f"   - {status}: {count}")
    print(f"\n💰 Total Revenue: €{total_revenue:,.2f}")
    print(f"   (Simulates Level 2 - Growth)")
    print("\n" + "="*50)
    print("✨ Dashboard ready at: http://localhost:5173")
    print("   Login: admin@autobroker.com / admin")
    print("="*50)


async def main():
    """Main seeding function."""
    print("🚀 AUTO-BROKER Dashboard Seeder")
    print("="*50)
    
    # Initialize database
    print("\n📡 Initializing database...")
    await init_db()
    
    async with get_db_session() as db:
        try:
            # Check if data already exists
            from sqlalchemy import select, func
            result = await db.execute(select(func.count()).select_from(Spedizione))
            existing = result.scalar()
            
            if existing and existing > 0:
                print(f"\n⚠️  Found {existing} existing shipments.")
                response = input("   Do you want to continue and add more? (y/N): ")
                if response.lower() != 'y':
                    print("   Aborted.")
                    return
            
            # Seed data
            carriers = await seed_carriers(db)
            shipments = await seed_shipments(db, carriers)
            payments = await seed_payments(db)
            
            # Print summary
            await print_summary(db)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())