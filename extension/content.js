const API_URL = 'http://localhost:8000/predict';
const analyzed = new WeakSet();

function addBadge(image, result) {
  const wrapper = document.createElement('span');
  wrapper.textContent = result.label === 'clickbait' ? 'Likely clickbait' : 'Likely not clickbait';
  wrapper.style.cssText = [
    'position:absolute', 'z-index:2147483647', 'top:6px', 'left:6px',
    'padding:4px 7px', 'border-radius:4px', 'font:600 11px sans-serif',
    'color:#fff', `background:${result.label === 'clickbait' ? '#c2410c' : '#047857'}`,
    'box-shadow:0 1px 4px #0008', 'pointer-events:none'
  ].join(';');
  const parent = image.parentElement;
  if (!parent) return;
  if (getComputedStyle(parent).position === 'static') parent.style.position = 'relative';
  parent.appendChild(wrapper);
}

async function analyzeImage(image) {
  if (analyzed.has(image) || !image.currentSrc) return;
  analyzed.add(image);
  try {
    const response = await fetch(image.currentSrc);
    if (!response.ok) return;
    const body = new FormData();
    body.append('thumbnail', await response.blob(), 'thumbnail.jpg');
    const prediction = await fetch(API_URL, { method: 'POST', body });
    if (prediction.ok) addBadge(image, await prediction.json());
  } catch (_error) {
    // A page image may block cross-origin access; skip it quietly.
  }
}

function scanImages() {
  document.querySelectorAll('img').forEach((image) => {
    if (image.naturalWidth >= 160 && image.naturalHeight >= 90) analyzeImage(image);
  });
}

scanImages();
new MutationObserver(scanImages).observe(document.body, { childList: true, subtree: true });