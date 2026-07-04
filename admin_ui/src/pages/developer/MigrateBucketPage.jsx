import { useState } from 'react';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import { I } from '../../components/icons';

export default function MigrateBucketPage() {
  const [oldPattern, setOldPattern] = useState('faculty-appraisal-uploads');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');
  const [results, setResults]       = useState(null);

  async function handleMigrate(e) {
    e.preventDefault();
    if (!oldPattern.trim()) {
      setError('Please provide a pattern to search for.');
      return;
    }

    if (!window.confirm('Are you sure you want to run the migration? This will overwrite URLs in database records.')) {
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const res = await api.developer.migrateUrls(oldPattern);
      setResults(res);
    } catch (err) {
      setError(err.message || 'An error occurred during URL migration.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-enter">
      <PageHead title="GCS URL Migration" sub="Convert hardcoded Google Cloud Storage URLs to portable relative API paths" />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        
        {/* Warning card */}
        <div style={{
          padding: 16, borderRadius: 10,
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          display: 'flex', gap: 12, alignItems: 'flex-start'
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'rgba(239, 68, 68, 0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#ef4444', flexShrink: 0, marginTop: 2
          }}>
            <I.lock size={16} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#ef4444', textTransform: 'uppercase', letterSpacing: .5 }}>
              ⚠️ Caution: Critical DB Operation
            </div>
            <div style={{ fontSize: 12, color: C.subtle, marginTop: 4, lineHeight: 1.5 }}>
              This script performs bulk updates on `appraisal_documents`, `appraisal_snapshots`, `reviewer_snapshots`, and `non_teaching_appraisals` tables. It replaces absolute GCP GCS urls containing the pattern (e.g. `faculty-appraisal-uploads`) with a database-portable path `/api/v1/upload/view/[storage_path]`.
            </div>
            <div style={{ fontSize: 11, color: C.muted, marginTop: 8, fontWeight: 600 }}>
              Ensure you have a recent SQL backup before running this tool in production.
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 14 }}>
          
          {/* Main Action Form Card */}
          <Card title="Migration Settings">
            <form onSubmit={handleMigrate} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: C.subtle, marginBottom: 6, textTransform: 'uppercase', letterSpacing: .5 }}>
                  GCP Bucket Name / Search Pattern
                </label>
                <input
                  type="text"
                  value={oldPattern}
                  onChange={e => setOldPattern(e.target.value)}
                  placeholder="e.g. faculty-appraisal-uploads"
                  disabled={loading}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 8,
                    background: 'rgba(255,255,255,.03)',
                    border: '1px solid rgba(255,255,255,.08)',
                    color: C.text, fontFamily: 'inherit', fontSize: 13,
                    outline: 'none', transition: 'border-color .15s',
                  }}
                  onFocus={e => e.target.style.borderColor = 'rgba(59,130,246,.5)'}
                  onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,.08)'}
                />
                <div style={{ fontSize: 10.5, color: C.muted, marginTop: 5, lineHeight: 1.4 }}>
                  Urls matching `https://storage.googleapis.com/{oldPattern}/` will be rewritten to `/api/v1/upload/view/`.
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  width: '100%', padding: '11px 16px', borderRadius: 8,
                  background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                  color: '#fff', border: 'none', cursor: 'pointer',
                  fontSize: 13, fontWeight: 600,
                  boxShadow: '0 4px 12px rgba(59,130,246,.25)',
                  opacity: loading ? 0.75 : 1,
                  transition: 'opacity .15s, transform .1s',
                }}
              >
                <I.refresh size={14} className={loading ? 'spin' : ''} />
                {loading ? 'Migrating Database Records...' : 'Start URL Migration'}
              </button>
            </form>

            {error && (
              <div style={{
                marginTop: 12, padding: '10px 14px', borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)',
                color: '#ef4444', fontSize: 12,
              }}>
                {error}
              </div>
            )}
          </Card>

          {/* Results Summary Card */}
          <Card title="Migration Summary">
            {!results && !loading && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 0', color: C.muted, gap: 10 }}>
                <I.monitor size={32} stroke="currentColor" style={{ opacity: .3 }} />
                <span style={{ fontSize: 12 }}>Run migration to view results.</span>
              </div>
            )}

            {loading && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 0', color: C.muted, gap: 10 }}>
                <I.refresh size={32} stroke="currentColor" className="spin" style={{ color: C.accent }} />
                <span style={{ fontSize: 12 }}>Scanning database tables...</span>
              </div>
            )}

            {results && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{
                  padding: '10px 12px', borderRadius: 8,
                  background: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  color: '#10b981', fontSize: 12.5, fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 6
                }}>
                  <I.check size={14} /> {results.message}
                </div>

                {[
                  { label: 'Updated Document Links', value: results.updated_documents },
                  { label: 'Updated Form Snapshots', value: results.updated_snapshots },
                  { label: 'Updated Reviewer Snapshots', value: results.updated_reviewer_snapshots },
                  { label: 'Updated Non-Teaching Forms', value: results.updated_non_teaching_appraisals },
                ].map(x => (
                  <div key={x.label} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '11px 0', borderBottom: '1px solid rgba(255,255,255,.05)',
                    fontSize: 13
                  }}>
                    <span style={{ color: C.subtle }}>{x.label}</span>
                    <span style={{ fontWeight: 700, color: C.text }}>{x.value}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

        </div>
      </div>
    </div>
  );
}
