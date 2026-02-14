import { useState } from 'react';
import { motion } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Zap, Eye, EyeOff, Lock, Mail, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useUIStore } from '@/store';
import { authApi } from '@/api/client';

const loginSchema = z.object({
  email: z.string().email('Email non valida'),
  password: z.string().min(6, 'Password minimo 6 caratteri'),
});

type LoginForm = z.infer<typeof loginSchema>;

const LoginPage = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const { addToast } = useUIStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    try {
      const result = await authApi.login(data.email, data.password);
      login(result.user, result.token);
      addToast({
        type: 'success',
        title: 'Login effettuato',
        message: `Benvenuto, ${result.user.name}`,
        duration: 3000,
      });
      navigate('/');
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Login fallito',
        message: 'Credenziali non valide',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background Effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-success/10 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="glass-panel-strong w-full max-w-md p-8 relative z-10"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-primary to-success flex items-center justify-center mb-4 shadow-glow-primary">
            <Zap className="w-10 h-10 text-background" />
          </div>
          <h1 className="text-3xl font-bold mb-2">Auto-Broker</h1>
          <p className="text-text-secondary">Mission Control Center</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-secondary" />
              <input
                {...register('email')}
                type="email"
                placeholder="admin@autobroker.com"
                className="input-glass w-full pl-10"
              />
            </div>
            {errors.email && (
              <p className="text-danger text-sm mt-1 flex items-center gap-1">
                <AlertCircle className="w-4 h-4" />
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-secondary" />
              <input
                {...register('password')}
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                className="input-glass w-full pl-10 pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
            {errors.password && (
              <p className="text-danger text-sm mt-1 flex items-center gap-1">
                <AlertCircle className="w-4 h-4" />
                {errors.password.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full btn-primary py-3 font-semibold flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <div className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                Accesso...
              </>
            ) : (
              'Accedi'
            )}
          </button>
        </form>

        {/* Demo Credentials */}
        <div className="mt-6 p-4 rounded-lg bg-surface border border-border">
          <p className="text-xs text-text-secondary text-center">
            <strong>Demo:</strong> admin@autobroker.com / password
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export default LoginPage;