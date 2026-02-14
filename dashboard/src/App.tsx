import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/store';
import { useWebSocket } from '@/hooks/useWebSocket';

// Pages
import LoginPage from '@/pages/Login';
import DashboardPage from '@/pages/Dashboard';
import ShipmentsPage from '@/pages/Shipments';
import RevenuePage from '@/pages/Revenue';
import AgentsPage from '@/pages/Agents';
import SettingsPage from '@/pages/Settings';

// Components
import { ToastContainer } from '@/components/ui/ToastContainer';
import { ModalContainer } from '@/components/ui/ModalContainer';

// ============================================
// PROTECTED ROUTE COMPONENT
// ============================================

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuthStore();
  
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          <p className="text-text-secondary font-mono text-sm">CARICAMENTO...</p>
        </div>
      </div>
    );
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

// ============================================
// WEBSOCKET WRAPPER
// ============================================

const WebSocketWrapper = ({ children }: { children: React.ReactNode }) => {
  useWebSocket();
  return <>{children}</>;
};

// ============================================
// MAIN APP
// ============================================

function App() {
  return (
    <Router>
      <AnimatePresence mode="wait">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <WebSocketWrapper>
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/shipments" element={<ShipmentsPage />} />
                    <Route path="/revenue" element={<RevenuePage />} />
                    <Route path="/agents" element={<AgentsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                  </Routes>
                </WebSocketWrapper>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AnimatePresence>
      
      <ToastContainer />
      <ModalContainer />
    </Router>
  );
}

export default App;