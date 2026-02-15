"""
Data Seeder Utility
Popola il database con dati demo per testing e sviluppo
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import datetime, timedelta
import random
import uuid

from config import settings
from models import Spedizione, Pagamento


async def seed_demo_data(db: AsyncSession) -> dict:
    """
    Popola il database con dati demo:
    - 15-20 spedizioni
    - 4 carrier (Bartolini, DHL, SDA, TNT)
    - Revenue iniziale €4.500 (Livello 2)
    """
    if not settings.DEMO_MODE:
        return {
            "status": "error",
            "message": "Only available in DEMO_MODE"
        }
    
    # Verifica se ci sono già dati
    result = await db.execute(select(Spedizione))
    existing = result.scalars().first()
    
    if existing:
        return {
            "status": "skipped",
            "message": "Database already contains data",
            "action": "Use reset_demo_data to clear and re-seed"
        }
    
    # Dati demo
    carriers = [
        {"id": "BRT", "name": "Bartolini", "color": "#ef4444"},
        {"id": "DHL", "name": "DHL Express", "color": "#eab308"},
        {"id": "SDA", "name": "SDA", "color": "#3b82f6"},
        {"id": "TNT", "name": "TNT", "color": "#f97316"},
    ]
    
    clients = [
        {"name": "Rossi Srl", "city": "Milano"},
        {"name": "Bianchi Spa", "city": "Roma"},
        {"name": "Verdi & Co", "city": "Torino"},
        {"name": "Neri Logistics", "city": "Bologna"},
        {"name": "Gialli Trasporti", "city": "Napoli"},
    ]
    
    lanes = [
        {"from": "Milano", "to": "Roma", "distance": 570},
        {"from": "Torino", "to": "Palermo", "distance": 1650},
        {"from": "Bologna", "to": "Napoli", "distance": 580},
        {"from": "Verona", "to": "Bari", "distance": 890},
        {"from": "Firenze", "to": "Genova", "distance": 230},
        {"from": "Roma", "to": "Milano", "distance": 570},
        {"from": "Napoli", "to": "Torino", "distance": 890},
    ]
    
    statuses = ["in_transito", "consegnata", "ritirata", "in_preparazione"]
    
    created_shipments = []
    total_revenue = 0
    
    # Crea 18 spedizioni
    for i in range(18):
        lane = random.choice(lanes)
        carrier = random.choice(carriers)
        client = random.choice(clients)
        status = random.choice(statuses)
        
        # Calcola importi
        base_cost = lane["distance"] * random.uniform(0.8, 1.5)
        revenue = round(base_cost * random.uniform(1.2, 1.4), 2)
        total_revenue += revenue
        
        shipment = Spedizione(
            id=uuid.uuid4(),
            numero_tracking=f"SHIP-{uuid.uuid4().hex[:8].upper()}",
            mittente_nome=client["name"],
            mittente_indirizzo=f"Via Demo {random.randint(1, 100)}, {lane['from']}",
            mittente_citta=lane["from"],
            destinatario_nome=f"Cliente {random.randint(1, 100)}",
            destinatario_indirizzo=f"Via Dest {random.randint(1, 100)}, {lane['to']}",
            destinatario_citta=lane["to"],
            peso_kg=random.randint(50, 2000),
            volume_m3=round(random.uniform(0.5, 20), 2),
            corriere_id=carrier["id"],
            corriere_nome=carrier["name"],
            status=status,
            data_creazione=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            data_spedizione=datetime.utcnow() - timedelta(days=random.randint(0, 15)) if status != "in_preparazione" else None,
            data_consegna_stimata=datetime.utcnow() + timedelta(days=random.randint(1, 7)),
        )
        
        db.add(shipment)
        created_shipments.append(shipment)
    
    # Crea pagamenti per spedizioni consegnate
    delivered = [s for s in created_shipments if s.status == "consegnata"]
    for shipment in delivered[:5]:  # Solo prime 5
        payment = Pagamento(
            id=uuid.uuid4(),
            spedizione_id=shipment.id,
            importo_cliente=round(random.uniform(200, 1500), 2),
            costo_corriere=round(random.uniform(150, 1200), 2),
            profitto_finale=round(random.uniform(50, 300), 2),
            stripe_payment_status="succeeded",
            data_pagamento=datetime.utcnow() - timedelta(days=random.randint(0, 10)),
        )
        db.add(payment)
    
    await db.commit()
    
    return {
        "status": "success",
        "message": "Demo database seeded successfully",
        "created": {
            "shipments": len(created_shipments),
            "payments": min(5, len(delivered)),
            "carriers": len(carriers),
            "clients": len(clients)
        },
        "initial_revenue": round(total_revenue, 2),
        "level": 2,
        "mock": True
    }


async def reset_demo_data(db: AsyncSession) -> dict:
    """Cancella tutti i dati e re-seeda"""
    if not settings.DEMO_MODE:
        return {
            "status": "error",
            "message": "Only available in DEMO_MODE"
        }
    
    # Delete all data
    await db.execute(text("TRUNCATE TABLE pagamenti CASCADE"))
    await db.execute(text("TRUNCATE TABLE spedizioni CASCADE"))
    
    await db.commit()
    
    # Re-seed
    return await seed_demo_data(db)
