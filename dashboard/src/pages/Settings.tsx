import { useState } from 'react';
import { User, Bell, Shield, Database, Zap, Save } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useAuthStore, useUIStore } from '@/store';

const SettingsPage = () => {
  const { user } = useAuthStore();
  const { addToast } = useUIStore();
  const [activeTab, setActiveTab] = useState<'profile' | 'notifications' | 'security' | 'system'>('profile');

  const handleSave = () => {
    addToast({
      type: 'success',
      title: 'Impostazioni salvate',
      message: 'Le modifiche sono state salvate con successo',
    });
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="px-6 py-4 border-b border-border">
          <h1 className="text-2xl font-bold">Impostazioni</h1>
          <p className="text-text-secondary text-sm">
            Gestisci le preferenze del sistema
          </p>
        </header>

        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-4xl mx-auto">
            <div className="grid grid-cols-12 gap-6">
              {/* Sidebar */}
              <div className="col-span-3">
                <nav className="space-y-1">
                  {[
                    { id: 'profile', label: 'Profilo', icon: User },
                    { id: 'notifications', label: 'Notifiche', icon: Bell },
                    { id: 'security', label: 'Sicurezza', icon: Shield },
                    { id: 'system', label: 'Sistema', icon: Database },
                  ].map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setActiveTab(item.id as typeof activeTab)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-colors ${
                        activeTab === item.id
                          ? 'bg-primary/20 text-primary border border-primary/30'
                          : 'text-text-secondary hover:text-text-primary hover:bg-surface'
                      }`}
                    >
                      <item.icon className="w-5 h-5" />
                      <span className="font-medium">{item.label}</span>
                    </button>
                  ))}
                </nav>
              </div>

              {/* Content */}
              <div className="col-span-9">
                <div className="glass-panel p-6">
                  {activeTab === 'profile' && (
                    <div className="space-y-6">
                      <h3 className="text-lg font-semibold">Profilo Utente</h3>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium mb-2">Nome</label>
                          <input
                            type="text"
                            defaultValue={user?.name}
                            className="input-glass w-full"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-2">Email</label>
                          <input
                            type="email"
                            defaultValue={user?.email}
                            className="input-glass w-full"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-2">Ruolo</label>
                        <input
                          type="text"
                          value={user?.role}
                          disabled
                          className="input-glass w-full opacity-50"
                        />
                      </div>
                    </div>
                  )}

                  {activeTab === 'notifications' && (
                    <div className="space-y-6">
                      <h3 className="text-lg font-semibold">Preferenze Notifiche</h3>
                      
                      {[
                        { id: 'email', label: 'Notifiche Email', desc: 'Ricevi aggiornamenti via email' },
                        { id: 'push', label: 'Notifiche Push', desc: 'Notifiche push nel browser' },
                        { id: 'paolo', label: 'Alert PAOLO', desc: 'Notifiche quando PAOLO suggerisce azioni' },
                        { id: 'revenue', label: 'Aggiornamenti Revenue', desc: 'Notifiche sui cambi di livello' },
                      ].map((item) => (
                        <div key={item.id} className="flex items-center justify-between p-4 rounded-lg bg-surface border border-border">
                          <div>
                            <p className="font-medium">{item.label}</p>
                            <p className="text-sm text-text-secondary">{item.desc}</p>
                          </div>
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" className="sr-only peer" defaultChecked />
                            <div className="w-11 h-6 bg-surface peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
                          </label>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'security' && (
                    <div className="space-y-6">
                      <h3 className="text-lg font-semibold">Sicurezza</h3>
                      
                      <div>
                        <label className="block text-sm font-medium mb-2">Password Corrente</label>
                        <input type="password" className="input-glass w-full" />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-2">Nuova Password</label>
                        <input type="password" className="input-glass w-full" />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-2">Conferma Password</label>
                        <input type="password" className="input-glass w-full" />
                      </div>

                      <div className="p-4 rounded-lg bg-warning/10 border border-warning/30">
                        <p className="text-sm text-warning">
                          <strong>2FA:</strong> L'autenticazione a due fattori è consigliata per gli account admin.
                        </p>
                      </div>
                    </div>
                  )}

                  {activeTab === 'system' && (
                    <div className="space-y-6">
                      <h3 className="text-lg font-semibold">Configurazione Sistema</h3>
                      
                      <div className="p-4 rounded-lg bg-surface border border-border">
                        <div className="flex items-center justify-between mb-4">
                          <div>
                            <p className="font-medium">Versione Dashboard</p>
                            <p className="text-sm text-text-secondary">v1.0.0</p>
                          </div>
                          <Zap className="w-5 h-5 text-primary" />
                        </div>
                        
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">API Endpoint</p>
                            <p className="text-sm text-text-secondary">/api/v1</p>
                          </div>
                          <div className="badge badge-success">Online</div>
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-2">Refresh Rate (secondi)</label>
                        <input
                          type="number"
                          defaultValue={5}
                          className="input-glass w-full"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-2">Tema</label>
                        <select className="input-glass w-full">
                          <option value="dark">Dark (Default)</option>
                          <option value="light" disabled>Light (Coming Soon)</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {/* Save Button */}
                  <div className="mt-6 pt-6 border-t border-border flex justify-end">
                    <button
                      onClick={handleSave}
                      className="btn-primary flex items-center gap-2"
                    >
                      <Save className="w-4 h-4" />
                      Salva Modifiche
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;