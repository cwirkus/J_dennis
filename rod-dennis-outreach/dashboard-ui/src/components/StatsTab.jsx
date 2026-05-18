// Globals assumed: React, useState, useEffect, useCallback, API_BASE, S, apiFetch

function StatsTab() {
  const { useState, useEffect, useCallback } = React;
  const [stats, setStats] = useState(null);
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, l] = await Promise.all([
        apiFetch('/api/v1/dashboard/stats'),
        apiFetch('/api/v1/discovery/log').catch(() => []),
      ]);
      setStats(s);
      setLog((l || []).slice(0, 5));
    } catch (e) {
      console.error('[StatsTab]', e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  function formatDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
      });
    } catch { return iso; }
  }

  const statCards = [
    { label: 'Total Prospects',  value: stats?.total_prospects  ?? '—' },
    { label: 'Pending Approval', value: stats?.pending_approval ?? '—' },
    { label: 'Sent This Month',  value: stats?.sent_this_month  ?? '—' },
    { label: 'Replies Received', value: stats?.replied          ?? '—' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 24 }}>
        <button onClick={load} style={S.btnGhost} disabled={loading}>
          {loading ? '…' : '↻ REFRESH'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 36 }}>
        {statCards.map(({ label, value }) => (
          <div key={label} style={S.card}>
            <div style={{ fontSize: 44, fontWeight: 300, color: '#d4a847', lineHeight: 1, letterSpacing: '-0.02em' }}>
              {value}
            </div>
            <div style={{ color: '#666', fontSize: 12, marginTop: 8, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {label}
            </div>
          </div>
        ))}
      </div>

      <div style={{ ...S.fieldLabel, marginBottom: 14 }}>DISCOVERY RUNS</div>

      {log.length === 0 ? (
        <div style={{ color: '#555', fontSize: 13 }}>No discovery runs yet.</div>
      ) : (
        <div style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2a2a' }}>
                {['Date', 'Prospects Found', 'Prospects Added'].map(h => (
                  <th key={h} style={{
                    padding: '10px 18px',
                    textAlign: 'left',
                    color: '#555',
                    fontWeight: 500,
                    fontSize: 10,
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {log.map((row, i) => (
                <tr key={row.id || i} style={{
                  borderBottom: i < log.length - 1 ? '1px solid #222' : 'none',
                }}>
                  <td style={{ padding: '10px 18px', color: '#aaa' }}>{formatDate(row.run_at)}</td>
                  <td style={{ padding: '10px 18px', color: '#d4a847' }}>{row.prospects_found}</td>
                  <td style={{ padding: '10px 18px', color: '#d4a847' }}>{row.prospects_added}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
