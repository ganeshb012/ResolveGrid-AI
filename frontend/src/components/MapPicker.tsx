import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import { MapPin, Navigation, Compass } from 'lucide-react';

// Fix leaflet default icon in webpack/vite
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface MapPickerProps {
  latitude: number;
  longitude: number;
  onLocationChange: (lat: number, lng: number, addressSuggestion?: string) => void;
}

const PUNE_PRESETS = [
  { name: 'Shivajinagar', lat: 18.5314, lng: 73.8446, addr: 'Near Shivajinagar Station, Pune 411005' },
  { name: 'Kothrud', lat: 18.5074, lng: 73.8077, addr: 'Near Paud Road, Kothrud, Pune 411038' },
  { name: 'Swargate', lat: 18.5018, lng: 73.8636, addr: 'Jedhe Chowk, Swargate, Pune 411042' },
  { name: 'Viman Nagar', lat: 18.5679, lng: 73.9143, addr: 'Symbiosis Road, Viman Nagar, Pune 411014' },
  { name: 'Baner', lat: 18.5590, lng: 73.7868, addr: 'Baner High Street, Pune 411045' },
  { name: 'Hinjewadi', lat: 18.5913, lng: 73.7389, addr: 'Phase 1 Circle, Hinjewadi IT Park, Pune 411057' },
];

function LocationMarker({
  position,
  onLocationChange,
}: {
  position: [number, number];
  onLocationChange: (lat: number, lng: number) => void;
}) {
  const map = useMap();

  useMapEvents({
    click(e) {
      onLocationChange(e.latlng.lat, e.latlng.lng);
      map.flyTo(e.latlng, map.getZoom());
    },
  });

  return position ? <Marker position={position} /> : null;
}

function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center);
  }, [center, map]);
  return null;
}

export const MapPicker: React.FC<MapPickerProps> = ({
  latitude,
  longitude,
  onLocationChange,
}) => {
  const [currentPos, setCurrentPos] = useState<[number, number]>([latitude, longitude]);

  useEffect(() => {
    setCurrentPos([latitude, longitude]);
  }, [latitude, longitude]);

  const handlePresetClick = (preset: typeof PUNE_PRESETS[0]) => {
    setCurrentPos([preset.lat, preset.lng]);
    onLocationChange(preset.lat, preset.lng, preset.addr);
  };

  return (
    <div className="space-y-3">
      {/* Pune Quick Presets */}
      <div>
        <div className="flex items-center gap-1.5 text-xs text-slate-600 mb-2 font-semibold">
          <Compass className="w-3.5 h-3.5 text-blue-600" />
          <span>Quick Pune Landmarks (Click to pin location):</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {PUNE_PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              onClick={() => handlePresetClick(p)}
              className="px-2.5 py-1 text-xs rounded-lg bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 transition-colors flex items-center gap-1 font-medium shadow-xs"
            >
              <MapPin className="w-3 h-3 text-blue-600" />
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Leaflet Map Box */}
      <div className="relative h-64 w-full rounded-2xl overflow-hidden border border-slate-300 shadow-sm">
        <MapContainer
          center={currentPos}
          zoom={13}
          scrollWheelZoom={false}
          className="h-full w-full"
        >
          <ChangeView center={currentPos} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <LocationMarker
            position={currentPos}
            onLocationChange={(lat, lng) => {
              setCurrentPos([lat, lng]);
              onLocationChange(lat, lng);
            }}
          />
        </MapContainer>

        {/* Floating coordinates badge */}
        <div className="absolute bottom-2 left-2 z-[400] bg-white/95 border border-slate-200 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-700 backdrop-blur-sm flex items-center gap-2 shadow-md">
          <Navigation className="w-3.5 h-3.5 text-blue-600" />
          <span>Lat: {currentPos[0].toFixed(5)}, Lon: {currentPos[1].toFixed(5)}</span>
        </div>
      </div>
    </div>
  );
};
