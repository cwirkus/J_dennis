// Globals assumed: React, useState, API_BASE, S
// Tab components: OutreachTab, SocialTab, InboxTab, StatsTab

function App() {
  const { useState } = React;
  const [activeTab, setActiveTab] = useState('outreach');

  const tabs = [
    { id: 'outreach', label: 'OUTREACH' },
    { id: 'social',   label: 'SOCIAL'   },
    { id: 'inbox',    label: 'INBOX'    },
    { id: 'stats',    label: 'STATS'    },
  ];

  return (
    <div style={{ background: '#0f0f0f', minHeight: '100vh', color: '#f0ede8', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 28px' }}>

        {/* Header */}
        <div style={{ padding: '22px 0 0' }}>
          <span style={{
            fontVariant: 'small-caps',
            fontSize: 12,
            letterSpacing: '0.14em',
            color: '#555',
          }}>
            J. Rodney Dennis — Outreach Dashboard
          </span>
        </div>

        {/* Tab bar */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid #2a2a2a',
          marginTop: 18,
        }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                background: 'none',
                border: 'none',
                color: activeTab === tab.id ? '#f0ede8' : '#555',
                fontSize: 11,
                letterSpacing: '0.15em',
                padding: '10px 22px',
                cursor: 'pointer',
                borderBottom: activeTab === tab.id ? '2px solid #d4a847' : '2px solid transparent',
                marginBottom: -1,
                transition: 'color 0.15s',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ paddingTop: 28, paddingBottom: 60 }}>
          {activeTab === 'outreach' && <OutreachTab />}
          {activeTab === 'social'   && <SocialTab />}
          {activeTab === 'inbox'    && <InboxTab />}
          {activeTab === 'stats'    && <StatsTab />}
        </div>

      </div>
    </div>
  );
}
