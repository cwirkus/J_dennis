// Globals assumed: React, useState, useEffect, useCallback, API_BASE, S, apiFetch

function InboxTab() {
  const { useState, useEffect, useCallback } = React;
  const [messages, setMessages] = useState([]);
  const [highPriorityIds, setHighPriorityIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [edits, setEdits] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [hp, pending] = await Promise.all([
        apiFetch('/api/v1/chat/high-priority').catch(() => []),
        apiFetch('/api/v1/chat/pending').catch(() => []),
      ]);
      const hpIds = new Set((hp || []).map(m => m.id));
      setHighPriorityIds(hpIds);
      // Merge: HP first, then remaining pending, deduplicated
      const seen = new Set();
      const merged = [...(hp || []), ...(pending || [])].filter(m => {
        if (seen.has(m.id)) return false;
        seen.add(m.id);
        return true;
      });
      setMessages(merged);
    } catch (e) {
      console.error('[InboxTab]', e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function approveSend(msgId) {
    try {
      const res = await apiFetch(`/api/v1/chat/${msgId}/approve-response`, { method: 'POST' });
      if (res.sent) {
        setMessages(prev => prev.filter(m => m.id !== msgId));
      } else {
        alert('Send failed: ' + (res.error || 'unknown error'));
      }
    } catch (e) { alert('Error: ' + e.message); }
  }

  async function saveEdit(msgId) {
    const draft = edits[msgId];
    if (draft === undefined) return;
    try {
      await apiFetch(`/api/v1/chat/${msgId}/edit-response`, {
        method: 'PATCH',
        body: JSON.stringify({ draft_response: draft }),
      });
    } catch (e) { alert('Save failed: ' + e.message); }
  }

  function formatDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      });
    } catch { return iso; }
  }

  if (loading) return <div style={S.emptyState}>Loading…</div>;
  if (!messages.length) return <div style={S.emptyState}>No pending messages.</div>;

  return (
    <div>
      {messages.map(msg => {
        const isHP = highPriorityIds.has(msg.id);
        const draftText = edits[msg.id] ?? (msg.draft_response || '');

        return (
          <div key={msg.id} style={{
            ...S.card,
            borderColor: isHP ? '#3a3020' : '#2a2a2a',
            borderLeftColor: isHP ? '#d4a847' : '#2a2a2a',
            borderLeftWidth: isHP ? 3 : 1,
          }}>
            {/* Sender row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <span style={{ fontWeight: 600, fontSize: 15 }}>{msg.sender_name || '—'}</span>
                <span style={{ color: '#888', marginLeft: 8, fontSize: 13 }}>{msg.sender_email}</span>
                {msg.channel && (
                  <span style={{
                    marginLeft: 10,
                    fontSize: 10,
                    padding: '2px 7px',
                    background: '#222',
                    borderRadius: 3,
                    color: '#666',
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                  }}>
                    {msg.channel}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0, marginLeft: 12 }}>
                {isHP && (
                  <span style={{
                    fontSize: 10,
                    padding: '2px 8px',
                    background: '#d4a847',
                    color: '#0f0f0f',
                    borderRadius: 3,
                    fontWeight: 700,
                    letterSpacing: '0.1em',
                  }}>
                    HIGH PRIORITY
                  </span>
                )}
                <span style={{ fontSize: 11, color: '#555' }}>{formatDate(msg.created_at)}</span>
              </div>
            </div>

            {/* Their message */}
            <div style={{
              padding: '10px 14px',
              background: '#111',
              border: '1px solid #1f1f1f',
              borderRadius: 5,
              fontSize: 13,
              color: '#bbb',
              lineHeight: 1.65,
              marginBottom: 14,
              whiteSpace: 'pre-wrap',
            }}>
              {msg.message}
            </div>

            {/* Draft response */}
            <div style={S.fieldLabel}>DRAFT RESPONSE</div>
            <textarea
              value={draftText}
              onChange={e => setEdits(prev => ({ ...prev, [msg.id]: e.target.value }))}
              rows={6}
              style={{ ...S.input, resize: 'vertical', lineHeight: 1.65, marginTop: 6, marginBottom: 12 }}
            />

            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => approveSend(msg.id)} style={S.btnGreen}>APPROVE & SEND</button>
              <button onClick={() => saveEdit(msg.id)} style={S.btnAmber}>EDIT & SAVE</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
