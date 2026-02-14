import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  LayoutDashboard, 
  Package, 
  TrendingUp, 
  Bot, 
  Settings, 
  LogOut,
  Zap,
} from 'lucide-react';
import { useAuthStore, useUIStore } from '@/store';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/shipments', icon: Package, label: 'Spedizioni' },
  { path: '/revenue', icon: TrendingUp, label: 'Revenue' },
  { path: '/agents', icon: Bot, label: 'Agenti AI' },
  { path: '/settings', icon: Settings, label: 'Impostazioni' },
];

export const Sidebar = () => {
  const { user, logout } = useAuthStore();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarOpen ? 240 : 72 }}
      className="glass-panel border-r-0 border-t-0 border-b-0 h-screen sticky top-0 flex flex-col"
    >
      {/* Logo */}
      <div className="p-4 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-success flex items-center justify-center flex-shrink-0">
          <Zap className="w-5 h-5 text-background" />
        </div>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <h1 className="font-bold text-lg">Auto-Broker</h1>
            <p className="text-xs text-text-secondary">Mission Control</p>
          </motion.div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group ${
                isActive
                  ? 'bg-primary/20 text-primary border border-primary/30'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface'
              }`
            }
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {sidebarOpen && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="font-medium text-sm"
              >
                {item.label}
              </motion.span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User & Logout */}
      <div className="p-3 border-t border-border">
        {sidebarOpen && user && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="px-3 py-2 mb-2"
          >
            <p className="font-medium text-sm">{user.name}</p>
            <p className="text-xs text-text-secondary">{user.email}</p>
          </motion.div>
        )}
        
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-3 rounded-xl text-text-secondary hover:text-danger hover:bg-danger/10 transition-all duration-200"
        >
          <LogOut className="w-5 h-5 flex-shrink-0" />
          {sidebarOpen && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-medium text-sm"
            >
              Logout
            </motion.span>
          )}
        </button>
      </div>

      {/* Toggle Button */}
      <button
        onClick={toggleSidebar}
        className="absolute -right-3 top-20 w-6 h-6 rounded-full bg-surface border border-border flex items-center justify-center text-text-secondary hover:text-text-primary transition-colors"
      >
        <motion.span
          animate={{ rotate: sidebarOpen ? 0 : 180 }}
          className="text-xs"
        >
          ←
        </motion.span>
      </button>
    </motion.aside>
  );
};