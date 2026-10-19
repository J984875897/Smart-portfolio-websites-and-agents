import fs from 'node:fs';
const output = new URL('./', import.meta.url);
const targets = await (await fetch('http://127.0.0.1:9223/json')).json();
const target = targets.find(t => t.type === 'page');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let sequence = 0;
const pending = new Map();
ws.onmessage = event => {
  const data = JSON.parse(event.data);
  if (pending.has(data.id)) {
    const { resolve, reject } = pending.get(data.id);
    pending.delete(data.id);
    if (data.error) reject(new Error(JSON.stringify(data.error))); else resolve(data.result);
  }
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
  const end = Date.now() + 20000;
  while(Date.now() < end) {
    if(await evaluate(expression)) return;
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error('Timed out: '+expression);
}
async function clickText(selector, text) {
  await evaluate(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.innerText.trim() === ${JSON.stringify(text)}); if(!el) throw new Error('Missing control'); el.click(); return true; })()`);
}
await call('Page.enable');
await call('Emulation.setDeviceMetricsOverride', { width:1440, height:1200, deviceScaleFactor:1, mobile:false });
await call('Page.navigate', {url:'http://127.0.0.1:8501'});
await waitFor("document.body.innerText.includes('研究数据工作台')");
await clickText('[data-testid="stRadio"] label', '港币收益查验');
await waitFor("document.body.innerText.includes('选择数据')");
await clickText('[data-testid="stRadio"] label', '人工测试案例');
await waitFor("document.body.innerText.includes('美元本币收益')");
await waitFor("!!document.querySelector('[data-testid=stSelectbox] button[aria-haspopup=listbox]')");
await evaluate(`document.querySelector('[data-testid="stSelectbox"] button[aria-haspopup="listbox"]').click()`);
await waitFor("!!document.querySelector('[role=option]')");
await clickText('[role=option]', '完整人工汇率案例');
await waitFor("document.body.innerText.includes('2024-12-31 为 7.8')");
await clickText('button', '计算港币收益对照');
await waitFor("document.body.innerText.includes('收益查验结果')");
await evaluate('document.fonts.ready.then(() => true)');
const snapshot = await evaluate(`(() => ({
  title:document.title,
  resultVisible:document.body.innerText.includes('收益查验结果'),
  errorVisible:!!document.querySelector('[data-testid="stException"]'),
  icons:[...document.querySelectorAll('[data-testid="stIconMaterial"]')].map(e => ({text:e.textContent, font:getComputedStyle(e).fontFamily})),
  bodyWidth:document.body.scrollWidth, viewport:window.innerWidth
}))()`);
for (const width of [1440,720]) {
  await call('Emulation.setDeviceMetricsOverride', { width,height:1200,deviceScaleFactor:1,mobile:false });
  await new Promise(r => setTimeout(r, 400));
  const shot = await call('Page.captureScreenshot', {format:'png'});
  fs.writeFileSync(new URL('browser_'+width+'.png',output),Buffer.from(shot.data,'base64'));
}
await call('Emulation.setDeviceMetricsOverride', {width:1440,height:1200,deviceScaleFactor:1,mobile:false});
await evaluate(`document.querySelector('[data-testid="stMain"]').scrollTo(0,document.querySelector('[data-testid="stMain"]').scrollHeight)`);
await new Promise(r => setTimeout(r,400));
const resultShot = await call('Page.captureScreenshot',{format:'png'});
fs.writeFileSync(new URL('browser_result.png',output),Buffer.from(resultShot.data,'base64'));
snapshot.httpStatus=(await fetch('http://127.0.0.1:8501')).status;
snapshot.healthStatus=(await fetch('http://127.0.0.1:8501/_stcore/health')).status;
snapshot.passed=snapshot.resultVisible && !snapshot.errorVisible && snapshot.httpStatus===200 && snapshot.healthStatus===200;
fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify(snapshot,null,2)+'\n');
console.log(JSON.stringify(snapshot,null,2));
ws.close();
process.exitCode=snapshot.passed?0:1;
