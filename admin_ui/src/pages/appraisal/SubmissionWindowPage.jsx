import { useState, useEffect, useRef } from 'react';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import { useFetch } from '../../hooks/useFetch';
import { Loading, ApiError } from '../../components/LoadingState';
import { inp, lbl, pBtn, oBtn } from '../../constants/styleTokens';
import Badge from '../../components/Badge';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import { I } from '../../components/icons';
import { logAction } from '../../utils/activityLog';

function daysLeft(dateStr) {
  if (!dateStr) return null;
  const diff = new Date(dateStr) - new Date();
  return Math.max(0, Math.ceil(diff / 86400000));
}

function toDateInput(iso) {
  if (!iso) return '';
  return new Date(iso).toISOString().slice(0, 16);
}

export default function SubmissionWindowPage() {
  const [tick, setTick] = useState(0);
  const { data: configs, loading, error } = useFetch(() => api.cycle.list(), [tick]);
  const allConfigs = Array.isArray(configs) ? configs : [];
  const current    = allConfigs[0] ?? null;

  // Tabs state
  const [activeTab, setActiveTab] = useState('window');

  // Window Config State
  const [year,  setYear]  = useState('');
  const [start, setStart] = useState('');
  const [end,   setEnd]   = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  // Year Transition State
  const [fromYear, setFromYear] = useState('2025-2026');
  const [toYear, setToYear] = useState('2026-2027');
  const [loadingTransition, setLoadingTransition] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [errorTransition, setErrorTransition] = useState('');
  
  // Revert Puzzle State
  const [puzzle, setPuzzle] = useState(null);
  const [answer, setAnswer] = useState('');
  const [puzzleLoading, setPuzzleLoading] = useState(false);

  const consoleEndRef = useRef(null);

  // Auto-scroll the terminal logs
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  function appendLog(message, isHeader = false) {
    const time = new Date().toLocaleTimeString();
    const formatted = `[${time}] ${message}`;
    setLogs(prev => [...prev, { text: formatted, isHeader }]);
  }

  useEffect(() => {
    if (current) {
      setYear(current.academic_year ?? '');
      setStart(toDateInput(current.submission_start));
      setEnd(toDateInput(current.submission_end));
      setIsOpen(current.is_open ?? false);

      // Pre-populate transition years based on current configuration
      setFromYear(current.academic_year ?? '2025-2026');
      const curr = current.academic_year ?? '';
      const match = curr.match(/^(\d{4})-(\d{4})$/);
      if (match) {
        const nextStart = parseInt(match[1]) + 1;
        const nextEnd = parseInt(match[2]) + 1;
        setToYear(`${nextStart}-${nextEnd}`);
      } else {
        setToYear('2026-2027');
      }
    }
  }, [current]);

  const handleSave = async () => {
    if (!year.trim()) {
      setMsg({ ok: false, msg: 'Academic year is required.' });
      return;
    }
    setSaving(true); setMsg(null);
    try {
      const payload = {
        is_open: isOpen,
        submission_start: start ? new Date(start).toISOString() : null,
        submission_end:   end   ? new Date(end).toISOString()   : null,
      };
      const exists = allConfigs.find(c => c.academic_year === year.trim());
      if (exists) {
        await api.cycle.update(year.trim(), payload);
      } else {
        await api.cycle.create({ academic_year: year.trim(), ...payload });
      }
      setMsg({ ok: true, msg: 'Window configuration saved.' });
      setTick(t => t + 1);
    } catch (e) {
      setMsg({ ok: false, msg: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (open) => {
    if (!year.trim()) return;
    const exists = allConfigs.find(c => c.academic_year === year.trim());
    if (!exists) {
      setMsg({ ok: false, msg: `No config found for "${year}". Save the window first.` });
      return;
    }
    setSaving(true); setMsg(null);
    try {
      await api.cycle.update(year.trim(), { is_open: open });
      setIsOpen(open);
      setMsg({ ok: true, msg: open ? 'Submission window opened.' : 'Submission window closed.' });
      setTick(t => t + 1);
    } catch (e) {
      setMsg({ ok: false, msg: e.message });
    } finally {
      setSaving(false);
    }
  };

  async function handleSwitch(e) {
    e.preventDefault();
    if (!fromYear.trim() || !toYear.trim()) {
      setErrorTransition('Please specify both source and target academic years.');
      return;
    }

    if (!window.confirm(`Are you sure you want to transition active data from ${fromYear} to ${toYear}? Relational tables for ${fromYear} will be cleared.`)) {
      return;
    }

    setLoadingTransition(true);
    setErrorTransition('');
    setProgress(0);
    setLogs([]);
    appendLog(`Initializing switch transition from ${fromYear} to ${toYear}...`, true);

    try {
      const token = localStorage.getItem('admin_token');
      const response = await fetch('/api/v1/admin/transition/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          from_year: fromYear,
          to_year: toYear
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.user_message || errorData?.detail || `Server error (${response.status})`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported by browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // save trailing line fragment

        for (const line of lines) {
          if (line.trim().startsWith('data: ')) {
            const rawJson = line.replace('data: ', '').trim();
            const data = JSON.parse(rawJson);

            if (data.error) {
              throw new Error(data.error);
            }

            if (data.step) {
              appendLog(data.step);
            }
            if (data.progress !== undefined) {
              setProgress(data.progress);
            }
          }
        }
      }
      appendLog('Transition completed successfully! Active database is ready for the new academic year.', true);
      logAction('transition_executed', 'Academic Year Transition', `Transitioned active database from ${fromYear} to ${toYear}`, { fromYear, toYear });
      setTick(t => t + 1);
    } catch (err) {
      setErrorTransition(err.message || 'An error occurred during year switch.');
      appendLog(`ERR: ${err.message || 'Transition failed.'}`, true);
    } finally {
      setLoadingTransition(false);
    }
  }

  async function handleFetchPuzzle() {
    setPuzzleLoading(true);
    setErrorTransition('');
    setPuzzle(null);
    setAnswer('');
    
    try {
      const token = localStorage.getItem('admin_token');
      const response = await fetch('/api/v1/admin/transition/puzzle', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || data.user_message || 'Failed to fetch authorization puzzle.');
      }
      setPuzzle(data);
    } catch (err) {
      setErrorTransition(err.message);
    } finally {
      setPuzzleLoading(false);
    }
  }

  async function handleRevert(e) {
    e.preventDefault();
    if (!puzzle) return;
    if (!answer.trim()) {
      setErrorTransition('Please provide the puzzle solution to proceed.');
      return;
    }

    if (!window.confirm(`CRITICAL WARNING: You are reverting the active year from ${toYear} to ${fromYear}. Active tables will be cleared and repopulated with ${fromYear} snapshot data. Are you sure?`)) {
      return;
    }

    setLoadingTransition(true);
    setErrorTransition('');
    setProgress(0);
    setLogs([]);
    appendLog(`Initializing reversion from ${toYear} to ${fromYear}...`, true);

    try {
      const token = localStorage.getItem('admin_token');
      const response = await fetch('/api/v1/admin/transition/revert', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          from_year: fromYear,
          to_year: toYear,
          token: puzzle.token,
          answer: answer
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.user_message || errorData?.detail || `Server error (${response.status})`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported by browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.trim().startsWith('data: ')) {
            const rawJson = line.replace('data: ', '').trim();
            const data = JSON.parse(rawJson);

            if (data.error) {
              throw new Error(data.error);
            }

            if (data.step) {
              appendLog(data.step);
            }
            if (data.progress !== undefined) {
              setProgress(data.progress);
            }
          }
        }
      }
      appendLog(`Reversion completed successfully! Active year is restored to ${fromYear}.`, true);
      logAction('revert_executed', 'Academic Year Revert', `Reverted active database from ${toYear} to ${fromYear}`, { fromYear, toYear });
      setPuzzle(null);
      setAnswer('');
      setTick(t => t + 1);
    } catch (err) {
      setErrorTransition(err.message || 'Reversion failed.');
      appendLog(`ERR: ${err.message || 'Reversion failed.'}`, true);
    } finally {
      setLoadingTransition(false);
    }
  }

  const left = daysLeft(end);

  return (
    <div className="page-enter">
      <PageHead title="Submission Window" sub="Control when faculty can submit appraisals or transition the academic year cycle" />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '1px solid rgba(255,255,255,.06)', paddingBottom: 10 }}>
        <button
          onClick={() => setActiveTab('window')}
          style={{
            padding: '8px 16px', borderRadius: 8, border: 'none',
            background: activeTab === 'window' ? 'rgba(59,130,246,.15)' : 'transparent',
            color: activeTab === 'window' ? '#3b82f6' : C.muted,
            fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit',
            transition: 'all .15s ease'
          }}
        >
          Window Settings
        </button>
        <button
          onClick={() => setActiveTab('transition')}
          style={{
            padding: '8px 16px', borderRadius: 8, border: 'none',
            background: activeTab === 'transition' ? 'rgba(59,130,246,.15)' : 'transparent',
            color: activeTab === 'transition' ? '#3b82f6' : C.muted,
            fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit',
            transition: 'all .15s ease'
          }}
        >
          Academic Year Transition
        </button>
      </div>

      {loading && <Loading />}
      {error   && <ApiError message={error} />}

      {!loading && !error && activeTab === 'window' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Card title="Window Configuration" delay={0}>
            <div style={{ marginBottom: 14 }}>
              <label style={lbl}>Academic Year</label>
              <input className="ifield" value={year} onChange={e => setYear(e.target.value)}
                placeholder="e.g. 2025-26" style={inp} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label style={lbl}>Submission Opens</label>
              <input className="ifield" type="datetime-local" value={start}
                onChange={e => setStart(e.target.value)} style={inp} />
            </div>
            <div style={{ marginBottom: 18 }}>
              <label style={lbl}>Submission Closes</label>
              <input className="ifield" type="datetime-local" value={end}
                onChange={e => setEnd(e.target.value)} style={inp} />
            </div>

            {msg && (
              <div style={{ marginBottom: 14, padding: '10px 14px', borderRadius: 8, fontSize: 13,
                color: msg.ok ? C.green : C.red,
                background: msg.ok ? 'rgba(52,211,153,.08)' : 'rgba(248,113,113,.08)',
                border: `1px solid ${msg.ok ? 'rgba(52,211,153,.2)' : 'rgba(248,113,113,.2)'}` }}>
                {msg.msg}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10 }}>
              <button className="act-btn" style={pBtn} onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save Window'}
              </button>
              <button className="act-btn"
                style={{ ...oBtn, color: isOpen ? C.red : C.green,
                  borderColor: isOpen ? 'rgba(248,113,113,.25)' : 'rgba(52,211,153,.25)' }}
                onClick={() => handleToggle(!isOpen)} disabled={saving || !year}>
                {isOpen ? 'Close Now' : 'Open Now'}
              </button>
            </div>
          </Card>

          <Card title="Current Status" delay={60}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{ fontSize: 36, marginBottom: 10 }}>{isOpen ? '🟢' : '🔴'}</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: isOpen ? C.green : C.red, marginBottom: 6 }}>
                Window {isOpen ? 'Open' : 'Closed'}
              </div>
              {year && (
                <Badge color={isOpen ? 'green' : 'red'}>{year}</Badge>
              )}
              {isOpen && end && left !== null && (
                <div style={{ marginTop: 20, padding: '12px 16px', borderRadius: 10, background: 'rgba(52,211,153,.08)', border: '1px solid rgba(52,211,153,.2)' }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: C.text, fontFamily: "'JetBrains Mono',monospace" }}>{left}</div>
                  <div style={{ fontSize: 11, color: C.muted }}>days remaining</div>
                </div>
              )}
              {!isOpen && (
                <div style={{ marginTop: 20, fontSize: 12, color: C.muted }}>
                  Faculty cannot submit appraisals while the window is closed.
                </div>
              )}

              {current && (
                <div style={{ marginTop: 20, textAlign: 'left' }}>
                  {[
                    { l: 'Opens',    v: current.submission_start ? new Date(current.submission_start).toLocaleDateString() : '—' },
                    { l: 'Closes',   v: current.submission_end   ? new Date(current.submission_end).toLocaleDateString()   : '—' },
                    { l: 'Updated',  v: current.updated_at       ? new Date(current.updated_at).toLocaleDateString()       : '—' },
                  ].map(x => (
                    <div key={x.l} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--c-row-border)', fontSize: 12 }}>
                      <span style={{ color: C.muted }}>{x.l}</span>
                      <span style={{ color: C.subtle, fontFamily: "'JetBrains Mono',monospace" }}>{x.v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {!loading && !error && activeTab === 'transition' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} className="page-enter">
          
          {/* Warning caution card */}
          <div style={{
            padding: 16, borderRadius: 10,
            background: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            display: 'flex', gap: 12, alignItems: 'flex-start'
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'rgba(245, 158, 11, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#f59e0b', flexShrink: 0, marginTop: 2
            }}>
              <I.shield size={16} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', textTransform: 'uppercase', letterSpacing: .5 }}>
                ⚠️ Caution: Critical Transition Operations
              </div>
              <div style={{ fontSize: 12, color: C.subtle, marginTop: 4, lineHeight: 1.5 }}>
                Transitioning academic years involves deactivating the current appraisal cycle, archiving all active forms, and clearing live active tables to make space for the new cycle. 
                Reverting (falling back) restores the past year's active records from snapshots, but is dangerous. Ensure you backup your database first.
              </div>
            </div>
          </div>

          {/* Step-by-step Instruction guide box */}
          <div style={{
            padding: 16, borderRadius: 10,
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            display: 'flex', gap: 12, alignItems: 'flex-start'
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#10b981', flexShrink: 0, marginTop: 2
            }}>
              <I.check size={16} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: .5 }}>
                📖 Step-by-Step Transition Guide
              </div>
              <div style={{ fontSize: 12, color: C.subtle, marginTop: 6, lineHeight: 1.6 }}>
                Follow these steps to transition the system to a new academic year:
                <ol style={{ margin: '6px 0 0 16px', padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <li>
                    <strong>Step 1: Save Submission Window Config</strong>: Before starting, make sure the current year configuration is saved. If not, go to the <strong>Submission Window</strong> tab, enter the current year name (e.g. <code>2025-2026</code>), select any mock dates, and click <strong>Save Window</strong>.
                  </li>
                  <li>
                    <strong>Step 2: Backup the Database</strong>: Go to <strong>Developer</strong> &rarr; <strong>Backup & Restore</strong> in the sidebar. Run a backup of the current database to ensure no data is lost.
                  </li>
                  <li>
                    <strong>Step 3: Execute Year Transition</strong>: Under the forms below, type the Current Year (e.g., <code>2025-2026</code>) and the New Year (e.g., <code>2026-2027</code>). Click <strong>Execute Year Transition</strong>.
                    <br />
                    <em>Note: This will automatically close the current year cycle, archive all active submissions into snapshots (visible in the year-by-year selector), and clear active tables for the new cycle.</em>
                  </li>
                  <li>
                    <strong>Step 4: Verify and Open Submission Window</strong>: Go back to the <strong>Submission Window</strong> tab, select the new year (e.g., <code>2026-2027</code>), configure the submission start and end dates, and click <strong>Open Now</strong> to open submissions.
                  </li>
                </ol>
              </div>
            </div>
          </div>

          {/* Outer 2-column layout */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 14 }}>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              
              {/* Year Switch Form Card */}
              <Card title="Switch to New Academic Year">
                <form onSubmit={handleSwitch} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: C.subtle, marginBottom: 6, textTransform: 'uppercase' }}>
                        Current Year (Close)
                      </label>
                      <input
                        type="text"
                        value={fromYear}
                        onChange={e => setFromYear(e.target.value)}
                        placeholder="e.g. 2025-2026"
                        disabled={loadingTransition}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: C.subtle, marginBottom: 6, textTransform: 'uppercase' }}>
                        New Year (Open)
                      </label>
                      <input
                        type="text"
                        value={toYear}
                        onChange={e => setToYear(e.target.value)}
                        placeholder="e.g. 2026-2027"
                        disabled={loadingTransition}
                        style={inputStyle}
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loadingTransition}
                    style={{
                      ...buttonStyle,
                      background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                      boxShadow: '0 4px 12px rgba(59,130,246,.25)',
                      opacity: loadingTransition ? 0.7 : 1
                    }}
                  >
                    <I.refresh size={14} className={loadingTransition ? 'spin' : ''} />
                    {loadingTransition ? 'Executing Transition...' : 'Execute Year Transition'}
                  </button>
                </form>
              </Card>

              {/* Reversion Card - Danger Zone */}
              <Card title="Fallback / Revert to Past Year">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ fontSize: 12.5, color: '#f87171', fontWeight: 600 }}>
                    ⚠️ DANGER ZONE: ONLY ADMIN / DEVELOPER
                  </div>
                  <div style={{ fontSize: 11.5, color: C.subtle, lineHeight: 1.5 }}>
                    This restores the live tables back to the previous academic year. Early-bird data entered in the new year will be buffered in snapshots, but live tables will be overwritten.
                  </div>

                  {!puzzle ? (
                    <button
                      onClick={handleFetchPuzzle}
                      disabled={puzzleLoading || loadingTransition}
                      style={{
                        ...buttonStyle,
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        color: '#ef4444',
                        boxShadow: 'none'
                      }}
                    >
                      <I.lock size={14} />
                      {puzzleLoading ? 'Requesting Authorization...' : 'Request Revert Authorization'}
                    </button>
                  ) : (
                    <form onSubmit={handleRevert} style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 12, borderRadius: 8, background: 'rgba(255,255,255,.01)', border: '1px solid rgba(255,255,255,.05)' }}>
                      <div style={{ fontSize: 12.5, color: C.text, lineHeight: 1.5, fontWeight: 500 }}>
                        <strong>Challenge:</strong> {puzzle.question}
                      </div>

                      <div>
                        <input
                          type="text"
                          value={answer}
                          onChange={e => setAnswer(e.target.value)}
                          placeholder="Enter numerical answer"
                          disabled={loadingTransition}
                          style={inputStyle}
                        />
                      </div>

                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          type="button"
                          onClick={() => setPuzzle(null)}
                          disabled={loadingTransition}
                          style={{
                            ...buttonStyle,
                            background: 'rgba(255,255,255,.05)',
                            border: 'none',
                            color: C.subtle,
                            flex: 1,
                            boxShadow: 'none'
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={loadingTransition || !answer}
                          style={{
                            ...buttonStyle,
                            background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                            color: '#fff',
                            flex: 2,
                            boxShadow: '0 4px 12px rgba(239,68,68,.2)'
                          }}
                        >
                          <I.check size={14} />
                          Confirm Revert
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </Card>

              {errorTransition && (
                <div style={{
                  padding: '12px 14px', borderRadius: 8,
                  background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)',
                  color: '#ef4444', fontSize: 12.5, lineHeight: 1.5
                }}>
                  <div style={{ fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <I.bug size={14} /> Transition Error
                  </div>
                  <div>{errorTransition}</div>
                  {(errorTransition.toLowerCase().includes('not found') || errorTransition.toLowerCase().includes('config')) && (
                    <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(239, 68, 68, 0.15)', color: '#fff' }}>
                      <div style={{ fontWeight: 600, color: '#f87171', marginBottom: 4 }}>How to resolve this:</div>
                      <ol style={{ margin: '4px 0 0 16px', padding: 0, fontSize: 11.5, color: C.subtle, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <li>In the tab above, switch back to <strong>Window Settings</strong>.</li>
                        <li>Create and save academic year <strong>{fromYear}</strong>.</li>
                        <li>Return to this tab and retry.</li>
                      </ol>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Console / Monitor Progress Card */}
            <Card title="Migration Progress Monitor">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                
                {/* Progress bar */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12, fontWeight: 600 }}>
                  <span style={{ color: C.subtle }}>Overall Status</span>
                  <span style={{ color: progress === 100 ? '#10b981' : C.accent }}>{progress}%</span>
                </div>
                <div style={{ background: 'rgba(255,255,255,.05)', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                  <div style={{
                    background: progress === 100 ? '#10b981' : 'linear-gradient(90deg, #3b82f6, #6366f1)',
                    width: `${progress}%`, height: '100%',
                    borderRadius: 4, transition: 'width 0.3s ease'
                  }} />
                </div>

                {/* Console terminal */}
                <div style={{
                  background: '#090d16', border: '1px solid rgba(255,255,255,.05)',
                  borderRadius: 8, height: 260, padding: 12, overflowY: 'auto',
                  fontFamily: "'Courier New', Courier, monospace", fontSize: 11.5,
                  color: '#10b981', display: 'flex', flexDirection: 'column', gap: 6,
                  boxShadow: 'inset 0 4px 18px rgba(0,0,0,.6)'
                }}>
                  {logs.length === 0 ? (
                    <div style={{ color: 'rgba(16,185,129,.35)', fontStyle: 'italic', textAlign: 'center', marginTop: 100 }}>
                      Console idle. Ready for operations.
                    </div>
                  ) : (
                    logs.map((log, i) => (
                      <div key={i} style={{
                        color: log.isHeader ? '#f59e0b' : '#10b981',
                        fontWeight: log.isHeader ? 'bold' : 'normal',
                        borderBottom: log.isHeader && i > 0 ? '1px solid rgba(245,158,11,.15)' : 'none',
                        paddingBottom: log.isHeader && i > 0 ? 4 : 0,
                        marginTop: log.isHeader && i > 0 ? 8 : 0,
                        whiteSpace: 'pre-wrap', lineHeight: 1.4
                      }}>
                        {log.text}
                      </div>
                    ))
                  )}
                  <div ref={consoleEndRef} />
                </div>
              </div>
            </Card>

          </div>
        </div>
      )}
    </div>
  );
}

const inputStyle = {
  width: '100%', padding: '10px 12px', borderRadius: 8,
  background: 'rgba(255,255,255,.03)',
  border: '1px solid rgba(255,255,255,.08)',
  color: '#fff', fontFamily: 'inherit', fontSize: 13,
  outline: 'none', transition: 'border-color .15s',
};

const buttonStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
  width: '100%', padding: '11px 16px', borderRadius: 8,
  color: '#fff', border: 'none', cursor: 'pointer',
  fontSize: 13, fontWeight: 600,
  transition: 'opacity .15s, transform .1s',
};
