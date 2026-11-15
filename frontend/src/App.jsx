import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, AlertCircle, ArrowUpRight, Camera, CheckCircle2, ChevronDown,
  Download, FileImage, History, ImagePlus, Leaf, Loader2, Search,
  Share2, ShieldCheck, Sprout, UploadCloud, X, BarChart3, RefreshCw
} from 'lucide-react';

const API = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const crops = ['Apple', 'Bell Pepper', 'Blueberry', 'Cherry', 'Corn (Maize)', 'Grape', 'Orange', 'Peach', 'Potato', 'Raspberry', 'Soybean', 'Squash', 'Strawberry', 'Tomato'];

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Not provided';
  const n = Number(value);
  return `${Math.round(n <= 1 ? n * 100 : n)}%`;
}
function titleCase(value = '') {
  return String(value).replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}
function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function App() {
  const [page, setPage] = useState('scan');
  const [crop, setCrop] = useState('Tomato');
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [apiStatus, setApiStatus] = useState('checking');
  const [sampleCode, setSampleCode] = useState('');
  const [observer, setObserver] = useState('');
  const [notes, setNotes] = useState('');
  const [scans, setScans] = useState([]);
  const [stats, setStats] = useState({ total_scans: 0, by_crop: [], top_diseases: [] });
  const [loading, setLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [search, setSearch] = useState('');
  const fileRef = useRef(null);

  useEffect(() => {
    checkHealth();
    return () => { if (preview) URL.revokeObjectURL(preview); };
  }, [preview]);

  useEffect(() => {
    if (page === 'history' || page === 'research') loadResearchData();
  }, [page]);

  async function checkHealth() {
    try {
      if (!API) return setApiStatus('offline');
      const response = await fetch(`${API}/api/health`);
      const data = await response.json();
      setApiStatus(response.ok && data.status === 'ok' ? 'ready' : 'offline');
    } catch { setApiStatus('offline'); }
  }

  async function loadResearchData() {
    if (!API) return;
    setLoading(true);
    setHistoryError('');
    try {
      const [scanResponse, statsResponse] = await Promise.all([
        fetch(`${API}/api/scans?limit=500`), fetch(`${API}/api/stats`)
      ]);
      if (!scanResponse.ok || !statsResponse.ok) throw new Error('Could not load research records. Check the backend.');
      const [scanData, statsData] = await Promise.all([scanResponse.json(), statsResponse.json()]);
      setScans(Array.isArray(scanData) ? scanData : []);
      setStats(statsData);
    } catch (err) { setHistoryError(err.message || 'Unable to load research data.'); }
    finally { setLoading(false); }
  }

  function chooseFile(selected) {
    if (!selected) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type)) return setError('Please choose a JPG, PNG or WebP image.');
    if (selected.size > 8 * 1024 * 1024) return setError('Image must be smaller than 8 MB.');
    if (preview) URL.revokeObjectURL(preview);
    setError(''); setResult(null); setFile(selected); setPreview(URL.createObjectURL(selected));
  }

  async function submit(event) {
    event.preventDefault();
    if (!file) return setError('Capture or select a clear leaf image first.');
    if (!API) return setError('The backend address is not configured.');
    setBusy(true); setError(''); setResult(null);
    const body = new FormData();
    body.append('image', file);
    body.append('crop', crop.toLowerCase());
    body.append('sample_code', sampleCode);
    body.append('observer', observer);
    body.append('notes', notes);
    try {
      const response = await fetch(`${API}/api/diagnose`, { method: 'POST', body });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `AI server error (${response.status}).`);
      if (!data.disease || data.confidence === undefined) throw new Error('The AI server returned an incomplete diagnosis.');
      setResult(data);
      loadResearchData();
    } catch (err) { setError(err.message || 'Network error. Check that the backend is running.'); }
    finally { setBusy(false); }
  }

  async function shareResult() {
    if (!result) return;
    const report = `PlantCare AI report\nCrop: ${titleCase(result.crop)}\nPossible issue: ${titleCase(result.disease)}\nConfidence score: ${percent(result.confidence)}\nAI screening only; expert confirmation recommended.`;
    if (navigator.share) {
      try { await navigator.share({ title: 'PlantCare AI scan report', text: report }); } catch {}
    } else {
      try { await navigator.clipboard.writeText(report); alert('Report copied.'); }
      catch { alert(report); }
    }
  }

  const filteredScans = useMemo(() => {
    const term = search.trim().toLowerCase();
    return scans.filter(scan => !term || [scan.crop, scan.disease, scan.sample_code, scan.observer, scan.notes].join(' ').toLowerCase().includes(term));
  }, [scans, search]);

  function exportCsv() {
    if (API) window.open(`${API}/api/export.csv`, '_blank', 'noopener,noreferrer');
  }
  const imageUrl = filename => `${API}/api/images/${encodeURIComponent(filename)}`;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Sprout size={22}/></div><div><b>PlantCare AI</b><small>RESEARCH LAB</small></div></div>
      <div className="side-label">WORKSPACE</div>
      <button className={`nav-item ${page === 'scan' ? 'active' : ''}`} onClick={() => setPage('scan')}><Camera size={18}/> Disease scanner</button>
      <button className={`nav-item ${page === 'history' ? 'active' : ''}`} onClick={() => setPage('history')}><History size={18}/> Scan history</button>
      <button className={`nav-item ${page === 'research' ? 'active' : ''}`} onClick={() => setPage('research')}><BarChart3 size={18}/> Research dashboard</button>
      <div className="sidebar-bottom">
        <div className="privacy-note"><ShieldCheck size={17}/><span>Scan images and research records are stored on your local backend.</span></div>
        <div className="version">PLANTCARE AI · v3.0</div>
      </div>
    </aside>

    <main className="main">
      <header className="topbar">
        <div className="mobile-brand"><Sprout size={20}/> PlantCare AI</div>
        <div className="crumb">Workspace <span>/</span> {page === 'scan' ? 'Disease scanner' : page === 'history' ? 'Scan history' : 'Research dashboard'}</div>
        <div className={`connection ${apiStatus}`}><i/>{apiStatus === 'ready' ? 'AI service connected' : 'Server offline'}</div>
      </header>

      {page === 'scan' && <section className="content">
        <div className="hero"><div><div className="eyebrow"><span className="eyebrow-dot"/> CROP HEALTH INTELLIGENCE</div><h1>Understand what’s<br/><em>affecting your crops.</em></h1><p>Upload a leaf image to screen for possible plant diseases. Successful scans are saved to your local research database.</p></div><div className="hero-art"><div className="art-circle"><Leaf size={72} strokeWidth={1.1}/></div><span className="art-tag">IMAGE · ANALYSE · LEARN</span></div></div>
        <div className="section-heading"><div><span className="step-number">01</span><h2>New plant scan</h2></div><span className="muted">JPG, PNG or WebP · Max 8 MB</span></div>
        <form className="scan-grid" onSubmit={submit}>
          <div className="panel upload-panel">
            <div className="panel-title"><div><FileImage size={18}/><b>Leaf image</b></div><span>REQUIRED</span></div>
            <div className={`dropzone ${preview ? 'has-image' : ''}`} onClick={() => fileRef.current?.click()}>
              {preview ? <><img src={preview} alt="Selected plant leaf"/><div className="replace"><ImagePlus size={16}/> Replace image</div></> : <div className="upload-prompt"><div className="upload-icon"><Camera size={25}/></div><b>Capture or upload a photo</b><span>Tap to open camera or choose from gallery</span><small>Photograph one leaf in natural light.</small></div>}
            </div>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e => chooseFile(e.target.files?.[0])}/>
            <div className="upload-actions">
              <button type="button" className="secondary-btn" onClick={() => fileRef.current?.click()}><Camera size={16}/> Open camera</button>
              <button type="button" className="text-btn" onClick={() => fileRef.current?.click()}><UploadCloud size={16}/> Browse files</button>
              {file && <button type="button" className="clear-btn" onClick={() => { if (preview) URL.revokeObjectURL(preview); setFile(null); setPreview(''); setResult(null); }}>Remove</button>}
            </div>
          </div>
          <div className="panel details-panel">
            <div className="panel-title"><div><Sprout size={18}/><b>Diagnosis settings</b></div><span>SUPPORTED MODEL CROPS</span></div>
            <label>Crop type <sup>*</sup></label><div className="select-wrap"><select value={crop} onChange={e => setCrop(e.target.value)}>{crops.map(item => <option key={item}>{item}</option>)}</select><ChevronDown size={16}/></div>
            <label>Research sample code <span className="optional">OPTIONAL</span></label><input value={sampleCode} onChange={e => setSampleCode(e.target.value)} maxLength={80} placeholder="e.g. TOM-001"/>
            <label>Observer name <span className="optional">OPTIONAL</span></label><input value={observer} onChange={e => setObserver(e.target.value)} maxLength={100} placeholder="Person collecting the sample"/>
            <label>Research notes <span className="optional">OPTIONAL</span></label><textarea value={notes} onChange={e => setNotes(e.target.value)} maxLength={1000} rows={3} placeholder="Location, symptoms, date observed..."/>
            <button className="primary-btn" type="submit" disabled={busy || !file}>{busy ? <><Loader2 className="spin" size={17}/> Analysing image…</> : <>Analyse and save scan <ArrowUpRight size={17}/></>}</button>
            <p className="secure-line"><ShieldCheck size={14}/> Saved locally after successful analysis.</p>
          </div>
        </form>
        {error && <div className="error-banner"><AlertCircle size={18}/><span>{error}</span><button onClick={() => setError('')}><X size={16}/></button></div>}
        {result && <div className="result-panel">
          <div className="result-top"><div><div className="eyebrow">SCAN COMPLETE · SAVED TO HISTORY</div><h2>Analysis report</h2></div><span className="result-badge"><CheckCircle2 size={15}/> Analysis complete</span></div>
          <div className="result-body"><div className="result-image">{preview && <img src={preview} alt="Analysed leaf"/>}</div><div className="result-info">
            <span className="result-label">{result.result_status === 'healthy' ? 'HEALTHY LEAF PREDICTED' : 'POSSIBLE ISSUE IDENTIFIED'}</span><h3>{titleCase(result.disease)}</h3>
            <div className="result-meta"><span>{titleCase(result.crop)}</span><span>·</span><span>{formatDate(result.created_at)}</span></div>
            <div className="confidence"><div><span>Model confidence (estimate)</span><b>{percent(result.confidence)}</b></div><div className="meter"><i style={{width: `${Math.min(100, Math.max(0, Number(result.confidence) * (Number(result.confidence) <= 1 ? 100 : 1) || 0))}%`}}/></div></div>
            {result.treatment?.cure && <div className="guidance"><p><b>Possible action:</b> {result.treatment.cure}</p></div>}
            {result.severity && <p><b>Severity:</b> {titleCase(result.severity)}</p>}{result.pathogen && <p><b>Possible pathogen:</b> {result.pathogen}</p>}
            <div className="caution"><AlertCircle size={16}/><span>AI screening is not a confirmed diagnosis. Consult an agricultural expert before taking treatment action.</span></div>
            <button className="secondary-btn share-btn" onClick={shareResult}><Share2 size={16}/> Share report</button>
          </div></div>
        </div>}
        <div className="bottom-stats"><div><span className="stat-icon"><ShieldCheck size={18}/></span><div><b>{stats.total_scans} saved scans</b><small>Local research database</small></div></div><button onClick={() => setPage('history')}>View scan history <ArrowUpRight size={15}/></button></div>
      </section>}

      {page === 'history' && <section className="content research-content">
        <div className="research-heading"><div><div className="eyebrow">RESEARCH RECORDS</div><h1>Scan <em>history.</em></h1><p>Browse previous diagnoses and saved research details.</p></div><button className="secondary-btn" onClick={loadResearchData}><RefreshCw size={15}/> Refresh</button></div>
        <div className="table-panel">
          <div className="table-head"><div><History size={18}/><b>Saved scans</b><span>{filteredScans.length} records</span></div><div className="searchbox"><Search size={15}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search crop, disease, sample..."/></div></div>
          <div className="table-scroll"><table><thead><tr><th>DATE</th><th>CROP</th><th>PREDICTION</th><th>CONFIDENCE</th><th>SAMPLE CODE</th><th>OBSERVER</th><th>IMAGE</th></tr></thead><tbody>
            {filteredScans.map(scan => <tr key={scan.id}><td>{formatDate(scan.created_at)}</td><td><span className="crop-chip">{titleCase(scan.crop)}</span></td><td>{titleCase(scan.disease)}</td><td>{percent(scan.confidence)}</td><td>{scan.sample_code || '—'}</td><td>{scan.observer || '—'}</td><td><a href={imageUrl(scan.image_filename)} target="_blank" rel="noreferrer">View image</a></td></tr>)}
          </tbody></table></div>
          {loading && <div className="empty-state"><Loader2 className="spin"/> Loading records…</div>}
          {!loading && !historyError && filteredScans.length === 0 && <div className="empty-state"><History size={25}/><b>No matching records</b><span>Try another search term.</span></div>}
        </div>
        {historyError && <div className="error-banner"><AlertCircle size={18}/>{historyError}</div>}
      </section>}

      {page === 'research' && <section className="content research-content">
        <div className="research-heading"><div><div className="eyebrow">RESEARCH OVERVIEW</div><h1>Research <em>dashboard.</em></h1><p>Summary of records saved in your local SQLite database.</p></div><button className="secondary-btn export-btn" onClick={exportCsv}><Download size={15}/> Export CSV</button></div>
        <div className="stats-grid">
          <div className="stat-card"><span>Total scans</span><b>{stats.total_scans ?? 0}</b><small>Saved research records</small></div>
          <div className="stat-card"><span>Crop types recorded</span><b>{stats.by_crop?.length ?? 0}</b><small>Distinct crops in database</small></div>
          <div className="stat-card"><span>Disease labels recorded</span><b>{stats.top_diseases?.length ?? 0}</b><small>Top labels returned by API</small></div>
        </div>
        <div className="stats-grid">
          <div className="table-panel"><div className="table-head"><div><Sprout size={18}/><b>Scans by crop</b></div></div><div className="table-scroll"><table><thead><tr><th>CROP</th><th>RECORDS</th></tr></thead><tbody>{(stats.by_crop || []).map(item => <tr key={item.crop}><td>{titleCase(item.crop)}</td><td>{item.count}</td></tr>)}</tbody></table></div></div>
          <div className="table-panel"><div className="table-head"><div><Activity size={18}/><b>Most recorded predictions</b></div></div><div className="table-scroll"><table><thead><tr><th>PREDICTION</th><th>RECORDS</th></tr></thead><tbody>{(stats.top_diseases || []).map(item => <tr key={item.disease}><td>{titleCase(item.disease)}</td><td>{item.count}</td></tr>)}</tbody></table></div></div>
        </div>
        {loading && <div className="empty-state"><Loader2 className="spin"/> Updating dashboard…</div>}
        {historyError && <div className="error-banner"><AlertCircle size={18}/>{historyError}</div>}
        <p className="research-footnote"><ShieldCheck size={14}/> Statistics describe saved predictions; they do not measure model accuracy.</p>
      </section>}
      <footer>PLANTCARE AI <span>·</span> RESEARCH PROTOTYPE <span>·</span> Verify AI findings with an agricultural expert.</footer>
    </main>
  </div>;
}
