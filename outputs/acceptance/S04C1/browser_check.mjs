import fs from 'node:fs';

const output = new URL('./', import.meta.url);
const targets = await (await fetch('http://127.0.0.1:9226/json')).json();
const target = targets.find(t => t.type === 'page');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let sequence = 0;
const pending = new Map();
ws.onmessage = event => {
  const data = JSON.parse(event.data);
  if (pending.has(data.id)) {
    const {resolve, reject} = pending.get(data.id);
    pending.delete(data.id);
    if (data.error) reject(new Error(JSON.stringify(data.error))); else resolve(data.result);
  }
};
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    ws.send(JSON.stringify({id, method, params}));
  });
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
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
async function clickText(selector, label) {
  await evaluate(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.innerText.trim() === ${JSON.stringify(label)}); if (!el) throw new Error('Missing control'); el.click(); return true; })()`);
}
async function clickKey(key) {
  await evaluate(`(() => { const el = document.querySelector('.st-key-' + ${JSON.stringify(key)} + ' button'); if (!el || el.disabled) throw new Error('Missing/disabled control'); el.click(); return true; })()`);
}
async function clickElement(selector) {
  const point = await evaluate(`(() => { const el=document.querySelector(${JSON.stringify(selector)}); el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
  await call('Input.dispatchMouseEvent', {type:'mousePressed', button:'left', clickCount:1, ...point});
  await call('Input.dispatchMouseEvent', {type:'mouseReleased', button:'left', clickCount:1, ...point});
}
const runsRoot = new URL('../../../data/downloads/runs/', output);
const runsBefore = fs.readdirSync(runsRoot).sort();
const report = {checks: [], runsBefore};
const downloads = new URL('browser_exports/run-' + Date.now() + '/', output);
fs.mkdirSync(downloads, {recursive: true});
await call('Page.enable');
await call('Browser.setDownloadBehavior', {behavior:'allow', downloadPath: downloads.pathname});
await call('Emulation.setDeviceMetricsOverride', {width:1440, height:1400, deviceScaleFactor:1, mobile:false});
await call('Page.navigate', {url:'http://127.0.0.1:8501'});
await waitFor("[...document.querySelectorAll('[data-testid=stRadio] label')].some(e => e.innerText.trim() === '日线月度查验')");
await clickText('[data-testid=stRadio] label', '日线月度查验');
await waitFor("document.querySelector('.st-key-dm_compute button')");
report.defaultHasNoResult = !(await evaluate("Boolean(document.querySelector('.st-key-dm_download_returns button'))"));
await clickElement('.st-key-dm_confirm label');
await waitFor("document.querySelector('.st-key-dm_confirm input').checked");
await clickKey('dm_compute');
await waitFor("document.querySelector('.st-key-dm_download_returns button')");
report.completeBody = await evaluate('document.body.innerText');
await evaluate('document.fonts.ready.then(() => true)');
for (const width of [1440, 720]) {
  await call('Emulation.setDeviceMetricsOverride', {width, height:1400, deviceScaleFactor:1, mobile:false});
  await evaluate("document.querySelector('[data-testid=stMain]').scrollTop = 0; true");
  await new Promise(resolve => setTimeout(resolve, 400));
  const shot = await call('Page.captureScreenshot', {format:'png'});
  fs.writeFileSync(new URL('browser_' + width + '.png', output), Buffer.from(shot.data, 'base64'));
  report.checks.push(await evaluate(`({viewport:window.innerWidth,bodyWidth:document.body.scrollWidth,errorVisible:!!document.querySelector('[data-testid=stException]'),icons:[...document.querySelectorAll('[data-testid=stIconMaterial]')].map(e=>({text:e.textContent,font:getComputedStyle(e).fontFamily}))})`));
}
await call('Emulation.setDeviceMetricsOverride', {width:1440, height:1600, deviceScaleFactor:1, mobile:false});
await evaluate("document.querySelector('[data-testid=stExpander] summary').click(); true");
await evaluate("document.querySelector('.st-key-dm_download_returns').scrollIntoView({block:'center'}); true");
await clickKey('dm_download_returns');
const exported = new URL('returns.csv', downloads);
for (let count=0; count<60 && !fs.existsSync(exported); count++) await new Promise(resolve => setTimeout(resolve, 200));
if (!fs.existsSync(exported)) throw new Error('Native CSV download missing');
report.nativeCsvDownloaded = true;
report.nativeCsvPath = exported.pathname;
fs.writeFileSync(new URL('browser_exports/verified_returns.csv', output), fs.readFileSync(exported));
await evaluate("document.querySelector('[data-testid=stMain]').scrollTop = 430; true");
const resultShot = await call('Page.captureScreenshot', {format:'png'});
fs.writeFileSync(new URL('browser_result.png', output), Buffer.from(resultShot.data, 'base64'));
// Changing confirmation must withdraw every old result download before recompute.
await clickElement('.st-key-dm_confirm label');
await waitFor("!document.querySelector('.st-key-dm_download_returns button')");
report.confirmationWithdrawsResult = true;
await clickKey('dm_compute');
await waitFor("document.querySelector('.st-key-dm_download_returns button')");
report.unconfirmedBody = await evaluate('document.body.innerText');
report.unconfirmedMetrics = await evaluate("[...document.querySelectorAll('[data-testid=stMetric]')].map(e => e.innerText)");
report.unconfirmedCheckbox = await evaluate("document.querySelector('.st-key-dm_confirm input').checked");
if (report.unconfirmedCheckbox || !report.unconfirmedMetrics.some(text => /可预览收益月数\s+0/.test(text))) throw new Error('Unconfirmed block not visible');
await evaluate("document.querySelector('[data-testid=stMain]').scrollTop = 430; true");
const blockedShot = await call('Page.captureScreenshot', {format:'png'});
fs.writeFileSync(new URL('browser_blocked.png', output), Buffer.from(blockedShot.data, 'base64'));
report.runsAfter = fs.readdirSync(runsRoot).sort();
report.noNewDownloads = JSON.stringify(report.runsAfter) === JSON.stringify(runsBefore);
if (!report.defaultHasNoResult || !report.noNewDownloads || report.checks.some(c=>c.errorVisible || c.viewport !== c.bodyWidth)) throw new Error('Browser acceptance failed');
fs.writeFileSync(new URL('browser_checks.json', output), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({checks:report.checks, defaultHasNoResult:report.defaultHasNoResult, nativeCsvDownloaded:report.nativeCsvDownloaded, confirmationWithdrawsResult:report.confirmationWithdrawsResult, noNewDownloads:report.noNewDownloads}));
ws.close();
