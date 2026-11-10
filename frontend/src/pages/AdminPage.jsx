import React, { useState, useEffect } from 'react';
import { api } from '../api';
import {
  Users,
  Shield,
  Key,
  Activity,
  UserPlus,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCw,
} from 'lucide-react';

export default function AdminPage() {
  const [activeSubTab, setActiveSubTab] = useState('members');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // 1. Members State
  const [members, setMembers] = useState([]);
  const [newMemberEmail, setNewMemberEmail] = useState('');
  const [newMemberPassword, setNewMemberPassword] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('member');

  // 2. Teams State
  const [teams, setTeams] = useState([]);
  const [newTeamName, setNewTeamName] = useState('');
  const [selectedTeamId, setSelectedTeamId] = useState('');
  const [selectedUserId, setSelectedUserId] = useState('');

  // 3. API Keys State
  const [apiKeys, setApiKeys] = useState([]);
  const [newRawKey, setNewRawKey] = useState(null);
  const [copied, setCopied] = useState(false);

  // 4. Usage State
  const [usage, setUsage] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [membersData, teamsData, keysData, usageData] = await Promise.all([
        api.listMembers().catch(() => []),
        api.listTeams().catch(() => []),
        api.listApiKeys().catch(() => []),
        api.getUsage().catch(() => null),
      ]);
      setMembers(membersData);
      setTeams(teamsData);
      setApiKeys(keysData);
      setUsage(usageData);
    } catch (err) {
      setError(err.message || 'Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  // Handlers
  const handleInviteMember = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      await api.inviteMember({
        email: newMemberEmail.trim(),
        password: newMemberPassword,
        role: newMemberRole,
      });
      setSuccess(`Member ${newMemberEmail} added successfully.`);
      setNewMemberEmail('');
      setNewMemberPassword('');
      const updated = await api.listMembers();
      setMembers(updated);
    } catch (err) {
      setError(err.message || 'Failed to add member');
    }
  };

  const handleCreateTeam = async (e) => {
    e.preventDefault();
    if (!newTeamName.trim()) return;
    setError('');
    setSuccess('');
    try {
      await api.createTeam({ name: newTeamName.trim() });
      setSuccess(`Team "${newTeamName.trim()}" created successfully.`);
      setNewTeamName('');
      const updated = await api.listTeams();
      setTeams(updated);
    } catch (err) {
      setError(err.message || 'Failed to create team');
    }
  };

  const handleAddTeamMember = async (e) => {
    e.preventDefault();
    if (!selectedTeamId || !selectedUserId) return;
    setError('');
    setSuccess('');
    try {
      await api.addTeamMember(selectedTeamId, selectedUserId);
      setSuccess('User added to team successfully.');
      setSelectedUserId('');
    } catch (err) {
      setError(err.message || 'Failed to add team member');
    }
  };

  const handleCreateApiKey = async () => {
    setError('');
    setSuccess('');
    try {
      const res = await api.createApiKey();
      setNewRawKey(res.api_key);
      const updated = await api.listApiKeys();
      setApiKeys(updated);
    } catch (err) {
      setError(err.message || 'Failed to create API key');
    }
  };

  const handleRevokeApiKey = async (keyId) => {
    if (!window.confirm('Are you sure you want to revoke this API key?')) return;
    try {
      await api.revokeApiKey(keyId);
      setSuccess('API key revoked.');
      const updated = await api.listApiKeys();
      setApiKeys(updated);
    } catch (err) {
      setError(err.message || 'Failed to revoke API key');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <Shield className="h-6 w-6 text-indigo-600" />
            <span>Admin Center</span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage organization members, team access boundaries, API keys, and token usage controls.
          </p>
        </div>
        <button
          onClick={loadAll}
          disabled={loading}
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 shadow-sm"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="flex items-center space-x-2 p-4 text-sm rounded-xl bg-red-50 text-red-700 border border-red-200">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="flex items-center space-x-2 p-4 text-sm rounded-xl bg-green-50 text-green-700 border border-green-200">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* Sub Tabs */}
      <div className="flex border-b border-gray-200 space-x-4">
        {[
          { id: 'members', label: 'Members', icon: Users },
          { id: 'teams', label: 'Teams', icon: Shield },
          { id: 'apikeys', label: 'API Keys', icon: Key },
          { id: 'usage', label: 'Usage & Tokens', icon: Activity },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              className={`flex items-center space-x-2 py-3 px-2 border-b-2 font-medium text-sm transition-colors ${
                activeSubTab === tab.id
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: MEMBERS */}
      {activeSubTab === 'members' && (
        <div className="space-y-6">
          {/* Add member form */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-base font-semibold text-gray-900 mb-4 flex items-center space-x-2">
              <UserPlus className="h-4 w-4 text-indigo-600" />
              <span>Invite New Member</span>
            </h3>
            <form onSubmit={handleInviteMember} className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  required
                  placeholder="colleague@company.com"
                  value={newMemberEmail}
                  onChange={(e) => setNewMemberEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                  Temporary Password
                </label>
                <input
                  type="password"
                  required
                  placeholder="Min 6 chars"
                  value={newMemberPassword}
                  onChange={(e) => setNewMemberPassword(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">Role</label>
                <select
                  value={newMemberRole}
                  onChange={(e) => setNewMemberRole(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div className="sm:col-span-4 flex justify-end">
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Add Member
                </button>
              </div>
            </form>
          </div>

          {/* Members list */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 font-semibold text-gray-900 text-sm">
              Organization Members ({members.length})
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Email</th>
                    <th className="px-6 py-3">Role</th>
                    <th className="px-6 py-3">User ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {members.map((m) => (
                    <tr key={m.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-medium text-gray-900">{m.email}</td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded text-xs font-semibold uppercase ${
                            m.role === 'admin'
                              ? 'bg-purple-100 text-purple-800'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {m.role}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-gray-400">{m.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: TEAMS */}
      {activeSubTab === 'teams' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Create team */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-base font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                <Plus className="h-4 w-4 text-indigo-600" />
                <span>Create New Team</span>
              </h3>
              <form onSubmit={handleCreateTeam} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                    Team Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Engineering, Sales, DevOps"
                    value={newTeamName}
                    onChange={(e) => setNewTeamName(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Create Team
                </button>
              </form>
            </div>

            {/* Add member to team */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-base font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                <Users className="h-4 w-4 text-indigo-600" />
                <span>Add Member to Team</span>
              </h3>
              <form onSubmit={handleAddTeamMember} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                    Select Team
                  </label>
                  <select
                    value={selectedTeamId}
                    onChange={(e) => setSelectedTeamId(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="">-- Choose Team --</option>
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                    Select Member
                  </label>
                  <select
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="">-- Choose Member --</option>
                    {members.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.email} ({m.role})
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Assign to Team
                </button>
              </form>
            </div>
          </div>

          {/* Teams List */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 font-semibold text-gray-900 text-sm">
              Existing Teams ({teams.length})
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Team Name</th>
                    <th className="px-6 py-3">Team ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {teams.map((t) => (
                    <tr key={t.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-semibold text-gray-900">{t.name}</td>
                      <td className="px-6 py-4 font-mono text-xs text-gray-400">{t.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: API KEYS */}
      {activeSubTab === 'apikeys' && (
        <div className="space-y-6">
          {/* Create key banner */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h3 className="text-base font-semibold text-gray-900">Manage API Keys</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                API keys authenticate automated /query calls using X-API-Key header.
              </p>
            </div>
            <button
              onClick={handleCreateApiKey}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center space-x-1.5 shadow-sm"
            >
              <Plus className="h-4 w-4" />
              <span>Create New Key</span>
            </button>
          </div>

          {/* New Key Display Box (Shown Once) */}
          {newRawKey && (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wide text-amber-800">
                  Copy API Key Now (Shown Only Once)
                </span>
                <button
                  onClick={() => setNewRawKey(null)}
                  className="text-xs text-amber-700 hover:text-amber-900 underline"
                >
                  Dismiss
                </button>
              </div>
              <div className="flex items-center space-x-2 bg-white p-2.5 rounded-lg border border-amber-200 font-mono text-xs break-all">
                <span className="flex-1 select-all">{newRawKey}</span>
                <button
                  onClick={() => copyToClipboard(newRawKey)}
                  className="p-1.5 rounded hover:bg-amber-100 text-amber-800 flex items-center space-x-1"
                >
                  {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>
          )}

          {/* Keys list */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 font-semibold text-gray-900 text-sm">
              Active & Revoked API Keys ({apiKeys.length})
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Prefix</th>
                    <th className="px-6 py-3">Created</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {apiKeys.map((k) => (
                    <tr key={k.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-mono font-medium text-gray-900">
                        {k.prefix}...
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-500">
                        {new Date(k.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4">
                        {k.revoked_at ? (
                          <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">
                            Revoked
                          </span>
                        ) : (
                          <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {!k.revoked_at && (
                          <button
                            onClick={() => handleRevokeApiKey(k.id)}
                            className="text-gray-400 hover:text-red-600 p-1 rounded hover:bg-red-50"
                            title="Revoke Key"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: USAGE & TOKENS */}
      {activeSubTab === 'usage' && (
        <div className="space-y-6">
          {usage ? (
            <>
              {/* Stat Cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
                  <span className="text-xs font-semibold text-gray-500 uppercase">Total Queries</span>
                  <div className="text-2xl font-bold text-gray-900 mt-1 font-mono">
                    {usage.total_queries}
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
                  <span className="text-xs font-semibold text-gray-500 uppercase">Total Tokens</span>
                  <div className="text-2xl font-bold text-indigo-600 mt-1 font-mono">
                    {usage.total_tokens?.toLocaleString() || 0}
                  </div>
                  <div className="text-[10px] text-gray-400 mt-1 font-mono">
                    {usage.total_prompt_tokens?.toLocaleString()} in / {usage.total_completion_tokens?.toLocaleString()} out
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
                  <span className="text-xs font-semibold text-gray-500 uppercase">Avg / p95 Latency</span>
                  <div className="text-2xl font-bold text-gray-900 mt-1 font-mono">
                    {usage.avg_latency_ms?.toFixed(0)} ms
                  </div>
                  <div className="text-[10px] text-gray-400 mt-1 font-mono">
                    p95: {usage.p95_latency_ms?.toFixed(0)} ms
                  </div>
                </div>

                <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
                  <span className="text-xs font-semibold text-gray-500 uppercase">Cache Hit Rate</span>
                  <div className="text-2xl font-bold text-emerald-600 mt-1 font-mono">
                    {(usage.cache_hit_rate * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Per-User Usage Breakdown */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200 font-semibold text-gray-900 text-sm">
                  Per-User Usage Breakdown
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm text-gray-600">
                    <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500">
                      <tr>
                        <th className="px-6 py-3">User</th>
                        <th className="px-6 py-3">Queries</th>
                        <th className="px-6 py-3">Prompt Tokens</th>
                        <th className="px-6 py-3">Completion Tokens</th>
                        <th className="px-6 py-3">Total Tokens</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {usage.per_user_usage?.map((u) => (
                        <tr key={u.user_id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 font-medium text-gray-900">{u.email}</td>
                          <td className="px-6 py-4 font-mono">{u.query_count}</td>
                          <td className="px-6 py-4 font-mono text-gray-500">{u.prompt_tokens.toLocaleString()}</td>
                          <td className="px-6 py-4 font-mono text-gray-500">{u.completion_tokens.toLocaleString()}</td>
                          <td className="px-6 py-4 font-mono font-semibold text-indigo-600">
                            {u.total_tokens.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-gray-400 bg-white rounded-2xl border border-gray-200">
              <Activity className="h-8 w-8 mx-auto text-gray-300 mb-2" />
              <p className="text-sm">No usage data logged yet</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
