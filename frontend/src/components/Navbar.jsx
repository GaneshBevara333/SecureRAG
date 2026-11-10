import React from 'react';
import { Shield, FileText, MessageSquare, BarChart3, Settings, LogOut } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, user, onLogout }) {
  const isAdmin = user?.role === 'admin';

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo and Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('chat')}>
            <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-sm">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <span className="text-xl font-bold text-gray-900 tracking-tight">SecureRAG</span>
              <span className="hidden sm:inline-block ml-2 text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
                Phase 8
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex space-x-1 sm:space-x-2">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center space-x-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'chat'
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              <MessageSquare className="h-4 w-4" />
              <span>Chat</span>
            </button>

            <button
              onClick={() => setActiveTab('documents')}
              className={`flex items-center space-x-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'documents'
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              <FileText className="h-4 w-4" />
              <span>Documents</span>
            </button>

            <button
              onClick={() => setActiveTab('metrics')}
              className={`flex items-center space-x-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'metrics'
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              <BarChart3 className="h-4 w-4" />
              <span>Metrics</span>
            </button>

            {isAdmin && (
              <button
                onClick={() => setActiveTab('admin')}
                className={`flex items-center space-x-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'admin'
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Settings className="h-4 w-4" />
                <span>Admin</span>
              </button>
            )}
          </nav>

          {/* User profile & Logout */}
          <div className="flex items-center space-x-3">
            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold text-gray-900">{user?.email}</div>
              <div className="flex items-center justify-end space-x-1 mt-0.5">
                <span className={`inline-block text-[10px] font-semibold uppercase px-1.5 py-0.2 rounded ${
                  isAdmin ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-700'
                }`}>
                  {user?.role}
                </span>
              </div>
            </div>

            <button
              onClick={onLogout}
              title="Log out"
              className="p-2 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
