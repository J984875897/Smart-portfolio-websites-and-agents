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

if (!(await evaluate("document.querySelector('.st-key-dh_fx_confirm input').checked"))) await clickElement('.st-key-dh_fx_confirm label');
await waitFor("document.querySelector('.st-key-dh_fx_confirm input').checked");
// Keyboard opening avoids stale mouse coordinates during Streamlit rerender.
await evaluate("document.querySelector('.st-key-dh_fx_case input[role=combobox]').focus(); true");
await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
await waitFor("[...document.querySelectorAll('[role=option]')].some(e=>e.innerText.trim()==='缺期末月')");
await clickText('[role=option]', '缺期末月');
await waitFor("!document.querySelector('.st-key-dh_download_reconciliation button')");
await clickKey('dh_compute');
await waitFor("document.querySelector('.st-key-dh_download_reconciliation button')");
const metrics = await evaluate("[...document.querySelectorAll('[data-testid=stMetric]')].map(e=>e.innerText)");
if(!metrics.some(t=>/可预览港币月数\s+0/.test(t))) throw new Error('Missing FX not blocked');
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1600,deviceScaleFactor:1,mobile:false});
await waitFor('window.innerWidth===1440');
await evaluate("document.querySelector('[data-testid=stMetric]').scrollIntoView({block:'start'}); document.fonts.ready.then(()=>true)");
await evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))");
const shot=await call('Page.captureScreenshot',{format:'png'});
fs.writeFileSync(new URL('browser_missing_fx.png',output),Buffer.from(shot.data,'base64'));
const report={missingFxBlocks:true,metrics,frameworkError:await evaluate("!!document.querySelector('[data-testid=stException]')")};
if(report.frameworkError)throw new Error('Framework error');
fs.writeFileSync(new URL('browser_extra_checks.json',output),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
ws.close();
