// Offline browser acceptance; requires a dedicated Chrome CDP on localhost:9224.
import fs from 'node:fs';
const output = new URL('../outputs/acceptance/S04C3/', import.meta.url);
fs.mkdirSync(output, { recursive: true });
const targets = await (await fetch('http://127.0.0.1:9224/json')).json();
const target = targets.find(t => t.type === 'page');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let sequence = 0;
const pending = new Map();
ws.onmessage = event => {
  const data = JSON.parse(event.data);
  if (!pending.has(data.id)) return;
  const { resolve, reject } = pending.get(data.id);
  pending.delete(data.id);
  if (data.error) reject(new Error(JSON.stringify(data.error)));
  else resolve(data.result);
};
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function waitFor(expression) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error('Timed out: ' + expression);
}
async function clickLabel(text) {
  await evaluate(`(() => { const label = [...document.querySelectorAll('[data-testid=stRadio] label')].find(e => e.innerText.trim() === ${JSON.stringify(text)}); if (!label) throw new Error('missing label'); label.click(); })()`);
}
try {
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1200, deviceScaleFactor: 1, mobile: false });
  await call('Page.navigate', { url: 'http://127.0.0.1:8501' });
  await waitFor("document.body.innerText.includes('历史资格查验')");
  await clickLabel('历史资格查验');
  await waitFor("document.body.innerText.includes('SYNTH 时间案例')");
  await clickLabel('SYNTH 时间案例');
  await waitFor("document.body.innerText.includes('本地版本时间通过月数')");
  await evaluate('document.fonts.ready.then(() => true)');
  const checks = [];
  for (const width of [1440, 720]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height: 1200, deviceScaleFactor: 1, mobile: false });
    await new Promise(resolve => setTimeout(resolve, 500));
    const state = await evaluate(`({width: innerWidth, bodyWidth: document.body.scrollWidth, exception: !!document.querySelector('[data-testid=stException]'), metric: document.querySelector('[data-testid=stMetricValue]')?.innerText, downloadCount: document.querySelectorAll('[data-testid=stDownloadButton]').length})`);
    if (state.exception || state.metric !== '1' || state.bodyWidth > width || state.downloadCount !== 2) throw new Error(JSON.stringify(state));
    const shot = await call('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(new URL(`browser_${width}.png`, output), Buffer.from(shot.data, 'base64'));
    checks.push(state);
  }
  fs.writeFileSync(new URL('browser_checks.json', output), JSON.stringify(checks, null, 2) + '\n');
  console.log(JSON.stringify(checks));
} finally {
  ws.close();
}
