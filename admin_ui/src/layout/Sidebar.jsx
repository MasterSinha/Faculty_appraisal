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

function NavSection({ section, defaultOpen, colorIdx, collapsed, onToggle }) {
  const location = useLocation();
  const navigate = useNavigate();
  const isChildActive = section.children.some(c => c.path === location.pathname);
  const [open, setOpen] = useState(defaultOpen || isChildActive);
  const Icon = section.icon;
  const col  = SEC_COLORS[colorIdx % SEC_COLORS.length];

  const handleSectionClick = () => {
    if (collapsed) {
      onToggle();
    } else {
      setOpen(o => !o);
    }
  };

  return (
    <div style={{ marginBottom: 3 }}>
      {/* Section header */}
      <button
        className="nav-sec-btn"
        onClick={handleSectionClick}
        title={collapsed ? section.label : undefined}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: collapsed ? 0 : 10,
          padding: collapsed ? '9px 0' : '9px 10px', background: isChildActive ? `${col}12` : 'transparent',
          border: `1px solid ${isChildActive ? `${col}25` : 'transparent'}`,
          borderRadius: 10, cursor: 'pointer',
          color: isChildActive ? 'var(--c-sidebar-text)' : 'var(--c-sidebar-muted)',
          fontFamily: 'inherit', fontSize: 10.5, fontWeight: 700,
          justifyContent: collapsed ? 'center' : 'flex-start',
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

        {!collapsed && <span style={{ flex: 1, textAlign: 'left' }}>{section.label}</span>}

        {!collapsed && (
          <div style={{
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform .2s ease', opacity: .4,
          }}>
            <I.chevron size={10} />
          </div>
        )}
      </button>

      {/* Children */}
      {open && !collapsed && (
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

export default function Sidebar({ collapsed, onToggle }) {
  const navigate    = useNavigate();
  const profile     = api.getProfile();
  const initials    = profile?.full_name?.split(' ').map(w => w[0]).slice(0, 2).join('') || 'AD';
  const isSuperAdmin = profile?.appraisal_role === 'super_admin';
  const isAdmin      = profile?.appraisal_role === 'admin' || isSuperAdmin;
  const visibleNav   = profile?.email === 'experimental@gmail.com' ? [] : NAV.filter(s => {
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
      width: collapsed ? 72 : 264, flexShrink: 0, height: '100vh', position: 'sticky', top: 0,
      background: 'var(--c-sidebar-bg)',
      borderRight: '1px solid var(--c-sidebar-border)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      transition: 'width .25s cubic-bezier(0.4, 0, 0.2, 1), border-color .25s ease',
    }}>

      {/* ── Brand ─────────────────────────────────────────────────────────── */}
      <div style={{ padding: collapsed ? '16px 0' : '22px 18px 18px', flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: collapsed ? 0 : 16, justifyContent: 'center', width: '100%' }}>
          {/* Logo mark */}
          <div className="float" style={{
            width: 40, height: 40, borderRadius: 12, flexShrink: 0,
            background: 'linear-gradient(135deg,#3b82f6 0%,#818cf8 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 28px rgba(59,130,246,.5), 0 4px 14px rgba(0,0,0,.3)',
            cursor: 'pointer'
          }} onClick={onToggle}>
            <I.school size={20} stroke="#fff" />
          </div>
          {!collapsed && (
            <div>
              <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--c-sidebar-text)', letterSpacing: -.5, lineHeight: 1 }}>
                DYP Admin
              </div>
              <div style={{ fontSize: 9.5, color: 'var(--c-sidebar-muted)', letterSpacing: .9, textTransform: 'uppercase', marginTop: 4 }}>
                Faculty Appraisal
              </div>
            </div>
          )}
        </div>

        {!collapsed && <div style={{ height: 1, width: '100%', background: 'linear-gradient(90deg,transparent,rgba(59,130,246,.25),rgba(129,140,248,.25),transparent)' }} />}
      </div>

      {/* ── Cycle badge ───────────────────────────────────────────────────── */}
      {!collapsed && (
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
      )}

      {/* ── Nav ───────────────────────────────────────────────────────────── */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: collapsed ? '4px 0' : '4px 10px 8px', scrollbarWidth: 'none' }}>
        {visibleNav.map((section, i) => (
          <NavSection key={section.label} section={section} defaultOpen={i === 0} colorIdx={i} collapsed={collapsed} onToggle={onToggle} />
        ))}
        {profile?.email === 'experimental@gmail.com' && (
          <NavSection
            section={{
              label: "Experimental Sandbox",
              icon: I.idea,
              children: [
                { label: "Form Canvas", icon: I.edit, path: "/developer/sandbox/form-builder" },
                { label: "Reporting Mappings", icon: I.users, path: "/developer/sandbox/reporting-lines" },
                { label: "Hierarchy Simulator", icon: I.time, path: "/developer/sandbox/workflow-sim" },
                { label: "Deploy & Export", icon: I.dl, path: "/developer/sandbox/deploy-export" }
              ]
            }}
            defaultOpen={true}
            colorIdx={5}
            collapsed={collapsed}
            onToggle={onToggle}
          />
        )}
      </nav>

      {/* ── Profile card ──────────────────────────────────────────────────── */}
      {/* ── Profile card ──────────────────────────────────────────────────── */}
      <div style={{ padding: collapsed ? '10px 0 16px' : '10px 14px 16px', flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* Top divider */}
        <div style={{ height: 1, width: '100%', marginBottom: 12, background: 'var(--c-sidebar-divider)' }} />

        <div style={{ marginBottom: 10, width: '100%', display: 'flex', justifyContent: 'center' }}>
          <ThemeToggle collapsed={collapsed} />
        </div>

        {/* Profile row */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: collapsed ? 0 : 10,
          padding: collapsed ? '4px' : '8px 10px', borderRadius: 12,
          background: collapsed ? 'transparent' : 'var(--c-sidebar-profile-bg)',
          border: collapsed ? 'none' : '1px solid var(--c-sidebar-profile-border)',
          justifyContent: collapsed ? 'center' : 'flex-start',
          width: collapsed ? 'auto' : '100%',
          boxSizing: 'border-box',
        }}>
          {/* Avatar */}
          <div style={{
            width: 34, height: 34, borderRadius: 10,
            background: 'linear-gradient(135deg,#3b82f620 0%,#818cf8 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, fontWeight: 700, color: '#3b82f6', flexShrink: 0,
            border: '1px solid #3b82f630',
          }}>
            {initials}
          </div>

          {!collapsed && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--c-sidebar-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {profile?.full_name || 'Admin'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--c-sidebar-muted)', textTransform: 'capitalize', marginTop: 1 }}>
                {profile?.appraisal_role?.replace('_', ' ') || 'Administrator'}
              </div>
            </div>
          )}
        </div>

        {/* Toggle Collapse Button */}
        <button
          onClick={onToggle}
          style={{
            marginTop: 12, width: collapsed ? 34 : '100%', height: collapsed ? 34 : 'auto',
            padding: collapsed ? 0 : '8px 12px', borderRadius: 8,
            border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)',
            color: 'var(--c-sidebar-muted)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            transition: 'all 0.15s ease'
          }}
          title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {collapsed ? '❯' : '❮ Collapse Menu'}
        </button>

        {/* Sign Out Button */}
        <button
          onClick={handleLogout}
          style={{
            marginTop: 8, width: collapsed ? 34 : '100%', height: collapsed ? 34 : 'auto',
            padding: collapsed ? 0 : '8px 12px', borderRadius: 8,
            border: '1px solid rgba(239, 68, 68, 0.2)', background: 'transparent',
            color: '#ef4444', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            transition: 'all 0.15s ease'
          }}
          title={collapsed ? "Sign Out" : undefined}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>
          </svg>
          {!collapsed && 'Sign Out'}
        </button>
      </div>
    </aside>
  );
}
