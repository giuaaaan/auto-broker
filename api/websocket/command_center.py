"""
AUTO-BROKER: WebSocket Command Center
Real-time updates for Mission Control Dashboard.
"""
import socketio
from datetime import datetime
from typing import Dict, Any

# Create Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    async_mode='asgi',
    logger=True,
    engineio_logger=True
)

# Store connected clients
connected_clients: Dict[str, Dict[str, Any]] = {}


# ==========================================
# EVENT HANDLERS
# ==========================================

@sio.event
async def connect(sid: str, environ: dict):
    """Handle client connection."""
    print(f"[WebSocket] Client {sid} connected to Command Center")
    connected_clients[sid] = {
        "connected_at": datetime.utcnow(),
        "last_ping": datetime.utcnow()
    }
    
    # Send welcome message
    await sio.emit('connection_established', {
        'sid': sid,
        'timestamp': datetime.utcnow().isoformat(),
        'message': 'Connected to Auto-Broker Command Center'
    }, room=sid)


@sio.event
async def disconnect(sid: str):
    """Handle client disconnection."""
    print(f"[WebSocket] Client {sid} disconnected")
    if sid in connected_clients:
        del connected_clients[sid]


@sio.event
async def ping(sid: str):
    """Handle ping from client."""
    if sid in connected_clients:
        connected_clients[sid]["last_ping"] = datetime.utcnow()
    await sio.emit('pong', {'timestamp': datetime.utcnow().isoformat()}, room=sid)


@sio.event
async def subscribe(sid: str, data: dict):
    """Handle subscription to specific channels."""
    channel = data.get('channel', 'all')
    print(f"[WebSocket] Client {sid} subscribed to {channel}")
    
    # Join room for specific channel
    await sio.enter_room(sid, channel)
    
    await sio.emit('subscribed', {
        'channel': channel,
        'timestamp': datetime.utcnow().isoformat()
    }, room=sid)


# ==========================================
# BROADCAST FUNCTIONS
# ==========================================

async def broadcast_update(event_type: str, data: dict):
    """Broadcast update to all connected clients."""
    message = {
        'type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }
    await sio.emit(event_type, message)
    print(f"[WebSocket] Broadcasted {event_type} to {len(connected_clients)} clients")


async def broadcast_shipment_update(shipment_id: str, status: str, position: dict = None, eta: str = None):
    """Broadcast shipment status update."""
    await broadcast_update('shipment_update', {
        'shipment_id': shipment_id,
        'status': status,
        'current_position': position,
        'eta': eta
    })


async def broadcast_carrier_position(carrier_id: str, lat: float, lon: float, heading: float = None, speed: float = None):
    """Broadcast carrier position update."""
    await broadcast_update('carrier_position', {
        'carrier_id': carrier_id,
        'position': {
            'lat': lat,
            'lng': lon
        },
        'heading': heading,
        'speed': speed
    })


async def broadcast_agent_activity(agent_id: str, activity: dict):
    """Broadcast agent activity."""
    await broadcast_update('agent_activity', {
        'agent_id': agent_id,
        'activity': activity
    })


async def broadcast_revenue_update(mrr: float, growth: float):
    """Broadcast revenue update."""
    await broadcast_update('revenue_update', {
        'mrr': mrr,
        'growth': growth,
        'timestamp': datetime.utcnow().isoformat()
    })


async def broadcast_system_alert(alert_type: str, message: str, severity: str = 'info'):
    """Broadcast system alert."""
    await broadcast_update('system_alert', {
        'type': alert_type,
        'message': message,
        'severity': severity,
        'timestamp': datetime.utcnow().isoformat()
    })


# ==========================================
# INTEGRATION HELPERS
# ==========================================

class WebSocketNotifier:
    """Helper class to integrate WebSocket with services."""
    
    @staticmethod
    async def notify_shipment_created(shipment_data: dict):
        """Notify when new shipment is created."""
        await broadcast_shipment_update(
            shipment_id=shipment_data['id'],
            status='pending'
        )
    
    @staticmethod
    async def notify_shipment_status_changed(shipment_id: str, old_status: str, new_status: str):
        """Notify when shipment status changes."""
        await broadcast_shipment_update(
            shipment_id=shipment_id,
            status=new_status
        )
    
    @staticmethod
    async def notify_paolo_suggestion(suggestion: dict):
        """Notify when PAOLO suggests an action."""
        await broadcast_agent_activity('PAOLO', {
            'id': suggestion.get('id'),
            'type': 'suggestion',
            'title': suggestion.get('title'),
            'description': suggestion.get('description'),
            'priority': suggestion.get('priority', 'medium'),
            'shipment_id': suggestion.get('shipment_id'),
            'actions': suggestion.get('actions', []),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @staticmethod
    async def notify_revenue_threshold_reached(level_id: str, revenue: float):
        """Notify when revenue reaches new level."""
        await broadcast_system_alert(
            alert_type='level_up',
            message=f'Raggiunto livello {level_id}! Revenue: €{revenue:,.2f}',
            severity='success'
        )
    
    @staticmethod
    async def notify_emergency_stop(reason: str, operator: str):
        """Notify emergency stop activation."""
        await broadcast_system_alert(
            alert_type='emergency_stop',
            message=f'Emergency Stop attivato da {operator}: {reason}',
            severity='error'
        )


# Create ASGI app for mounting
socket_app = socketio.ASGIApp(sio)