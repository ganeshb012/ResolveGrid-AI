import axios from 'axios';
import {
  User,
  Incident,
  Worker,
  Assignment,
  IncidentEvidence,
  AgentExecution,
  HumanApproval,
  OverviewStats,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL
  ? `${(import.meta.env.VITE_API_URL as string).replace(/\/$/, '')}/api/v1`
  : '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach Authorization header if token exists
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 unauthorized
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.includes('/login')) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
    return Promise.reject(error);
  }
);

export const api = {
  auth: {
    login: async (credentials: any) => {
      const res = await apiClient.post('/auth/login', credentials);
      return res.data;
    },
    register: async (data: any) => {
      const res = await apiClient.post('/auth/register', data);
      return res.data;
    },
    getMe: async (): Promise<User> => {
      const res = await apiClient.get('/auth/me');
      return res.data;
    },
  },

  incidents: {
    list: async (params?: any): Promise<Incident[]> => {
      const res = await apiClient.get('/incidents', { params });
      return res.data;
    },
    get: async (id: string): Promise<any> => {
      const res = await apiClient.get(`/incidents/${id}`);
      return res.data;
    },
    create: async (data: any): Promise<Incident> => {
      const res = await apiClient.post('/incidents', data);
      return res.data;
    },
    update: async (id: string, data: any): Promise<Incident> => {
      const res = await apiClient.patch(`/incidents/${id}`, data);
      return res.data;
    },
    getHistory: async (id: string) => {
      const res = await apiClient.get(`/incidents/${id}/history`);
      return res.data;
    },
    uploadEvidence: async (id: string, formData: FormData) => {
      const res = await apiClient.post(`/incidents/${id}/evidence`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
    getEvidence: async (id: string): Promise<IncidentEvidence[]> => {
      const res = await apiClient.get(`/incidents/${id}/evidence`);
      return res.data;
    },
    verify: async (id: string, notes?: string) => {
      const res = await apiClient.post(`/incidents/${id}/verify`, { notes });
      return res.data;
    },
  },

  workers: {
    list: async (params?: any): Promise<Worker[]> => {
      const res = await apiClient.get('/workers', { params });
      return res.data;
    },
    getMe: async (): Promise<Worker> => {
      const res = await apiClient.get('/workers/me');
      return res.data;
    },
    get: async (id: string): Promise<Worker> => {
      const res = await apiClient.get(`/workers/${id}`);
      return res.data;
    },
    updateAvailability: async (id: string, status: string, notes?: string) => {
      const res = await apiClient.patch(`/workers/${id}/availability`, { status, notes });
      return res.data;
    },
    updateLocation: async (id: string, latitude: number, longitude: number) => {
      const res = await apiClient.patch(`/workers/${id}/location`, { latitude, longitude });
      return res.data;
    },
  },

  assignments: {
    list: async (params?: any): Promise<Assignment[]> => {
      const res = await apiClient.get('/assignments', { params });
      return res.data;
    },
    listMy: async (): Promise<Assignment[]> => {
      const res = await apiClient.get('/assignments/my');
      return res.data;
    },
    create: async (data: any): Promise<Assignment> => {
      const res = await apiClient.post('/assignments', data);
      return res.data;
    },
    updateStatus: async (id: string, status: string, notes?: string, rejectionReason?: string) => {
      const res = await apiClient.patch(`/assignments/${id}`, {
        status,
        worker_notes: notes,
        rejection_reason: rejectionReason,
      });
      return res.data;
    },
  },

  agents: {
    listActivity: async (params?: any): Promise<AgentExecution[]> => {
      const res = await apiClient.get('/agents/activity', { params });
      return res.data;
    },
    getExecution: async (id: string): Promise<AgentExecution> => {
      const res = await apiClient.get(`/agents/executions/${id}`);
      return res.data;
    },
    runWorkflow: async (incidentId: string) => {
      const res = await apiClient.post('/agents/run', { incident_id: incidentId });
      return res.data;
    },
  },

  approvals: {
    list: async (status: string = 'PENDING'): Promise<HumanApproval[]> => {
      const res = await apiClient.get('/approvals', { params: { status } });
      return res.data;
    },
    approve: async (id: string, notes?: string) => {
      const res = await apiClient.post(`/approvals/${id}/approve`, {
        decision: 'APPROVE',
        review_notes: notes,
      });
      return res.data;
    },
    reject: async (id: string, notes?: string) => {
      const res = await apiClient.post(`/approvals/${id}/reject`, {
        decision: 'REJECT',
        review_notes: notes,
      });
      return res.data;
    },
  },

  voice: {
    transcribe: async (file: File | Blob, language: string = 'indic-auto') => {
      const formData = new FormData();
      const ext = file.type.includes('webm')
        ? 'webm'
        : file.type.includes('ogg')
        ? 'ogg'
        : file.type.includes('mp3')
        ? 'mp3'
        : 'wav';
      const filename = (file instanceof File && file.name) ? file.name : `voice_recording.${ext}`;
      formData.append('file', file, filename);
      formData.append('language', language);
      const res = await apiClient.post('/voice/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
    speak: async (text: string, language: string = 'en') => {
      const res = await apiClient.post('/voice/speak', { text, language });
      return res.data;
    },
    reason: async (text: string) => {
      const res = await apiClient.post('/voice/reason', { text });
      return res.data;
    },
    conversation: async (sessionId: string, message: string, language: string = 'en') => {
      const res = await apiClient.post('/voice/conversation', {
        session_id: sessionId,
        text_message: message,
        language,
      });
      return res.data;
    },
    getStatus: async () => {
      const res = await apiClient.get('/voice/status');
      return res.data;
    },
  },

  analytics: {
    getOverview: async (): Promise<OverviewStats> => {
      const res = await apiClient.get('/analytics/overview');
      return res.data;
    },
    getIncidents: async () => {
      const res = await apiClient.get('/analytics/incidents');
      return res.data;
    },
    getDepartments: async () => {
      const res = await apiClient.get('/analytics/departments');
      return res.data;
    },
  },

  users: {
    list: async (params?: { role?: string; search?: string; is_active?: boolean }) => {
      const res = await apiClient.get('/users', { params });
      return res.data;
    },
    get: async (id: string) => {
      const res = await apiClient.get(`/users/${id}`);
      return res.data;
    },
    create: async (data: any) => {
      const res = await apiClient.post('/users', data);
      return res.data;
    },
    update: async (id: string, data: any) => {
      const res = await apiClient.patch(`/users/${id}`, data);
      return res.data;
    },
    resetPassword: async (id: string, newPassword: string) => {
      const res = await apiClient.post(`/users/${id}/reset-password`, { new_password: newPassword });
      return res.data;
    },
    getDepartments: async () => {
      const res = await apiClient.get('/users/departments');
      return res.data;
    },
    deactivate: async (id: string) => {
      const res = await apiClient.delete(`/users/${id}`);
      return res.data;
    },
  },
};
