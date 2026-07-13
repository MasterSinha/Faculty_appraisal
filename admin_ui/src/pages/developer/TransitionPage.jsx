import { useState, useRef, useEffect } from 'react';
import { C } from '../../constants/colors';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import { I } from '../../components/icons';

export default function TransitionPage() {
  const [fromYear, setFromYear] = useState('2025-2026');
  const [toYear, setToYear] = useState('2026-2027');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState('');
  
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

  async function handleSwitch(e) {
    e.preventDefault();
    if (!fromYear.trim() || !toYear.trim()) {
      setError('Please specify both source and target academic years.');
      return;
    }

    if (!window.confirm(`Are you sure you want to transition active data from ${fromYear} to ${toYear}? Relational tables for ${fromYear} will be cleared.`)) {
      return;
    }

    setLoading(true);
    setError('');
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
    } catch (err) {
      setError(err.message || 'An error occurred during year switch.');
      appendLog(`ERR: ${err.message || 'Transition failed.'}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function handleFetchPuzzle() {
    setPuzzleLoading(true);
    setError('');
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
      setError(err.message);
    } finally {
      setPuzzleLoading(false);
    }
  }

  async function handleRevert(e) {
    e.preventDefault();
    if (!puzzle) return;
    if (!answer.trim()) {
      setError('Please provide the puzzle solution to proceed.');
      return;
    }

    if (!window.confirm(`CRITICAL WARNING: You are reverting the active year from ${toYear} to ${fromYear}. Active tables will be cleared and repopulated with ${fromYear} snapshot data. Are you sure?`)) {
      return;
    }

    setLoading(true);
    setError('');
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
      setPuzzle(null);
      setAnswer('');
    } catch (err) {
      setError(err.message || 'Reversion failed.');
      appendLog(`ERR: ${err.message || 'Reversion failed.'}`, true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-enter">
      <PageHead title="Academic Year Transition" sub="Transition the active appraisal cycle database or safely revert back to a past cycle" />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        
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
              Transitioning academic years involves deactivating the current appraisal cycle, archiving all forms, and clearing live active tables to make space for the new cycle. 
              Reverting (falling back) restores the past year's active records from snapshots, but is dangerous. Ensure you backup your database first.
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
                      disabled={loading}
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
                      disabled={loading}
                      style={inputStyle}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    ...buttonStyle,
                    background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                    boxShadow: '0 4px 12px rgba(59,130,246,.25)',
                    opacity: loading ? 0.7 : 1
                  }}
                >
                  <I.refresh size={14} className={loading ? 'spin' : ''} />
                  {loading ? 'Executing Transition...' : 'Execute Year Transition'}
                </button>
              </form>
            </Card>

            {/* Reversion Card - Danger Zone */}
            <Card title="Fallback / Revert to Past Year">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ fontSize: 12.5, color: '#f87171', fontWeight: 600 }}>
                  ⚠️ DANGER ZONE: ONLY SUPER ADMIN
                </div>
                <div style={{ fontSize: 11.5, color: C.subtle, lineHeight: 1.5 }}>
                  This restores the live tables back to the previous academic year. Early-bird data entered in the new year will be buffered in snapshots, but live tables will be overwritten.
                </div>

                {!puzzle ? (
                  <button
                    onClick={handleFetchPuzzle}
                    disabled={puzzleLoading || loading}
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
                        disabled={loading}
                        style={inputStyle}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        onClick={() => setPuzzle(null)}
                        disabled={loading}
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
                        disabled={loading || !answer}
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

            {error && (
              <div style={{
                padding: '10px 14px', borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)',
                color: '#ef4444', fontSize: 12,
              }}>
                {error}
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
    </div>
  );
}

// Reusable styles
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
