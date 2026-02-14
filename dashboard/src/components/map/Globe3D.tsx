import { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Stars, Html } from '@react-three/drei';
import * as THREE from 'three';
import { useMapStore, useDashboardStore } from '@/store';
import type { Shipment } from '@/types';

// Earth sphere
function Earth() {
  const meshRef = useRef<THREE.Mesh>(null);
  
  // Create earth texture (dark blue with grid)
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 512;
    const ctx = canvas.getContext('2d')!;
    
    // Dark background
    ctx.fillStyle = '#0A1628';
    ctx.fillRect(0, 0, 1024, 512);
    
    // Grid lines
    ctx.strokeStyle = '#1a3a5c';
    ctx.lineWidth = 1;
    
    // Latitude lines
    for (let i = 0; i <= 10; i++) {
      const y = (i / 10) * 512;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(1024, y);
      ctx.stroke();
    }
    
    // Longitude lines
    for (let i = 0; i <= 20; i++) {
      const x = (i / 20) * 1024;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 512);
      ctx.stroke();
    }
    
    const tex = new THREE.CanvasTexture(canvas);
    return tex;
  }, []);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.05;
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[2, 64, 64]} />
      <meshPhongMaterial
        map={texture}
        emissive="#0A1628"
        emissiveIntensity={0.2}
        shininess={10}
      />
    </mesh>
  );
}

// Atmosphere glow
function Atmosphere() {
  return (
    <mesh scale={[2.1, 2.1, 2.1]}>
      <sphereGeometry args={[2, 64, 64]} />
      <meshBasicMaterial
        color="#00D9FF"
        transparent
        opacity={0.1}
        side={THREE.BackSide}
      />
    </mesh>
  );
}

// Marker on globe
function Marker({ 
  position, 
  color, 
  label, 
  onClick 
}: { 
  position: [number, number, number]; 
  color: string; 
  label: string;
  onClick?: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const [isClient, setIsClient] = useState(false);
  
  useEffect(() => {
    setIsClient(true);
  }, []);

  useFrame((state) => {
    if (meshRef.current) {
      const scale = hovered ? 1.5 : 1;
      meshRef.current.scale.setScalar(scale + Math.sin(state.clock.elapsedTime * 3) * 0.1);
    }
  });

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
        onClick={onClick}
      >
        <sphereGeometry args={[0.05, 16, 16]} />
        <meshBasicMaterial color={color} />
      </mesh>
      
      {/* Glow effect */}
      <mesh scale={[0.15, 0.15, 0.15]}>
        <sphereGeometry args={[1, 16, 16]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.3}
        />
      </mesh>
      
      {/* Label */}
      {isClient && hovered && (
        <Html distanceFactor={10}>
          <div className="glass-panel px-3 py-2 text-xs whitespace-nowrap pointer-events-none">
            <span style={{ color }}>{label}</span>
          </div>
        </Html>
      )}
    </group>
  );
}

// Connection line between two points
function Connection({ 
  start, 
  end, 
  color = '#00D9FF' 
}: { 
  start: [number, number, number]; 
  end: [number, number, number];
  color?: string;
}) {
  const points = useMemo(() => {
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...start),
      new THREE.Vector3(
        (start[0] + end[0]) * 0.5,
        (start[1] + end[1]) * 0.5 + 0.5,
        (start[2] + end[2]) * 0.5
      ),
      new THREE.Vector3(...end)
    );
    return curve.getPoints(50);
  }, [start, end]);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    return geo;
  }, [points]);

  return (
    <line geometry={geometry}>
      <lineBasicMaterial color={color} transparent opacity={0.6} linewidth={2} />
    </line>
  );
}

// Convert lat/lng to 3D position
function latLngToVector3(lat: number, lng: number, radius: number = 2): [number, number, number] {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  
  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);
  
  return [x, y, z];
}

interface Globe3DProps {
  onMarkerClick?: (shipment: Shipment) => void;
}

function Scene({ onMarkerClick }: Globe3DProps) {
  const { shipments } = useDashboardStore();
  const { setViewMode } = useMapStore();
  
  // Create markers from shipments
  const markers = useMemo(() => {
    const result: Array<{
      id: string;
      position: [number, number, number];
      color: string;
      label: string;
      shipment: Shipment;
    }> = [];
    
    shipments.forEach((shipment) => {
      // Origin marker
      result.push({
        id: `${shipment.id}-origin`,
        position: latLngToVector3(shipment.origin.lat, shipment.origin.lng),
        color: '#00FF88',
        label: `${shipment.trackingNumber} - Partenza: ${shipment.origin.city}`,
        shipment,
      });
      
      // Destination marker
      result.push({
        id: `${shipment.id}-dest`,
        position: latLngToVector3(shipment.destination.lat, shipment.destination.lng),
        color: '#FF6B00',
        label: `${shipment.trackingNumber} - Destinazione: ${shipment.destination.city}`,
        shipment,
      });
      
      // Carrier position (if available)
      if (shipment.currentPosition) {
        result.push({
          id: `${shipment.id}-carrier`,
          position: latLngToVector3(
            shipment.currentPosition.lat,
            shipment.currentPosition.lng
          ),
          color: '#00D9FF',
          label: `${shipment.trackingNumber} - In transito`,
          shipment,
        });
      }
    });
    
    return result;
  }, [shipments]);

  // Create connections
  const connections = useMemo(() => {
    return shipments.map((shipment) => ({
      id: shipment.id,
      start: latLngToVector3(shipment.origin.lat, shipment.origin.lng),
      end: shipment.currentPosition
        ? latLngToVector3(shipment.currentPosition.lat, shipment.currentPosition.lng)
        : latLngToVector3(shipment.destination.lat, shipment.destination.lng),
    }));
  }, [shipments]);

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1} />
      
      <Stars
        radius={100}
        depth={50}
        count={5000}
        factor={4}
        saturation={0}
        fade
        speed={1}
      />
      
      <Earth />
      <Atmosphere />
      
      {connections.map((conn) => (
        <Connection
          key={conn.id}
          start={conn.start}
          end={conn.end}
        />
      ))}
      
      {markers.map((marker) => (
        <Marker
          key={marker.id}
          position={marker.position}
          color={marker.color}
          label={marker.label}
          onClick={() => onMarkerClick?.(marker.shipment)}
        />
      ))}
      
      <OrbitControls
        enablePan={false}
        enableZoom={true}
        minDistance={3}
        maxDistance={10}
        autoRotate
        autoRotateSpeed={0.5}
      />
    </>
  );
}

import { useState } from 'react';

export const Globe3D = ({ onMarkerClick }: Globe3DProps) => {
  const { setViewMode } = useMapStore();
  
  return (
    <div className="relative w-full h-full">
      <Canvas
        camera={{ position: [0, 0, 5], fov: 45 }}
        style={{ background: '#0A0A0A' }}
      >
        <Scene onMarkerClick={onMarkerClick} />
      </Canvas>
      
      {/* Controls Overlay */}
      <div className="absolute top-4 right-4">
        <div className="glass-panel p-2">
          <p className="text-xs text-text-secondary mb-2">Vista Mappa</p>
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode('2d')}
              className="px-3 py-1.5 rounded-lg bg-surface text-text-secondary text-xs font-medium hover:text-text-primary"
            >
              2D
            </button>
            <button
              onClick={() => setViewMode('3d')}
              className="px-3 py-1.5 rounded-lg bg-primary/20 text-primary text-xs font-medium"
            >
              3D
            </button>
          </div>
        </div>
      </div>
      
      {/* Legend */}
      <div className="absolute bottom-4 left-4 glass-panel p-3">
        <p className="text-xs text-text-secondary mb-2">Legenda</p>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-success" />
            <span className="text-xs">Origine</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-warning" />
            <span className="text-xs">Destinazione</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span className="text-xs">In Transito</span>
          </div>
        </div>
      </div>
    </div>
  );
};