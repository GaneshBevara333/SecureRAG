import React, { useState } from 'react';
import { api, setToken, setUser } from '../api';
import { Shield, Lock, Mail, Building, ArrowRight, Loader2 } from 'lucide-react';

export default function AuthPage({ onAuthSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [formData, setFormData] = useState({
    org_name: '',
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        if (!formData.org_name.trim()) {
          throw new Error('Organization name is required');
        }
        const data = await api.register({
          org_name: formData.org_name.trim(),
          email: formData.email.trim(),
          password: formData.password,
        });
        setToken(data.access_token);
        setUser(data.user);
        onAuthSuccess(data.user);
      } else {
        const data = await api.login({
          email: formData.email.trim(),
          password: formData.password,
        });
        setToken(data.access_token);
        setUser(data.user);
        onAuthSuccess(data.user);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-gray-100 to-indigo-50 p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden">
        {/* Header Banner */}
        <div className="bg-indigo-600 p-8 text-white text-center">
          <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-white/10 backdrop-blur-md mb-3 border border-white/20 shadow-inner">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">SecureRAG</h1>
          <p className="text-indigo-100 text-sm mt-1">
            Multi-tenant RAG platform with retrieval-time access control
          </p>
        </div>

        {/* Toggle Mode */}
        <div className="flex border-b border-gray-200">
          <button
            type="button"
            onClick={() => { setIsRegister(false); setError(''); }}
            className={`flex-1 py-3 text-sm font-semibold transition-colors ${
              !isRegister
                ? 'text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/30'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setIsRegister(true); setError(''); }}
            className={`flex-1 py-3 text-sm font-semibold transition-colors ${
              isRegister
                ? 'text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/30'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Create Organization
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 sm:p-8 space-y-4">
          {error && (
            <div className="p-3 text-xs rounded-lg bg-red-50 text-red-700 border border-red-200">
              {error}
            </div>
          )}

          {isRegister && (
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                Organization Name
              </label>
              <div className="relative">
                <Building className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  required
                  placeholder="Acme Corp"
                  value={formData.org_name}
                  onChange={(e) => setFormData({ ...formData, org_name: e.target.value })}
                  className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
              Work Email
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                type="email"
                required
                placeholder="alice@company.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                type="password"
                required
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 flex items-center justify-center space-x-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-sm transition-colors shadow-sm disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <span>{isRegister ? 'Register Organization & Admin' : 'Sign In'}</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>

          <p className="text-center text-xs text-gray-500 pt-2">
            Retrieval-time ACLs & security boundaries enforced per tenant.
          </p>
        </form>
      </div>
    </div>
  );
}
