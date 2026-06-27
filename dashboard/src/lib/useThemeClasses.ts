import { useOutletContext } from 'react-router-dom';

export function useTheme() {
  const ctx = useOutletContext<{ isDark: boolean }>();
  const isDark = ctx?.isDark ?? true;
  return {
    isDark,
    card: isDark ? 'bg-[#1e293b] border-slate-700' : 'bg-white border-slate-200 shadow-sm',
    input: isDark ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400',
    text: isDark ? 'text-slate-300' : 'text-slate-600',
    textH: isDark ? 'text-white' : 'text-slate-900',
    textMuted: isDark ? 'text-slate-400' : 'text-slate-500',
    textXs: isDark ? 'text-slate-500' : 'text-slate-400',
    border: isDark ? 'border-slate-700' : 'border-slate-200',
    borderSub: isDark ? 'border-slate-700/50' : 'border-slate-100',
    badge: isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-100 text-slate-600',
    btnSecondary: isDark ? 'bg-slate-700 hover:bg-slate-600 text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700',
  };
}
