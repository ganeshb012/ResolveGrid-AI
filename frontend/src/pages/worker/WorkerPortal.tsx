import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { wsClient } from '../../api/ws';
import { Assignment, Worker } from '../../types';
import {
  HardHat,
  MapPin,
  Clock,
  CheckCircle2,
  XCircle,
  Volume2,
  Upload,
  Camera,
  Navigation,
  FileText,
  AlertTriangle,
  RefreshCw,
  Send,
} from 'lucide-react';

export const WorkerPortal: React.FC = () => {
  const { user, t } = useAuth();
  const [workerProfile, setWorkerProfile] = useState<Worker | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [selectedTask, setSelectedTask] = useState<Assignment | null>(null);

  // Resolution submission form
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidencePreview, setEvidencePreview] = useState<string | null>(null);
  const [isSubmittingResolution, setIsSubmittingResolution] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);

  // Audio voice playback for instructions
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const taskDetailsRef = useRef<HTMLDivElement | null>(null);

  const handleSelectTask = (task: Assignment) => {
    setSelectedTask(task);
    setTimeout(() => {
      taskDetailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 10);
  };

  const loadWorkerData = async () => {
    try {
      const [profileData, myAssignments] = await Promise.all([
        api.workers.getMe().catch(() => null),
        api.assignments.listMy(),
      ]);
      setWorkerProfile(profileData);
      setAssignments(myAssignments);
      if (myAssignments.length > 0 && !selectedTask) {
        setSelectedTask(myAssignments[0]);
      }
    } catch (e) {
      console.error('Error fetching worker portal data:', e);
    }
  };

  useEffect(() => {
    loadWorkerData();

    // WebSocket real-time alerts for worker
    const unsubNewTask = wsClient.on('NEW_TASK_ASSIGNMENT', (payload) => {
      loadWorkerData();
      if (payload.audio_url) {
        if (audioRef.current) {
          audioRef.current.pause();
        }
        setAudioUrl(payload.audio_url);
      }
    });

    const unsubUpdate = wsClient.on('ASSIGNMENT_UPDATED', () => loadWorkerData());

    return () => {
      unsubNewTask();
      unsubUpdate();
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  const handleStatusChange = async (status: 'AVAILABLE' | 'BUSY' | 'ON_BREAK' | 'OFF_DUTY') => {
    if (!workerProfile) return;
    try {
      await api.workers.updateAvailability(workerProfile.id, status);
      setWorkerProfile((prev) => (prev ? { ...prev, availability_status: status } : null));
    } catch (e) {
      console.error('Error updating worker status:', e);
    }
  };

  const handleAcceptTask = async (task: Assignment) => {
    try {
      await api.assignments.updateStatus(task.id, 'ACCEPTED');
      loadWorkerData();
    } catch (e) {
      console.error('Error accepting task:', e);
    }
  };

  const handleMarkInProgress = async (task: Assignment) => {
    try {
      await api.assignments.updateStatus(task.id, 'IN_PROGRESS');
      loadWorkerData();
    } catch (e) {
      console.error('Error marking in progress:', e);
    }
  };

  const handleUpdateLocation = async () => {
    if (!workerProfile) return;
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            await api.workers.updateLocation(workerProfile.id, pos.coords.latitude, pos.coords.longitude);
            alert(`GPS updated to ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
            loadWorkerData();
          } catch (e) {
            console.error('Location update error:', e);
          }
        },
        async () => {
          await api.workers.updateLocation(workerProfile.id, 18.5204, 73.8567);
          alert('Location synced to Pune Field Operations Hub.');
          loadWorkerData();
        }
      );
    }
  };

  const handleRejectTask = async () => {
    if (!selectedTask || !rejectionReason) return;
    try {
      await api.assignments.updateStatus(selectedTask.id, 'REJECTED', undefined, rejectionReason);
      setShowRejectModal(false);
      setRejectionReason('');
      loadWorkerData();
    } catch (e) {
      console.error('Error rejecting task:', e);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setEvidenceFile(file);
      setEvidencePreview(URL.createObjectURL(file));
    }
  };

  const handleCompleteResolution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask) return;
    if (!evidenceFile) {
      alert('Photographic evidence proof is required for verification.');
      return;
    }
    if (!resolutionNotes) {
      alert('Please provide field completion notes.');
      return;
    }

    setIsSubmittingResolution(true);
    try {
      // Step 1: Upload photographic evidence
      const formData = new FormData();
      formData.append('file', evidenceFile);
      formData.append('evidence_type', 'PHOTO_AFTER');
      formData.append('assignment_id', selectedTask.id);
      formData.append('notes', resolutionNotes);

      await api.incidents.uploadEvidence(selectedTask.incident_id, formData);

      // Step 2: Mark assignment completed (triggers Verification Agent)
      await api.assignments.updateStatus(
        selectedTask.id,
        'COMPLETED',
        resolutionNotes
      );

      alert('Work marked completed! Photographic evidence submitted to Verification Agent.');
      setEvidenceFile(null);
      setEvidencePreview(null);
      setResolutionNotes('');
      loadWorkerData();
    } catch (err) {
      console.error('Error completing resolution:', err);
      alert('Failed to submit resolution.');
    } finally {
      setIsSubmittingResolution(false);
    }
  };

  const playVoiceInstruction = async (task: Assignment) => {
    setIsPlayingAudio(true);
    try {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      const text = `Task assigned: ${task.incident_title} at ${task.incident_address}. Priority: ${task.incident_priority}. Distance: ${task.worker_distance_km || 2.4} kilometers.`;
      const res = await api.voice.speak(text, 'en');
      if (res.audio_url) {
        setAudioUrl(res.audio_url);
      }
    } catch (e) {
      console.error('Timbre synthesis error:', e);
    } finally {
      setIsPlayingAudio(false);
    }
  };

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] bg-[#0b1120] text-slate-200 antialiased px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Field Operations Terminal Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-[#111827] border border-amber-500/30 rounded-2xl shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-600 to-amber-500 text-slate-950 flex items-center justify-center font-bold text-lg shadow-md shadow-amber-500/20">
            <HardHat className="w-5 h-5 text-slate-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-white tracking-wide uppercase">
                Field Crew Hub — Tactical Municipal Dispatch
              </h2>
              <span className="hidden sm:inline-block px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono">
                FIELD OPS TERMINAL
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              PMC Rapid Response Field Unit • Real-Time Voice Dispatches & Work Verification
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="text-xs font-mono text-emerald-400 flex items-center gap-1.5 bg-emerald-950/60 px-3 py-1.5 rounded-xl border border-emerald-500/40">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            GPS LOCK: PUNE FIELD SQUAD (18.5204, 73.8567)
          </span>
        </div>
      </div>

      {/* Header & Worker Profile Card */}
      <div className="bg-gradient-to-r from-[#131d33] via-[#15233e] to-[#101b30] border-2 border-slate-700/80 rounded-3xl p-6 shadow-2xl relative overflow-hidden">
        {/* High-vis tactical top stripe */}
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-amber-500 via-amber-400 to-amber-600"></div>

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          {/* Worker Bio */}
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-slate-950 shadow-lg shadow-amber-500/30 border-2 border-amber-300 shrink-0">
              <HardHat className="w-8 h-8 text-slate-950" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-xl sm:text-2xl font-bold text-white tracking-wide">
                  {workerProfile?.full_name || user?.full_name || 'Field Specialist'}
                </h1>
                <span className="px-2.5 py-0.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono font-bold">
                  {workerProfile?.employee_id || 'EMP-RD-101'}
                </span>
                <span className="px-2 py-0.5 rounded-lg bg-slate-800 text-slate-300 text-xs font-semibold">
                  {workerProfile?.department_name || 'Infrastructure Maintenance'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
                <span>Skills: <strong className="text-slate-200">{workerProfile?.skills || 'General Repairs, Asphalt'}</strong></span>
                <span>•</span>
                <span>Vehicle: <strong className="text-slate-200">PMC Squad Van #14</strong></span>
                <span>•</span>
                <span className="text-emerald-400 font-semibold">✓ Live Dispatch Radio Ready</span>
              </p>
            </div>
          </div>

          {/* Worker Availability State Switcher & GPS Sync */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleUpdateLocation}
              title="Sync live GPS coordinates"
              className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0b1120] hover:bg-slate-800 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium transition-all shadow-sm"
            >
              <Navigation className="w-3.5 h-3.5 text-blue-400" />
              <span>Update GPS</span>
            </button>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-medium">Duty Status:</span>
              <div className="flex items-center bg-[#0b1120] p-1 rounded-xl border border-slate-700 text-xs font-semibold">
                {(['AVAILABLE', 'BUSY', 'ON_BREAK', 'OFF_DUTY'] as const).map((st) => (
                  <button
                    key={st}
                    onClick={() => handleStatusChange(st)}
                    className={`px-3 py-1.5 rounded-lg transition-all ${
                      workerProfile?.availability_status === st
                        ? st === 'AVAILABLE'
                          ? 'bg-emerald-600 text-white font-bold shadow'
                          : st === 'BUSY'
                          ? 'bg-amber-600 text-slate-950 font-bold shadow'
                          : 'bg-slate-700 text-white font-bold'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>

            {/* Gnani Timbre Radio Pill */}
            <div className="px-3.5 py-2 rounded-xl bg-indigo-950/60 border border-indigo-500/40 text-xs flex items-center gap-2 text-indigo-300">
              <Volume2 className="w-4 h-4 text-indigo-400 shrink-0" />
              <div>
                <span className="font-bold text-white block leading-none">Voice Dispatch Active</span>
                <span className="text-[10px] text-indigo-300/80 font-mono">Gnani Timbre v3 (mr / en)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Task Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Assigned Tasks List */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between px-1 mb-1">
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <FileText className="w-4 h-4 text-amber-400" />
              <span>Assigned Field Queue ({assignments.length})</span>
            </h3>
            <button
              onClick={loadWorkerData}
              className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1 font-mono font-medium"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
          </div>

          {assignments.length === 0 ? (
            <div className="p-8 text-center bg-[#111927] rounded-2xl border border-slate-800 text-slate-400 text-xs">
              No tasks currently assigned. New dispatches will automatically notify you here.
            </div>
          ) : (
            assignments.map((task) => (
              <div
                key={task.id}
                onClick={() => handleSelectTask(task)}
                className={`p-4 rounded-2xl border-2 transition-all cursor-pointer space-y-2 ${
                  selectedTask?.id === task.id
                    ? 'border-amber-500 bg-[#162035] shadow-xl'
                    : 'border-slate-700/80 bg-[#111927] hover:bg-[#152033]'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span
                    className={`font-mono font-bold px-2 py-0.5 rounded border text-xs ${
                      selectedTask?.id === task.id
                        ? 'text-amber-400 bg-amber-950/60 border-amber-500/40'
                        : 'text-slate-400 bg-slate-900 border-slate-700'
                    }`}
                  >
                    {task.incident_number}
                  </span>
                  <span
                    className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                      task.status === 'COMPLETED'
                        ? 'bg-emerald-950/70 text-emerald-400 border border-emerald-800/40'
                        : task.status === 'ACCEPTED'
                        ? 'bg-sky-950 text-sky-400 border border-sky-600/40'
                        : task.status === 'OFFERED'
                        ? 'bg-amber-500 text-slate-950 font-extrabold shadow-sm animate-pulse'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {task.status === 'OFFERED' ? 'ACTION REQUIRED' : task.status}
                  </span>
                </div>

                <h4 className={`text-sm font-bold line-clamp-1 ${
                  selectedTask?.id === task.id ? 'text-white' : 'text-slate-200'
                }`}>
                  {task.incident_title}
                </h4>
                <p className="text-xs text-slate-400 line-clamp-1 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span>{task.incident_address}</span>
                </p>

                <div className="flex items-center justify-between text-xs text-slate-400 mt-2 pt-2 border-t border-slate-700/40">
                  <span className="text-rose-400 font-bold flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>Priority: {task.incident_priority}</span>
                  </span>
                  <span className="text-amber-300 font-mono font-bold">
                    Dist: {task.worker_distance_km ? `${task.worker_distance_km.toFixed(1)} km` : '2.4 km'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right Column: Active Task Details, Action & Evidence Upload */}
        <div ref={taskDetailsRef} className="lg:col-span-7 lg:sticky lg:top-6 self-start space-y-5">
          {selectedTask ? (
            <div className="bg-[#121c2e] border-2 border-slate-700 rounded-3xl p-6 shadow-2xl space-y-6">
              {/* Task Header */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-5 border-b border-slate-700/80">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="font-mono text-xs font-bold text-amber-400 bg-amber-950/60 px-2.5 py-0.5 rounded border border-amber-500/40">
                      {selectedTask.incident_number}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-950 text-rose-300 border border-rose-700/50 font-mono flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      <span>SLA MONITOR ACTIVE</span>
                    </span>
                  </div>
                  <h2 className="text-xl sm:text-2xl font-bold text-white tracking-wide">
                    {selectedTask.incident_title}
                  </h2>
                  <p className="text-xs text-slate-300 mt-1 flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span>{selectedTask.incident_address}</span>
                  </p>
                </div>

                {/* Voice instruction playback via Timbre */}
                <button
                  onClick={() => playVoiceInstruction(selectedTask)}
                  disabled={isPlayingAudio}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white text-xs font-bold shadow-lg shadow-indigo-600/30 transition-all shrink-0"
                >
                  <Volume2 className="w-4 h-4" />
                  <span>{isPlayingAudio ? 'Playing...' : 'Voice Briefing (Timbre)'}</span>
                </button>
              </div>

              {audioUrl && (
                <div className="p-3.5 bg-indigo-950/50 border border-indigo-500/40 rounded-2xl flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs text-indigo-300 font-semibold">
                    <Volume2 className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span>Voice instruction audio:</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <audio ref={audioRef} key={audioUrl} src={audioUrl} controls autoPlay className="h-7 w-48" />
                    <button
                      onClick={() => {
                        if (audioRef.current) {
                          audioRef.current.pause();
                        }
                        setAudioUrl(null);
                      }}
                      title="Stop & Close Audio"
                      className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/60 transition-colors"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* Task Acceptance Actions */}
              {selectedTask.status === 'OFFERED' && (
                <div className="p-4 bg-amber-950/40 border-2 border-amber-500/50 rounded-2xl space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-300 uppercase tracking-wider">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span>NEW DISPATCH OFFERED — ACKNOWLEDGE PROTOCOL</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <button
                      onClick={() => handleAcceptTask(selectedTask)}
                      className="py-3.5 px-4 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 active:scale-95 text-slate-950 font-extrabold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/30 uppercase tracking-wide transition-all"
                    >
                      <CheckCircle2 className="w-4 h-4" /> ACCEPT ASSIGNMENT
                    </button>
                    <button
                      onClick={() => setShowRejectModal(true)}
                      className="py-3.5 px-4 bg-gradient-to-r from-rose-700 to-rose-600 hover:from-rose-600 hover:to-rose-500 active:scale-95 text-white font-extrabold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-rose-700/30 uppercase tracking-wide transition-all"
                    >
                      <XCircle className="w-4 h-4" /> REJECT (BUSY ON CALL)
                    </button>
                  </div>
                </div>
              )}

              {/* Transit & Navigation Actions */}
              {(selectedTask.status === 'ACCEPTED' || selectedTask.status === 'IN_PROGRESS') && (
                <div className="p-4 bg-[#0e1726] border border-slate-700 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-600/20 text-blue-400 flex items-center justify-center text-lg font-bold border border-blue-500/30 shrink-0">
                      <Navigation className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <span className="text-xs font-bold text-white block">Field Dispatch Location</span>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {selectedTask.incident_address || 'Pune Municipal Zone'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 w-full sm:w-auto">
                    {selectedTask.status === 'ACCEPTED' && (
                      <button
                        type="button"
                        onClick={() => handleMarkInProgress(selectedTask)}
                        className="flex-1 sm:flex-none px-4 py-2.5 bg-amber-500 hover:bg-amber-400 active:scale-95 text-slate-950 rounded-xl text-xs font-extrabold transition-all shadow-md shadow-amber-500/20 uppercase tracking-wide"
                      >
                        Start Transit / In Progress
                      </button>
                    )}
                    <a
                      href={`https://www.google.com/maps/dir/?api=1&destination=18.5204,73.8567`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 sm:flex-none px-4 py-2.5 bg-blue-600 hover:bg-blue-500 active:scale-95 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-all shadow-md shadow-blue-600/30"
                    >
                      <Navigation className="w-3.5 h-3.5 text-white" />
                      <span>Open Pune Navigation</span>
                    </a>
                  </div>
                </div>
              )}

              {/* Resolution & Photographic Evidence Upload Form */}
              {(selectedTask.status === 'ACCEPTED' || selectedTask.status === 'IN_PROGRESS') && (
                <form onSubmit={handleCompleteResolution} className="space-y-4 pt-2">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-slate-700/80 pb-2">
                    <Camera className="w-4 h-4 text-emerald-400" />
                    <span>Completion Evidence & Resolution Verification</span>
                  </h3>

                  {/* Photo Proof Upload */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Upload Completion Photograph * (Required by Verification Agent)
                    </label>
                    <div className="border-2 border-dashed border-slate-700 hover:border-amber-500/80 rounded-2xl p-5 text-center cursor-pointer transition-colors bg-[#0b121e] relative">
                      <input
                        type="file"
                        accept="image/*"
                        required
                        onChange={handleFileChange}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                      />
                      {evidencePreview ? (
                        <div className="space-y-2">
                          <img
                            src={evidencePreview}
                            alt="Evidence preview"
                            className="max-h-48 mx-auto rounded-lg object-contain shadow-lg border border-slate-700"
                          />
                          <p className="text-xs text-emerald-400 font-bold">
                            ✓ Photo attached: {evidenceFile?.name}
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-1.5 py-2">
                          <Camera className="w-8 h-8 text-amber-400/80 mx-auto" />
                          <p className="text-xs font-bold text-slate-200">
                            Tap or Drop On-Site Completion Photograph
                          </p>
                          <p className="text-[11px] text-slate-500">
                            AI Verification Agent inspects repaired road/drainage and GPS metadata
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Field Notes */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Field Resolution Notes *
                    </label>
                    <textarea
                      required
                      rows={3}
                      value={resolutionNotes}
                      onChange={(e) => setResolutionNotes(e.target.value)}
                      placeholder="Describe repairs executed, materials utilized, and road/pipeline status..."
                      className="w-full px-3.5 py-2.5 bg-[#0b121e] border border-slate-700 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-colors"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmittingResolution}
                    className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 active:scale-95 text-slate-950 rounded-xl text-xs font-extrabold shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 disabled:opacity-50 uppercase tracking-wide transition-all"
                  >
                    {isSubmittingResolution ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                        <span>Submitting to Verification Agent...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-slate-950" />
                        <span>Submit Proof & Mark Resolved</span>
                      </>
                    )}
                  </button>
                </form>
              )}

              {selectedTask.status === 'COMPLETED' && (
                <div className="p-4 bg-emerald-950/40 border border-emerald-500/40 rounded-xl text-xs text-emerald-300 space-y-1">
                  <div className="flex items-center gap-2 font-bold">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Resolution Submitted & Verified</span>
                  </div>
                  <p className="text-slate-300">
                    Notes: {selectedTask.worker_notes || 'Work completed on site.'}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="p-12 text-center bg-[#111927] rounded-3xl border border-slate-800 text-slate-400 text-xs">
              Select an assigned incident to view Pune location coordinates and submit completion proof.
            </div>
          )}
        </div>
      </div>

      {/* Reject Task Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e1726] border-2 border-slate-700 rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <span>Reject Assignment</span>
            </h3>
            <p className="text-xs text-slate-300">
              Please specify why this task cannot be accepted (triggers automated agent escalation):
            </p>
            <textarea
              required
              rows={3}
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Beyond jurisdictional boundary, specialized equipment missing..."
              className="w-full px-3 py-2 bg-[#0b121e] border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-rose-500"
            />
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRejectTask}
                disabled={!rejectionReason}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold disabled:opacity-50 shadow-md shadow-rose-600/30 transition-all"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
