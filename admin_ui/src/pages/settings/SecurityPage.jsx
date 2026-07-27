import { useState, useEffect } from 'react';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import Badge from '../../components/Badge';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import Toggle from '../../components/Toggle';
import { I } from '../../components/icons';
import { useFetch } from '../../hooks/useFetch';

function makePassword(len = 14) {
  const pool = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%&';
  return Array.from({ length: len }, () => pool[Math.floor(Math.random() * pool.length)]).join('');
}

export default function SecurityPage() {
  const [twoFA, setTwoFA]                   = useState(false);
  const [sessionTimeout, setSessionTimeout] = useState(true);
  const [auditLog, setAuditLog]             = useState(true);

  useEffect(() => {
    let active = true;
    async function fetchConfig() {
      try {
        const data = await api.config.get();
        if (!active) return;
        if (data) {
          setTwoFA(data.TWO_FACTOR_AUTH === 'true');
          setSessionTimeout(data.SESSION_TIMEOUT !== 'false');
          setAuditLog(data.AUDIT_LOGGING !== 'false');
        }
      } catch (err) {
        console.error('Failed to load security config:', err);
      }
    }
    fetchConfig();
    return () => { active = false; };
  }, []);

  async function handleToggle(key, val, setter) {
    try {
      setter(val);
      await api.config.update({ [key]: val ? 'true' : 'false' });
    } catch (err) {
      setter(!val); // revert on failure
      console.error(`Failed to update ${key}:`, err);
    }
  }


  const [generated,  setGenerated]  = useState(null);   // { email, fullName, password }
  const [genLoading, setGenLoading] = useState(false);
  const [genTarget,  setGenTarget]  = useState(null);   // email being processed
  const [genError,   setGenError]   = useState('');
  const [copied,     setCopied]     = useState(false);

  const { data: vcList, loading: vcLoading } = useFetch(
    () => api.users.list({ role: 'vc' }),
    [],
  );

  const vcs = Array.isArray(vcList) ? vcList : [];

  async function handleGenerate(email, fullName) {
    setGenError('');
    setGenerated(null);
    setGenTarget(email);
    setGenLoading(true);
    const password = makePassword();
    try {
      await api.users.update(email, { password });
      setGenerated({ email, fullName, password });
    } catch (err) {
      setGenError(err.message);
    } finally {
      setGenLoading(false);
      setGenTarget(null);
    }
  }

  function copyCredentials() {
    if (!generated) return;
    navigator.clipboard.writeText(`Email: ${generated.email}\nPassword: ${generated.password}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="page-enter">
      <PageHead title="Security" sub="Authentication, session, and audit settings" />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <Card title="Authentication" delay={0}>
          {[
            { l: 'Two-Factor Authentication', d: 'Require 2FA for admin login',  v: twoFA,          s: (v) => handleToggle('TWO_FACTOR_AUTH', v, setTwoFA)          },
            { l: 'Session Timeout',           d: 'Auto-logout after 30 minutes', v: sessionTimeout, s: (v) => handleToggle('SESSION_TIMEOUT', v, setSessionTimeout) },
            { l: 'Audit Logging',             d: 'Log all admin actions',        v: auditLog,       s: (v) => handleToggle('AUDIT_LOGGING', v, setAuditLog)       },
          ].map((c, i) => (
            <div key={c.l} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '13px 0', borderBottom: i < 2 ? '1px solid rgba(255,255,255,.05)' : 'none' }}>
              <div>
                <div style={{ fontWeight: 600, color: C.text, fontSize: 13 }}>{c.l}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{c.d}</div>
              </div>
              <Toggle val={c.v} onChange={c.s} />
            </div>
          ))}
        </Card>

        <Card title="Security Status" delay={60}>
          {[
            { l: '2FA',        v: twoFA          ? 'Enabled'  : 'Disabled', c: twoFA          ? 'green' : 'red'  },
            { l: 'Session',    v: sessionTimeout ? 'Active'   : 'Inactive', c: sessionTimeout ? 'green' : 'gray' },
            { l: 'Audit Logs', v: auditLog       ? 'Running'  : 'Paused',   c: auditLog       ? 'green' : 'gray' },
            { l: 'JWT Secret', v: 'Configured',                              c: 'green'                           },
            { l: 'Auth Mode',  v: 'Local JWT',                               c: 'blue'                            },
          ].map((x, i) => (
            <div key={x.l} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '11px 0', borderBottom: i < 4 ? '1px solid rgba(255,255,255,.05)' : 'none', fontSize: 13 }}>
              <span style={{ color: C.subtle }}>{x.l}</span>
              <Badge color={x.c}>{x.v}</Badge>
            </div>
          ))}
        </Card>
      </div>

      {/* VC Credential Generation ─────────────────────────────────────────── */}
      <div style={{ marginTop: 14 }}>
        <Card
          title="VC Credentials"
          sub="Generate or reset login credentials for Vice Chancellor accounts"
          delay={120}
        >
          {vcLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[0, 1].map(i => (
                <div key={i} className="skeleton" style={{ height: 48, borderRadius: 8, animationDelay: `${i * 80}ms` }} />
              ))}
            </div>
          ) : vcs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '18px 0', color: C.muted, fontSize: 12 }}>
              No VC accounts found in the system.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {vcs.map((vc, i) => (
                <div
                  key={vc.email}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 0',
                    borderBottom: i < vcs.length - 1 ? '1px solid rgba(255,255,255,.05)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 34, height: 34, borderRadius: '50%',
                      background: `${C.yellow}18`, border: `1.5px solid ${C.yellow}40`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: C.yellow, flexShrink: 0,
                    }}>
                      <I.star size={14} />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, color: C.text, fontSize: 13 }}>
                        {vc.full_name || 'Vice Chancellor'}
                      </div>
                      <div style={{ fontSize: 11, color: C.muted, marginTop: 1 }}>{vc.email}</div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleGenerate(vc.email, vc.full_name || 'Vice Chancellor')}
                    disabled={genLoading && genTarget === vc.email}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: '7px 14px', borderRadius: 8, border: 'none', cursor: 'pointer',
                      background: `${C.yellow}18`, color: C.yellow,
                      fontSize: 12, fontWeight: 600,
                      opacity: genLoading && genTarget === vc.email ? 0.6 : 1,
                      transition: 'opacity .15s',
                    }}
                  >
                    <I.key size={13} />
                    {genLoading && genTarget === vc.email ? 'Generating…' : 'Generate Password'}
                  </button>
                </div>
              ))}
            </div>
          )}

          {genError && (
            <div style={{
              marginTop: 12, padding: '10px 14px', borderRadius: 8,
              background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.2)',
              color: '#f87171', fontSize: 12,
            }}>
              {genError}
            </div>
          )}

          {generated && (
            <div style={{
              marginTop: 14, padding: 16, borderRadius: 10,
              background: 'rgba(251,191,36,.06)', border: '1px solid rgba(251,191,36,.2)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.yellow, textTransform: 'uppercase', letterSpacing: .5 }}>
                    Credentials Generated
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
                    Save these now — this password will not be shown again.
                  </div>
                </div>
                <button
                  onClick={copyCredentials}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '5px 11px', borderRadius: 7, border: 'none', cursor: 'pointer',
                    background: copied ? 'rgba(52,211,153,.15)' : 'rgba(255,255,255,.07)',
                    color: copied ? '#34d399' : C.subtle, fontSize: 11, fontWeight: 600,
                    transition: 'all .2s',
                  }}
                >
                  {copied ? <I.check size={12} /> : <I.dl size={12} />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>

              {[
                { label: 'Email',    value: generated.email    },
                { label: 'Password', value: generated.password },
              ].map(row => (
                <div key={row.label} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 3, fontWeight: 600, textTransform: 'uppercase', letterSpacing: .4 }}>
                    {row.label}
                  </div>
                  <div style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 13, color: C.text,
                    background: 'rgba(255,255,255,.04)', borderRadius: 6,
                    padding: '7px 10px', letterSpacing: .5,
                    border: '1px solid rgba(255,255,255,.06)',
                    wordBreak: 'break-all',
                  }}>
                    {row.value}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
