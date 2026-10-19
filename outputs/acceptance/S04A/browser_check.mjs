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
    if(await evaluate(`Boolean(${expression})`)) return;
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error('Timed out: '+expression);
}
async function clickText(selector, text) {
  await evaluate(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.innerText.trim() === ${JSON.stringify(text)}); if(!el) throw new Error('Missing control'); el.click(); return true; })()`);
}
await call('Page.enable');
await call('DOM.enable');
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1400,deviceScaleFactor:1,mobile:false});
await call('Page.navigate',{url:'http://127.0.0.1:8501'});
await waitFor("[...document.querySelectorAll('[data-testid=stRadio] label')].some(e=>e.innerText.trim()==='下载与缓存')");
const report={checks:[]};
const runsBefore=fs.readdirSync(new URL('../../../data/downloads/runs/',output)).sort();
// Exercise native browser upload before the cache-to-import handoff.
const uploadFile=new URL('browser_upload.csv',output);
fs.copyFileSync(new URL('../../../tests/fixtures/imports/ten_products.csv',output),uploadFile);
const doc=await call('DOM.getDocument');
const input=await call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'input[type=file]'});
await call('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[uploadFile.pathname]});
await waitFor("document.body.innerText.includes('来源文件：browser_upload.csv')");
report.nativeUploadMounted=true;
await clickText('[data-testid=stRadio] label','下载与缓存');
await waitFor("document.querySelector('.st-key-dl_prepare button')");
async function clickKey(key){
  await evaluate(`(()=>{const el=document.querySelector('.st-key-'+${JSON.stringify(key)}+' button');if(!el||el.disabled)throw new Error('Missing or disabled key '+${JSON.stringify(key)});el.click();return true;})()`);
}
await clickKey('dl_prepare');
await waitFor("document.querySelector('.st-key-dl_cancel button')");
await clickKey('dl_cancel');
await waitFor("!document.querySelector('.st-key-dl_start button')");
report.planCancelled=true;
await clickKey('dl_open');
await waitFor("document.querySelector('.st-key-dl_to_import button')");
report.cacheOpened=true;
await evaluate('document.fonts.ready.then(()=>true)');
for(const width of [1440,720]){
  await call('Emulation.setDeviceMetricsOverride',{width,height:1400,deviceScaleFactor:1,mobile:false});
  await new Promise(r=>setTimeout(r,350));
  const shot=await call('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(new URL('browser_'+width+'.png',output),Buffer.from(shot.data,'base64'));
  report.checks.push(await evaluate(`({viewport:window.innerWidth,bodyWidth:document.body.scrollWidth,errorVisible:!!document.querySelector('[data-testid=stException]'),icons:[...document.querySelectorAll('[data-testid=stIconMaterial]')].map(e=>({text:e.textContent,font:getComputedStyle(e).fontFamily}))})`));
}
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1400,deviceScaleFactor:1,mobile:false});
await clickKey('dl_to_import');
await waitFor("document.body.innerText.includes('来源文件：')&&document.body.innerText.includes('SPY')&&document.querySelector('.st-key-check button')");
report.handoffBody=await evaluate('document.body.innerText');
report.sourceReplaced=!report.handoffBody.includes('来源文件：browser_upload.csv')&&report.handoffBody.includes('import_SPY.csv');
await clickKey('check');
await waitFor("document.querySelector('.st-key-commit button')");
report.importCheckedWithoutSave=true;
await evaluate("document.querySelector('.st-key-kind').scrollIntoView({block:'center'});true");
await waitFor("document.querySelector('.st-key-kind input').value.includes('adjusted_price')");
report.supplier=await evaluate("document.querySelector('.st-key-supplier input').value");
report.kind=await evaluate("document.querySelector('.st-key-kind input').value");
report.handoffReplacedUpload=report.sourceReplaced&&report.kind.includes('adjusted_price')&&report.supplier.includes('Yahoo chart / ')&&report.supplier.includes('raw sha256');
const handoff=await call('Page.captureScreenshot',{format:'png'});
fs.writeFileSync(new URL('browser_import.png',output),Buffer.from(handoff.data,'base64'));
// Open the original mixed outcome as history, preserving its failed SPY row.
await clickText('[data-testid=stRadio] label','下载与缓存');
await waitFor("document.querySelector('.st-key-dl_run input')");
await clickKey('dl_run');
await waitFor("[...document.querySelectorAll('[role=option]')].some(e=>e.textContent.includes('20261016T032413288256Z-59063f7bab694be2b37f76b2ec4f1b51'))");
await evaluate("[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.includes('20261016T032413288256Z-59063f7bab694be2b37f76b2ec4f1b51')).click();true");
await clickKey('dl_open');
await waitFor("document.querySelector('.st-key-dl_symbol input')?.value==='2800.HK'");
report.historicalPartialRunOpened=true;
await evaluate("document.querySelector('.st-key-dl_open').scrollIntoView({block:'start'});true");
const mixed=await call('Page.captureScreenshot',{format:'png'});
fs.writeFileSync(new URL('browser_partial_history.png',output),Buffer.from(mixed.data,'base64'));
const runsAfter=fs.readdirSync(new URL('../../../data/downloads/runs/',output)).sort();
report.noNewUpdateRun=JSON.stringify(runsBefore)===JSON.stringify(runsAfter);
report.httpStatus=(await fetch('http://127.0.0.1:8501')).status;
report.healthStatus=(await fetch('http://127.0.0.1:8501/_stcore/health')).status;
report.passed=report.historicalPartialRunOpened&&report.nativeUploadMounted&&report.planCancelled&&report.cacheOpened&&report.handoffReplacedUpload&&report.importCheckedWithoutSave&&report.noNewUpdateRun&&report.checks.every(x=>!x.errorVisible&&x.bodyWidth<=x.viewport)&&report.httpStatus===200&&report.healthStatus===200;
fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,checks:report.checks,handoffReplacedUpload:report.handoffReplacedUpload,noNewUpdateRun:report.noNewUpdateRun}));
ws.close();process.exitCode=report.passed?0:1;
