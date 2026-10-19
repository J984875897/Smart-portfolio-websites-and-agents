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
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1400,deviceScaleFactor:1,mobile:false});
await call('Page.navigate',{url:'http://127.0.0.1:8501'});
await waitFor("[...document.querySelectorAll('[data-testid=stRadio] label')].some(e=>e.innerText.trim()==='港币利率查验')");
await clickText('[data-testid="stRadio"] label','港币利率查验');
await waitFor("[...document.querySelectorAll('button')].some(e=>e.innerText.trim()==='查验港币利率代理'&&!e.disabled)");
await clickText('button','查验港币利率代理');
await waitFor("document.body.innerText.includes('可用月份 3 / 3')");
await evaluate('document.fonts.ready.then(()=>true)');
const report={completeExpected:true,checks:[]};
for(const width of [1440,720]){
  await call('Emulation.setDeviceMetricsOverride',{width,height:1400,deviceScaleFactor:1,mobile:false});
  await new Promise(r=>setTimeout(r,350));
  const shot=await call('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(new URL('browser_'+width+'.png',output),Buffer.from(shot.data,'base64'));
  report.checks.push(await evaluate(`({viewport:window.innerWidth,bodyWidth:document.body.scrollWidth,errorVisible:!!document.querySelector('[data-testid="stException"]'),icons:[...document.querySelectorAll('[data-testid="stIconMaterial"]')].map(e=>({text:e.textContent,font:getComputedStyle(e).fontFamily}))})`));
}
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1400,deviceScaleFactor:1,mobile:false});
await evaluate(`(()=>{const el=[...document.querySelectorAll('[data-testid="stExpander"] summary')].find(e=>e.textContent.includes('完整证据与结果下载'));if(!el)throw new Error('Evidence expander missing');el.click();})()`);
await waitFor("[...document.querySelectorAll('[data-testid=stDownloadButton]')].some(e=>e.textContent.includes('下载利率查验报告 CSV'))");
report.resultDownloadsPresentBeforeChange=true;
const decisionSelector=await evaluate(`(() => {const el=[...document.querySelectorAll('input')].find(e=>e.value==='2024-03-31T16:00:00+08:00');if(!el)throw new Error('Decision input not found');return 'input[aria-label='+JSON.stringify(el.getAttribute('aria-label'))+']';})()`);
await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(decisionSelector)});el.focus();el.select();})()`);
await call('Input.insertText',{text:'2024-03-31T15:59:59+08:00'});
await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
await waitFor("!document.body.innerText.includes('可用月份 3 / 3')");
report.changedInputClearsOldResult=await evaluate("![...document.querySelectorAll('[data-testid=stDownloadButton]')].some(e=>e.textContent.includes('下载利率查验报告 CSV')||e.textContent.includes('下载港币代理收益 CSV'))");
await clickText('button','查验港币利率代理');
await waitFor("document.body.innerText.includes('可用月份 2 / 3')");
report.immatureExpected=true;
const blocked=await call('Page.captureScreenshot',{format:'png'});
fs.writeFileSync(new URL('browser_blocked.png',output),Buffer.from(blocked.data,'base64'));
report.httpStatus=(await fetch('http://127.0.0.1:8501')).status;
report.healthStatus=(await fetch('http://127.0.0.1:8501/_stcore/health')).status;
report.bodyText=await evaluate('document.body.innerText');
report.passed=report.completeExpected&&report.immatureExpected&&report.resultDownloadsPresentBeforeChange&&report.changedInputClearsOldResult&&report.checks.every(x=>!x.errorVisible&&x.bodyWidth<=x.viewport)&&report.httpStatus===200&&report.healthStatus===200;
fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,checks:report.checks,changedInputClearsOldResult:report.changedInputClearsOldResult,httpStatus:report.httpStatus,healthStatus:report.healthStatus}));
ws.close();
process.exitCode=report.passed?0:1;
