import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowUpRight, CheckCircle2, ImagePlus, LoaderCircle, ScanSearch, Sparkles, Upload, X } from 'lucide-react';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const signalLabels = {
  curiosity_gap: 'Curiosity gap',
  sensational_wording: 'Sensational wording',
  excessive_capitalization: 'Excessive capitalization',
  question_style: 'Question-style headline',
  exclamation_emphasis: 'Exclamation emphasis',
};

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
      const response = await fetch(`${API_URL}/predict`, { method: 'POST', body });
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
        <div className="brand"><span className="brand-mark"><ScanSearch size={18} /></span><span>signal<span className="brand-slash">/</span>clickbait</span></div>
        <div className="status"><span className="status-dot" /> Multimodal analysis <ArrowUpRight size={15} /></div>
      </nav>

      <section className="intro">
        <div className="eyebrow"><Sparkles size={15} /> HEADLINE + VISUAL INTELLIGENCE</div>
        <h1>Does it earn<br /><em>your click?</em></h1>
        <p>DistilBERT reads the language. CLIP reads the image. A fusion model weighs both signals and shows its work.</p>
      </section>

      <section className="workspace">
        <div className="input-panel panel">
          <div className="panel-heading"><div><span className="section-kicker">01 / INPUT</span><h2>Bring something to inspect</h2></div><Activity size={21} /></div>
          <label className="field-label" htmlFor="headline">Headline or video title</label>
          <textarea id="headline" value={headline} onChange={(event) => { setHeadline(event.target.value); setResult(null); }} placeholder="Paste the headline you are not quite sure about..." />
          <div className="drop-zone">
            {preview ? <div className="preview-wrap"><img src={preview} alt="Uploaded thumbnail preview" /><button className="icon-button" onClick={clearThumbnail} aria-label="Remove thumbnail"><X size={17} /></button></div> : <label htmlFor="thumbnail" className="upload-label"><ImagePlus size={25} /><span>Drop a thumbnail here</span><small>PNG, JPG or WEBP</small><input id="thumbnail" type="file" accept="image/png,image/jpeg,image/webp" onChange={handleThumbnail} /></label>}
          </div>
          <button className="analyze-button" onClick={analyze} disabled={loading}>{loading ? <><LoaderCircle className="spin" size={18} /> Reading signals...</> : <><ScanSearch size={18} /> Analyze content</>}</button>
          {error && <div className="error-message">{error}</div>}
          <div className="model-note"><CheckCircle2 size={16} /><span>Powered by <strong>DistilBERT</strong> + <strong>CLIP</strong> fusion</span></div>
        </div>

        <div className="result-panel panel">
          {!result && !loading && <div className="empty-state"><div className="empty-icon"><ScanSearch size={30} /></div><span className="section-kicker">02 / RESULT</span><h2>Your readout will land here</h2><p>Submit a headline, thumbnail, or both to see the model's confidence and the language signals behind it.</p></div>}
          {loading && <div className="empty-state"><LoaderCircle className="spin" size={34} /><span className="section-kicker">02 / RESULT</span><h2>Comparing two modalities</h2><p>Embedding the words and visual composition, then fusing the evidence.</p></div>}
          {result && <Result result={result} />}
        </div>
      </section>
      <footer><span>CLICKBAIT AI / RESEARCH PREVIEW</span><span>Signals are probabilistic, not a verdict.</span></footer>
    </main>
  );
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
