import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader2, Volume2, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface VoiceRecorderProps {
  onTranscriptionComplete: (text: string, language: string, confidence: number) => void;
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({ onTranscriptionComplete }) => {
  const { language, t } = useAuth();
  const [speechLanguage, setSpeechLanguage] = useState<string>(
    language === 'mr' ? 'mr-IN' : language === 'hi' ? 'hi-IN' : 'en-IN'
  );
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordedAudioUrl, setRecordedAudioUrl] = useState<string | null>(null);
  const [transcribedText, setTranscribedText] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [providerInfo, setProviderInfo] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<any>(null);

  useEffect(() => {
    setSpeechLanguage(language === 'mr' ? 'mr-IN' : language === 'hi' ? 'hi-IN' : 'en-IN');
  }, [language]);

  const startRecording = async () => {
    try {
      setTranscribedText(null);
      setRecordedAudioUrl(null);
      setErrorMessage(null);
      audioChunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        const audioUrl = URL.createObjectURL(audioBlob);
        setRecordedAudioUrl(audioUrl);
        await handleTranscribe(audioBlob);
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Error accessing microphone:', err);
      setErrorMessage('Microphone access was denied or is not supported by your browser.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      clearInterval(timerIntervalRef.current);
    }
  };

  const handleTranscribe = async (blob: Blob) => {
    setIsTranscribing(true);
    setErrorMessage(null);
    try {
      const res = await api.voice.transcribe(blob, speechLanguage);
      if (!res.text || res.text.trim() === '') {
        setErrorMessage('No recognizable speech was detected in the audio. Please speak clearly into your microphone.');
        return;
      }
      setTranscribedText(res.text);
      setConfidence(res.confidence);
      setProviderInfo(res.provider || 'Gnani Prisma');
      onTranscriptionComplete(res.text, res.detected_language, res.confidence);
    } catch (err: any) {
      console.error('Gnani Prisma transcription error:', err);
      setErrorMessage('Voice transcription failed. Please check network connectivity or retry recording.');
    } finally {
      setIsTranscribing(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-5 pb-3 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
            <Mic className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              {t.voiceReport}
              <span className="text-xs uppercase font-mono px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
                Gnani Prisma STT
              </span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Speak in Marathi, Hindi, or English — speech is automatically recognized and structured.
            </p>
          </div>
        </div>
      </div>

      {/* Recording Interface */}
      <div className="flex flex-col items-center justify-center gap-4 bg-slate-50 border border-slate-200/80 rounded-2xl p-6 text-center">
        {!isRecording ? (
          <button
            type="button"
            onClick={startRecording}
            disabled={isTranscribing}
            className="flex items-center gap-3 px-8 py-4 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-bold text-base shadow-lg shadow-blue-600/25 transition-all disabled:opacity-50"
          >
            <Mic className="w-5 h-5 animate-pulse" />
            <span>{t.recordAudio} (बोला / बोलिए)</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={stopRecording}
            className="flex items-center gap-3 px-8 py-4 rounded-2xl bg-rose-600 hover:bg-rose-700 active:scale-95 text-white font-bold text-base shadow-lg shadow-rose-600/25 transition-all animate-pulse"
          >
            <Square className="w-5 h-5 fill-white" />
            <span>{t.stopRecording} ({recordingSeconds}s)</span>
          </button>
        )}

        {isRecording && (
          <div className="flex items-center gap-2 text-xs font-semibold text-rose-600">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
            </span>
            <span>{t.recording} ({speechLanguage}) — Click Stop when finished speaking</span>
          </div>
        )}

        {isTranscribing && (
          <div className="flex items-center gap-2 text-xs text-blue-600 font-semibold">
            <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
            <span>{t.transcribingPrisma}</span>
          </div>
        )}

        {recordedAudioUrl && !isRecording && (
          <div className="flex items-center gap-2 mt-1">
            <Volume2 className="w-4 h-4 text-slate-500" />
            <audio src={recordedAudioUrl} controls className="h-8 w-60 sm:w-72" />
          </div>
        )}
      </div>

      {/* Error Alert Box */}
      {errorMessage && (
        <div className="mt-4 p-3.5 bg-rose-50 border border-rose-200 rounded-2xl text-xs text-rose-800 flex items-center gap-2.5 font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Transcription Preview Box */}
      {transcribedText && (
        <div className="mt-4 p-4 bg-emerald-50/60 border border-emerald-200 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-xs text-emerald-800 font-bold">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" /> {providerInfo || 'Transcribed by Gnani Prisma'}
            </span>
            {confidence && (
              <span className="font-mono text-xs bg-white px-2.5 py-0.5 rounded-full border border-emerald-300 text-emerald-700 shadow-xs">
                Confidence: {(confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <p className="text-sm text-slate-800 font-medium italic bg-white p-3 rounded-xl border border-emerald-100 shadow-xs">
            "{transcribedText}"
          </p>
        </div>
      )}
    </div>
  );
};
