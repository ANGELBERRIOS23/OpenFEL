import { useTheme } from '../lib/useThemeClasses';

const endpoints = [
  {
    section: 'Health',
    items: [
      { method: 'GET', path: '/api/health', role: 'público', desc: 'Estado de los 4 servidores SAT (DNS, TLS, HTTP, latencia). No requiere API key.' },
    ],
  },
  {
    section: 'NIT',
    items: [
      { method: 'POST', path: '/api/nit/lookup', role: 'VIEWER', desc: 'Consultar nombre de un NIT en el RTU. Body: { account_nit, nit }' },
    ],
  },
  {
    section: 'DTE (Documentos Tributarios)',
    items: [
      { method: 'POST', path: '/api/dte/emit', role: 'OPERATOR', desc: 'Emitir un DTE. Body: { account_nit, tipo, receptor_nit, receptor_nombre, items: [{descripcion, cantidad, precio_unitario}] }' },
      { method: 'POST', path: '/api/dte/annul', role: 'OPERATOR', desc: 'Anular un DTE. Body: { account_nit, uuid, motivo }' },
      { method: 'GET', path: '/api/dte/emitted?account_nit=X', role: 'VIEWER', desc: 'Listar últimos DTEs emitidos (hasta 100).' },
      { method: 'GET', path: '/api/dte/received?account_nit=X', role: 'VIEWER', desc: 'Listar últimos DTEs recibidos (hasta 100).' },
      { method: 'GET', path: '/api/dte/{uuid}/detail?account_nit=X', role: 'VIEWER', desc: 'Detalle completo de un DTE por UUID.' },
      { method: 'GET', path: '/api/dte/{uuid}/pdf?account_nit=X', role: 'VIEWER', desc: 'Descargar PDF de un DTE.' },
    ],
  },
  {
    section: 'Cuentas SAT',
    items: [
      { method: 'GET', path: '/api/accounts', role: 'ADMIN', desc: 'Listar todas las cuentas SAT registradas.' },
      { method: 'POST', path: '/api/accounts', role: 'ADMIN', desc: 'Crear cuenta. Body: { nit, login_password, cert_password, preferred_api: "mixed"|"mobile"|"web", affiliation: "GEN"|"PEQ" }' },
      { method: 'GET', path: '/api/accounts/{nit}', role: 'ADMIN', desc: 'Obtener detalle de una cuenta.' },
      { method: 'PATCH', path: '/api/accounts/{nit}', role: 'ADMIN', desc: 'Editar cuenta (contraseñas, modo API, afiliación, nombre, estado).' },
      { method: 'DELETE', path: '/api/accounts/{nit}', role: 'ADMIN', desc: 'Eliminar cuenta permanentemente.' },
    ],
  },
  {
    section: 'API Keys',
    items: [
      { method: 'GET', path: '/api/keys', role: 'ADMIN', desc: 'Listar todas las API keys.' },
      { method: 'POST', path: '/api/keys', role: 'ADMIN', desc: 'Crear key. Body: { name, role: "VIEWER"|"OPERATOR"|"ADMIN", allowed_accounts: ["NIT1"] }' },
      { method: 'PATCH', path: '/api/keys/{id}', role: 'ADMIN', desc: 'Actualizar key (nombre, rol, estado, cuentas permitidas).' },
      { method: 'DELETE', path: '/api/keys/{id}', role: 'ADMIN', desc: 'Revocar key (soft delete).' },
    ],
  },
  {
    section: 'Audit Log',
    items: [
      { method: 'GET', path: '/api/logs', role: 'ADMIN', desc: 'Consultar log de auditoría. Query params: action, account_nit, limit, offset.' },
    ],
  },
];

const methodColors: Record<string, string> = {
  GET: 'bg-green-900/30 text-green-400',
  POST: 'bg-blue-900/30 text-blue-400',
  PATCH: 'bg-amber-900/30 text-amber-400',
  DELETE: 'bg-red-900/30 text-red-400',
};

export default function Docs() {
  const t = useTheme();

  return (
    <div className="max-w-4xl">
      <h2 className={`text-xl sm:text-2xl font-bold ${t.textH} mb-2`}>Documentación API</h2>
      <p className={`${t.textMuted} text-sm mb-6`}>
        Todos los endpoints (excepto /api/health) requieren el header <code className={`px-1 rounded ${t.badge} text-xs`}>X-API-Key</code>.
      </p>

      {/* Roles explanation */}
      <div className={`rounded-xl border p-4 sm:p-5 mb-6 ${t.card}`}>
        <h3 className={`font-semibold ${t.textH} mb-3`}>Roles</h3>
        <div className="space-y-2 text-sm">
          <div><span className={`inline-block w-24 px-2 py-0.5 rounded text-xs ${t.badge}`}>VIEWER</span> <span className={t.text}>Solo lectura: consultar NIT, listar DTEs, descargar PDF, ver health</span></div>
          <div><span className="inline-block w-24 px-2 py-0.5 rounded text-xs bg-blue-900/30 text-blue-400">OPERATOR</span> <span className={t.text}>+ Emitir y anular DTEs</span></div>
          <div><span className="inline-block w-24 px-2 py-0.5 rounded text-xs bg-purple-900/30 text-purple-400">ADMIN</span> <span className={t.text}>+ Gestionar cuentas, API keys, ver logs</span></div>
        </div>
      </div>

      {/* API modes explanation */}
      <div className={`rounded-xl border p-4 sm:p-5 mb-6 ${t.card}`}>
        <h3 className={`font-semibold ${t.textH} mb-3`}>Modos de API por cuenta</h3>
        <div className="space-y-2 text-sm">
          <div><span className={`inline-block w-20 font-mono text-xs ${t.textH}`}>mixed</span> <span className={t.text}>Inteligente: usa mobile (rápida, 12h token) y cae a web automáticamente. Para consultas que requieren fecha usa web.</span></div>
          <div><span className={`inline-block w-20 font-mono text-xs ${t.textH}`}>mobile</span> <span className={t.text}>Solo API móvil. Más rápida (~5s), token 12h, pero sin descarga XML ni filtro por fechas.</span></div>
          <div><span className={`inline-block w-20 font-mono text-xs ${t.textH}`}>web</span> <span className={t.text}>Solo API web. Sesión 25min, soporta XML, XLS, filtro por fechas, pero más lenta (~10s).</span></div>
        </div>
      </div>

      {/* Endpoints */}
      {endpoints.map(section => (
        <div key={section.section} className="mb-6">
          <h3 className={`font-semibold ${t.textH} mb-3`}>{section.section}</h3>
          <div className={`rounded-xl border overflow-hidden ${t.card}`}>
            {section.items.map((ep, i) => (
              <div key={i} className={`p-3 sm:p-4 ${i > 0 ? `border-t ${t.borderSub}` : ''}`}>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${methodColors[ep.method] || t.badge}`}>{ep.method}</span>
                  <code className={`text-xs sm:text-sm font-mono ${t.textH} break-all`}>{ep.path}</code>
                  <span className={`px-2 py-0.5 rounded text-xs ${t.badge}`}>{ep.role}</span>
                </div>
                <p className={`${t.textMuted} text-xs sm:text-sm`}>{ep.desc}</p>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Example */}
      <div className={`rounded-xl border p-4 sm:p-5 ${t.card}`}>
        <h3 className={`font-semibold ${t.textH} mb-3`}>Ejemplo: emitir factura con curl</h3>
        <pre className={`text-xs p-3 rounded-lg overflow-x-auto ${t.isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-700'}`}>{`curl -X POST http://localhost:8000/api/dte/emit \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ofel_k1_..." \\
  -d '{
    "account_nit": "120405237",
    "tipo": "FACT",
    "receptor_nit": "CF",
    "receptor_nombre": "Consumidor Final",
    "items": [
      {"descripcion": "Servicio profesional", "cantidad": 1, "precio_unitario": 500.00}
    ]
  }'`}</pre>
      </div>
    </div>
  );
}
