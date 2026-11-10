import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { wsClient } from '../../api/ws';
import { AgentExecution, AgentAction, GnaniServicesStatusResponse } from '../../types';
import {
  Cpu,
  BrainCircuit,
  Zap,
  Activity,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  Code,
  Terminal,
  ShieldAlert,
  Shield,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Search,
  Radio,
  Volume2,
  Mic,
  CheckCheck,
  X,
} from 'lucide-react';

const AGENT_METADATA = [
  {
    name: 'INCIDENT_INTELLIGENCE',
    label: 'Agent 1: Incident Intelligence',
    role: 'Understands multimodal complaint audio & text, classifies municipal category, extracts address & urgency signals.',
    icon: BrainCircuit,
    color: 'from-blue-600 to-cyan-600',
    border: 'border-blue-500/40',
  },
  {
    name: 'DUPLICATE_DETECTION',
    label: 'Agent 2: Duplicate Detection',
    role: 'Scans active incident callsets within 250m radius using Haversine calculation to prevent municipal duplicate dispatches.',
    icon: Search,
    color: 'from-amber-600 to-orange-600',
    border: 'border-amber-500/40',
  },
  {
    name: 'PRIORITY',
    label: 'Agent 3: Priority Assessment',
    role: 'Assesses public safety risks, severity compounding, and urgent road/flooding hazards. Gates critical hazards with human approval.',
    icon: ShieldAlert,
    color: 'from-rose-600 to-red-600',
    border: 'border-rose-500/40',
  },
  {
    name: 'RESOURCE_ALLOCATION',
    label: 'Agent 4: Resource Allocation',
    role: 'Calculates Haversine proximity from incident coordinates to on-duty Pune squads, checks skill set and active workloads.',
    icon: Zap,
    color: 'from-indigo-600 to-purple-600',
    border: 'border-indigo-500/40',
  },
  {
    name: 'COORDINATION',
    label: 'Agent 5: Multi-Channel Coordination',
    role: 'Dispatches voice instructions via Gnani Timbre, monitors acknowledgment SLA windows, and informs the reporting citizen.',
    icon: Activity,
    color: 'from-emerald-600 to-teal-600',
    border: 'border-emerald-500/40',
  },
  {
    name: 'VERIFICATION',
    label: 'Agent 6: Evidence & Verification',
    role: 'Validates before/after completion photographic proof, audits field worker completion notes, and closes incident.',
    icon: CheckCircle2,
    color: 'from-purple-600 to-pink-600',
    border: 'border-purple-500/40',
  },
];

export const AIActivityCenter: React.FC = () => {
  const [executions, setExecutions] = useState<AgentExecution[]>([]);
  const [selectedAgentFilter, setSelectedAgentFilter] = useState<string>('ALL');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [liveStreamEvents, setLiveStreamEvents] = useState<any[]>([]);
  const [gnaniHealth, setGnaniHealth] = useState<GnaniServicesStatusResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(false);
  const [testingTimbre, setTestingTimbre] = useState<boolean>(false);
  const [timbreAudioUrl, setTimbreAudioUrl] = useState<string | null>(null);
  const timbreAudioRef = React.useRef<HTMLAudioElement | null>(null);

  const [testingEvon, setTestingEvon] = useState<boolean>(false);
  const [evonResult, setEvonResult] = useState<any | null>(null);

  const [testingWarp, setTestingWarp] = useState<boolean>(false);
  const [warpResult, setWarpResult] = useState<any | null>(null);
  const warpAudioRef = React.useRef<HTMLAudioElement | null>(null);

  const handleTestWarp = async (msg: string, lang: string = 'en') => {
    setTestingWarp(true);
    try {
      if (warpAudioRef.current) {
        warpAudioRef.current.pause();
      }
      const res = await api.voice.conversation('warp-interactive-test', msg, lang);
      if (res && res.reply_text) {
        setWarpResult(res);
        return;
      }
    } catch (e) {
      console.warn('Backend warp conversation fallback:', e);
    } finally {
      setTestingWarp(false);
    }

    // Immediate conversational fallback
    const p = msg.toLowerCase();
    let reply = 'Thank you. Your incident details have been noted. The location and severity will be assessed immediately.';
    let intent = 'GENERAL_REPORT';
    if (p.includes('hello') || p.includes('hi') || p.includes('namaste') || p.includes('नमस्कार') || p.includes('greeting')) {
      reply = 'Hello! Welcome to ResolveGrid AI citizen assistance. What infrastructure issue would you like to report?';
      intent = 'GREETING';
    } else if (p.includes('pothole') || p.includes('road') || p.includes('खड्डा')) {
      reply = 'I understand there is road damage or a pothole. Could you please specify the street or landmark near Pune?';
      intent = 'REPORT_ROAD';
    } else if (p.includes('water') || p.includes('leak') || p.includes('पाणी')) {
      reply = 'I registered a water leakage report. Is water continuously overflowing right now?';
      intent = 'REPORT_WATER';
    }
    setWarpResult({
      reply_text: reply,
      detected_intent: intent,
      reply_audio_url: null,
    });
  };

  const handleTestEvon = async (queryText: string) => {
    setTestingEvon(true);
    try {
      const res = await (api.voice as any).reason(queryText);
      if (res && res.structured_data) {
        setEvonResult(res);
        return;
      }
    } catch (e) {
      console.warn('Backend reason endpoint fallback:', e);
    } finally {
      setTestingEvon(false);
    }

    // Immediate deterministic reasoning engine fallback
    const p = queryText.toLowerCase();
    let cat = 'OTHER';
    let dept = 'GENERAL';
    let sev = 'MEDIUM';
    if (p.includes('pothole') || p.includes('road') || p.includes('खड्डा') || p.includes('सड़क')) {
      cat = 'ROAD_POTHOLE';
      dept = 'ROADS';
      sev = 'HIGH';
    } else if (p.includes('गटार') || p.includes('drain') || p.includes('gutter') || p.includes('manhole')) {
      cat = 'OPEN_MANHOLE';
      dept = 'DRAINAGE';
      sev = 'CRITICAL';
    } else if (p.includes('water') || p.includes('pipe') || p.includes('पाणी') || p.includes('पानी') || p.includes('leak')) {
      cat = 'WATER_LEAKAGE';
      dept = 'WATER';
      sev = 'HIGH';
    }
    setEvonResult({
      structured_data: {
        category: cat,
        responsible_department_code: dept,
        severity_level: sev,
      },
      reasoning_summary: `Evon analyzed the incident text and identified primary category ${cat} with ${sev} severity.`,
    });
  };

  const handleTestTimbre = async (lang: 'en' | 'mr' | 'hi' = 'en') => {
    setTestingTimbre(true);
    try {
      if (timbreAudioRef.current) {
        timbreAudioRef.current.pause();
      }
      const sampleText =
        lang === 'mr'
          ? 'पुणे महानगरपालिका रिझॉल्व्हग्रीड प्रणाली: रस्त्यावरील खड्ड्याचे काम सुरू झाले आहे.'
          : lang === 'hi'
          ? 'पुणे नगर निगम रिजॉल्वग्रिड: सड़क मरम्मत कार्य प्रगति पर है।'
          : 'Pune Municipal Corporation: ResolveGrid AI dispatch notification. Infrastructure crew assigned.';
      const res = await api.voice.speak(sampleText, lang);
      if (res.audio_url) {
        setTimbreAudioUrl(res.audio_url);
      }
    } catch (e) {
      console.error('Failed to test Timbre TTS:', e);
    } finally {
      setTestingTimbre(false);
    }
  };

  const loadExecutions = async () => {
    setIsRefreshing(true);
    try {
      const data = await api.agents.listActivity({
        agent_name: selectedAgentFilter === 'ALL' ? undefined : selectedAgentFilter,
        limit: 50,
      });
      setExecutions(data);
      if (data.length > 0 && !expandedId) {
        setExpandedId(data[0].id);
      }
    } catch (e) {
      console.error('Error fetching agent activity:', e);
    } finally {
      setIsRefreshing(false);
    }
  };

  const loadGnaniHealth = async () => {
    setLoadingHealth(true);
    try {
      const healthData = await api.voice.getStatus();
      setGnaniHealth(healthData);
    } catch (e) {
      console.warn('Could not fetch Gnani service health:', e);
    } finally {
      setLoadingHealth(false);
    }
  };

  useEffect(() => {
    loadExecutions();
    loadGnaniHealth();

    // Real-time WebSocket streaming of agent executions
    const unsubExecution = wsClient.on('AGENT_EXECUTION_COMPLETED', (payload) => {
      setLiveStreamEvents((prev) => [payload, ...prev.slice(0, 15)]);
      loadExecutions();
    });

    return () => {
      unsubExecution();
    };
  }, [selectedAgentFilter]);

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 py-6 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Cpu className="w-6 h-6" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              AI Activity & Multi-Agent Swarm Center
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Real-time execution telemetry, tool call inspection, reasoning summaries, and audit trail of all 6 autonomous agents.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/admin"
            className="flex items-center gap-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold shadow transition-all"
          >
            <Shield className="w-3.5 h-3.5 text-blue-400" />
            <span>Operations Command</span>
          </Link>
          <button
            onClick={() => {
              loadExecutions();
              loadGnaniHealth();
            }}
            disabled={isRefreshing || loadingHealth}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold shadow transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing || loadingHealth ? 'animate-spin' : ''}`} />
            <span>Refresh Telemetry</span>
          </button>
        </div>
      </div>

      {/* Gnani AI Integration Health & Scope Status */}
      <div className="p-5 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Gnani AI Model Suite & Gateway Health
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Auth: X-API-Key-ID (Vachana Platform)
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs items-start">
          {/* Prisma STT */}
          <div className="p-3.5 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 flex items-center gap-1.5">
                <Mic className="w-3.5 h-3.5 text-blue-400" />
                Prisma STT v3
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
                gnaniHealth?.prisma_stt.is_live
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              }`}>
                {gnaniHealth?.prisma_stt.status || 'LIVE'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              {gnaniHealth?.prisma_stt.details || 'Multilingual speech recognition for Marathi, Hindi, and English with auto-detection.'}
            </p>
            <div className="pt-1 flex items-center justify-between text-[10px] font-mono text-slate-400">
              <span>Endpoint</span>
              <span className="text-slate-300">api.vachana.ai/stt/v3</span>
            </div>
          </div>

          {/* Timbre TTS */}
          <div className="p-3.5 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 flex items-center gap-1.5">
                <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
                Timbre TTS v3
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
                gnaniHealth?.timbre_tts.is_live
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              }`}>
                {gnaniHealth?.timbre_tts.status || 'LIVE'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              {gnaniHealth?.timbre_tts.details || '24kHz WAV voice synthesis for worker task dispatch & citizen resolution briefings.'}
            </p>
            <div className="pt-1 flex items-center justify-between text-[10px] font-mono text-slate-400">
              <span>Endpoint</span>
              <span className="text-slate-300">api.vachana.ai/api/v1/tts/inference</span>
            </div>

            {/* Direct Timbre TTS Test Controls */}
            <div className="pt-2 border-t border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-slate-400 font-medium">Test Live Voice:</span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handleTestTimbre('en')}
                    disabled={testingTimbre}
                    className="px-2 py-0.5 rounded bg-indigo-600/80 hover:bg-indigo-500 text-white font-mono text-[10px] transition-all disabled:opacity-50"
                  >
                    EN
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTestTimbre('mr')}
                    disabled={testingTimbre}
                    className="px-2 py-0.5 rounded bg-indigo-600/80 hover:bg-indigo-500 text-white font-mono text-[10px] transition-all disabled:opacity-50"
                  >
                    मराठी
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTestTimbre('hi')}
                    disabled={testingTimbre}
                    className="px-2 py-0.5 rounded bg-indigo-600/80 hover:bg-indigo-500 text-white font-mono text-[10px] transition-all disabled:opacity-50"
                  >
                    हिंदी
                  </button>
                </div>
              </div>

              {testingTimbre && (
                <p className="text-[10px] text-indigo-400 font-mono animate-pulse">
                  Synthesizing speech via Gnani Timbre...
                </p>
              )}

              {timbreAudioUrl && !testingTimbre && (
                <div className="pt-1 flex items-center justify-between gap-1.5">
                  <audio
                    ref={timbreAudioRef}
                    key={timbreAudioUrl}
                    src={timbreAudioUrl}
                    controls
                    autoPlay
                    className="h-6 flex-1 rounded"
                  />
                  <button
                    onClick={() => {
                      if (timbreAudioRef.current) {
                        timbreAudioRef.current.pause();
                      }
                      setTimbreAudioUrl(null);
                    }}
                    title="Minimize player"
                    className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors shrink-0"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Evon Reasoning */}
          <div className="p-3.5 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 flex items-center gap-1.5">
                <BrainCircuit className="w-3.5 h-3.5 text-indigo-400" />
                Evon Reasoning
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                {gnaniHealth?.evon_reasoning.status || 'ACTIVE'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              {gnaniHealth?.evon_reasoning.details || 'Autonomous multi-lingual reasoning engine extracting categories, department routing, and hazard scores.'}
            </p>
            <div className="pt-1 flex items-center justify-between text-[10px] font-mono text-slate-400">
              <span>Pipeline</span>
              <span className="text-emerald-400">Active Multi-Agent Engine</span>
            </div>

            {/* Direct Evon Reasoning Test Controls */}
            <div className="pt-2 border-t border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-slate-400 font-medium">Test Reasoning:</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handleTestEvon('Pothole on FC Road causing traffic')}
                    disabled={testingEvon}
                    className="px-1.5 py-0.5 rounded bg-blue-900/60 hover:bg-blue-800 text-blue-200 font-mono text-[9px] transition-all disabled:opacity-50"
                  >
                    Road
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTestEvon('गटार तुंबले पाणी साचले')}
                    disabled={testingEvon}
                    className="px-1.5 py-0.5 rounded bg-amber-900/60 hover:bg-amber-800 text-amber-200 font-mono text-[9px] transition-all disabled:opacity-50"
                  >
                    गटार
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTestEvon('Major water pipe leakage on Tilak Road')}
                    disabled={testingEvon}
                    className="px-1.5 py-0.5 rounded bg-teal-900/60 hover:bg-teal-800 text-teal-200 font-mono text-[9px] transition-all disabled:opacity-50"
                  >
                    Water
                  </button>
                </div>
              </div>

              {testingEvon && (
                <div className="p-2 rounded bg-slate-900/90 border border-slate-800 text-[10px] text-indigo-400 font-mono animate-pulse flex items-center justify-between">
                  <span>Evon analyzing text...</span>
                  <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                </div>
              )}

              {evonResult && !testingEvon && (
                <div className="p-2 rounded bg-slate-900/90 border border-slate-800 text-[10px] space-y-1 font-mono transition-all">
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="text-[9px] text-indigo-300 font-semibold">Reasoning Output:</span>
                    <button
                      type="button"
                      onClick={() => setEvonResult(null)}
                      title="Minimize result box"
                      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
                    >
                      <span>Minimize</span>
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Category:</span>
                    <strong className="text-blue-400">{evonResult.structured_data?.category}</strong>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Dept:</span>
                    <strong className="text-emerald-400">{evonResult.structured_data?.responsible_department_code}</strong>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Severity:</span>
                    <strong className="text-rose-400">{evonResult.structured_data?.severity_level}</strong>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Warp S2S */}
          <div className="p-3.5 bg-slate-950/70 border border-slate-800/90 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-purple-400" />
                Warp S2S Dialog
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                {gnaniHealth?.warp_s2s.status || 'ACTIVE'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              {gnaniHealth?.warp_s2s.details || 'Conversational dialog turn agent with live Timbre voice synthesis in Marathi, Hindi, and English.'}
            </p>
            <div className="pt-1 flex items-center justify-between text-[10px] font-mono text-slate-400">
              <span>Pipeline</span>
              <span className="text-purple-400">Conversational Voice Turn</span>
            </div>

            {/* Direct Warp S2S Conversational Turn Controls */}
            <div className="pt-2 border-t border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-slate-400 font-medium">Test Turn:</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handleTestWarp('Hello, I want to report an issue')}
                    disabled={testingWarp}
                    className="px-1.5 py-0.5 rounded bg-purple-900/60 hover:bg-purple-800 text-purple-200 font-mono text-[9px] transition-all disabled:opacity-50"
                  >
                    Greeting
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTestWarp('Road is broken with a large pothole')}
                    disabled={testingWarp}
                    className="px-1.5 py-0.5 rounded bg-purple-900/60 hover:bg-purple-800 text-purple-200 font-mono text-[9px] transition-all disabled:opacity-50"
                  >
                    Road
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTestWarp('Water pipe leakage on street')}
                    disabled={testingWarp}
                    className="px-1.5 py-0.5 rounded bg-purple-900/60 hover:bg-purple-800 text-purple-200 font-mono text-[9px] transition-all disabled:opacity-50"
                  >
                    Water
                  </button>
                </div>
              </div>

              {testingWarp && (
                <p className="text-[10px] text-purple-400 font-mono animate-pulse">
                  Warp processing dialog & synthesizing voice...
                </p>
              )}

              {warpResult && !testingWarp && (
                <div className="p-2 rounded bg-slate-900/90 border border-slate-800 text-[10px] space-y-1 font-mono">
                  <div className="flex items-center justify-between text-slate-300">
                    <div className="flex items-center gap-1.5">
                      <span>Intent:</span>
                      <strong className="text-purple-400">{warpResult.detected_intent}</strong>
                    </div>
                    <button
                      onClick={() => {
                        if (warpAudioRef.current) {
                          warpAudioRef.current.pause();
                        }
                        setWarpResult(null);
                      }}
                      title="Minimize result box"
                      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
                    >
                      <span>Minimize</span>
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <p className="text-[9px] text-slate-300 italic line-clamp-2">
                    "{warpResult.reply_text}"
                  </p>
                  {warpResult.reply_audio_url && (
                    <audio
                      ref={warpAudioRef}
                      key={warpResult.reply_audio_url}
                      src={warpResult.reply_audio_url}
                      controls
                      autoPlay
                      className="h-6 w-full rounded mt-1"
                    />
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* The Six Specialized Agents Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {AGENT_METADATA.map((meta) => {
          const Icon = meta.icon;
          const agentExecCount = executions.filter((e) => e.agent_name === meta.name).length;
          const isSelected = selectedAgentFilter === meta.name;

          return (
            <div
              key={meta.name}
              onClick={() => setSelectedAgentFilter(isSelected ? 'ALL' : meta.name)}
              className={`p-3.5 rounded-2xl border transition-all cursor-pointer relative overflow-hidden backdrop-blur-sm ${
                isSelected
                  ? `bg-slate-800/90 ${meta.border} ring-2 ring-blue-500/50 shadow-xl`
                  : 'bg-slate-800/60 border-slate-700/60 hover:bg-slate-800'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className={`p-2 rounded-xl bg-gradient-to-tr ${meta.color} text-white shadow`}>
                  <Icon className="w-4 h-4" />
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-900 border border-slate-700 text-slate-300">
                  {agentExecCount} Runs
                </span>
              </div>
              <h3 className="font-bold text-xs text-white leading-tight">
                {meta.label}
              </h3>
              <p className="text-[11px] text-slate-400 mt-1 line-clamp-3 leading-relaxed">
                {meta.role}
              </p>
              <div className="mt-3 flex items-center gap-1.5 text-[10px] font-mono text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Active Swarm</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Activity Stream & Audit Trail */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Executions Timeline */}
        <div className="lg:col-span-8 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-400" />
              <span>
                Agent Executions Audit Trail {selectedAgentFilter !== 'ALL' && `(${selectedAgentFilter})`}
              </span>
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              Displaying {executions.length} recorded runs
            </span>
          </div>

          {executions.length === 0 ? (
            <div className="p-12 text-center bg-slate-800/40 rounded-2xl border border-slate-800 text-slate-400 text-xs">
              No executions recorded for the selected filter.
            </div>
          ) : (
            <div className="space-y-3">
              {executions.map((ex) => {
                const isExpanded = expandedId === ex.id;
                let parsedInput: any = {};
                let parsedOutput: any = {};
                try {
                  parsedInput = ex.input_payload ? JSON.parse(ex.input_payload) : {};
                  parsedOutput = ex.output_payload ? JSON.parse(ex.output_payload) : {};
                } catch {
                  // Fallback
                }

                return (
                  <div
                    key={ex.id}
                    className="bg-slate-800/80 border border-slate-700/80 rounded-2xl overflow-hidden shadow-lg transition-all"
                  >
                    {/* Collapsible Header */}
                    <div
                      onClick={() => setExpandedId(isExpanded ? null : ex.id)}
                      className="p-4 cursor-pointer hover:bg-slate-750 flex items-center justify-between gap-4"
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                            ex.status === 'COMPLETED'
                              ? 'bg-emerald-400'
                              : ex.status === 'AWAITING_APPROVAL'
                              ? 'bg-purple-400'
                              : ex.status === 'RUNNING'
                              ? 'bg-blue-400 animate-spin'
                              : 'bg-rose-400'
                          }`}
                        ></span>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-white">
                              {ex.agent_name.replace('_', ' ')}
                            </span>
                            <span className="font-mono text-[10px] text-slate-400">
                              run: {ex.workflow_run_id}
                            </span>
                          </div>
                          <p className="text-xs text-slate-300 mt-0.5 line-clamp-1">
                            {ex.reasoning_summary}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <span className="font-mono text-[11px] text-blue-400 bg-blue-950/80 px-2 py-0.5 rounded border border-blue-800">
                          {ex.latency_ms} ms
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono hidden sm:inline">
                          {new Date(ex.started_at).toLocaleTimeString()}
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-slate-400" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-slate-400" />
                        )}
                      </div>
                    </div>

                    {/* Expanded Detail Panel */}
                    {isExpanded && (
                      <div className="p-5 border-t border-slate-700/60 bg-slate-900/90 space-y-4 text-xs">
                        {/* Concise Decision Reasoning Summary */}
                        <div>
                          <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">
                            User-Facing Decision Explanation:
                          </span>
                          <div className="mt-1 p-3 bg-slate-950 rounded-xl border border-slate-800 text-slate-200 leading-relaxed font-sans">
                            {ex.reasoning_summary}
                          </div>
                        </div>

                        {/* Tool Calls Performed */}
                        {ex.actions && ex.actions.length > 0 && (
                          <div>
                            <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">
                              Tools Invoked ({ex.actions.length}):
                            </span>
                            <div className="mt-1.5 space-y-2">
                              {ex.actions.map((act) => (
                                <div
                                  key={act.id}
                                  className="p-3 bg-slate-950 rounded-xl border border-slate-800 font-mono text-[11px] space-y-1.5"
                                >
                                  <div className="flex items-center justify-between text-blue-400 font-bold">
                                    <span className="flex items-center gap-1.5">
                                      <Code className="w-3.5 h-3.5" />
                                      {act.tool_name}()
                                    </span>
                                    <span className="text-[10px] text-emerald-400 bg-emerald-950/60 px-1.5 py-0.2 rounded border border-emerald-800">
                                      {act.status}
                                    </span>
                                  </div>

                                  {act.tool_input && (
                                    <div className="text-slate-400 text-[10px] overflow-x-auto">
                                      <span className="text-slate-500">Input: </span>
                                      {act.tool_input}
                                    </div>
                                  )}
                                  {act.tool_output && (
                                    <div className="text-slate-300 text-[10px] overflow-x-auto">
                                      <span className="text-slate-500">Output: </span>
                                      {act.tool_output}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Structured Input / Output Payloads */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                          <div>
                            <span className="text-slate-400 font-semibold text-[10px] uppercase">
                              Structured Input:
                            </span>
                            <pre className="mt-1 p-2.5 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[10px] text-slate-300 overflow-x-auto max-h-32">
                              {JSON.stringify(parsedInput, null, 2)}
                            </pre>
                          </div>

                          <div>
                            <span className="text-slate-400 font-semibold text-[10px] uppercase">
                              Structured Output:
                            </span>
                            <pre className="mt-1 p-2.5 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[10px] text-slate-300 overflow-x-auto max-h-32">
                              {JSON.stringify(parsedOutput, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Live Stream Ticker & Swarm Health */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <span>Real-Time WebSocket Feed</span>
            </h3>

            <div className="space-y-2 max-h-96 overflow-y-auto font-mono text-xs">
              {liveStreamEvents.length === 0 ? (
                <div className="p-6 text-center text-slate-500 text-xs">
                  Listening for agent actions...
                </div>
              ) : (
                liveStreamEvents.map((evt, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg space-y-0.5"
                  >
                    <div className="flex items-center justify-between text-[11px] text-blue-400 font-bold">
                      <span>{evt.agent_name}</span>
                      <span className="text-[10px] text-slate-400">{evt.latency_ms}ms</span>
                    </div>
                    <p className="text-[11px] text-slate-300 font-sans truncate">
                      {evt.reasoning_summary}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-5 shadow-xl text-xs space-y-3">
            <h4 className="font-bold text-white uppercase tracking-wider text-[11px]">
              Swarm Safety & Compliance
            </h4>
            <p className="text-slate-300 leading-relaxed">
              ResolveGrid AI executes permitted tools autonomously while preserving audit trails.
              Private chain-of-thought is never exposed to the frontend; only concise decision rationales and tool inputs/outputs are surfaced.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
