import { useState, useRef } from 'react';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import { I } from '../../components/icons';
import { pBtn, oBtn, lbl } from '../../constants/styleTokens';

export default function BackupPage() {
  const [dbLoading, setDbLoading] = useState(false);
  const [dbError, setDbError] = useState('');
  const [dbSuccess, setDbSuccess] = useState(false);
  const [dbFile, setDbFile] = useState(null);

  const [uploadsLoading, setUploadsLoading] = useState(false);
  const [uploadsError, setUploadsError] = useState('');
  const [uploadsSuccess, setUploadsSuccess] = useState(false);
  const [uploadsFile, setUploadsFile] = useState(null);

  const dbInputRef = useRef(null);
  const uploadsInputRef = useRef(null);

  // DB Backup Export
  const handleExportDb = async () => {
    setDbLoading(true);
    setDbError('');
    setDbSuccess(false);
    try {
      const blob = await api.developer.backupDb();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `db_backup_${new Date().toISOString().slice(0, 10)}_${Date.now()}.sql`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setDbError(err.message || 'Failed to download database backup.');
    } finally {
      setDbLoading(false);
    }
  };

  // DB Restore Import
  const handleRestoreDb = async (e) => {
    e.preventDefault();
    if (!dbFile) {
      setDbError('Please select a .sql file to restore.');
      return;
    }
    if (!window.confirm('WARNING: Restoring the database will drop/overwrite all existing data and revert it to the backup state. This action CANNOT be undone. Are you sure you want to proceed?')) {
      return;
    }
    setDbLoading(true);
    setDbError('');
    setDbSuccess(false);
    try {
      await api.developer.restoreDb(dbFile);
      setDbSuccess(true);
      setDbFile(null);
      if (dbInputRef.current) dbInputRef.current.value = '';
    } catch (err) {
      setDbError(err.message || 'Failed to restore database.');
    } finally {
      setDbLoading(false);
    }
  };

  // Uploads Backup Export
  const handleExportUploads = async () => {
    setUploadsLoading(true);
    setUploadsError('');
    setUploadsSuccess(false);
    try {
      const blob = await api.developer.backupUploads();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `uploads_backup_${new Date().toISOString().slice(0, 10)}_${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setUploadsError(err.message || 'Failed to download uploads backup.');
    } finally {
      setUploadsLoading(false);
    }
  };

  // Uploads Restore Import
  const handleRestoreUploads = async (e) => {
    e.preventDefault();
    if (!uploadsFile) {
      setUploadsError('Please select a .zip file to restore.');
      return;
    }
    if (!window.confirm('WARNING: Restoring the uploads directory will overwrite existing files with matching names. Are you sure you want to proceed?')) {
      return;
    }
    setUploadsLoading(true);
    setUploadsError('');
    setUploadsSuccess(false);
    try {
      await api.developer.restoreUploads(uploadsFile);
      setUploadsSuccess(true);
      setUploadsFile(null);
      if (uploadsInputRef.current) uploadsInputRef.current.value = '';
    } catch (err) {
      setUploadsError(err.message || 'Failed to restore uploads folder.');
    } finally {
      setUploadsLoading(false);
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="page-enter">
      <PageHead 
        title="Backup & Restore Manager" 
        sub="Export or import PostgreSQL database dumps and uploaded proof files directly to/from the local system" 
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        
        {/* Banner Warning / Limitation */}
        <div style={{
          padding: '14px 16px', borderRadius: 10,
          background: 'rgba(59, 130, 246, 0.08)',
          border: '1px solid rgba(59, 130, 246, 0.2)',
          display: 'flex', gap: 12, alignItems: 'flex-start'
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'rgba(59, 130, 246, 0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: C.accent, flexShrink: 0, marginTop: 1
          }}>
            <I.bell size={16} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.accent, textTransform: 'uppercase', letterSpacing: .5 }}>
              Browser Upload & Size Limitations
            </div>
            <div style={{ fontSize: 12, color: C.subtle, marginTop: 3, lineHeight: 1.5 }}>
              Web-based file transfers are subject to network timeouts and container memory allocation. 
              Do not use this UI for uploaded folder backups exceeding <strong>500MB</strong>. For large media/file sizes, 
              please use direct server command-line tools (SCP/SFTP and SSH) as described in the system docs.
            </div>
          </div>
        </div>

        {/* 2-Column Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* ======================================================== */}
          {/* DATABASE (PostgreSQL) CARD */}
          {/* ======================================================== */}
          <Card title="PostgreSQL Database" sub="SQL data dumps and schema recovery">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              
              {/* Export DB section */}
              <div>
                <label style={lbl}>Export Database Dump</label>
                <p style={{ fontSize: 12, color: C.muted, margin: '0 0 12px 0', lineHeight: 1.5 }}>
                  Generates a full PostgreSQL database dump containing all tables, appraisal forms, snapshot configurations, and user credentials.
                </p>
                <button 
                  onClick={handleExportDb}
                  disabled={dbLoading}
                  style={{ ...pBtn, width: '100%' }}
                >
                  <I.dl size={14} className={dbLoading ? 'spin' : ''} />
                  {dbLoading ? 'Generating Dump...' : 'Download Database SQL'}
                </button>
              </div>

              {/* Divider */}
              <div style={{ height: 1, background: 'rgba(255,255,255,.05)' }} />

              {/* Import DB section */}
              <div>
                <label style={lbl}>Restore / Import Database</label>
                
                {/* Danger callout */}
                <div style={{
                  padding: '10px 12px', borderRadius: 8,
                  background: 'rgba(248, 113, 113, 0.06)',
                  border: '1px solid rgba(248, 113, 113, 0.2)',
                  fontSize: 11.5, color: C.red, marginBottom: 12, lineHeight: 1.4
                }}>
                  <strong>CRITICAL WARNING:</strong> Restoring database dumps replaces the live schema. All data registered since the backup date will be permanently deleted.
                </div>

                <form onSubmit={handleRestoreDb} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{
                    border: `1.5px dashed ${dbFile ? 'rgba(59,130,246,.4)' : 'rgba(255,255,255,.1)'}`,
                    borderRadius: 8, padding: '16px 12px', textAlign: 'center',
                    background: dbFile ? 'rgba(59,130,246,.02)' : 'rgba(0,0,0,.1)',
                    cursor: 'pointer', transition: 'all .15s'
                  }} onClick={() => dbInputRef.current?.click()}>
                    
                    <input 
                      type="file" 
                      ref={dbInputRef} 
                      accept=".sql" 
                      style={{ display: 'none' }} 
                      onChange={e => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setDbFile(file);
                          setDbError('');
                          setDbSuccess(false);
                        }
                      }}
                    />
                    
                    <I.doc size={20} stroke={dbFile ? C.accent : C.muted} style={{ margin: '0 auto 8px', display: 'block' }} />
                    {dbFile ? (
                      <div>
                        <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{dbFile.name}</span>
                        <span style={{ fontSize: 11, color: C.muted, display: 'block', marginTop: 3 }}>({formatBytes(dbFile.size)})</span>
                      </div>
                    ) : (
                      <div>
                        <span style={{ fontSize: 12.5, color: C.subtle, fontWeight: 500 }}>Click to choose SQL dump file</span>
                        <span style={{ fontSize: 10.5, color: C.muted, display: 'block', marginTop: 3 }}>Only .sql files are allowed</span>
                      </div>
                    )}
                  </div>

                  {dbFile && (
                    <button 
                      type="submit"
                      disabled={dbLoading}
                      style={{ 
                        ...pBtn, 
                        background: 'linear-gradient(135deg, #f87171 0%, #dc2626 100%)',
                        boxShadow: '0 4px 14px rgba(248,113,113,.25)',
                        width: '100%' 
                      }}
                    >
                      <I.refresh size={14} className={dbLoading ? 'spin' : ''} />
                      {dbLoading ? 'Restoring Database...' : 'Restore Database Now'}
                    </button>
                  )}
                </form>

                {dbSuccess && (
                  <div style={{
                    marginTop: 12, padding: '10px 12px', borderRadius: 8,
                    background: 'rgba(52,211,153,.08)', border: '1px solid rgba(52,211,153,.25)',
                    color: C.green, fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 6
                  }}>
                    <I.check size={14} /> Database restored successfully!
                  </div>
                )}

                {dbError && (
                  <div style={{
                    marginTop: 12, padding: '10px 12px', borderRadius: 8,
                    background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.2)',
                    color: C.red, fontSize: 12, lineHeight: 1.4
                  }}>
                    {dbError}
                  </div>
                )}

              </div>
            </div>
          </Card>

          {/* ======================================================== */}
          {/* UPLOADED FILES (ZIP) CARD */}
          {/* ======================================================== */}
          <Card title="Uploaded Proof Files" sub="PDF documents, attachments, and uploads backup">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              
              {/* Export Uploads section */}
              <div>
                <label style={lbl}>Export Uploaded Documents</label>
                <p style={{ fontSize: 12, color: C.muted, margin: '0 0 12px 0', lineHeight: 1.5 }}>
                  Zips the entire storage uploads directory containing all faculty-provided PDF attachments and proof files.
                </p>
                <button 
                  onClick={handleExportUploads}
                  disabled={uploadsLoading}
                  style={{ ...pBtn, width: '100%' }}
                >
                  <I.dl size={14} className={uploadsLoading ? 'spin' : ''} />
                  {uploadsLoading ? 'Creating Zip...' : 'Download Uploads ZIP'}
                </button>
              </div>

              {/* Divider */}
              <div style={{ height: 1, background: 'rgba(255,255,255,.05)' }} />

              {/* Import Uploads section */}
              <div>
                <label style={lbl}>Restore / Import Uploads</label>
                
                {/* Info warning */}
                <div style={{
                  padding: '10px 12px', borderRadius: 8,
                  background: 'rgba(251, 191, 36, 0.05)',
                  border: '1px solid rgba(251, 191, 36, 0.2)',
                  fontSize: 11.5, color: C.yellow, marginBottom: 12, lineHeight: 1.4
                }}>
                  <strong>NOTE:</strong> Restoring uploads will overwrite files with matching names inside the uploads directory. Existing unique files will not be deleted.
                </div>

                <form onSubmit={handleRestoreUploads} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{
                    border: `1.5px dashed ${uploadsFile ? 'rgba(59,130,246,.4)' : 'rgba(255,255,255,.1)'}`,
                    borderRadius: 8, padding: '16px 12px', textAlign: 'center',
                    background: uploadsFile ? 'rgba(59,130,246,.02)' : 'rgba(0,0,0,.1)',
                    cursor: 'pointer', transition: 'all .15s'
                  }} onClick={() => uploadsInputRef.current?.click()}>
                    
                    <input 
                      type="file" 
                      ref={uploadsInputRef} 
                      accept=".zip" 
                      style={{ display: 'none' }} 
                      onChange={e => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setUploadsFile(file);
                          setUploadsError('');
                          setUploadsSuccess(false);
                        }
                      }}
                    />
                    
                    <I.doc size={20} stroke={uploadsFile ? C.accent : C.muted} style={{ margin: '0 auto 8px', display: 'block' }} />
                    {uploadsFile ? (
                      <div>
                        <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{uploadsFile.name}</span>
                        <span style={{ fontSize: 11, color: C.muted, display: 'block', marginTop: 3 }}>({formatBytes(uploadsFile.size)})</span>
                      </div>
                    ) : (
                      <div>
                        <span style={{ fontSize: 12.5, color: C.subtle, fontWeight: 500 }}>Click to choose ZIP backup archive</span>
                        <span style={{ fontSize: 10.5, color: C.muted, display: 'block', marginTop: 3 }}>Only .zip files are allowed</span>
                      </div>
                    )}
                  </div>

                  {uploadsFile && (
                    <button 
                      type="submit"
                      disabled={uploadsLoading}
                      style={{ ...pBtn, width: '100%' }}
                    >
                      <I.refresh size={14} className={uploadsLoading ? 'spin' : ''} />
                      {uploadsLoading ? 'Restoring Uploads...' : 'Restore Uploads Now'}
                    </button>
                  )}
                </form>

                {uploadsSuccess && (
                  <div style={{
                    marginTop: 12, padding: '10px 12px', borderRadius: 8,
                    background: 'rgba(52,211,153,.08)', border: '1px solid rgba(52,211,153,.25)',
                    color: C.green, fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 6
                  }}>
                    <I.check size={14} /> Uploads folder restored successfully!
                  </div>
                )}

                {uploadsError && (
                  <div style={{
                    marginTop: 12, padding: '10px 12px', borderRadius: 8,
                    background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.2)',
                    color: C.red, fontSize: 12, lineHeight: 1.4
                  }}>
                    {uploadsError}
                  </div>
                )}

              </div>
            </div>
          </Card>

        </div>
      </div>
    </div>
  );
}
