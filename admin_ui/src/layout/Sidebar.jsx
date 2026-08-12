import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { C } from '../constants/colors';
import { NAV } from '../constants/nav';
import { I } from '../components/icons';
import { api } from '../api/client';
import ThemeToggle from '../components/ThemeToggle';

function formatCycleLabel(yearStr) {
  if (!yearStr) return 'Active Cycle';
  const parts = yearStr.split('-');
  if (parts.length === 2) {
    const y1 = parts[0].trim();
    let y2 = parts[1].trim();
    if (y2.length === 4) y2 = y2.slice(2);
    return `Cycle ${y1}–${y2}`;
  }
  return `Cycle ${yearStr}`;
}

// One accent colour per nav section
const SEC_COLORS = [
  '#3b82f6', // Dashboard     — blue
  '#a78bfa', // User Reg      — purple
  '#34d399', // Appraisal     — green
  '#fbbf24', // Tracking      — amber
  '#22d3ee', // Analytics     — cyan
  '#fb923c', // Feedback      — orange
  '#818cf8', // Announcements — indigo
  '#94a3b8', // Settings      — slate
];

function NavSection({ section, defaultOpen, colorIdx }) {
  const location = useLocation();
  const navigate = useNavigate();
  const isChildActive = section.children.some(c => c.path === location.pathname);
  const [open, setOpen] = useState(defaultOpen || isChildActive);
  const Icon = section.icon;
  const col  = SEC_COLORS[colorIdx % SEC_COLORS.length];

  return (
    <div style={{ marginBottom: 3 }}>
      {/* Section header */}
      <button
        className="nav-sec-btn"
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 10px', background: isChildActive ? `${col}12` : 'transparent',
          border: `1px solid ${isChildActive ? `${col}25` : 'transparent'}`,
          borderRadius: 10, cursor: 'pointer',
          color: isChildActive ? 'var(--c-sidebar-text)' : 'var(--c-sidebar-muted)',
          fontFamily: 'inherit', fontSize: 10.5, fontWeight: 700,
          letterSpacing: .7, textTransform: 'uppercase',
          transition: 'all .15s ease',
        }}
      >
        {/* Icon box */}
        <div style={{
          width: 30, height: 30, borderRadius: 8, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: isChildActive ? `${col}22` : 'var(--c-sidebar-icon-bg)',
          border: `1px solid ${isChildActive ? `${col}35` : 'var(--c-sidebar-icon-border)'}`,
          boxShadow: isChildActive ? `0 0 10px ${col}25` : 'none',
          transition: 'all .15s ease',
        }}>
          <Icon size={14} stroke={isChildActive ? col : C.muted} />
        </div>

        <span style={{ flex: 1, textAlign: 'left' }}>{section.label}</span>

        <div style={{
          transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform .2s ease', opacity: .4,
        }}>
          <I.chevron size={10} />
        </div>
      </button>

      {/* Children */}
      {open && (
        <div className="nav-children" style={{
          marginTop: 2, marginLeft: 8, marginBottom: 4,
          paddingLeft: 12, borderLeft: `1.5px solid var(--c-sidebar-tree)`,
        }}>
          {section.children.map(child => {
            const active = location.pathname === child.path;
            const CIcon  = child.icon;
            return (
              <button
                key={child.label}
                className="nav-child-btn"
                onClick={() => navigate(child.path)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 9,
                  padding: '8px 11px 8px 13px',
                  background: active ? `${col}14` : 'transparent',
                  border: 'none',
                  borderLeft: active ? `2.5px solid ${col}` : '2.5px solid transparent',
                  borderRadius: '0 8px 8px 0',
                  cursor: 'pointer',
                  color: active ? col : 'var(--c-sidebar-muted)',
                  fontFamily: 'inherit', fontSize: 12.5,
                  fontWeight: active ? 600 : 400,
                  marginBottom: 2, textAlign: 'left',
                  boxShadow: active ? `inset 0 0 16px ${col}0d` : 'none',
                  transition: 'all .15s ease',
                }}
              >
                <CIcon size={13} stroke="currentColor" />
                {child.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Sidebar() {
  const navigate    = useNavigate();
  const profile     = api.getProfile();
  const initials    = profile?.full_name?.split(' ').map(w => w[0]).slice(0, 2).join('') || 'AD';
  const isSuperAdmin = profile?.appraisal_role === 'super_admin';
  const isAdmin      = profile?.appraisal_role === 'admin' || isSuperAdmin;
  const visibleNav   = NAV.filter(s => {
    if (s.superAdminOnly && !isSuperAdmin) return false;
    if (s.adminOnly && !isAdmin) return false;
    return true;
  });

  const [activeYear, setActiveYear] = useState(null);
  const [isCycleOpen, setIsCycleOpen] = useState(true);

  useEffect(() => {
    let active = true;
    api.cycle.list()
      .then(configs => {
        if (!active || !Array.isArray(configs) || configs.length === 0) return;
        const live = configs.find(c => c.is_open) || configs[0];
        if (live && live.academic_year) {
          setActiveYear(live.academic_year);
          setIsCycleOpen(Boolean(live.is_open));
        }
      })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  function handleLogout() {
    api.logout();
    navigate('/login');
  }

  return (
    <aside style={{
      width: 264, flexShrink: 0, height: '100vh', position: 'sticky', top: 0,
      background: 'var(--c-sidebar-bg)',
      borderRight: '1px solid var(--c-sidebar-border)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      transition: 'border-color .25s ease',
    }}>

      {/* ── Brand ─────────────────────────────────────────────────────────── */}
      <div style={{ padding: '22px 18px 18px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          {/* Logo mark */}
          <div className="float" style={{
            width: 42, height: 42, borderRadius: 12, flexShrink: 0,
            background: 'linear-gradient(135deg,#3b82f6 0%,#818cf8 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 28px rgba(59,130,246,.5), 0 4px 14px rgba(0,0,0,.3)',
          }}>
            <I.school size={20} stroke="#fff" />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--c-sidebar-text)', letterSpacing: -.5, lineHeight: 1 }}>
              DYP Admin
            </div>
            <div style={{ fontSize: 9.5, color: 'var(--c-sidebar-muted)', letterSpacing: .9, textTransform: 'uppercase', marginTop: 4 }}>
              Faculty Appraisal
            </div>
          </div>
        </div>

        {/* Gradient divider */}
        <div style={{ height: 1, background: 'linear-gradient(90deg,transparent,rgba(59,130,246,.25),rgba(129,140,248,.25),transparent)' }} />
      </div>

      {/* ── Cycle badge ───────────────────────────────────────────────────── */}
      <div style={{ padding: '0 14px 10px', flexShrink: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 12px', borderRadius: 9,
          background: isCycleOpen ? 'rgba(59,130,246,.07)' : 'rgba(251,191,36,.07)',
          border: `1px solid ${isCycleOpen ? 'rgba(59,130,246,.15)' : 'rgba(251,191,36,.2)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div className="notif-dot" style={{
              width: 6, height: 6, borderRadius: '50%',
              background: isCycleOpen ? C.green : C.yellow,
              boxShadow: `0 0 8px ${isCycleOpen ? C.green : C.yellow}`
            }} />
            <span style={{ fontSize: 11, color: 'var(--c-sidebar-muted)', fontWeight: 500 }}>
              {formatCycleLabel(activeYear)}
            </span>
          </div>
          <span style={{
            fontSize: 9.5,
            color: isCycleOpen ? '#3b82f6' : C.yellow,
            fontWeight: 700, letterSpacing: .4, textTransform: 'uppercase'
          }}>
            {isCycleOpen ? 'Live' : 'Closed'}
          </span>
        </div>
      </div>

      {/* ── Nav ───────────────────────────────────────────────────────────── */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '4px 10px 8px', scrollbarWidth: 'none' }}>
        {visibleNav.map((section, i) => (
          <NavSection key={section.label} section={section} defaultOpen={i === 0} colorIdx={i} />
        ))}
        {profile?.email === 'experimental@gmail.com' && (
          <NavSection
            section={{
              label: "Experimental Sandbox",
              icon: I.idea,
              children: [
                { label: "Sandbox Playground", icon: I.edit, path: "/developer/sandbox" }
              ]
            }}
            defaultOpen={false}
            colorIdx={5}
          />
        )}
      </nav>

      {/* ── Profile card ──────────────────────────────────────────────────── */}
      <div style={{ padding: '10px 14px 16px', flexShrink: 0 }}>
        {/* Top divider */}
        <div style={{ height: 1, marginBottom: 12, background: 'var(--c-sidebar-divider)' }} />

        <div style={{ marginBottom: 10 }}>
          <ThemeToggle />
        </div>

        {/* Profile row */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px', borderRadius: 11, marginBottom: 9,
          background: 'var(--c-sidebar-card-bg)',
          border: '1px solid var(--c-sidebar-card-border)',
        }}>
          {/* Avatar */}
          <div style={{
            width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
            background: 'linear-gradient(135deg,#1d4ed8,#3b82f6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 700, color: '#fff',
            fontFamily: "'JetBrains Mono',monospace",
            boxShadow: '0 0 14px rgba(59,130,246,.35)',
          }}>
            {initials}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--c-sidebar-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {profile?.full_name || 'Admin'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 3 }}>
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: C.green, boxShadow: `0 0 5px ${C.green}80` }} />
              <span style={{ fontSize: 10, color: 'var(--c-sidebar-muted)', letterSpacing: .3 }}>
                {isSuperAdmin ? 'Developer' : 'Administrator'}
              </span>
            </div>
          </div>
        </div>

        {/* Edit Profile */}
        <button
          onClick={() => navigate('/profile')}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 12px', marginBottom: 7,
            background: 'transparent',
            border: '1px solid transparent',
            borderRadius: 9, cursor: 'pointer',
            color: 'var(--c-sidebar-muted)', fontSize: 12, fontWeight: 500,
            fontFamily: 'inherit', transition: 'all .15s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background    = 'rgba(59,130,246,.07)'
            e.currentTarget.style.borderColor   = 'rgba(59,130,246,.18)'
            e.currentTarget.style.color         = C.accent
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background    = 'transparent'
            e.currentTarget.style.borderColor   = 'transparent'
            e.currentTarget.style.color         = 'var(--c-sidebar-muted)'
          }}
        >
          <I.edit size={13} stroke="currentColor" />
          Edit Profile
        </button>

        {/* Sign out */}
        <button
          onClick={handleLogout}
          className="signout-btn"
          style={{
            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
            padding: '9px 12px',
            background: 'rgba(248,113,113,.06)',
            border: '1px solid rgba(248,113,113,.15)',
            borderRadius: 9, cursor: 'pointer',
            color: C.red, fontSize: 12, fontWeight: 500,
            fontFamily: 'inherit',
          }}
        >
          <I.lock size={13} stroke={C.red} /> Sign Out
        </button>
      </div>
    </aside>
  );
}
