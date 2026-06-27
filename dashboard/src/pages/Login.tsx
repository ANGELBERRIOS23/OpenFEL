import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { setKey, api } from '../lib/api';
import { Key } from 'lucide-react';

export default function Login() {
  const [key, setKeyInput] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setKey(key);
    try {
      await api.health();
      navigate('/');
    } catch {
      setError('Key inválida o servidor no disponible');
      setKey('');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary">
      <form onSubmit={handleSubmit} className="bg-bg-secondary p-8 rounded-xl w-96 shadow-2xl border border-slate-700">
        <div className="flex items-center gap-3 mb-6">
          <Key size={28} className="text-accent" />
          <h1 className="text-2xl font-bold text-white">OpenFEL</h1>
        </div>
        <p className="text-slate-400 text-sm mb-6">Ingresa tu API key para acceder al dashboard.</p>
        <input
          type="password"
          value={key}
          onChange={e => setKeyInput(e.target.value)}
          placeholder="ofel_k1_..."
          className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-accent mb-4"
        />
        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
        <button
          type="submit"
          disabled={loading || !key}
          className="w-full py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors disabled:opacity-50 cursor-pointer"
        >
          {loading ? 'Validando...' : 'Ingresar'}
        </button>
      </form>
    </div>
  );
}
