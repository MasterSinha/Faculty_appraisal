import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { C } from '../constants/colors';
import { I } from '../components/icons';
import { api } from '../api/client';
import { inp, lbl } from '../constants/styleTokens';

const EyeOff = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
);

const Spinner = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.5" strokeLinecap="round"
    style={{ animation: 'spin .7s linear infinite' }}>
    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
  </svg>
);

const FEATURES = [
  { Icon: I.users,  text: 'Manage faculty accounts'       },
  { Icon: I.check,  text: 'Track submission status'       },
  { Icon: I.chart,  text: 'Analytics & school reports'    },
  { Icon: I.key,    text: 'Credential management'         },
  { Icon: I.gear,   text: 'System configuration'          },
];

export default function Login() {
  const navigate = useNavigate();
  const [email,   setEmail]   = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd]  = useState(false);
  const [loading, setLoading]  = useState(false);
  const [error,   setError]    = useState('');

  // MFA states
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaToken, setMfaToken] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [mfaLoading, setMfaLoading] = useState(false);

  useEffect(() => {
    if (localStorage.getItem('admin_token')) navigate('/', { replace: true });
  }, [navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await api.login(email, password);
      if (res?.mfa_required) {
        setMfaRequired(true);
        setMfaToken(res.mfa_token);
      } else {
        navigate('/');
      }
    } catch (err) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp(e) {
    e.preventDefault();
    setMfaLoading(true); setError('');
    try {
      await api.verifyMfa(mfaToken, otpCode.trim());
      navigate('/');
    } catch (err) {
      setError(err.message || 'Incorrect or expired verification code');
    } finally {
      setMfaLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: C.bg, overflow: 'hidden' }}>

      {/* ── Left branding panel ── */}
      <div style={{
        width: 420, flexShrink: 0, position: 'relative', overflow: 'hidden',
        background: 'linear-gradient(160deg,#0d1b30 0%,#080c14 60%)',
        borderRight: '1px solid rgba(255,255,255,.055)',
        display: 'flex', flexDirection: 'column', padding: '48px 44px',
      }}>
        {/* Background glows */}
        <div style={{ position: 'absolute', top: '25%', left: '50%', transform: 'translate(-50%,-50%)',
          width: 380, height: 380, background: 'radial-gradient(ellipse,rgba(59,130,246,.14) 0%,transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', bottom: '15%', right: '-60px',
          width: 260, height: 260, background: 'radial-gradient(ellipse,rgba(129,140,248,.09) 0%,transparent 70%)', pointerEvents: 'none' }} />

        {/* Brand mark */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, position: 'relative' }}>
          <div style={{
            width: 46, height: 46, borderRadius: 13,
            background: 'linear-gradient(135deg,#3b82f6,#818cf8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 28px rgba(59,130,246,.4)', flexShrink: 0,
          }}>
            <I.school size={21} stroke="#fff" />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 800, color: '#f1f5f9', letterSpacing: -.3 }}>DYP University</div>
            <div style={{ fontSize: 11, color: '#64748b' }}>Faculty Appraisal System</div>
          </div>
        </div>

        {/* Headline */}
        <div style={{ marginTop: 64, marginBottom: 40, position: 'relative' }}>
          <div style={{ fontSize: 30, fontWeight: 800, color: '#f1f5f9', lineHeight: 1.18,
            letterSpacing: -.6, marginBottom: 14 }}>
            Admin<br />Portal
          </div>
          <div style={{ fontSize: 13, color: '#64748b', lineHeight: 1.75, maxWidth: 280 }}>
            Centralized control for faculty appraisals across all schools and departments.
          </div>
        </div>

        {/* Feature list */}
        <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 13 }}>
          {FEATURES.map(({ Icon, text }, i) => (
            <div key={text} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              animation: `fadeUp .35s cubic-bezier(.22,1,.36,1) ${200 + i * 70}ms both`,
            }}>
              <div style={{
                width: 34, height: 34, borderRadius: 9, flexShrink: 0,
                background: 'rgba(59,130,246,.1)', border: '1px solid rgba(59,130,246,.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background .2s ease, border-color .2s ease',
              }}>
                <Icon size={15} stroke={C.accent} />
              </div>
              <span style={{ fontSize: 13, color: '#94a3b8' }}>{text}</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ marginTop: 'auto', paddingTop: 40, fontSize: 11, color: '#64748b',
          borderTop: '1px solid rgba(255,255,255,.05)', position: 'relative' }}>
          DY Patil International University · 2024–25 Cycle
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '40px 24px', position: 'relative' }}>
        {/* Subtle glow */}
        <div style={{ position: 'absolute', top: '45%', left: '50%', transform: 'translate(-50%,-50%)',
          width: 480, height: 400, background: 'radial-gradient(ellipse,rgba(59,130,246,.05) 0%,transparent 70%)',
          pointerEvents: 'none' }} />

        <div className="card-appear" style={{ width: '100%', maxWidth: 420, position: 'relative' }}>

          {/* Form header */}
          <div style={{ marginBottom: 34 }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: C.text, letterSpacing: -.5, marginBottom: 7 }}>
              {mfaRequired ? 'Enter Verification Code' : 'Welcome back'}
            </div>
            <div style={{ fontSize: 13, color: C.muted }}>
              {mfaRequired
                ? 'We\'ve sent a 6-digit code to your registered email and phone (if available)'
                : 'Sign in with your admin credentials to continue'}
            </div>
          </div>

          {mfaRequired ? (
            <form onSubmit={handleVerifyOtp} noValidate>
              {/* OTP Code */}
              <div style={{ marginBottom: 24 }}>
                <label style={lbl}>Verification Code</label>
                <input
                  className="ifield"
                  type="text"
                  value={otpCode}
                  onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  maxLength={6}
                  required
                  style={inp}
                />
              </div>

              {/* Error */}
              {error && (
                <div style={{ marginBottom: 20, padding: '11px 14px', borderRadius: 9,
                  background: 'rgba(248,113,113,.09)', border: '1px solid rgba(248,113,113,.22)',
                  color: C.red, fontSize: 13, display: 'flex', alignItems: 'center', gap: 9 }}>
                  <I.x size={14} stroke={C.red} />
                  {error}
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={mfaLoading}
                style={{
                  width: '100%', padding: '13px',
                  background: mfaLoading
                    ? 'rgba(59,130,246,.45)'
                    : 'linear-gradient(135deg,#3b82f6,#2563eb)',
                  color: '#fff', border: 'none', borderRadius: 10,
                  cursor: mfaLoading ? 'default' : 'pointer',
                  fontSize: 14, fontWeight: 700, letterSpacing: .2,
                  boxShadow: mfaLoading ? 'none' : '0 4px 22px rgba(59,130,246,.35)',
                  transition: 'all .2s ease',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9,
                  marginBottom: 12,
                }}>
                {mfaLoading ? <><Spinner /> Verifying…</> : 'Verify Code'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setMfaRequired(false);
                  setOtpCode('');
                  setError('');
                }}
                style={{
                  width: '100%', padding: '12px',
                  background: 'transparent',
                  color: C.muted, border: '1px solid rgba(255,255,255,.08)', borderRadius: 10,
                  cursor: 'pointer', fontSize: 13, fontWeight: 600,
                  transition: 'all .2s ease',
                }}>
                Back to Login
              </button>
            </form>
          ) : (
            <form onSubmit={handleSubmit} noValidate>
              {/* Email */}
              <div style={{ marginBottom: 18 }}>
                <label style={lbl}>Email address</label>
                <input
                  className="ifield"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="admin@dypiu.ac.in"
                  required
                  autoComplete="email"
                  style={inp}
                />
              </div>

              {/* Password */}
              <div style={{ marginBottom: 28 }}>
                <label style={lbl}>Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    className="ifield"
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    autoComplete="current-password"
                    style={{ ...inp, paddingRight: 44 }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(v => !v)}
                    style={{ position: 'absolute', right: 13, top: '50%', transform: 'translateY(-50%)',
                      background: 'none', border: 'none', cursor: 'pointer', padding: 0,
                      color: C.muted, display: 'flex', alignItems: 'center' }}>
                    {showPwd ? <EyeOff /> : <I.eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div style={{ marginBottom: 20, padding: '11px 14px', borderRadius: 9,
                  background: 'rgba(248,113,113,.09)', border: '1px solid rgba(248,113,113,.22)',
                  color: C.red, fontSize: 13, display: 'flex', alignItems: 'center', gap: 9 }}>
                  <I.x size={14} stroke={C.red} />
                  {error}
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%', padding: '13px',
                  background: loading
                    ? 'rgba(59,130,246,.45)'
                    : 'linear-gradient(135deg,#3b82f6,#2563eb)',
                  color: '#fff', border: 'none', borderRadius: 10,
                  cursor: loading ? 'default' : 'pointer',
                  fontSize: 14, fontWeight: 700, letterSpacing: .2,
                  boxShadow: loading ? 'none' : '0 4px 22px rgba(59,130,246,.35)',
                  transition: 'all .2s ease',
                }}>
                {loading ? <><Spinner /> Signing in…</> : 'Sign In'}
              </button>
            </form>
          )}

          {/* Footer note */}
          <div style={{ marginTop: 24, padding: '12px 16px', borderRadius: 10,
            background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.055)',
            fontSize: 12, color: C.muted, lineHeight: 1.6 }}>
            This portal is restricted to administrators only. If you cannot log in, contact IT support.
          </div>
        </div>
      </div>
    </div>
  );
}
