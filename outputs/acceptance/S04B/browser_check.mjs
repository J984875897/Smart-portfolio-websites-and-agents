import fs from 'node:fs';
const output = new URL('./', import.meta.url);
const targets = await (await fetch('http://127.0.0.1:9225/json')).json();
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
await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:new URL('browser_exports/',output).pathname});
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1400,deviceScaleFactor:1,mobile:false});
await call('Page.navigate',{url:'http://127.0.0.1:8501'});
await waitFor("[...document.querySelectorAll('[data-testid=stRadio] label')].some(e=>e.innerText.trim()==='因子与官方汇率')");
const root=new URL('../../../data/reference_downloads/runs/',output);
const before=fs.readdirSync(root).sort();
const report={checks:[],runsBefore:before};
await clickText('[data-testid=stRadio] label','因子与官方汇率');
await waitFor("document.querySelector('.st-key-ref_prepare button')");
async function clickKey(key){
  await evaluate(`(()=>{const el=document.querySelector('.st-key-'+${JSON.stringify(key)}+' button');if(!el||el.disabled)throw new Error('Missing/disabled '+${JSON.stringify(key)});el.click();return true;})()`);
}
await clickKey('ref_prepare');
await waitFor("document.querySelector('.st-key-ref_cancel button')");
report.planPreview=await evaluate('document.body.innerText');
await clickKey('ref_cancel');
await waitFor("!document.querySelector('.st-key-ref_start button')");
report.prestartCancel=true;
await clickKey('ref_open');
await waitFor("document.querySelector('.st-key-ref_dataset input')&&document.querySelector('.st-key-ref_table button')");
report.cacheBody=await evaluate('document.body.innerText');
report.activeDataset=await evaluate("document.querySelector('.st-key-ref_dataset input').value");
report.manifestRun=before[0];
await evaluate('document.fonts.ready.then(()=>true)');
for(const width of [1440,720]){
  await call('Emulation.setDeviceMetricsOverride',{width,height:1400,deviceScaleFactor:1,mobile:false});
  await evaluate("document.querySelector('[data-testid=stMain]').scrollTop=0;true");
  await new Promise(r=>setTimeout(r,350));
  const shot=await call('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(new URL('browser_'+width+'.png',output),Buffer.from(shot.data,'base64'));
  report.checks.push(await evaluate(`({viewport:window.innerWidth,bodyWidth:document.body.scrollWidth,errorVisible:!!document.querySelector('[data-testid=stException]'),icons:[...document.querySelectorAll('[data-testid=stIconMaterial]')].map(e=>({text:e.textContent,font:getComputedStyle(e).fontFamily}))})`));
}
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1400,deviceScaleFactor:1,mobile:false});
await evaluate("document.querySelector('.st-key-ref_dataset').scrollIntoView({block:'center'});true");
const tableShot=await call('Page.captureScreenshot',{format:'png'});
fs.writeFileSync(new URL('browser_cache.png',output),Buffer.from(tableShot.data,'base64'));
await clickKey('ref_table');
const manifest=JSON.parse(fs.readFileSync(new URL(before[0]+'/snapshot_manifest.json',root)));
const us=manifest.items.find(i=>i.dataset==='US_FF3');
const exported=new URL('browser_exports/'+us.table_file,output);
for(let i=0;i<60&&!fs.existsSync(exported);i++)await new Promise(r=>setTimeout(r,200));
if(!fs.existsSync(exported))throw new Error('Native CSV download missing');
report.nativeCsvDownloadExact=fs.readFileSync(exported).equals(fs.readFileSync(new URL(before[0]+'/'+us.table_file,root)));
report.runsAfter=fs.readdirSync(root).sort();
report.noNewDownloads=JSON.stringify(report.runsAfter)===JSON.stringify(before);
if(report.checks.some(c=>c.errorVisible||c.viewport!==c.bodyWidth)||!report.noNewDownloads||!report.nativeCsvDownloadExact)throw new Error('Browser acceptance failed');
fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({checks:report.checks,prestartCancel:report.prestartCancel,nativeCsvDownloadExact:report.nativeCsvDownloadExact,noNewDownloads:report.noNewDownloads}));
ws.close();
