import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { Incident, Worker } from '../types';
import { AlertTriangle, HardHat, CheckCircle2, Clock } from 'lucide-react';

interface IncidentMapProps {
  incidents: Incident[];
  workers?: Worker[];
  center?: [number, number];
  zoom?: number;
  onSelectIncident?: (incident: Incident) => void;
}

// Custom styled div icons for incident markers
const createIncidentIcon = (priority: string, category: string) => {
  const colorMap: Record<string, string> = {
    CRITICAL: '#ef4444', // Red
    HIGH: '#f97316',     // Orange
    MEDIUM: '#eab308',   // Yellow
    LOW: '#3b82f6',      // Blue
  };

  const color = colorMap[priority] || '#3b82f6';
  const pulseClass = priority === 'CRITICAL' ? 'animate-ping' : '';

  return L.divIcon({
    className: 'custom-incident-pin',
    html: `
      <div style="position: relative; width: 28px; height: 28px;">
        <span class="${pulseClass}" style="position: absolute; width: 100%; height: 100%; border-radius: 50%; background-color: ${color}; opacity: 0.4;"></span>
        <div style="position: absolute; top: 2px; left: 2px; width: 24px; height: 24px; border-radius: 50%; background-color: ${color}; border: 2px solid white; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
          <span style="color: white; font-size: 11px; font-weight: bold;">!</span>
        </div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
};

const createWorkerIcon = (status: string) => {
  const isAvail = status === 'AVAILABLE';
  const color = isAvail ? '#10b981' : '#64748b';

  return L.divIcon({
    className: 'custom-worker-pin',
    html: `
      <div style="width: 26px; height: 26px; border-radius: 50%; background-color: #0f172a; border: 2px solid ${color}; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 5px rgba(0,0,0,0.4);">
        <span style="color: ${color}; font-size: 13px;">👷</span>
      </div>
    `,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -13],
  });
};

export const IncidentMap: React.FC<IncidentMapProps> = ({
  incidents,
  workers = [],
  center = [18.5204, 73.8567], // Pune center
  zoom = 12,
  onSelectIncident,
}) => {
  return (
    <div className="relative w-full h-full min-h-[420px] rounded-xl overflow-hidden border border-slate-700 shadow-xl">
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={true}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Incident Markers */}
        {incidents.map((inc) => (
          <Marker
            key={inc.id}
            position={[inc.latitude, inc.longitude]}
            icon={createIncidentIcon(inc.priority, inc.category)}
            eventHandlers={{
              click: () => onSelectIncident && onSelectIncident(inc),
            }}
          >
            <Popup>
              <div className="p-1 min-w-[200px] text-slate-100">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-blue-300 border border-slate-700">
                    {inc.incident_number}
                  </span>
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      inc.priority === 'CRITICAL'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : inc.priority === 'HIGH'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-blue-500/20 text-blue-300'
                    }`}
                  >
                    {inc.priority}
                  </span>
                </div>
                <h4 className="font-semibold text-xs text-white mb-1 leading-snug">
                  {inc.title}
                </h4>
                <p className="text-[11px] text-slate-300 mb-2 line-clamp-2">
                  {inc.address}
                </p>
                <div className="flex items-center justify-between text-[10px] pt-1 border-t border-slate-700 text-slate-400">
                  <span className="font-mono">Status: {inc.status}</span>
                  {onSelectIncident && (
                    <button
                      onClick={() => onSelectIncident(inc)}
                      className="text-blue-400 hover:text-blue-300 font-semibold"
                    >
                      View Details →
                    </button>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Worker Markers */}
        {workers.map((w) => {
          if (!w.current_latitude || !w.current_longitude) return null;
          return (
            <Marker
              key={w.id}
              position={[w.current_latitude, w.current_longitude]}
              icon={createWorkerIcon(w.availability_status)}
            >
              <Popup>
                <div className="p-1 min-w-[180px] text-slate-100">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 mb-1">
                    <HardHat className="w-3.5 h-3.5" />
                    <span>{w.full_name}</span>
                  </div>
                  <p className="text-[11px] text-slate-300 mb-1">
                    Dept: {w.department_name || 'Municipal Field Operations'}
                  </p>
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-700">
                    <span className="font-mono">Tasks: {w.current_active_tasks}</span>
                    <span
                      className={`font-semibold ${
                        w.availability_status === 'AVAILABLE'
                          ? 'text-emerald-400'
                          : 'text-amber-400'
                      }`}
                    >
                      {w.availability_status}
                    </span>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Floating Legend */}
      <div className="absolute top-3 right-3 z-[400] bg-slate-900/90 border border-slate-700/80 px-3 py-2 rounded-xl text-[11px] text-slate-300 backdrop-blur-md shadow-2xl flex flex-col gap-1.5 pointer-events-auto">
        <span className="font-bold text-slate-200 text-[10px] uppercase tracking-wider">
          Pune Operations Map
        </span>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse"></span>
          <span>Critical / Pothole Hazard</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
          <span>High / Water Pipe Leak</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
          <span>Medium Priority</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
          <span>Field Crew Worker</span>
        </div>
      </div>
    </div>
  );
};
