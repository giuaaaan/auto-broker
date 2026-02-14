import { useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useMapStore, useDashboardStore } from '@/store';
import type { Shipment } from '@/types';

// CartoDB Dark Matter style
const MAP_STYLE = {
  version: 8,
  sources: {
    'carto-dark': {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
      ],
      tileSize: 256,
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    },
  },
  layers: [
    {
      id: 'carto-dark-layer',
      type: 'raster',
      source: 'carto-dark',
    },
  ],
};

interface Map2DProps {
  onMarkerClick?: (shipment: Shipment) => void;
}

export const Map2D = ({ onMarkerClick }: Map2DProps) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Record<string, maplibregl.Marker>>({});
  
  const { markers, routes, selectedMarker } = useMapStore();
  const { shipments } = useDashboardStore();

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE as maplibregl.StyleSpecification,
      center: [12.5, 42.0], // Center of Italy
      zoom: 5,
      pitch: 45,
      attributionControl: false,
    });

    // Add navigation controls
    map.current.addControl(
      new maplibregl.NavigationControl(),
      'bottom-right'
    );

    // Add attribution
    map.current.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      'bottom-left'
    );

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Update markers
  const updateMarkers = useCallback(() => {
    if (!map.current) return;

    // Clear existing markers
    Object.values(markersRef.current).forEach((marker) => marker.remove());
    markersRef.current = {};

    // Add new markers
    markers.forEach((markerData) => {
      const el = document.createElement('div');
      el.className = 'custom-marker';
      
      // Style based on type
      const color = markerData.type === 'origin' 
        ? '#00FF88' 
        : markerData.type === 'destination' 
        ? '#FF6B00' 
        : '#00D9FF';
      
      el.innerHTML = `
        <div style="
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: ${color};
          border: 3px solid #0A0A0A;
          box-shadow: 0 0 20px ${color}80;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: bold;
          color: #0A0A0A;
        ">
          ${markerData.type === 'origin' ? 'O' : markerData.type === 'destination' ? 'D' : 'C'}
        </div>
      `;

      const marker = new maplibregl.Marker({
        element: el,
        anchor: 'center',
      })
        .setLngLat(markerData.position)
        .addTo(map.current);

      // Add popup
      const popup = new maplibregl.Popup({
        offset: 25,
        closeButton: false,
        className: 'dark-popup',
      }).setHTML(`
        <div style="color: #fff; font-family: Inter, sans-serif;">
          <strong>${markerData.label}</strong>
          <br/>
          <span style="color: #A0A0A0; font-size: 12px;">
            ${markerData.type === 'carrier' ? 'In transito' : markerData.type === 'origin' ? 'Partenza' : 'Destinazione'}
          </span>
        </div>
      `);

      marker.setPopup(popup);

      el.addEventListener('click', () => {
        if (markerData.shipmentId && onMarkerClick) {
          const shipment = shipments.find((s) => s.id === markerData.shipmentId);
          if (shipment) onMarkerClick(shipment);
        }
      });

      markersRef.current[markerData.id] = marker;
    });
  }, [markers, shipments, onMarkerClick]);

  // Update routes
  const updateRoutes = useCallback(() => {
    if (!map.current) return;

    // Remove existing route layers
    routes.forEach((route) => {
      const layerId = `route-${route.id}`;
      const sourceId = `route-source-${route.id}`;
      
      if (map.current?.getLayer(layerId)) {
        map.current.removeLayer(layerId);
      }
      if (map.current?.getSource(sourceId)) {
        map.current.removeSource(sourceId);
      }
    });

    // Add new routes
    routes.forEach((route) => {
      const layerId = `route-${route.id}`;
      const sourceId = `route-source-${route.id}`;

      map.current?.addSource(sourceId, {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: route.coordinates,
          },
        },
      });

      map.current?.addLayer({
        id: layerId,
        type: 'line',
        source: sourceId,
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
        },
        paint: {
          'line-color': route.color,
          'line-width': 3,
          'line-opacity': 0.8,
          ...(route.animated && {
            'line-dasharray': [2, 2],
          }),
        },
      });

      // Animate line if needed
      if (route.animated) {
        let offset = 0;
        const animate = () => {
          offset -= 1;
          map.current?.setPaintProperty(layerId, 'line-dashoffset', offset);
          requestAnimationFrame(animate);
        };
        animate();
      }
    });
  }, [routes]);

  // Update on data changes
  useEffect(() => {
    updateMarkers();
  }, [updateMarkers]);

  useEffect(() => {
    if (map.current?.loaded()) {
      updateRoutes();
    } else {
      map.current?.on('load', updateRoutes);
    }
  }, [updateRoutes]);

  // Fly to selected marker
  useEffect(() => {
    if (selectedMarker && map.current) {
      const marker = markersRef.current[selectedMarker];
      if (marker) {
        const lngLat = marker.getLngLat();
        map.current.flyTo({
          center: [lngLat.lng, lngLat.lat],
          zoom: 12,
          duration: 1000,
        });
        marker.togglePopup();
      }
    }
  }, [selectedMarker]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full rounded-xl" />
      
      {/* Map Controls Overlay */}
      <div className="absolute top-4 right-4 flex flex-col gap-2">
        <div className="glass-panel p-2">
          <p className="text-xs text-text-secondary mb-2">Vista Mappa</p>
          <div className="flex gap-2">
            <button
              onClick={() => useMapStore.getState().setViewMode('2d')}
              className="px-3 py-1.5 rounded-lg bg-primary/20 text-primary text-xs font-medium"
            >
              2D
            </button>
            <button
              onClick={() => useMapStore.getState().setViewMode('3d')}
              className="px-3 py-1.5 rounded-lg bg-surface text-text-secondary text-xs font-medium hover:text-text-primary"
            >
              3D
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};