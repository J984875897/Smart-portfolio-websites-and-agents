import fs from 'node:fs';
const output = new URL('./', import.meta.url);
const targets = await (await fetch('http://127.0.0.1:9224/json')).json();
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
await waitFor("[...document.querySelectorAll('[data-testid=stRadio] label')].some(e=>e.innerText.trim()==='共同窗口查验')");
await clickText('[data-testid="stRadio"] label', '共同窗口查验');
await waitFor("document.body.innerText.includes('查验共同窗口')");
await waitFor("[...document.querySelectorAll('[data-testid=stRadio] label')].some(e=>e.innerText.trim()==='人工测试案例')");
await clickText('[data-testid="stRadio"] label', '人工测试案例');
await waitFor("[...document.querySelectorAll('button')].some(e=>e.innerText.trim()==='查验共同窗口'&&!e.disabled)");
await clickText('button', '查验共同窗口');
await waitFor("!!document.querySelector('[data-testid=stDataFrame]')");
await evaluate('document.fonts.ready.then(() => true)');
const checks = [];
for (const width of [1440,720]) {
  await call('Emulation.setDeviceMetricsOverride', { width,height:1200,deviceScaleFactor:1,mobile:false });
  await new Promise(r => setTimeout(r, 400));
  const shot = await call('Page.captureScreenshot', {format:'png'});
  fs.writeFileSync(new URL('browser_'+width+'.png',output),Buffer.from(shot.data,'base64'));
  checks.push(await evaluate(`({viewport:window.innerWidth,bodyWidth:document.body.scrollWidth,errorVisible:!!document.querySelector('[data-testid="stException"]'),icons:[...document.querySelectorAll('[data-testid="stIconMaterial"]')].map(e=>({text:e.textContent,font:getComputedStyle(e).fontFamily}))})`));
}
await call('Emulation.setDeviceMetricsOverride', {width:1440,height:1200,deviceScaleFactor:1,mobile:false});
await evaluate(`document.querySelector('[data-testid="stMain"]').scrollTo(0,document.querySelector('[data-testid="stMain"]').scrollHeight)`);
await new Promise(r => setTimeout(r,400));
const resultShot = await call('Page.captureScreenshot',{format:'png'});
fs.writeFileSync(new URL('browser_result.png',output),Buffer.from(resultShot.data,'base64'));
const report = {checks,httpStatus:(await fetch('http://127.0.0.1:8501')).status,healthStatus:(await fetch('http://127.0.0.1:8501/_stcore/health')).status,bodyText:await evaluate('document.body.innerText')};
report.earlyExpected = report.bodyText.includes('通过 1 / 5 资产');
if (report.earlyExpected) {
  await evaluate(`(() => {const el=document.querySelector('input[aria-label="决策时点（香港时间，ISO +08:00）"]');el.focus();el.select();})()`);
  await call('Input.insertText',{text:'2025-02-01T06:00:00+08:00'});
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await waitFor("!document.body.innerText.includes('资产共同窗口摘要')");
  report.changedInputClearsOldResult = true;
  await clickText('button','查验共同窗口');
  await waitFor("document.body.innerText.includes('通过 2 / 5 资产')");
  report.lateExpected = true;
  const lateShot=await call('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(new URL('browser_late.png',output),Buffer.from(lateShot.data,'base64'));
}
report.passed = report.earlyExpected && report.lateExpected && report.changedInputClearsOldResult && checks.every(x=>!x.errorVisible&&x.bodyWidth<=x.viewport)&&report.httpStatus===200&&report.healthStatus===200;
fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
ws.close();
process.exitCode=report.passed?0:1;
