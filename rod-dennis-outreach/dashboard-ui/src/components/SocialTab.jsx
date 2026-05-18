// Globals assumed: React, useState, useEffect, useCallback, API_BASE, S, apiFetch

function SocialCard({ draft, label, edits, setEdits, approved, onApprove, onSave, maxChars }) {
  const content = edits[draft.id] ?? draft.content ?? '';
  const isApproved = approved[draft.id] || draft.status === 'approved';
  const overLimit = maxChars && content.length > maxChars;

  return (
    <div style={{ ...S.card, marginBottom: 0, display: 'flex', flexDirection: 'column' }}>
      <div style={S.fieldLabel}>{label}</div>
      <textarea
        value={content}
        onChange={e => setEdits(prev => ({ ...prev, [draft.id]: e.target.value }))}
        rows={label === 'LinkedIn' ? 11 : 4}
        disabled={isApproved}
        style={{
          ...S.input,
          resize: 'vertical',
          lineHeight: 1.65,
          marginTop: 8,
          marginBottom: 6,
          opacity: isApproved ? 0.55 : 1,
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 11, color: overLimit ? '#e05555' : '#555' }}>
          {content.length}{maxChars ? ` / ${maxChars}` : ''} chars
        </span>
      </div>
      {isApproved ? (
        <div style={{ fontSize: 11, color: '#d4a847', letterSpacing: '0.08em' }}>
          Approved — copy text and post manually
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => onApprove(draft.id)} style={S.btnGreen}>APPROVE</button>
          <button onClick={() => onSave(draft.id)} style={S.btnAmber}>EDIT & SAVE</button>
        </div>
      )}
    </div>
  );
}

function SocialTab() {
  const { useState, useEffect, useCallback } = React;
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [edits, setEdits] = useState({});
  const [approved, setApproved] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/v1/social/pending');
      setDrafts(data);
    } catch (e) {
      console.error('[SocialTab]', e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Group by trigger_event
  const groups = {};
  drafts.forEach(d => {
    const key = d.trigger_event || 'Untitled';
    if (!groups[key]) groups[key] = {};
    groups[key][d.platform] = d;
  });

  async function approveDraft(id) {
    try {
      await apiFetch(`/api/v1/social/${id}/approve`, { method: 'PATCH' });
      setApproved(prev => ({ ...prev, [id]: true }));
    } catch (e) { alert('Failed: ' + e.message); }
  }

  async function saveDraft(id) {
    const content = edits[id];
    if (content === undefined) return;
    try {
      await apiFetch(`/api/v1/social/${id}/edit`, {
        method: 'PATCH',
        body: JSON.stringify({ content }),
      });
    } catch (e) { alert('Save failed: ' + e.message); }
  }

  if (loading) return <div style={S.emptyState}>Loading…</div>;

  const groupKeys = Object.keys(groups);
  if (!groupKeys.length) return <div style={S.emptyState}>No pending social drafts.</div>;

  return (
    <div>
      {groupKeys.map(trigger => {
        const { linkedin, twitter } = groups[trigger];
        return (
          <div key={trigger} style={{ marginBottom: 36 }}>
            <div style={{ fontSize: 11, letterSpacing: '0.12em', color: '#666', textTransform: 'uppercase', marginBottom: 14 }}>
              {trigger}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {linkedin
                ? <SocialCard
                    draft={linkedin}
                    label="LinkedIn"
                    edits={edits}
                    setEdits={setEdits}
                    approved={approved}
                    onApprove={approveDraft}
                    onSave={saveDraft}
                    maxChars={null}
                  />
                : <div style={{ ...S.card, marginBottom: 0, color: '#555', fontSize: 13 }}>No LinkedIn draft</div>
              }
              {twitter
                ? <SocialCard
                    draft={twitter}
                    label="Twitter / X"
                    edits={edits}
                    setEdits={setEdits}
                    approved={approved}
                    onApprove={approveDraft}
                    onSave={saveDraft}
                    maxChars={280}
                  />
                : <div style={{ ...S.card, marginBottom: 0, color: '#555', fontSize: 13 }}>No Twitter draft</div>
              }
            </div>
          </div>
        );
      })}
    </div>
  );
}
