import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowUpRight, CheckCircle2, History, ImagePlus, KeyRound, LoaderCircle, LogIn, LogOut, ScanSearch, ShieldCheck, Sparkles, UserCircle, X, Zap } from 'lucide-react';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const signalLabels = {
  curiosity_gap: 'Curiosity gap',
  sensational_wording: 'Sensational wording',
  excessive_capitalization: 'Excessive capitalization',
  question_style: 'Question-style headline',
  exclamation_emphasis: 'Exclamation emphasis',
};

const quickScans = [
  'You will not believe what happened next',
  'The simple habit that changed my mornings',
  'Local team announces a new community project',
];

function scoreLabel(score) {
  if (score >= 0.75) return 'High signal';
  if (score >= 0.45) return 'Watch closely';
  return 'Low signal';
}

function App() {
  const [headline, setHeadline] = useState('');
  const [thumbnail, setThumbnail] = useState(null);
  const [preview, setPreview] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [user, setUser] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('clickbait_token');
    if (!token) return;
    fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then(setUser)
      .catch(() => localStorage.removeItem('clickbait_token'));
  }, []);

  function handleThumbnail(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setThumbnail(file);
    setPreview(URL.createObjectURL(file));
    setResult(null);
  }

  function clearThumbnail() {
    setThumbnail(null);
    setPreview('');
  }

  function useQuickScan(value) {
    setHeadline(value);
    setResult(null);
    setError('');
  }

  async function analyze() {
    if (!headline.trim() && !thumbnail) {
      setError('Add a headline or a thumbnail before analyzing.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    const body = new FormData();
    body.append('headline', headline);
    if (thumbnail) body.append('thumbnail', thumbnail);
    try {
      const token = localStorage.getItem('clickbait_token');
      const response = await fetch(`${API_URL}/predict`, { method: 'POST', body, headers: token ? { Authorization: `Bearer ${token}` } : {} });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The model could not analyze this item.');
      setResult(payload);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <nav className="topbar">
        <div className="brand"><span className="brand-mark"><ScanSearch size={18} /></span><span>Baitbuster</span></div>
        <div className="top-actions"><div className="status"><span className="status-dot" /> Model online <ArrowUpRight size={15} /></div>{user ? <div className="profile-wrap"><button className="profile-button" onClick={() => setProfileOpen(!profileOpen)}><UserCircle size={18} /><span>{user.username}</span></button>{profileOpen && <ProfileMenu user={user} onClose={() => setProfileOpen(false)} onLogout={() => { localStorage.removeItem('clickbait_token'); setUser(null); setProfileOpen(false); }} />}</div> : <button className="auth-button" onClick={() => setAuthOpen(true)}><LogIn size={16} /> Sign in</button>}</div>
      </nav>

      <section className="intro">
        <div className="eyebrow"><Sparkles size={15} /> HEADLINE + VISUAL INTELLIGENCE <span className="eyebrow-line" /></div>
        <h1>Spot the <em>clickbait</em><br />before it spots you.</h1>
        <p>Drop in a headline, a thumbnail, or both. Our AI will analyze the signals and give you a confidence score.</p>
        <div className="intro-meta"><span><Zap size={13} /> Fast signal scan</span><span><span className="meta-dot" /> Explainable output</span><span>01 / 02</span></div>
      </section>

      <section className="workspace">
        <div className="input-panel panel">
          <div className="panel-heading"><div><span className="section-kicker">01 / INPUT</span><h2>Bring something to inspect</h2></div><Activity size={21} /></div>
          <div className="field-label-row"><label className="field-label" htmlFor="headline">Headline or video title</label><span>{headline.length} / 500</span></div>
          <textarea id="headline" value={headline} onChange={(event) => { setHeadline(event.target.value); setResult(null); }} placeholder="Paste the headline you are not quite sure about..." />
          <div className="quick-scans"><span className="quick-label">Try a quick scan</span>{quickScans.map((scan) => <button key={scan} type="button" onClick={() => useQuickScan(scan)}>{scan}</button>)}</div>
          <div className="drop-zone">
            {preview ? <div className="preview-wrap"><img src={preview} alt="Uploaded thumbnail preview" /><button className="icon-button" onClick={clearThumbnail} aria-label="Remove thumbnail"><X size={17} /></button></div> : <label htmlFor="thumbnail" className="upload-label"><ImagePlus size={25} /><span>Drop a thumbnail here</span><small>PNG, JPG or WEBP</small><input id="thumbnail" type="file" accept="image/png,image/jpeg,image/webp" onChange={handleThumbnail} /></label>}
          </div>
          <button className="analyze-button" onClick={analyze} disabled={loading}>{loading ? <><LoaderCircle className="spin" size={18} /> Reading signals...</> : <><ScanSearch size={18} /> Scan for signals <ArrowUpRight size={17} /></>}</button>
          {error && <div className="error-message">{error}</div>}
          <div className="model-note"><CheckCircle2 size={16} /><span>Powered by <strong>DistilBERT</strong> + <strong>CLIP</strong> fusion</span><span className="secure-note">LOCAL MODEL</span></div>
        </div>

        <div className="result-panel panel">
          {!result && !loading && <div className="empty-state"><div className="empty-icon"><ScanSearch size={30} /></div><span className="section-kicker">02 / RESULT</span><h2>Your readout will land here</h2><p>Submit a headline, thumbnail, or both to see the model's confidence and the language signals behind it.</p></div>}
          {loading && <div className="empty-state"><LoaderCircle className="spin" size={34} /><span className="section-kicker">02 / RESULT</span><h2>Comparing two modalities</h2><p>Embedding the words and visual composition, then fusing the evidence.</p></div>}
          {result && <Result result={result} />}
        </div>
      </section>
      <footer><span>CLICKBAIT AI / RESEARCH PREVIEW</span><span>Signals are probabilistic, not a verdict.</span></footer>
      {!user && <button className="guest-note" onClick={() => setAuthOpen(true)}>Continue as guest <ArrowUpRight size={14} /></button>}
      {authOpen && <AuthModal onSuccess={(nextUser, token) => { localStorage.setItem('clickbait_token', token); setUser(nextUser); setAuthOpen(false); }} onClose={() => setAuthOpen(false)} />}
    </main>
  );
}

function ProfileMenu({ user, onClose, onLogout }) {
  const [view, setView] = useState(null);
  return <div className="profile-menu">{!view ? <><div className="profile-summary"><UserCircle size={29} /><div><strong>{user.username}</strong><span>{user.role === 'admin' ? 'Administrator' : 'Member'}</span></div></div><button onClick={() => setView('history')}><History size={15} /> View history</button><button onClick={() => setView('password')}><KeyRound size={15} /> Change password</button>{user.role === 'admin' && <button onClick={() => setView('admin')}><ShieldCheck size={15} /> Admin overview</button>}<button className="logout-button" onClick={onLogout}><LogOut size={15} /> Sign out</button></> : <ProfileDetail view={view} user={user} onBack={() => setView(null)} onClose={onClose} />}</div>;
}

function ProfileDetail({ view, user, onBack }) {
  const [items, setItems] = useState([]);
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({ current_password: '', new_password: '' });
  useEffect(() => { if (view === 'history' || view === 'admin') { const endpoint = view === 'admin' ? '/admin/history' : '/auth/history'; fetch(`${API_URL}${endpoint}`, { headers: { Authorization: `Bearer ${localStorage.getItem('clickbait_token')}` } }).then((response) => response.json()).then(setItems); } }, [view]);
  async function changePassword(event) { event.preventDefault(); const response = await fetch(`${API_URL}/auth/change-password`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('clickbait_token')}` }, body: JSON.stringify(form) }); const payload = await response.json(); setMessage(response.ok ? payload.message : payload.detail); }
  return <div className="profile-detail"><button className="back-button" onClick={onBack}>← Profile</button>{view === 'password' ? <form onSubmit={changePassword}><h3>Change password</h3><input type="password" placeholder="Current password" required value={form.current_password} onChange={(event) => setForm({ ...form, current_password: event.target.value })} /><input type="password" placeholder="New password" required value={form.new_password} onChange={(event) => setForm({ ...form, new_password: event.target.value })} /><button className="small-action">Update password</button></form> : <><h3>{view === 'admin' ? 'All activity' : 'Your history'}</h3>{items.length ? items.slice(0, 8).map((item) => <div className="history-item" key={item.id}><strong>{item.headline || 'Image-only scan'}</strong><span>{item.label} · {(item.clickbait_probability * 100).toFixed(0)}%</span></div>) : <p className="menu-muted">No saved scans yet.</p>}</>}{message && <p className="menu-message">{message}</p>}</div>;
}

function AuthModal({ onSuccess, onClose }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  async function submit(event) { event.preventDefault(); setError(''); const response = await fetch(`${API_URL}/auth/${mode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) }); const payload = await response.json(); if (!response.ok) { setError(payload.detail || 'Unable to authenticate.'); return; } onSuccess(payload.user, payload.token); }
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><div className="auth-modal"><button className="modal-close" onClick={onClose} aria-label="Close"><X size={18} /></button><span className="section-kicker">KEEP YOUR SIGNALS</span><h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2><p>{mode === 'login' ? 'Sign in to keep a private record of every scan.' : 'Your scan history will follow you across sessions.'}</p><form onSubmit={submit}><input placeholder="Username" autoComplete="username" required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /><input type="password" placeholder="Password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /><button className="small-action" type="submit">{mode === 'login' ? 'Sign in' : 'Create account'} <ArrowUpRight size={15} /></button></form>{error && <div className="error-message">{error}</div>}<button className="switch-auth" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>{mode === 'login' ? 'Need an account? Register' : 'Already have an account? Sign in'}</button></div></div>;
}

function Result({ result }) {
  const isClickbait = result.label === 'clickbait';
  return <div className="readout">
    <div className="result-head"><div><span className="section-kicker">02 / RESULT</span><div className={`verdict ${isClickbait ? 'danger' : 'clear'}`}>{isClickbait ? 'Likely clickbait' : 'Likely not clickbait'}</div></div><div className="confidence"><span>CONFIDENCE</span><strong>{(result.confidence * 100).toFixed(0)}%</strong></div></div>
    <div className="probability-hero"><div className="probability-number">{(result.clickbait_probability * 100).toFixed(1)}<small>%</small></div><div><span className="section-kicker">FUSED CLICKBAIT PROBABILITY</span><div className="meter"><span style={{ width: `${result.clickbait_probability * 100}%` }} /></div><p>{isClickbait ? 'The combined evidence leans toward attention engineering.' : 'The combined evidence looks relatively grounded.'}</p></div></div>
    <div className="modality-grid"><Probability title="Headline / DistilBERT" value={result.headline_probability} color="orange" /><Probability title="Thumbnail / CLIP" value={result.thumbnail_probability} color="teal" /></div>
    <div className="signals-heading"><div><span className="section-kicker">EXPLAINABILITY</span><h3>What pushed the score</h3></div><span className="signal-count">{Object.keys(result.signals).length} signals</span></div>
    <div className="signals-list">{Object.entries(result.signals).map(([key, value]) => <div className="signal-row" key={key}><div className="signal-name"><span className={`signal-dot ${value >= 0.45 ? 'active' : ''}`} />{signalLabels[key]}</div><div className="signal-track"><span style={{ width: `${value * 100}%` }} /></div><strong>{scoreLabel(value)}</strong></div>)}</div>
  </div>;
}

function Probability({ title, value, color }) {
  return <div className="modality"><div><span>{title}</span><strong>{(value * 100).toFixed(1)}%</strong></div><div className={`mini-meter ${color}`}><span style={{ width: `${value * 100}%` }} /></div></div>;
}

createRoot(document.getElementById('root')).render(<App />);
