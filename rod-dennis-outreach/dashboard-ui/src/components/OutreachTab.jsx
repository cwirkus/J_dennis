// Globals assumed: React, useState, useEffect, useCallback, API_BASE, S, apiFetch

function OutreachTab() {
  const { useState, useEffect, useCallback } = React;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [edits, setEdits] = useState({});
  const [showNotes, setShowNotes] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/v1/dashboard/pending-outreach');
      setItems(data);
    } catch (e) {
      console.error('[OutreachTab]', e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  function getEdit(id, field, fallback) {
    return edits[id]?.[field] ?? fallback;
  }

  function setEdit(id, field, value) {
    setEdits(prev => ({ ...prev, [id]: { ...prev[id], [field]: value } }));
  }

  async function approve(draftId) {
    try {
      await apiFetch(`/api/v1/dashboard/approve-outreach/${draftId}`, { method: 'POST' });
      setItems(prev => prev.filter(i => i.draft.id !== draftId));
    } catch (e) { alert('Approve failed: ' + e.message); }
  }

  async function save(draftId) {
    const update = edits[draftId];
    if (!update || !Object.keys(update).length) return;
    try {
      await apiFetch(`/api/v1/dashboard/edit-outreach/${draftId}`, {
        method: 'PATCH',
        body: JSON.stringify(update),
      });
      await load();
    } catch (e) { alert('Save failed: ' + e.message); }
  }

  async function reject(draftId) {
    try {
      await apiFetch(`/api/v1/dashboard/reject-outreach/${draftId}`, { method: 'POST' });
      setItems(prev => prev.filter(i => i.draft.id !== draftId));
    } catch (e) { alert('Reject failed: ' + e.message); }
  }

  if (loading) return <div style={S.emptyState}>Loading…</div>;

  return (
    <div>
      <div style={{ color: '#888', fontSize: 13, marginBottom: 20 }}>
        {items.length === 0
          ? 'No pending outreach.'
          : `${items.length} email${items.length !== 1 ? 's' : ''} pending your approval`}
      </div>

      {items.map(({ draft, prospect }) => {
        const p = prospect || {};
        const id = draft.id;
        const notesOpen = showNotes[id];

        return (
          <div key={id} style={S.card}>
            {/* Header row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
              <div>
                <span style={{ fontWeight: 600, fontSize: 15, color: '#f0ede8' }}>
                  {p.name || '—'}
                </span>
                {p.organization && (
                  <span style={{ color: '#888', marginLeft: 8, fontSize: 14 }}>{p.organization}</span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0, marginLeft: 12 }}>
                {p.country && (
                  <span style={{ color: '#666', fontSize: 12 }}>{p.country}</span>
                )}
                {p.priority && (
                  <span style={{
                    fontSize: 10,
                    padding: '2px 8px',
                    borderRadius: 3,
                    background: p.priority === '1' ? '#d4a847' : '#252525',
                    color: p.priority === '1' ? '#0f0f0f' : '#666',
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                  }}>
                    P{p.priority}
                  </span>
                )}
              </div>
            </div>

            {/* Subject */}
            <div style={{ marginBottom: 10 }}>
              <div style={S.fieldLabel}>SUBJECT</div>
              <input
                value={getEdit(id, 'subject', draft.subject || '')}
                onChange={e => setEdit(id, 'subject', e.target.value)}
                style={S.input}
              />
            </div>

            {/* Body */}
            <div style={{ marginBottom: 10 }}>
              <div style={S.fieldLabel}>BODY</div>
              <textarea
                value={getEdit(id, 'body', draft.body || '')}
                onChange={e => setEdit(id, 'body', e.target.value)}
                rows={9}
                style={{ ...S.input, resize: 'vertical', lineHeight: 1.65 }}
              />
            </div>

            {/* Research notes */}
            {p.notes && (
              <div style={{ marginBottom: 14 }}>
                <button
                  onClick={() => setShowNotes(prev => ({ ...prev, [id]: !notesOpen }))}
                  style={S.btnGhost}
                >
                  {notesOpen ? '▲ Hide research' : '▼ Show research'}
                </button>
                {notesOpen && (
                  <div style={{
                    marginTop: 8,
                    padding: '10px 14px',
                    background: '#111',
                    border: '1px solid #222',
                    borderRadius: 5,
                    fontSize: 13,
                    color: '#aaa',
                    lineHeight: 1.65,
                  }}>
                    {p.notes}
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => approve(id)} style={S.btnGreen}>APPROVE</button>
              <button onClick={() => save(id)} style={S.btnAmber}>EDIT & SAVE</button>
              <button onClick={() => reject(id)} style={S.btnRed}>REJECT</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
