import React, { useState, useEffect } from 'react';
import { getToken, getUser, setToken, setUser } from './api';
import Navbar from './components/Navbar';
import AuthPage from './pages/AuthPage';
import DocumentsPage from './pages/DocumentsPage';
import ChatPage from './pages/ChatPage';
import MetricsPage from './pages/MetricsPage';
import AdminPage from './pages/AdminPage';

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState('chat');
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    const token = getToken();
    const u = getUser();
    if (token && u) {
      setCurrentUser(u);
    }
    setInitialized(true);
  }, []);

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    setActiveTab('chat');
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setCurrentUser(null);
    setActiveTab('chat');
  };

  if (!initialized) {
    return null;
  }

  if (!currentUser) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-gray-900">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={currentUser}
        onLogout={handleLogout}
      />

      <main className="flex-1">
        {activeTab === 'chat' && <ChatPage user={currentUser} />}
        {activeTab === 'documents' && <DocumentsPage user={currentUser} />}
        {activeTab === 'metrics' && <MetricsPage user={currentUser} />}
        {activeTab === 'admin' && currentUser?.role === 'admin' && <AdminPage user={currentUser} />}
      </main>
    </div>
  );
}
