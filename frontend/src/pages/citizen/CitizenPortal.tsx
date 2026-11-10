import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { wsClient } from '../../api/ws';
import { Incident } from '../../types';
import { VoiceRecorder } from '../../components/VoiceRecorder';
import { MapPicker } from '../../components/MapPicker';
import {
  Send,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  Volume2,
  FileText,
  MapPin,
  Sparkles,
  RefreshCw,
  Info,
  Camera,
  Image as ImageIcon,
  Upload,
  UserCheck,
  AlertOctagon,
  ShieldAlert,
} from 'lucide-react';

export const CitizenPortal: React.FC = () => {
  const { user, language, t } = useAuth();

  // Form states
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('ROAD_POTHOLE');
  const [priority, setPriority] = useState('MEDIUM');
  const [latitude, setLatitude] = useState(18.5204);
  const [longitude, setLongitude] = useState(73.8567);
  const [address, setAddress] = useState('FC Road, Shivajinagar, Pune 411005');
  const [landmark, setLandmark] = useState('');
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidencePreview, setEvidencePreview] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Complaints history & selected for live tracking
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<any | null>(null);
  const [feedMode, setFeedMode] = useState<'mine' | 'public'>(user ? 'mine' : 'public');
  const [audioVoiceUrl, setAudioVoiceUrl] = useState<string | null>(null);
  const [isPlayingVoice, setIsPlayingVoice] = useState(false);
  const audioVoiceRef = useRef<HTMLAudioElement | null>(null);
  const incidentDetailsRef = useRef<HTMLDivElement | null>(null);
  const [activeTab, setActiveTab] = useState<'report' | 'track'>('report');

  const handleSelectIncident = (inc: Incident) => {
    setSelectedIncident(inc);
    setTimeout(() => {
      incidentDetailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 10);
  };

  const loadIncidents = async () => {
    try {
      const data = (feedMode === 'mine' && user)
        ? await api.incidents.list({ mine: true })
        : await api.incidents.list();
      setIncidents(data);
      if (data.length > 0) {
        if (!selectedIncident || !data.some((d) => d.id === selectedIncident.id)) {
          setSelectedIncident(data[0]);
        }
      } else {
        setSelectedIncident(null);
        setSelectedDetail(null);
      }
    } catch (e) {
      console.error('Error fetching citizen incidents:', e);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, [feedMode, user]);

  useEffect(() => {
    if (selectedIncident) {
      api.incidents.get(selectedIncident.id)
        .then((detail) => setSelectedDetail(detail))
        .catch(() => setSelectedDetail(null));
    } else {
      setSelectedDetail(null);
    }
  }, [selectedIncident]);

  useEffect(() => {
    // Subscribe to WebSocket status changes
    const unsubStatus = wsClient.on('INCIDENT_STATUS_CHANGED', (payload) => {
      loadIncidents();
      if (selectedIncident && selectedIncident.id === payload.incident_id) {
        setSelectedIncident((prev) => (prev ? { ...prev, status: payload.new_status } : null));
      }
    });

    const unsubAssigned = wsClient.on('INCIDENT_ASSIGNED', () => {
      loadIncidents();
    });

    const unsubCitizenAlert = wsClient.on('CITIZEN_STATUS_UPDATE', (payload) => {
      if (payload.audio_url) {
        setAudioVoiceUrl(payload.audio_url);
      }
      loadIncidents();
    });

    return () => {
      unsubStatus();
      unsubAssigned();
      unsubCitizenAlert();
      if (audioVoiceRef.current) {
        audioVoiceRef.current.pause();
      }
    };
  }, [selectedIncident, user]);

  const handleVoiceTranscription = (text: string, detectedLang: string, conf: number) => {
    setDescription(text);
    if (!title || title.trim() === '') {
      setTitle(text.length > 50 ? text.slice(0, 50).trim() + '...' : text);
    }
    const lower = text.toLowerCase();
    if (lower.includes('electric') || lower.includes('power') || lower.includes('light') || lower.includes('wire') || lower.includes('विद्युत') || lower.includes('बिजली') || lower.includes('लाईट') || lower.includes('फ्यूज')) {
      setCategory('STREETLIGHT');
    } else if (lower.includes('water') || lower.includes('pipe') || lower.includes('leak') || lower.includes('पाणी') || lower.includes('पानी')) {
      setCategory('WATER_LEAK');
    } else if (lower.includes('manhole') || lower.includes('drain') || lower.includes('सांडपाणी') || lower.includes('गटर') || lower.includes('नाली')) {
      setCategory('OPEN_MANHOLE');
    } else if (lower.includes('tree') || lower.includes('branch') || lower.includes('झाड') || lower.includes('पेड़')) {
      setCategory('TREE_FALL');
    } else if (lower.includes('garbage') || lower.includes('waste') || lower.includes('कचरा')) {
      setCategory('GARBAGE');
    } else if (lower.includes('pothole') || lower.includes('road') || lower.includes('रस्ता') || lower.includes('खड्डा') || lower.includes('सड़क')) {
      setCategory('ROAD_POTHOLE');
    }
  };

  const handleEvidenceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setEvidenceFile(file);
      setEvidencePreview(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !description || !address) {
      alert('Please fill in title, description, and location.');
      return;
    }

    setIsSubmitting(true);
    setSubmitSuccess(null);
    try {
      const created = await api.incidents.create({
        title,
        description,
        category,
        priority,
        latitude,
        longitude,
        address,
        landmark,
        source: 'MOBILE_PORTAL',
        language,
      });

      // Upload photo evidence if provided
      if (evidenceFile) {
        try {
          const formData = new FormData();
          formData.append('file', evidenceFile);
          formData.append('evidence_type', 'PHOTO_BEFORE');
          formData.append('notes', 'Initial on-site photographic evidence attached by citizen');
          await api.incidents.uploadEvidence(created.id, formData);
        } catch (uploadErr) {
          console.warn('Initial photo upload error:', uploadErr);
        }
      }

      setSubmitSuccess(created.incident_number);
      setSelectedIncident(created);
      setTitle('');
      setDescription('');
      setLandmark('');
      setEvidenceFile(null);
      setEvidencePreview(null);
      loadIncidents();
      setActiveTab('track');
    } catch (err: any) {
      console.error('Submission error:', err);
      alert('Failed to submit incident. Please check details.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const playVoiceUpdate = async (incident: Incident) => {
    setIsPlayingVoice(true);
    try {
      if (audioVoiceRef.current) {
        audioVoiceRef.current.pause();
      }
      const textToSpeak =
        language === 'mr'
          ? `तुमची तक्रार क्रमांक ${incident.incident_number} ही ${incident.status} स्थितीत आहे.`
          : language === 'hi'
          ? `आपकी शिकायत क्रमांक ${incident.incident_number} वर्तमान में ${incident.status} स्थिति में है।`
          : `Your complaint ${incident.incident_number} is currently ${incident.status}. The assigned municipal team is addressing it.`;

      const res = await api.voice.speak(textToSpeak, language);
      if (res.audio_url) {
        setAudioVoiceUrl(res.audio_url);
      }
    } catch (e) {
      console.error('Gnani Timbre TTS error:', e);
    } finally {
      setIsPlayingVoice(false);
    }
  };

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] bg-slate-50 text-slate-800 px-4 sm:px-6 lg:px-8 py-6">
      {/* Civic Pune Welcome Hero Banner */}
      <div className="bg-gradient-to-r from-blue-700 via-indigo-700 to-blue-800 rounded-3xl p-6 sm:p-8 text-white shadow-lg shadow-blue-900/10 mb-8 relative overflow-hidden">
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/15 backdrop-blur-md text-blue-100 text-xs font-semibold mb-3 border border-white/20">
            <span>🏛️ Pune Municipal Corporation (PMC)</span>
            <span>•</span>
            <span>Smart Citizen Assistance</span>
          </div>
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight leading-tight">
            {t.citizenPortal} — Report Municipal Issues
          </h1>
          <p className="text-blue-100 text-sm sm:text-base mt-2 leading-relaxed">
            Report roads, water leaks, manholes, or streetlights across Pune. Speak in Marathi, Hindi, or English — Multi-agent AI dispatches qualified crews immediately.
          </p>
        </div>

        {/* Decorative Civic Watermarks */}
        <div className="absolute -right-8 -bottom-8 w-64 h-64 rounded-full bg-white/5 pointer-events-none"></div>
        <div className="absolute right-24 -top-12 w-48 h-48 rounded-full bg-indigo-500/10 pointer-events-none"></div>
      </div>

      {/* Navigation Tabs (Report vs Live Status) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">
            {activeTab === 'report' ? 'Submit New Incident' : 'Track Active Incidents'}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {activeTab === 'report'
              ? 'Voice recording automatically transcribes with Gnani Prisma and structures via Evon.'
              : 'Real-time telemetry and timeline tracking for Pune municipal incident resolution.'}
          </p>
        </div>

        {/* Tab switch */}
        <div className="inline-flex rounded-xl bg-slate-200/80 p-1 text-xs font-semibold self-start sm:self-auto shadow-inner">
          <button
            type="button"
            onClick={() => setActiveTab('report')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'report'
                ? 'bg-white text-blue-700 shadow-sm font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {t.reportIncident}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('track')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'track'
                ? 'bg-white text-blue-700 shadow-sm font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>{t.liveStatus}</span>
            <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-mono">
              {incidents.length}
            </span>
          </button>
        </div>
      </div>

      {submitSuccess && (
        <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-800 text-xs flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            <span>
              Incident <strong className="font-mono text-emerald-950 font-bold">{submitSuccess}</strong> registered successfully! Multi-agent swarm is analyzing and dispatching.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setSubmitSuccess(null)}
            className="text-slate-500 hover:text-slate-800 text-xs px-2.5 py-1 rounded-lg bg-white border border-emerald-200 font-semibold shadow-xs"
          >
            ✕ Dismiss
          </button>
        </div>
      )}

      {/* Main Content Area */}
      {activeTab === 'report' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column: Voice & Form Input */}
          <div className="lg:col-span-7 space-y-6">
            {/* Gnani Prisma Voice Module */}
            <VoiceRecorder onTranscriptionComplete={handleVoiceTranscription} />

            {/* Structured Complaint Submission Form */}
            <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-7 shadow-sm hover:shadow-md transition-shadow space-y-5">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-600" />
                  <span>Complaint Information</span>
                </h2>
                <span className="text-xs px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100 font-semibold">
                  ⚡ Auto-filled by Evon AI
                </span>
              </div>

              {submitSuccess && (
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-800 text-xs flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                    <span>
                      Incident <strong className="font-mono text-emerald-950 font-bold">{submitSuccess}</strong> registered successfully!
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveTab('track')}
                    className="underline font-bold text-emerald-700 hover:text-emerald-900"
                  >
                    Track Live →
                  </button>
                </div>
              )}

              {/* Title Input */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Incident Title *
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={t.titlePlaceholder}
                  className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600 transition-colors"
                />
              </div>

              {/* Category & Priority Selectors */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    {t.category}
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
                  >
                    <option value="ROAD_POTHOLE">Damaged Roads & Potholes</option>
                    <option value="WATER_LEAKAGE">Water Pipeline Leakage</option>
                    <option value="OPEN_MANHOLE">Open Manhole / Gutter Chamber</option>
                    <option value="STREETLIGHT">Broken Streetlights</option>
                    <option value="GARBAGE_OVERFLOW">Garbage Overflow & Waste</option>
                    <option value="DRAINAGE">Drainage & Stormwater Flooding</option>
                    <option value="OTHER">Other Public Infrastructure</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Initial Urgency Assessment
                  </label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
                  >
                    <option value="CRITICAL">Critical (Immediate Public Danger)</option>
                    <option value="HIGH">High (Heavy Hazard / Flooding)</option>
                    <option value="MEDIUM">Medium (Normal Municipal Issue)</option>
                    <option value="LOW">Low (Minor Non-urgent)</option>
                  </select>
                </div>
              </div>

              {/* Detailed Description */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Incident Description & Details *
                </label>
                <textarea
                  required
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t.descPlaceholder}
                  className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600 transition-colors"
                />
              </div>

              {/* Address / Landmark Input */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Street Address in Pune *
                  </label>
                  <input
                    type="text"
                    required
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Prominent Landmark
                  </label>
                  <input
                    type="text"
                    value={landmark}
                    onChange={(e) => setLandmark(e.target.value)}
                    placeholder="Near metro pillar, opposite garden..."
                    className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
                  />
                </div>
              </div>

              {/* Photo Evidence Upload */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Camera className="w-3.5 h-3.5 text-blue-600" />
                    <span>Attach Photo Evidence (Optional)</span>
                  </span>
                  <span className="text-[10px] text-slate-400 font-normal">JPG, PNG, WebP up to 15MB</span>
                </label>
                <div className="border-2 border-dashed border-slate-200 hover:border-blue-500 rounded-2xl p-4 text-center cursor-pointer transition-colors bg-slate-50/60 relative">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleEvidenceChange}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                  {evidencePreview ? (
                    <div className="flex items-center justify-between gap-3 p-1">
                      <div className="flex items-center gap-2">
                        <img
                          src={evidencePreview}
                          alt="Evidence preview"
                          className="w-12 h-12 rounded-lg object-cover shadow border border-slate-200"
                        />
                        <div className="text-left">
                          <p className="text-xs text-emerald-700 font-semibold truncate max-w-[200px]">
                            {evidenceFile?.name}
                          </p>
                          <p className="text-[10px] text-slate-500 font-mono">
                            {((evidenceFile?.size || 0) / 1024).toFixed(0)} KB • Ready for submission
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setEvidenceFile(null);
                          setEvidencePreview(null);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 text-xs font-semibold shadow-xs"
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-2 py-1">
                      <Upload className="w-4 h-4 text-blue-600" />
                      <span className="text-xs text-slate-600 font-medium">Click to attach photograph of the road damage or hazard</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 px-4 rounded-2xl bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-bold text-sm shadow-md shadow-emerald-600/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Analyzing with Evon & Multi-Agent Swarm...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>{t.submitComplaint} (तक्रार दाखल करा)</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Right Column: Leaflet Map Location Picker */}
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
                    <MapPin className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      Geographic Pinpoint (Pune)
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Interactive Leaflet & OpenStreetMap coordinates
                    </p>
                  </div>
                </div>
              </div>

              <MapPicker
                latitude={latitude}
                longitude={longitude}
                onLocationChange={(lat, lng, addr) => {
                  setLatitude(lat);
                  setLongitude(lng);
                  if (addr) setAddress(addr);
                }}
              />

              <div className="mt-4 p-3.5 bg-blue-50/70 border border-blue-100 rounded-2xl text-xs text-slate-700 flex items-start gap-2">
                <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                <span>
                  Our Resource Allocation Agent calculates <strong>Haversine distances</strong> from these coordinates to dispatch the closest available Pune municipal squad.
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Track Live Complaints Section */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Incidents List */}
          <div className="lg:col-span-5 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2 p-1">
              <div className="inline-flex items-center bg-slate-200/80 p-1 rounded-xl text-xs font-semibold">
                {user && (
                  <button
                    type="button"
                    onClick={() => setFeedMode('mine')}
                    className={`px-3.5 py-1.5 rounded-lg transition-all ${
                      feedMode === 'mine' ? 'bg-white text-blue-700 shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    My Complaints
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setFeedMode('public')}
                  className={`px-3.5 py-1.5 rounded-lg transition-all ${
                    feedMode === 'public' ? 'bg-white text-blue-700 shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Pune City Feed
                </button>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto">
                <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-600 shadow-xs">
                  {feedMode === 'mine' ? 'Your Complaints' : 'All Pune Wards'}
                </span>
                <button
                  type="button"
                  onClick={loadIncidents}
                  className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-semibold"
                >
                  <RefreshCw className="w-3.5 h-3.5" /> Refresh ({incidents.length})
                </button>
              </div>
            </div>

            {incidents.length === 0 ? (
              <div className="p-8 text-center bg-white border border-slate-200 rounded-3xl text-slate-500 text-sm shadow-sm">
                No incidents reported yet. Submit your first complaint above!
              </div>
            ) : (
              incidents.map((inc) => (
                <div
                  key={inc.id}
                  onClick={() => handleSelectIncident(inc)}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                    selectedIncident?.id === inc.id
                      ? 'bg-blue-50/70 border-2 border-blue-500 shadow-sm'
                      : 'bg-white border-slate-200 hover:bg-slate-50/90 shadow-xs'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-mono text-xs font-bold text-blue-700">
                      {inc.incident_number}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                        inc.status === 'RESOLVED'
                          ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                          : inc.status === 'IN_PROGRESS' || inc.status === 'ASSIGNED'
                          ? 'bg-sky-50 text-sky-800 border border-sky-200'
                          : inc.status === 'ESCALATED'
                          ? 'bg-rose-50 text-rose-800 border border-rose-200'
                          : 'bg-amber-50 text-amber-800 border border-amber-200'
                      }`}
                    >
                      {inc.status}
                    </span>
                  </div>
                  <h4 className="font-bold text-sm text-slate-900 line-clamp-1">
                    {inc.title}
                  </h4>
                  <p className="text-xs text-slate-600 line-clamp-1 mt-1 flex items-center gap-1">
                    <MapPin className="w-3 h-3 text-blue-600 shrink-0" />
                    <span>{inc.address}</span>
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2.5 pt-2 border-t border-slate-100">
                    <span>Priority: <strong className="text-slate-800">{inc.priority}</strong></span>
                    <span>{new Date(inc.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Detail & Live Tracking Panel */}
          <div ref={incidentDetailsRef} className="lg:col-span-7 lg:sticky lg:top-6 self-start space-y-6">
            {selectedIncident ? (
              <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-7 shadow-sm space-y-6 text-slate-900">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-slate-100 pb-5">
                  <div>
                    <span className="text-xs font-mono text-blue-700 font-bold bg-blue-50 px-2.5 py-0.5 rounded-md border border-blue-100">
                      {selectedIncident.incident_number}
                    </span>
                    <h2 className="text-xl font-extrabold text-slate-900 mt-2">
                      {selectedIncident.title}
                    </h2>
                    <p className="text-xs text-slate-600 mt-1 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                      <span>{selectedIncident.address}</span>
                    </p>
                  </div>

                  {/* Play Voice Update Button (Gnani Timbre) */}
                  <button
                    type="button"
                    onClick={() => playVoiceUpdate(selectedIncident)}
                    disabled={isPlayingVoice}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white text-xs font-semibold shadow-sm transition-all disabled:opacity-50 shrink-0"
                  >
                    <Volume2 className="w-4 h-4" />
                    <span>{isPlayingVoice ? 'Synthesizing...' : t.listenStatusUpdate}</span>
                  </button>
                </div>

                {audioVoiceUrl && (
                  <div className="p-4 bg-indigo-50 border border-indigo-100 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
                    <div className="flex items-center gap-2 text-xs text-indigo-900 font-semibold">
                      <Volume2 className="w-4 h-4 text-indigo-600 shrink-0" />
                      <span>{t.voicePoweredTimbre}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <audio ref={audioVoiceRef} key={audioVoiceUrl} src={audioVoiceUrl} controls autoPlay className="h-7 w-48 sm:w-56" />
                      <button
                        type="button"
                        onClick={() => {
                          if (audioVoiceRef.current) {
                            audioVoiceRef.current.pause();
                          }
                          setAudioVoiceUrl(null);
                        }}
                        title="Stop & Close Audio"
                        className="p-1 rounded-lg text-slate-400 hover:text-slate-800 hover:bg-indigo-100 transition-colors"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}

                {/* Duplicate Notification Banner */}
                {selectedIncident.status === 'REJECTED' && (
                  <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Duplicate Incident Consolidated</p>
                      <p className="text-[11px] text-rose-700/90 mt-0.5">
                        Our Duplicate Detection Agent identified a concurrent active ticket for this exact location. Municipal crews are already addressing it.
                      </p>
                    </div>
                  </div>
                )}

                {/* Human Approval Alert Banner */}
                {selectedIncident.status === 'PENDING_APPROVAL' && (
                  <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-amber-900 text-xs flex items-start gap-2.5">
                    <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Critical Hazard: Awaiting Municipal Authorization</p>
                      <p className="text-[11px] text-amber-800 mt-0.5">
                        Due to public safety severity, this incident has been queued for immediate Municipal Admin authorization before field dispatch.
                      </p>
                    </div>
                  </div>
                )}

                {/* Assigned Field Crew Card */}
                {selectedDetail?.assigned_worker_name && (
                  <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-emerald-900">
                      <UserCheck className="w-4 h-4 text-emerald-600" />
                      <span>Assigned Field Crew: <strong>{selectedDetail.assigned_worker_name}</strong></span>
                    </div>
                    <span className="font-mono text-[10px] px-2.5 py-0.5 bg-white rounded-full border border-emerald-300 text-emerald-800 font-bold shadow-xs">
                      {selectedDetail.assignment_status || 'ASSIGNED'}
                    </span>
                  </div>
                )}

                {/* Status Timeline */}
                <div>
                  <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-4">
                    Incident Lifecycle Status
                  </h4>
                  <div className="space-y-4 relative pl-6 border-l-2 border-slate-200 ml-2">
                    <div className="relative">
                      <div className="absolute -left-[31px] top-0.5 w-4 h-4 rounded-full bg-emerald-500 border-2 border-white shadow-xs"></div>
                      <p className="text-xs font-bold text-emerald-700">1. Complaint Registered</p>
                      <p className="text-xs text-slate-500">Original report submitted by citizen</p>
                    </div>

                    <div className="relative">
                      <div className={`absolute -left-[31px] top-0.5 w-4 h-4 rounded-full border-2 border-white shadow-xs ${
                        selectedIncident.status !== 'REPORTED' ? 'bg-blue-600' : 'bg-slate-300'
                      }`}></div>
                      <p className="text-xs font-bold text-slate-800">2. Intelligent Classification & Priority</p>
                      <p className="text-xs text-slate-500">
                        Incident Intelligence Agent & Priority Agent categorized as <strong>{selectedIncident.category}</strong> ({selectedIncident.priority})
                      </p>
                    </div>

                    <div className="relative">
                      <div className={`absolute -left-[31px] top-0.5 w-4 h-4 rounded-full border-2 border-white shadow-xs ${
                        ['ASSIGNED', 'IN_PROGRESS', 'RESOLVED_PENDING_VERIFICATION', 'RESOLVED'].includes(selectedIncident.status) ? 'bg-blue-600' : 'bg-slate-300'
                      }`}></div>
                      <p className="text-xs font-bold text-slate-800">3. Field Crew Dispatched</p>
                      <p className="text-xs text-slate-500">
                        Assigned to closest municipal worker via Haversine calculation with voice dispatch (Timbre)
                      </p>
                    </div>

                    <div className="relative">
                      <div className={`absolute -left-[31px] top-0.5 w-4 h-4 rounded-full border-2 border-white shadow-xs ${
                        selectedIncident.status === 'RESOLVED' ? 'bg-emerald-500' : 'bg-slate-300'
                      }`}></div>
                      <p className="text-xs font-bold text-slate-800">4. Resolution & Evidence Verified</p>
                      <p className="text-xs text-slate-500">
                        Verification Agent checks photographic proof and closes complaint
                      </p>
                    </div>
                  </div>
                </div>

                {/* Additional Metadata */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 bg-slate-50 rounded-2xl border border-slate-200 text-xs">
                  <div>
                    <span className="text-slate-500">Department:</span>
                    <p className="font-bold text-slate-900 mt-0.5">{selectedIncident.department_name || 'Assigned Division'}</p>
                  </div>
                  <div>
                    <span className="text-slate-500">Confidence:</span>
                    <p className="font-bold text-slate-900 mt-0.5">{(selectedIncident.confidence_score * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <span className="text-slate-500">Safety Hazard:</span>
                    <p className="font-bold text-slate-900 mt-0.5">{selectedIncident.public_safety_risk ? 'Yes (Flagged)' : 'No'}</p>
                  </div>
                </div>

                {/* Resolution Photographic Proof Gallery */}
                {selectedDetail?.evidences && selectedDetail.evidences.length > 0 && (
                  <div className="space-y-3 pt-3 border-t border-slate-100">
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                      <ImageIcon className="w-3.5 h-3.5 text-blue-600" />
                      <span>Resolution Photographic Proof</span>
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {selectedDetail.evidences.map((ev: any) => (
                        <div key={ev.id} className="bg-slate-50 rounded-2xl p-3 border border-slate-200 space-y-2 shadow-xs">
                          <img
                            src={ev.file_path.startsWith('/') ? ev.file_path : `/uploads/${ev.file_path}`}
                            alt={ev.file_name}
                            className="w-full h-36 rounded-xl object-cover bg-white border border-slate-200"
                          />
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-semibold text-slate-700 font-mono text-[10px]">
                              {ev.evidence_type === 'PHOTO_AFTER' ? 'Completion Proof' : 'Initial Complaint Photo'}
                            </span>
                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                              ev.verification_status === 'ACCEPTED'
                                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                                : 'bg-slate-200 text-slate-600'
                            }`}>
                              {ev.verification_status}
                            </span>
                          </div>
                          {ev.verification_notes && (
                            <p className="text-[11px] text-slate-600 italic bg-white p-2.5 rounded-xl border border-slate-200">
                              "{ev.verification_notes}"
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-12 text-center bg-white border border-slate-200 rounded-3xl text-slate-500 shadow-sm">
                Select an incident from the list to track its live agent resolution progress.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
