import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, AlertCircle, ArrowUpRight, Camera, CheckCircle2, ChevronDown,
  Download, FileImage, FlaskConical, History, ImagePlus, Leaf, Loader2,
  Menu, Search, Share2, ShieldCheck, Sprout, UploadCloud, X
} from 'lucide-react';

const API = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');const crops = [
  // Existing supported crops
  'Apple',
  'Bell Pepper',
  'Blueberry',
  'Cherry',
  'Corn (Maize)',
  'Grape',
  'Orange',
  'Peach',
  'Potato',
  'Raspberry',
  'Soybean',
  'Squash',
  'Strawberry',
  'Tomato',

  // Additional crops
  'Rice',
  'Wheat',
  'Cotton',
  'Chilli',
  'Mustard',
  'Onion',
  'Garlic',
  'Ginger',
  'Turmeric',
  'Brinjal (Eggplant)',
  'Okra (Lady Finger)',
  'Cucumber',
  'Pumpkin',
  'Cabbage',
  'Cauliflower',
  'Banana',
  'Mango',
  'Papaya',
  'Lemon',
  'Guava',
  'Coconut',
  'Tea',
  'Sugarcane',
  'Groundnut',
  'Pulses',
  'Other'
];function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Not provided';
  const n = Number(value);
  return `${Math.round((n <= 1 ? n * 100 : n))}%`;
}
function titleCase(s='') { return String(s).replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()); }

export default function App() {
  const [page, setPage] = useState('scan');
  const [crop, setCrop] = useState('Tomato');
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [sampleCode, setSampleCode] = useState('');
  const [observer, setObserver] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [scans, setScans] = useState([]);
  const [stats, setStats] = useState({total_scans: 0, by_crop: [], top_diseases: []});
  const [apiStatus, setApiStatus] = useState('checking');
  const [query, setQuery] = useState('');
  const fileRef = useRef(null);

  useEffect(() => {
    checkHealth();
    loadResearch();
  }, []);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function checkHealth() {
    try {
      const r = await fetch(`${API}/api/health`);
      const d = await r.json();
setApiStatus(d.status === 'ok' ? 'ready' : 'offline');
    } catch { setApiStatus('offline'); }
  }
  async function loadResearch() {
    try {
      const [s, st] = await Promise.all([fetch(`${API}/api/scans?limit=200`), fetch(`${API}/api/stats`)]);
      if (s.ok) setScans(await s.json());
      if (st.ok) setStats(await st.json());
    } catch { /* API status is displayed in the header */ }
  }
  function chooseFile(f) {
    if (!f) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type)) {
      setError('Please choose a JPG, PNG or WebP image.'); return;
    }
    if (f.size > 8 * 1024 * 1024) { setError('Image must be smaller than 8 MB.'); return; }
    setError(''); setResult(null); setFile(f);
    setPreview(URL.createObjectURL(f));
  }
  async function submit(e) {
    e.preventDefault();
    if (!file) { setError('Capture or select a clear leaf image first.'); return; }
    setBusy(true); setError(''); setResult(null);
    const body = new FormData();
    body.append('image', file);
    body.append('crop', crop.toLowerCase());
    body.append('sample_code', sampleCode);
    body.append('observer', observer);
    body.append('notes', notes);
    try {
      const response = await fetch(`${API}/api/diagnose`, { method: 'POST', body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not analyse this image.');
      setResult(data);
      await loadResearch();
    } catch (err) {
      setError(err.message || 'Network error. Check your internet connection and API server.');
    } finally { setBusy(false); }
  }
  async function shareResult() {
    if (!result) return;
    const text = `PlantCare AI report\nCrop: ${titleCase(result.crop)}\nPossible issue: ${titleCase(result.disease)}\nConfidence: ${percent(result.confidence)}\nNote: AI screening only; expert confirmation recommended.`;
    if (navigator.share) {
      try { await navigator.share({ title: 'PlantCare AI scan report', text }); } catch {}
    } else {
      try { await navigator.clipboard.writeText(text); alert('Report copied. You can paste it into a message.'); }
      catch { alert(text); }
    }
  }
  const filtered = useMemo(() => scans.filter(s =>
    [s.crop, s.disease, s.sample_code, s.observer].join(' ').toLowerCase().includes(query.toLowerCase())
  ), [scans, query]);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Sprout size={22}/></div><div><b>PlantCare AI</b><small>RESEARCH LAB</small></div></div>
      <div className="side-label">WORKSPACE</div>
      <button className={`nav-item ${page==='scan'?'active':''}`} onClick={()=>setPage('scan')}><Camera size={18}/> Disease scanner</button>
      <button className={`nav-item ${page==='research'?'active':''}`} onClick={()=>{setPage('research');loadResearch();}}><FlaskConical size={18}/> Research data</button>
      <div className="sidebar-bottom">
        <div className="privacy-note"><ShieldCheck size={17}/><span>Research records are stored on your configured backend server.</span></div>
        <div className="version">PLANTCARE AI · v1.0</div>
      </div>
    </aside>

    <main className="main">
      <header className="topbar">
        <div className="mobile-brand"><Sprout size={20}/> PlantCare AI</div>
        <div className="crumb">Workspace <span>/</span> {page === 'scan' ? 'Disease scanner' : 'Research data'}</div>
        <div className={`connection ${apiStatus}`}><i/>{apiStatus==='ready'?'AI service connected':apiStatus==='needs-key'?'API key required':apiStatus==='offline'?'Server offline':'Checking server'}</div>
      </header>

      {page === 'scan' ? <section className="content">
        <div className="hero">
          <div>
            <div className="eyebrow"><span className="eyebrow-dot"/> CROP HEALTH INTELLIGENCE</div>
            <h1>Understand what’s<br/><em>affecting your crops.</em></h1>
            <p>Capture a leaf image to screen for possible plant diseases and build a structured research dataset.</p>
          </div>
          <div className="hero-art"><div className="art-circle"><Leaf size={72} strokeWidth={1.1}/></div><span className="art-tag">IMAGE · ANALYSE · LEARN</span></div>
        </div>

        <div className="section-heading"><div><span className="step-number">01</span><h2>New plant scan</h2></div><span className="muted">JPG, PNG or WebP · Max 8 MB</span></div>
        <form className="scan-grid" onSubmit={submit}>
          <div className="panel upload-panel">
            <div className="panel-title"><div><FileImage size={18}/><b>Leaf image</b></div><span>REQUIRED</span></div>
            <div className={`dropzone ${preview?'has-image':''}`} onClick={()=>fileRef.current?.click()}>
              {preview ? <><img src={preview} alt="Selected plant leaf"/><div className="replace"><ImagePlus size={16}/> Replace image</div></> :
                <div className="upload-prompt"><div className="upload-icon"><Camera size={25}/></div><b>Capture or upload a photo</b><span>Tap to open camera or choose from gallery</span><small>For best results, photograph one leaf in natural light.</small></div>}
            </div>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e=>chooseFile(e.target.files?.[0])}/>
            <div className="upload-actions">
              <button type="button" className="secondary-btn" onClick={()=>fileRef.current?.click()}><Camera size={16}/> Open camera</button>
              <button type="button" className="text-btn" onClick={()=>fileRef.current?.click()}><UploadCloud size={16}/> Browse files</button>
              {file && <button type="button" className="clear-btn" onClick={()=>{setFile(null);setPreview('');setResult(null);}}>Remove</button>}
            </div>
          </div>

          <div className="panel details-panel">
            <div className="panel-title"><div><Sprout size={18}/><b>Sample details</b></div><span>RESEARCH METADATA</span></div>
            <label>Crop type <sup>*</sup></label>
            <div className="select-wrap"><select value={crop} onChange={e=>setCrop(e.target.value)}>{crops.map(c=><option key={c}>{c}</option>)}</select><ChevronDown size={16}/></div>
            <label>Sample / field code <span className="optional">OPTIONAL</span></label>
            <input value={sampleCode} onChange={e=>setSampleCode(e.target.value)} placeholder="e.g. RICE-MGD-001"/>
            <label>Observer name <span className="optional">OPTIONAL</span></label>
            <input value={observer} onChange={e=>setObserver(e.target.value)} placeholder="Name of researcher"/>
            <label>Field notes <span className="optional">OPTIONAL</span></label>
            <textarea value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Location area, plant stage, symptoms noticed…" rows="3"/>
            <button className="primary-btn" type="submit" disabled={busy || !file}>{busy?<><Loader2 className="spin" size={17}/> Analysing image…</>:<>Analyse plant image <ArrowUpRight size={17}/></>}</button>
            <p className="secure-line"><ShieldCheck size={14}/> Image sent securely to your backend over your configured connection.</p>
          </div>
        </form>

        {error && <div className="error-banner"><AlertCircle size={18}/><span>{error}</span><button onClick={()=>setError('')}><X size={16}/></button></div>}

        {result && <div className="result-panel">
          <div className="result-top"><div><div className="eyebrow">SCAN COMPLETE</div><h2>Analysis report</h2></div><span className="result-badge"><CheckCircle2 size={15}/> Saved to research data</span></div>
          <div className="result-body">
            <div className="result-image">{preview && <img src={preview} alt="Analysed leaf"/>}</div>
            <div className="result-info">
              <span className="result-label">POSSIBLE ISSUE IDENTIFIED</span>
              <h3>{titleCase(result.disease)}</h3>
              <div className="result-meta"><span>{titleCase(result.crop)}</span><span>·</span><span>{new Date(result.created_at).toLocaleString()}</span></div>
              <div className="confidence"><div><span>Provider confidence</span><b>{percent(result.confidence)}</b></div><div className="meter"><i style={{width: `${Math.min(100, Math.max(0, Number(result.confidence) * (Number(result.confidence)<=1?100:1) || 0))}%`}}/></div></div>
              {result.treatment && <div className="guidance">
                {result.treatment.cure && <p><b>Possible action:</b> {result.treatment.cure}</p>}
                {result.treatment.prevention && <p><b>Prevention:</b> {result.treatment.prevention}</p>}
                {Array.isArray(result.treatment.recommended_sprays) && result.treatment.recommended_sprays.length>0 && <p><b>Provider-listed products:</b> {result.treatment.recommended_sprays.join(', ')}</p>}
              </div>}
              <div className="caution"><AlertCircle size={16}/><span>AI screening is not a confirmed diagnosis. Consult an agricultural expert before taking treatment action.</span></div>
              <button className="secondary-btn share-btn" onClick={shareResult}><Share2 size={16}/> Share report</button>
            </div>
          </div>
        </div>}

        <div className="bottom-stats">
          <div><span className="stat-icon"><Activity size={18}/></span><div><b>{stats.total_scans}</b><small>Research scans saved</small></div></div>
          <div><span className="stat-icon"><Sprout size={18}/></span><div><b>{stats.by_crop.length}</b><small>Crop types recorded</small></div></div>
          <button onClick={()=>{setPage('research');loadResearch();}}>View research records <ArrowUpRight size={16}/></button>
        </div>
      </section> : <section className="content research-content">
        <div className="research-heading"><div><div className="eyebrow">DATA COLLECTION</div><h1>Research <em>dataset.</em></h1><p>Review saved scan records and export your collected observations.</p></div><a className="primary-btn export-btn" href={`${API}/api/export.csv`}><Download size={17}/> Export CSV</a></div>
        <div className="stats-grid">
          <div className="stat-card"><span>Total scans</span><b>{stats.total_scans}</b><small>All saved records</small></div>
          <div className="stat-card"><span>Crop types</span><b>{stats.by_crop.length}</b><small>Distinct crop categories</small></div>
          <div className="stat-card"><span>Latest record</span><b>{scans[0]?new Date(scans[0].created_at).toLocaleDateString():'—'}</b><small>Most recent scan</small></div>
        </div>
        <div className="table-panel">
          <div className="table-head"><div><History size={18}/><b>Scan history</b><span>{filtered.length} records</span></div><div className="searchbox"><Search size={16}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search crop, disease, sample…"/></div></div>
          {filtered.length ? <div className="table-scroll"><table><thead><tr><th>DATE</th><th>CROP</th><th>PREDICTED ISSUE</th><th>CONFIDENCE</th><th>SAMPLE CODE</th></tr></thead><tbody>{filtered.map(s=><tr key={s.id}><td>{new Date(s.created_at).toLocaleDateString()}</td><td><span className="crop-chip">{titleCase(s.crop)}</span></td><td>{titleCase(s.disease)}</td><td>{percent(s.confidence)}</td><td>{s.sample_code || '—'}</td></tr>)}</tbody></table></div> :
            <div className="empty-state"><FlaskConical size={28}/><b>No research records yet</b><span>Complete a plant scan to start collecting your dataset.</span><button className="secondary-btn" onClick={()=>setPage('scan')}>Start first scan</button></div>}
        </div>
        <div className="research-footnote"><ShieldCheck size={16}/> Exported CSV contains metadata. Original images are stored separately in the backend uploads folder.</div>
      </section>}
      <footer>PLANTCARE AI <span>·</span> RESEARCH PROTOTYPE <span>·</span> Always verify AI findings with an agricultural expert.</footer>
    </main>
  </div>;
}
