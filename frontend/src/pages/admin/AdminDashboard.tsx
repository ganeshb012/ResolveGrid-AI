import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { wsClient } from '../../api/ws';
import {
  Incident,
  Worker,
  HumanApproval,
  OverviewStats,
} from '../../types';
import { IncidentMap } from '../../components/IncidentMap';
import {
  Shield,
  AlertTriangle,
  Clock,
  CheckCircle2,
  HardHat,
  Search,
  Filter,
  UserCheck,
  TrendingUp,
  AlertOctagon,
  RefreshCw,
  Check,
  X,
  MapPin,
  ChevronRight,
  Users,
  UserPlus,
  KeyRound,
  Edit,
  Power,
  Building2,
  UserX,
  Activity,
  Radio,
  Eye,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

export const AdminDashboard: React.FC = () => {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [approvals, setApprovals] = useState<HumanApproval[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [activeTab, setActiveTab] = useState<'map' | 'incidents' | 'approvals' | 'analytics' | 'workers' | 'users'>('map');

  // Approval modal state
  const [reviewNotes, setReviewNotes] = useState('');
  const [processingApprovalId, setProcessingApprovalId] = useState<string | null>(null);

  // Manual assign state
  const [assignWorkerModal, setAssignWorkerModal] = useState<Incident | null>(null);
  const [selectedWorkerId, setSelectedWorkerId] = useState<string>('');

  // User Management State
  const [managedUsers, setManagedUsers] = useState<any[]>([]);
  const [departmentsList, setDepartmentsList] = useState<{ id: string; name: string; code: string }[]>([]);
  const [userSearchTerm, setUserSearchTerm] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState<string>('ALL');
  const [userStatusFilter, setUserStatusFilter] = useState<string>('ALL');
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<any | null>(null);
  const [resetPasswordUser, setResetPasswordUser] = useState<any | null>(null);
  const [newPasswordVal, setNewPasswordVal] = useState('');
  const [userActionError, setUserActionError] = useState<string | null>(null);
  const [userActionSuccess, setUserActionSuccess] = useState<string | null>(null);

  // Live Operations Feed State
  interface OperationEvent {
    id: string;
    time: string;
    title: string;
    description: string;
    type: 'INCIDENT' | 'DISPATCH' | 'APPROVAL' | 'VERIFICATION' | 'SYSTEM';
    badge: string;
    badgeColor: string;
    incidentId?: string;
  }

  const [operationsFeed, setOperationsFeed] = useState<OperationEvent[]>([]);
  const [inspectorMode, setInspectorMode] = useState<'inspector' | 'operations'>('operations');

  // Create User Form State
  const [newUserForm, setNewUserForm] = useState({
    role: 'WORKER',
    full_name: '',
    email: '',
    phone: '',
    password: '',
    department_id: '',
    employee_id: '',
    skills: '',
    preferred_language: 'en',
  });

  const loadData = async () => {
    try {
      const [statsData, incidentsData, workersData, approvalsData, usersData, deptsData] = await Promise.all([
        api.analytics.getOverview(),
        api.incidents.list(),
        api.workers.list(),
        api.approvals.list('PENDING'),
        api.users.list().catch(() => []),
        api.users.getDepartments().catch(() => []),
      ]);
      setStats(statsData);
      setIncidents(incidentsData);
      setWorkers(workersData);
      setApprovals(approvalsData);
      if (usersData) setManagedUsers(usersData);
      if (deptsData) setDepartmentsList(deptsData);

      // Populate Live Operations Feed from active data
      const initialFeed: OperationEvent[] = [];
      incidentsData.slice(0, 15).forEach((inc) => {
        const timeStr = new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        if (inc.status === 'RESOLVED') {
          initialFeed.push({
            id: `op-res-${inc.id}`,
            time: timeStr,
            title: `Incident ${inc.incident_number} Verified & Resolved`,
            description: `Verification Agent confirmed photographic proof. Issue on ${inc.address} closed.`,
            type: 'VERIFICATION',
            badge: 'Resolved',
            badgeColor: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
            incidentId: inc.id,
          });
        } else if (inc.status === 'IN_PROGRESS' || inc.status === 'ASSIGNED') {
          initialFeed.push({
            id: `op-disp-${inc.id}`,
            time: timeStr,
            title: `Field Squad Active: ${inc.incident_number}`,
            description: `Resource Allocation Agent routed squad to ${inc.address}.`,
            type: 'DISPATCH',
            badge: 'Dispatched',
            badgeColor: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
            incidentId: inc.id,
          });
        } else if (inc.status === 'PENDING_APPROVAL') {
          initialFeed.push({
            id: `op-appr-${inc.id}`,
            time: timeStr,
            title: `High Hazard Awaiting Admin Approval: ${inc.incident_number}`,
            description: `Public safety threshold reached on ${inc.address}. Queued for authorization.`,
            type: 'APPROVAL',
            badge: 'Pending Review',
            badgeColor: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
            incidentId: inc.id,
          });
        } else {
          initialFeed.push({
            id: `op-new-${inc.id}`,
            time: timeStr,
            title: `New Incident Reported: ${inc.incident_number}`,
            description: `Citizen submitted: "${inc.title}" at ${inc.address}.`,
            type: 'INCIDENT',
            badge: inc.category,
            badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
            incidentId: inc.id,
          });
        }
      });
      setOperationsFeed(initialFeed);
    } catch (e) {
      console.error('Error fetching admin dashboard data:', e);
    }
  };

  useEffect(() => {
    loadData();

    // Real-time event listeners
    const unsubNewInc = wsClient.on('NEW_INCIDENT', (payload) => {
      loadData();
      setOperationsFeed((prev) => [
        {
          id: `op-live-${Date.now()}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          title: `New Citizen Grievance Registered`,
          description: payload?.title || 'Citizen submitted public infrastructure complaint via mobile portal.',
          type: 'INCIDENT',
          badge: 'New Incident',
          badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
          incidentId: payload?.id,
        },
        ...prev.slice(0, 29),
      ]);
    });

    const unsubStatus = wsClient.on('INCIDENT_STATUS_CHANGED', (payload) => {
      loadData();
      setOperationsFeed((prev) => [
        {
          id: `op-stat-${Date.now()}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          title: `Incident Status Updated: ${payload?.new_status || 'STATUS'}`,
          description: `Lifecycle transition triggered for incident ${payload?.incident_id?.slice(0, 8) || ''}.`,
          type: 'SYSTEM',
          badge: payload?.new_status || 'Updated',
          badgeColor: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
          incidentId: payload?.incident_id,
        },
        ...prev.slice(0, 29),
      ]);
    });

    const unsubApprReq = wsClient.on('APPROVAL_REQUESTED', (payload) => {
      loadData();
      setOperationsFeed((prev) => [
        {
          id: `op-appr-req-${Date.now()}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          title: `Emergency Hazard Queued for Human Approval`,
          description: payload?.reason || 'Multi-agent system flagged high public safety risk.',
          type: 'APPROVAL',
          badge: 'Approval Needed',
          badgeColor: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
          incidentId: payload?.incident_id,
        },
        ...prev.slice(0, 29),
      ]);
    });

    const unsubApprDec = wsClient.on('APPROVAL_DECIDED', (payload) => {
      loadData();
      setOperationsFeed((prev) => [
        {
          id: `op-appr-dec-${Date.now()}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          title: `Admin Authorization Processed`,
          description: `Operations Admin decided status: ${payload?.decision || 'DECIDED'}.`,
          type: 'APPROVAL',
          badge: payload?.decision || 'Decided',
          badgeColor: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
          incidentId: payload?.incident_id,
        },
        ...prev.slice(0, 29),
      ]);
    });

    const unsubAssigned = wsClient.on('INCIDENT_ASSIGNED', (payload) => {
      loadData();
      setOperationsFeed((prev) => [
        {
          id: `op-assign-${Date.now()}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          title: `Field Crew Dispatched to Location`,
          description: `Haversine routing matched nearest municipal specialist. Voice dispatch triggered.`,
          type: 'DISPATCH',
          badge: 'Assigned',
          badgeColor: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
          incidentId: payload?.incident_id,
        },
        ...prev.slice(0, 29),
      ]);
    });

    return () => {
      unsubNewInc();
      unsubStatus();
      unsubApprReq();
      unsubApprDec();
      unsubAssigned();
    };
  }, []);

  const handleApprove = async (approvalId: string) => {
    setProcessingApprovalId(approvalId);
    try {
      await api.approvals.approve(approvalId, reviewNotes || 'Approved by Operations Admin');
      setReviewNotes('');
      loadData();
    } catch (e) {
      console.error('Approval failed:', e);
    } finally {
      setProcessingApprovalId(null);
    }
  };

  const handleReject = async (approvalId: string) => {
    setProcessingApprovalId(approvalId);
    try {
      await api.approvals.reject(approvalId, reviewNotes || 'Rejected by Operations Admin');
      setReviewNotes('');
      loadData();
    } catch (e) {
      console.error('Rejection failed:', e);
    } finally {
      setProcessingApprovalId(null);
    }
  };

  const handleManualAssign = async () => {
    if (!assignWorkerModal || !selectedWorkerId) return;
    try {
      await api.assignments.create({
        incident_id: assignWorkerModal.id,
        worker_id: selectedWorkerId,
        assigned_by_type: 'ADMIN',
      });
      setAssignWorkerModal(null);
      setSelectedWorkerId('');
      loadData();
    } catch (e) {
      console.error('Manual assign error:', e);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setUserActionError(null);
    setUserActionSuccess(null);
    try {
      await api.users.create({
        ...newUserForm,
        department_id: newUserForm.role === 'WORKER' ? newUserForm.department_id : undefined,
      });
      setUserActionSuccess(`Successfully created ${newUserForm.role} account for ${newUserForm.full_name}`);
      setShowCreateUserModal(false);
      setNewUserForm({
        role: 'WORKER',
        full_name: '',
        email: '',
        phone: '',
        password: '',
        department_id: '',
        employee_id: '',
        skills: '',
        preferred_language: 'en',
      });
      loadData();
    } catch (err: any) {
      setUserActionError(err.response?.data?.detail || 'Failed to create user account.');
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    setUserActionError(null);
    setUserActionSuccess(null);
    try {
      await api.users.update(editingUser.id, {
        full_name: editingUser.full_name,
        phone: editingUser.phone,
        department_id: editingUser.department_id,
        skills: editingUser.skills,
      });
      setUserActionSuccess(`Updated account for ${editingUser.full_name}`);
      setEditingUser(null);
      loadData();
    } catch (err: any) {
      setUserActionError(err.response?.data?.detail || 'Failed to update user.');
    }
  };

  const handleToggleUserStatus = async (user: any) => {
    setUserActionError(null);
    setUserActionSuccess(null);
    const newStatus = !user.is_active;
    try {
      await api.users.update(user.id, { is_active: newStatus });
      setUserActionSuccess(`${user.full_name} is now ${newStatus ? 'Activated' : 'Deactivated'}`);
      loadData();
    } catch (err: any) {
      setUserActionError(err.response?.data?.detail || 'Failed to change account status.');
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetPasswordUser || !newPasswordVal) return;
    setUserActionError(null);
    setUserActionSuccess(null);
    try {
      await api.users.resetPassword(resetPasswordUser.id, newPasswordVal);
      setUserActionSuccess(`Password successfully reset for ${resetPasswordUser.email}`);
      setResetPasswordUser(null);
      setNewPasswordVal('');
    } catch (err: any) {
      setUserActionError(err.response?.data?.detail || 'Failed to reset password.');
    }
  };

  const filteredIncidents = incidents.filter((inc) => {
    const matchesSearch =
      inc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.address.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.incident_number.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = !statusFilter || inc.status === statusFilter;
    const matchesPriority = !priorityFilter || inc.priority === priorityFilter;
    return matchesSearch && matchesStatus && matchesPriority;
  });

  // Chart data
  const deptChartData =
    stats?.departments.map((d) => ({
      name: d.department_name.split(' ')[0],
      total: d.active_incidents,
      resolved: 0,
    })) || [];

  const priorityChartData = [
    { name: 'Critical', value: incidents.filter((i) => i.priority === 'CRITICAL').length },
    { name: 'High', value: incidents.filter((i) => i.priority === 'HIGH').length },
    { name: 'Medium', value: incidents.filter((i) => i.priority === 'MEDIUM').length },
    { name: 'Low', value: incidents.filter((i) => i.priority === 'LOW').length },
  ];

  const pieColors = ['#f43f5e', '#f97316', '#eab308', '#3b82f6'];

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Banner / Headline */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-2">
            <Shield className="w-7 h-7 text-blue-500" />
            <span>Operations Command Center</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Pune Municipal Corporation • Multi-Agent Autonomous Resolution & Oversight
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex flex-wrap items-center bg-slate-800 p-1 rounded-xl border border-slate-700 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('map')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'map' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Live Map
          </button>
          <button
            onClick={() => setActiveTab('incidents')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'incidents' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Incidents ({incidents.length})
          </button>
          <button
            onClick={() => setActiveTab('approvals')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              activeTab === 'approvals' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <span>Approvals Queue</span>
            {approvals.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] animate-pulse">
                {approvals.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('workers')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'workers' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Field Crew ({workers.length})
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'analytics' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Analytics & SLA
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              activeTab === 'users' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Manage Users ({managedUsers.filter((u) => u.role !== 'ADMIN').length})</span>
          </button>
        </div>
      </div>

      {/* KPI Statistic Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
        <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-lg">
          <span className="text-xs text-slate-400 font-medium">Total Incidents</span>
          <div className="text-2xl font-bold text-white mt-1">
            {stats?.incidents.total || incidents.length}
          </div>
          <span className="text-[11px] text-blue-400 flex items-center gap-1 mt-1">
            <TrendingUp className="w-3 h-3" /> Pune Municipal
          </span>
        </div>

        <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-lg">
          <span className="text-xs text-slate-400 font-medium">High / Critical</span>
          <div className="text-2xl font-bold text-rose-400 mt-1">
            {stats?.incidents.high_priority || 0}
          </div>
          <span className="text-[11px] text-rose-300 flex items-center gap-1 mt-1">
            <AlertTriangle className="w-3 h-3" /> Urgent Hazards
          </span>
        </div>

        <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-lg">
          <span className="text-xs text-slate-400 font-medium">In Progress</span>
          <div className="text-2xl font-bold text-amber-400 mt-1">
            {stats?.incidents.in_progress || 0}
          </div>
          <span className="text-[11px] text-amber-300 flex items-center gap-1 mt-1">
            <Clock className="w-3 h-3" /> Field Crew Active
          </span>
        </div>

        <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-lg">
          <span className="text-xs text-slate-400 font-medium">Resolved</span>
          <div className="text-2xl font-bold text-emerald-400 mt-1">
            {stats?.incidents.resolved || 0}
          </div>
          <span className="text-[11px] text-emerald-300 flex items-center gap-1 mt-1">
            <CheckCircle2 className="w-3 h-3" /> Verified Closed
          </span>
        </div>

        <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-lg">
          <span className="text-xs text-slate-400 font-medium">Pending Approvals</span>
          <div className="text-2xl font-bold text-purple-400 mt-1">
            {approvals.length}
          </div>
          <span className="text-[11px] text-purple-300 flex items-center gap-1 mt-1">
            <AlertOctagon className="w-3 h-3" /> Human Oversight
          </span>
        </div>

        <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-lg">
          <span className="text-xs text-slate-400 font-medium">Workers On Duty</span>
          <div className="text-2xl font-bold text-cyan-400 mt-1">
            {stats?.workers.available || 0} / {workers.length}
          </div>
          <span className="text-[11px] text-cyan-300 flex items-center gap-1 mt-1">
            <HardHat className="w-3 h-3" /> Ready to Dispatch
          </span>
        </div>
      </div>

      {/* TAB 1: LIVE MAP VIEW */}
      {activeTab === 'map' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8 h-[620px]">
            <IncidentMap
              incidents={incidents}
              workers={workers}
              onSelectIncident={(inc) => setSelectedIncident(inc)}
            />
          </div>

          {/* Quick Incident Inspector / Live Operations Stream Box */}
          <div className="lg:col-span-4 bg-slate-800/80 border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-4 overflow-y-auto max-h-[620px]">
            {/* Header with Mode Toggle */}
            <div className="flex items-center justify-between border-b border-slate-700 pb-3 gap-2">
              <div className="flex items-center bg-slate-900 p-0.5 rounded-xl border border-slate-700/80 text-xs">
                <button
                  type="button"
                  onClick={() => setInspectorMode('operations')}
                  className={`px-2.5 py-1.5 rounded-lg font-semibold transition-all flex items-center gap-1.5 ${
                    inspectorMode === 'operations'
                      ? 'bg-blue-600 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Activity className="w-3.5 h-3.5" />
                  <span>Live Operations</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-950 font-mono text-slate-300">
                    {operationsFeed.length}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setInspectorMode('inspector')}
                  className={`px-2.5 py-1.5 rounded-lg font-semibold transition-all flex items-center gap-1.5 ${
                    inspectorMode === 'inspector'
                      ? 'bg-blue-600 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Inspector</span>
                  {selectedIncident && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-950 font-mono text-blue-300">
                      Active
                    </span>
                  )}
                </button>
              </div>

              <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1.5 bg-emerald-950/40 px-2 py-1 rounded-lg border border-emerald-800/40 shrink-0">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>LIVE FEED</span>
              </span>
            </div>

            {/* Content Mode 1: Real-Time Municipal Operations Stream */}
            {inspectorMode === 'operations' ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                  <span>Municipal Operations Stream</span>
                  <span>Auto-updated via WebSocket</span>
                </div>

                {operationsFeed.length === 0 ? (
                  <div className="p-8 text-center text-slate-500 text-xs bg-slate-900/40 rounded-xl border border-slate-800">
                    Listening for municipal incident updates and field worker dispatches...
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {operationsFeed.map((op) => (
                      <div
                        key={op.id}
                        onClick={() => {
                          if (op.incidentId) {
                            const found = incidents.find((i) => i.id === op.incidentId);
                            if (found) {
                              setSelectedIncident(found);
                              setInspectorMode('inspector');
                            }
                          }
                        }}
                        className={`p-3 bg-slate-900/80 border border-slate-700/60 rounded-xl space-y-1.5 transition-all ${
                          op.incidentId ? 'cursor-pointer hover:border-blue-500/60 hover:bg-slate-900' : ''
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${op.badgeColor}`}>
                            {op.badge}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {op.time}
                          </span>
                        </div>
                        <h5 className="text-xs font-bold text-white line-clamp-1">{op.title}</h5>
                        <p className="text-[11px] text-slate-300 line-clamp-2 leading-relaxed">
                          {op.description}
                        </p>
                        {op.incidentId && (
                          <div className="pt-1 flex items-center justify-end text-[10px] text-blue-400 font-semibold gap-1">
                            <span>Inspect on Map</span>
                            <ChevronRight className="w-3 h-3" />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* Content Mode 2: Detailed Incident Inspector */
              <div>
                {selectedIncident ? (
                  <div className="space-y-4 text-xs">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-blue-400 text-xs font-bold">
                          {selectedIncident.incident_number}
                        </span>
                        <button
                          onClick={() => setInspectorMode('operations')}
                          className="text-[10px] text-slate-400 hover:text-white underline"
                        >
                          ← Back to Live Stream
                        </button>
                      </div>
                      <h4 className="text-base font-bold text-white mt-1">
                        {selectedIncident.title}
                      </h4>
                      <p className="text-slate-300 mt-1">{selectedIncident.description}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 p-3 bg-slate-900 rounded-xl border border-slate-700/60 font-mono text-[11px]">
                      <div>
                        <span className="text-slate-500">Category:</span>
                        <p className="text-slate-200 font-sans">{selectedIncident.category}</p>
                      </div>
                      <div>
                        <span className="text-slate-500">Priority:</span>
                        <p className="text-rose-400 font-bold">{selectedIncident.priority}</p>
                      </div>
                      <div>
                        <span className="text-slate-500">Status:</span>
                        <p className="text-amber-400">{selectedIncident.status}</p>
                      </div>
                      <div>
                        <span className="text-slate-500">Hazard:</span>
                        <p className="text-slate-200">{selectedIncident.public_safety_risk ? 'Yes' : 'No'}</p>
                      </div>
                    </div>

                    <div>
                      <span className="text-slate-400 font-medium">Pune Location:</span>
                      <p className="text-slate-200 font-semibold mt-0.5">{selectedIncident.address}</p>
                      <p className="text-slate-400 font-mono text-[10px] mt-0.5">
                        Coordinates: {selectedIncident.latitude.toFixed(4)}, {selectedIncident.longitude.toFixed(4)}
                      </p>
                    </div>

                    {/* Dispatch / Manual Override Button */}
                    <div className="pt-2 border-t border-slate-700 space-y-2">
                      <div className="flex gap-2">
                        <button
                          onClick={() => setAssignWorkerModal(selectedIncident)}
                          className="flex-1 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow"
                        >
                          <HardHat className="w-3.5 h-3.5" /> Assign Field Crew
                        </button>
                        <button
                          onClick={async () => {
                            await api.agents.runWorkflow(selectedIncident.id);
                            alert('Re-triggered LangGraph Multi-Agent Workflow');
                            loadData();
                          }}
                          className="py-2 px-3 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-semibold"
                        >
                          Re-run Agents
                        </button>
                      </div>

                      <div className="flex gap-2">
                        {selectedIncident.status === 'RESOLVED_PENDING_VERIFICATION' && (
                          <button
                            onClick={async () => {
                              try {
                                await api.incidents.verify(selectedIncident.id, 'Verified by Municipal Admin');
                                alert('Resolution verified! Incident closed and citizen notified.');
                                loadData();
                              } catch (e: any) {
                                alert('Verification failed: ' + (e.response?.data?.detail || e.message));
                              }
                            }}
                            className="flex-1 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" /> Verify & Close Incident
                          </button>
                        )}
                        {selectedIncident.status !== 'RESOLVED' && selectedIncident.status !== 'ESCALATED' && (
                          <button
                            onClick={async () => {
                              await api.incidents.update(selectedIncident.id, {
                                priority: 'CRITICAL',
                                status: 'ESCALATED',
                              });
                              alert('Incident escalated to CRITICAL priority.');
                              loadData();
                            }}
                            className="py-2 px-3 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-200 text-xs font-semibold border border-rose-700/60"
                          >
                            Escalate
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-8 text-center text-slate-400 text-xs space-y-3 bg-slate-900/40 rounded-xl border border-slate-800">
                    <p>Click any incident pin or worker icon on the map to inspect telemetry, assigned personnel, and trigger overrides.</p>
                    <button
                      onClick={() => setInspectorMode('operations')}
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow"
                    >
                      View Live Operations Stream
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: INCIDENTS TABLE & SEARCH */}
      {activeTab === 'incidents' && (
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search by ID, keyword, address..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              >
                <option value="">All Statuses</option>
                <option value="REPORTED">Reported</option>
                <option value="ASSIGNED">Assigned</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="RESOLVED_PENDING_VERIFICATION">Pending Verification</option>
                <option value="RESOLVED">Resolved</option>
              </select>

              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              >
                <option value="">All Priorities</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 font-semibold">
                  <th className="px-4 py-3">Incident Number</th>
                  <th className="px-4 py-3">Title & Location</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Reported Time</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredIncidents.map((inc) => (
                  <tr key={inc.id} className="hover:bg-slate-750 transition-colors">
                    <td className="px-4 py-3 font-mono font-bold text-blue-400">
                      {inc.incident_number}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-white">{inc.title}</p>
                      <p className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3" /> {inc.address}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-300 font-sans">
                      {inc.category}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                          inc.priority === 'CRITICAL'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : inc.priority === 'HIGH'
                            ? 'bg-orange-500/20 text-orange-300'
                            : inc.priority === 'MEDIUM'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-blue-500/20 text-blue-300'
                        }`}
                      >
                        {inc.priority}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-[11px] text-slate-200">
                        {inc.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 font-mono text-[11px]">
                      {new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => setAssignWorkerModal(inc)}
                        className="px-2.5 py-1 rounded bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 text-[11px] font-semibold transition-colors"
                      >
                        Dispatch
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: HUMAN APPROVAL QUEUE */}
      {activeTab === 'approvals' && (
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-700 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <AlertOctagon className="w-5 h-5 text-rose-400" />
                <span>Human Approval Queue (Autonomous Agent Escalations)</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Multi-agent system requires explicit human sign-off for critical risks and uncertain completions.
              </p>
            </div>
            <button
              onClick={loadData}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-semibold"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
          </div>

          {approvals.length === 0 ? (
            <div className="p-10 text-center text-slate-400 text-xs bg-slate-900/40 rounded-xl border border-slate-800">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-80" />
              All autonomous workflows cleared! No sensitive approvals pending currently.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {approvals.map((appr) => (
                <div
                  key={appr.id}
                  className="bg-slate-900/90 border border-rose-500/30 rounded-xl p-5 shadow-lg space-y-3"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-bold text-rose-400">
                      {appr.approval_type}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      Requested by: {appr.requested_by_agent}
                    </span>
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-white">
                      {appr.incident_title || `Incident #${appr.incident_id.slice(0, 8)}`}
                    </h4>
                    <p className="text-xs text-slate-300 mt-1 italic bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                      "{appr.reason}"
                    </p>
                  </div>

                  <div className="space-y-2 pt-2">
                    <input
                      type="text"
                      placeholder="Add reviewer notes (optional)..."
                      value={processingApprovalId === appr.id ? reviewNotes : ''}
                      onChange={(e) => {
                        setProcessingApprovalId(appr.id);
                        setReviewNotes(e.target.value);
                      }}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
                    />

                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(appr.id)}
                        disabled={processingApprovalId === appr.id}
                        className="flex-1 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow"
                      >
                        <Check className="w-4 h-4" /> Grant Approval & Dispatch
                      </button>
                      <button
                        onClick={() => handleReject(appr.id)}
                        disabled={processingApprovalId === appr.id}
                        className="py-2 px-4 rounded-xl bg-rose-900/60 hover:bg-rose-800 text-rose-200 font-semibold text-xs border border-rose-700/60"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: FIELD CREW ROSTER */}
      {activeTab === 'workers' && (
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-700 pb-3 gap-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <HardHat className="w-5 h-5 text-amber-400" />
                <span>Municipal Field Workforce Directory</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                On-duty status, real-time Pune GPS coordinates and task workload telemetry.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setNewUserForm({
                    role: 'WORKER',
                    full_name: '',
                    email: '',
                    phone: '',
                    password: '',
                    department_id: departmentsList[0]?.id || '',
                    employee_id: `PUMC-RD-${Math.floor(100 + Math.random() * 900)}`,
                    skills: 'Road repairs, asphalt compaction, water pipe welding',
                    preferred_language: 'mr',
                  });
                  setShowCreateUserModal(true);
                }}
                className="px-3.5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-emerald-600/20 transition-all flex items-center gap-1.5"
              >
                <UserPlus className="w-4 h-4" />
                <span>+ Create Field Crew Account</span>
              </button>
              <button
                onClick={loadData}
                className="text-xs text-slate-300 hover:text-white flex items-center gap-1 font-semibold px-3 py-2 bg-slate-900 rounded-xl border border-slate-700"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Refresh Roster
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {workers.map((w) => (
              <div
                key={w.id}
                className="bg-slate-900/90 border border-slate-700/70 rounded-xl p-4 shadow space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white text-sm">{w.full_name}</span>
                  <span
                    className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                      w.availability_status === 'AVAILABLE'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-slate-700 text-slate-400'
                    }`}
                  >
                    {w.availability_status}
                  </span>
                </div>
                <p className="text-xs text-blue-400 font-medium">
                  {w.department_name || 'Municipal Field Operations'}
                </p>
                <p className="text-[11px] text-slate-400">{w.skills}</p>
                <div className="flex items-center justify-between text-[11px] pt-2 border-t border-slate-800 text-slate-400 font-mono">
                  <span>ID: {w.employee_id}</span>
                  <span>Active Tasks: {w.current_active_tasks}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Department Management Capacity Cards */}
          {stats?.departments && stats.departments.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-slate-700/60">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-blue-400" />
                <span>Municipal Departments & Workforce Capacity</span>
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {stats.departments.map((dept) => (
                  <div key={dept.department_id} className="p-3 bg-slate-900/90 rounded-xl border border-slate-700/60 space-y-1">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-900/60 text-blue-300 border border-blue-700/60">
                      {dept.department_code}
                    </span>
                    <p className="font-semibold text-xs text-white truncate mt-1">{dept.department_name}</p>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                      <span>On-Duty: <strong className="text-emerald-400">{dept.active_workers}</strong></span>
                      <span>Active: <strong className="text-amber-400">{dept.active_incidents}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: ANALYTICS & SLA CHARTS */}
      {activeTab === 'analytics' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-3">
            <h3 className="text-sm font-bold text-white">Department Incident Resolution Load</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={deptChartData}>
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: 8, fontSize: 12 }}
                  />
                  <Bar dataKey="total" fill="#3b82f6" name="Total Incidents" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="resolved" fill="#10b981" name="Resolved" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-3">
            <h3 className="text-sm font-bold text-white">Priority Distribution</h3>
            <div className="h-64 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={priorityChartData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label
                  >
                    {priorityChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: 8, fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: USER MANAGEMENT & ROLE ADMINISTRATION */}
      {activeTab === 'users' && (
        <div className="space-y-6">
          {/* Action alerts */}
          {userActionSuccess && (
            <div className="p-3 bg-emerald-950/60 border border-emerald-500/40 rounded-xl text-xs text-emerald-300 flex items-center justify-between">
              <span>{userActionSuccess}</span>
              <button onClick={() => setUserActionSuccess(null)} className="text-emerald-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
          {userActionError && (
            <div className="p-3 bg-rose-950/60 border border-rose-500/40 rounded-xl text-xs text-rose-300 flex items-center justify-between">
              <span>{userActionError}</span>
              <button onClick={() => setUserActionError(null)} className="text-rose-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* User Metrics Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div
              onClick={() => setUserRoleFilter('ALL')}
              className={`p-3.5 rounded-xl border shadow cursor-pointer transition-all ${
                userRoleFilter === 'ALL'
                  ? 'bg-blue-950/40 border-blue-500/60 ring-2 ring-blue-500/30'
                  : 'bg-slate-800/80 border-slate-700/80 hover:bg-slate-800'
              }`}
            >
              <span className="text-[11px] text-slate-400 font-medium">Total Registered</span>
              <div className="text-xl font-bold text-white mt-0.5">
                {managedUsers.filter((u) => u.role !== 'ADMIN').length}
              </div>
              <span className="text-[10px] text-blue-400">Citizens & Field Crew →</span>
            </div>
            <div
              onClick={() => setUserRoleFilter('CITIZEN')}
              className={`p-3.5 rounded-xl border shadow cursor-pointer transition-all ${
                userRoleFilter === 'CITIZEN'
                  ? 'bg-amber-950/40 border-amber-500/60 ring-2 ring-amber-500/30'
                  : 'bg-slate-800/80 border-slate-700/80 hover:bg-slate-800'
              }`}
            >
              <span className="text-[11px] text-amber-400 font-medium flex items-center gap-1">
                <Users className="w-3.5 h-3.5" /> Registered Citizens
              </span>
              <div className="text-xl font-bold text-white mt-0.5">
                {managedUsers.filter((u) => u.role === 'CITIZEN').length}
              </div>
              <span className="text-[10px] text-amber-300">Click to view citizens →</span>
            </div>
            <div
              onClick={() => setUserRoleFilter('WORKER')}
              className={`p-3.5 rounded-xl border shadow cursor-pointer transition-all ${
                userRoleFilter === 'WORKER'
                  ? 'bg-emerald-950/40 border-emerald-500/60 ring-2 ring-emerald-500/30'
                  : 'bg-slate-800/80 border-slate-700/80 hover:bg-slate-800'
              }`}
            >
              <span className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                <HardHat className="w-3.5 h-3.5" /> Field Crew
              </span>
              <div className="text-xl font-bold text-white mt-0.5">
                {managedUsers.filter((u) => u.role === 'WORKER').length}
              </div>
              <span className="text-[10px] text-emerald-300">Click to view crew →</span>
            </div>
            <div
              onClick={() => setUserStatusFilter(userStatusFilter === 'ACTIVE' ? 'ALL' : 'ACTIVE')}
              className={`p-3.5 rounded-xl border shadow cursor-pointer transition-all ${
                userStatusFilter === 'ACTIVE'
                  ? 'bg-indigo-950/40 border-indigo-500/60 ring-2 ring-indigo-500/30'
                  : 'bg-slate-800/80 border-slate-700/80 hover:bg-slate-800'
              }`}
            >
              <span className="text-[11px] text-indigo-400 font-medium">Active Accounts</span>
              <div className="text-xl font-bold text-white mt-0.5">
                {managedUsers.filter((u) => u.role !== 'ADMIN' && u.is_active).length}
              </div>
              <span className="text-[10px] text-slate-400">Authorized status</span>
            </div>
          </div>

          {/* User Controls: Search, Filters, and Provision Button */}
          <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Users className="w-5 h-5 text-blue-400" />
                  <span>Platform User Management & Access Control</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Administer registered citizens, create municipal field crew accounts, assign departments, and maintain security.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => {
                    setNewUserForm({
                      role: 'WORKER',
                      full_name: '',
                      email: '',
                      phone: '',
                      password: '',
                      department_id: departmentsList[0]?.id || '',
                      employee_id: `PUMC-RD-${Math.floor(100 + Math.random() * 900)}`,
                      skills: 'Road repairs, asphalt compaction, water pipe welding',
                      preferred_language: 'mr',
                    });
                    setShowCreateUserModal(true);
                  }}
                  className="px-3.5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-emerald-600/20 transition-all flex items-center gap-1.5"
                >
                  <UserPlus className="w-4 h-4" />
                  <span>Provision User / Field Crew</span>
                </button>
              </div>
            </div>

            {/* Filters Row */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2 border-t border-slate-700/60">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search registered citizens or workers by name, email, phone or ID..."
                  value={userSearchTerm}
                  onChange={(e) => setUserSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Role filter pills (Citizens & Field Crew only) */}
              <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-700 text-xs font-medium">
                {(['ALL', 'CITIZEN', 'WORKER'] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setUserRoleFilter(r)}
                    className={`px-3 py-1 rounded-lg transition-all ${
                      userRoleFilter === r
                        ? 'bg-blue-600 text-white font-bold shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {r === 'ALL'
                      ? `All (${managedUsers.filter((u) => u.role !== 'ADMIN').length})`
                      : r === 'CITIZEN'
                      ? `👤 Citizens (${managedUsers.filter((u) => u.role === 'CITIZEN').length})`
                      : `👷 Field Crew (${managedUsers.filter((u) => u.role === 'WORKER').length})`}
                  </button>
                ))}
              </div>

              {/* Status filter */}
              <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-700 text-xs font-medium">
                {(['ALL', 'ACTIVE', 'INACTIVE'] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setUserStatusFilter(s)}
                    className={`px-2.5 py-1 rounded-lg transition-all ${
                      userStatusFilter === s
                        ? 'bg-indigo-600 text-white font-bold'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {s === 'ALL' ? 'All' : s === 'ACTIVE' ? 'Active' : 'Inactive'}
                  </button>
                ))}
              </div>
            </div>

            {/* Users Table */}
            <div className="overflow-x-auto rounded-xl border border-slate-700/60">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-700/80 bg-slate-900/60 text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
                    <th className="px-4 py-3">User Details</th>
                    <th className="px-4 py-3">System Role</th>
                    <th className="px-4 py-3">Department / Employee ID</th>
                    <th className="px-4 py-3">Phone</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Registered</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {managedUsers
                    .filter((u) => {
                      // EXCLUDE ADMINS: The user section is strictly for managing Citizens and Field Crew
                      if (u.role === 'ADMIN') return false;

                      const matchesSearch =
                        !userSearchTerm ||
                        u.full_name?.toLowerCase().includes(userSearchTerm.toLowerCase()) ||
                        u.email?.toLowerCase().includes(userSearchTerm.toLowerCase()) ||
                        u.phone?.includes(userSearchTerm) ||
                        u.employee_id?.toLowerCase().includes(userSearchTerm.toLowerCase());
                      const matchesRole = userRoleFilter === 'ALL' || u.role === userRoleFilter;
                      const matchesStatus =
                        userStatusFilter === 'ALL' ||
                        (userStatusFilter === 'ACTIVE' && u.is_active) ||
                        (userStatusFilter === 'INACTIVE' && !u.is_active);
                      return matchesSearch && matchesRole && matchesStatus;
                    })
                    .map((u) => (
                      <tr key={u.id} className="hover:bg-slate-750/30 transition-colors">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2.5">
                            <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-white font-bold text-xs ${
                              u.role === 'ADMIN'
                                ? 'bg-blue-600'
                                : u.role === 'WORKER'
                                ? 'bg-emerald-600'
                                : 'bg-amber-600'
                            }`}>
                              {u.full_name ? u.full_name[0].toUpperCase() : u.role[0]}
                            </div>
                            <div>
                              <p className="font-semibold text-white">{u.full_name}</p>
                              <p className="text-[11px] text-slate-400 font-mono">{u.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex px-2 py-0.5 rounded-full font-mono text-[10px] font-bold ${
                            u.role === 'ADMIN'
                              ? 'bg-blue-950 border border-blue-800 text-blue-300'
                              : u.role === 'WORKER'
                              ? 'bg-emerald-950 border border-emerald-800 text-emerald-300'
                              : 'bg-amber-950 border border-amber-800 text-amber-300'
                          }`}>
                            {u.role === 'WORKER' ? 'FIELD CREW' : u.role}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {u.role === 'WORKER' ? (
                            <div>
                              <span className="font-medium text-slate-200">
                                {u.department_name || 'Field Operations'}
                              </span>
                              <span className="block text-[10px] text-slate-500 font-mono">
                                {u.employee_id || 'ID Pending'}
                              </span>
                            </div>
                          ) : (
                            <span className="text-slate-500 italic">Not applicable</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-slate-300 font-mono text-[11px]">
                          {u.phone || '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            u.is_active
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                          }`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                            {u.is_active ? 'Active' : 'Deactivated'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-400 font-mono text-[11px]">
                          {new Date(u.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => setEditingUser(u)}
                              title="Edit user attributes"
                              className="p-1.5 rounded-lg bg-slate-700/60 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                            >
                              <Edit className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => setResetPasswordUser(u)}
                              title="Reset user password"
                              className="p-1.5 rounded-lg bg-indigo-900/40 hover:bg-indigo-900/70 border border-indigo-700/50 text-indigo-300 transition-colors"
                            >
                              <KeyRound className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleToggleUserStatus(u)}
                              title={u.is_active ? 'Deactivate account' : 'Activate account'}
                              className={`p-1.5 rounded-lg border transition-colors ${
                                u.is_active
                                  ? 'bg-rose-950/40 hover:bg-rose-900/60 border-rose-800/50 text-rose-300'
                                  : 'bg-emerald-950/40 hover:bg-emerald-900/60 border-emerald-800/50 text-emerald-300'
                              }`}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create User / Field Crew */}
      {showCreateUserModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <HardHat className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-white">Provision Field Crew Account</h3>
              </div>
              <button onClick={() => setShowCreateUserModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-3.5 text-xs">
              <div className="p-3 bg-emerald-950/40 border border-emerald-500/30 rounded-xl flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-300 flex items-center gap-2">
                  <HardHat className="w-4 h-4 text-emerald-400" />
                  <span>Account Role: Municipal Field Crew Responder</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-900/60 text-emerald-300 border border-emerald-700/60 font-bold">
                  WORKER
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={newUserForm.full_name}
                    onChange={(e) => setNewUserForm({ ...newUserForm, full_name: e.target.value, role: 'WORKER' })}
                    placeholder="Suresh Kadam"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Email Address</label>
                  <input
                    type="email"
                    required
                    value={newUserForm.email}
                    onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value, role: 'WORKER' })}
                    placeholder="suresh@resolvegrid.gov.in"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Phone Number</label>
                  <input
                    type="tel"
                    value={newUserForm.phone}
                    onChange={(e) => setNewUserForm({ ...newUserForm, phone: e.target.value, role: 'WORKER' })}
                    placeholder="+91 98220 00000"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Initial Password</label>
                  <input
                    type="password"
                    required
                    minLength={6}
                    value={newUserForm.password}
                    onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value, role: 'WORKER' })}
                    placeholder="Min 6 characters"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800 space-y-3">
                <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block">
                  Field Crew Department & Qualifications
                </span>
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Assigned Department *</label>
                  <select
                    required
                    value={newUserForm.department_id}
                    onChange={(e) => setNewUserForm({ ...newUserForm, department_id: e.target.value, role: 'WORKER' })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-slate-100 focus:outline-none"
                  >
                    <option value="">-- Select Municipal Department --</option>
                    {departmentsList.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.code})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Employee ID (Optional)</label>
                    <input
                      type="text"
                      value={newUserForm.employee_id}
                      onChange={(e) => setNewUserForm({ ...newUserForm, employee_id: e.target.value, role: 'WORKER' })}
                      placeholder="EMP-RD-105"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-slate-100 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Skills & Certifications</label>
                    <input
                      type="text"
                      value={newUserForm.skills}
                      onChange={(e) => setNewUserForm({ ...newUserForm, skills: e.target.value, role: 'WORKER' })}
                      placeholder="Road repairs, Asphalt compaction"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-slate-100 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCreateUserModal(false)}
                  className="px-4 py-2 rounded-xl font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-semibold shadow"
                >
                  Create Field Crew Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit User */}
      {editingUser && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Edit className="w-5 h-5 text-blue-400" />
                <h3 className="text-base font-bold text-white">Edit User Information</h3>
              </div>
              <button onClick={() => setEditingUser(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateUser} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-300 mb-1">Email (Immutable)</label>
                <input
                  type="text"
                  disabled
                  value={editingUser.email}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-500 font-mono cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={editingUser.full_name}
                  onChange={(e) => setEditingUser({ ...editingUser, full_name: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">Phone Number</label>
                <input
                  type="tel"
                  value={editingUser.phone || ''}
                  onChange={(e) => setEditingUser({ ...editingUser, phone: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>

              {editingUser.role === 'WORKER' && (
                <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800 space-y-3">
                  <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block">
                    Field Crew Assignment
                  </span>
                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Assigned Department</label>
                    <select
                      value={editingUser.department_id || ''}
                      onChange={(e) => setEditingUser({ ...editingUser, department_id: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-slate-100 focus:outline-none"
                    >
                      <option value="">-- Choose Department --</option>
                      {departmentsList.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.code})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Specialist Skills</label>
                    <input
                      type="text"
                      value={editingUser.skills || ''}
                      onChange={(e) => setEditingUser({ ...editingUser, skills: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-slate-100 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEditingUser(null)}
                  className="px-4 py-2 rounded-xl font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold shadow"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Reset Password */}
      {resetPasswordUser && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-bold text-white">Reset User Password</h3>
              </div>
              <button onClick={() => setResetPasswordUser(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-300">
              Setting new credentials for <strong className="text-white">{resetPasswordUser.email}</strong>
            </p>

            <form onSubmit={handleResetPassword} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-300 mb-1">New Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={newPasswordVal}
                  onChange={(e) => setNewPasswordVal(e.target.value)}
                  placeholder="Minimum 6 characters"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setResetPasswordUser(null)}
                  className="px-4 py-2 rounded-xl font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-semibold shadow"
                >
                  Reset Password
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Assign Worker Modal */}
      {assignWorkerModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white">Dispatch Field Crew</h3>
              <button
                onClick={() => setAssignWorkerModal(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-300">
              Assigning field squad to: <strong className="text-white">{assignWorkerModal.title}</strong>
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">
                Select Available Worker
              </label>
              <select
                value={selectedWorkerId}
                onChange={(e) => setSelectedWorkerId(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              >
                <option value="">-- Choose on-duty field personnel --</option>
                {workers.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.full_name} ({w.department_name || 'Ops'}) - Active Tasks: {w.current_active_tasks}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setAssignWorkerModal(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleManualAssign}
                disabled={!selectedWorkerId}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 shadow"
              >
                Confirm Dispatch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
