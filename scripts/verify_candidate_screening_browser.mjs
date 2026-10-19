// Offline UI acceptance through the dedicated local Chrome CDP session.
import fs from 'node:fs';
const output = new URL('../outputs/acceptance/S05C/', import.meta.url);
fs.mkdirSync(output, { recursive: true });
const targets = await (await fetch('http://127.0.0.1:9224/json')).json();
const target = targets.find(t => t.type === 'page');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject) => {ws.onopen=resolve;ws.onerror=reject;});
let sequence=0;
const pending=new Map();
ws.onmessage=event=>{
  const data=JSON.parse(event.data);
  if(!pending.has(data.id))return;
  const {resolve,reject}=pending.get(data.id);pending.delete(data.id);
  data.error ? reject(new Error(JSON.stringify(data.error))) : resolve(data.result);
};
function call(method,params={}) {
  return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
}
async function evaluate(expression) {
  const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
async function waitFor(expression) {
  const deadline=Date.now()+30000;
  while(Date.now()<deadline){if(await evaluate(`Boolean(${expression})`))return;await new Promise(r=>setTimeout(r,200));}
  throw new Error('Timeout: '+expression);
}
async function clickRadio(text) {
  await evaluate(`(()=>{const e=[...document.querySelectorAll('[data-testid=stRadio] label')].find(x=>x.innerText.trim()===${JSON.stringify(text)});if(!e)throw new Error('Missing radio');e.click();})()`);
}
async function clickButton(text) {
  await evaluate(`(()=>{const e=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()===${JSON.stringify(text)});if(!e)throw new Error('Missing button');e.click();})()`);
}
async function screenshot(name) {
  const shot=await call('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(new URL(name,output),Buffer.from(shot.data,'base64'));
}
try {
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1200,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:'http://127.0.0.1:8501'});
  await waitFor("document.body.innerText.includes('候选筛选')");
  await clickRadio('候选筛选');
  await waitFor("document.body.innerText.includes('查验数据并筛选')");
  // Explicitly reset the source: the browser may restore previous widget choices.
  await clickRadio('SYNTH 缺月与时间案例');
  await waitFor("document.body.innerText.includes('SYNTH人工五资产') && !document.body.innerText.includes('数量条件通过')");
  await clickRadio('SYNTH 100项边界演示');
  await waitFor("document.body.innerText.includes('SYNTH人工100项案例') && !document.body.innerText.includes('数量条件通过')");
  await evaluate(`(()=>{const box=document.querySelector('input[aria-label^="手动排除"]').closest('[data-testid=stMultiSelect]');box.querySelector('button[aria-label="Clear all"]')?.click();})()`);
  await waitFor(`document.querySelector('input[aria-label^="手动排除"]').closest('[data-testid=stMultiSelect]').querySelectorAll('[data-tag]').length===0`);
  await clickButton('查验数据并筛选');
  await waitFor("document.body.innerText.includes('合格 N = 100')");
  await evaluate('document.fonts.ready.then(()=>true)');
  const checks=[];
  for(const width of [1440,720,390]) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:1200,deviceScaleFactor:1,mobile:false});
    if(width<1000) await evaluate(`(()=>{const sidebar=document.querySelector('[data-testid=stSidebar]');const b=sidebar?.querySelector('[data-testid=stSidebarCollapseButton] button');if(sidebar?.getAttribute('aria-expanded')==='true'&&b)b.click();})()`);
    await new Promise(r=>setTimeout(r,500));
    await evaluate(`document.querySelector('[data-testid=stMain]').scrollTo(0,0)`);
    await screenshot(`inputs_${width}.png`);
    await evaluate(`(()=>{const h=[...document.querySelectorAll('h3')].find(e=>e.innerText.includes('数量条件'));if(h)h.scrollIntoView({block:'start'});})()`);
    const state=await evaluate(`({width:innerWidth,bodyWidth:document.body.scrollWidth,sidebarOpen:document.querySelector('[data-testid=stSidebar]')?.getAttribute('aria-expanded')==='true',exception:!!document.querySelector('[data-testid=stException]'),n100:document.body.innerText.includes('合格 N = 100'),exports:[...document.querySelectorAll('[data-testid=stDownloadButton]')].filter(e=>e.innerText.startsWith('下载筛选')).length})`);
    if(state.exception||state.bodyWidth>width||!state.n100||state.exports!==3||(width<1000&&state.sidebarOpen))throw new Error(JSON.stringify(state));
    await screenshot(`result_${width}.png`);
    checks.push(state);
  }
  // Trigger the browser's actual download, then inspect the downloaded CSV bytes.
  await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:decodeURIComponent(output.pathname)});
  await clickButton('下载筛选产品与原因 CSV');
  const downloaded=new URL('candidate_audit.csv',output);
  const deadline=Date.now()+15000;
  while(!fs.existsSync(downloaded)&&Date.now()<deadline)await new Promise(r=>setTimeout(r,200));
  const csv=fs.readFileSync(downloaded,'utf8');
  if(csv.trim().split('\n').length!==101||!csv.includes('SYNTH_SCREEN_099'))throw new Error('Bad audit export');
  fs.renameSync(downloaded,new URL('browser_candidate_audit.csv',output));
  // Choose one item through the real multiselect input and option list.
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1200,deviceScaleFactor:1,mobile:false});
  await new Promise(r=>setTimeout(r,700));
  const inputPoint=await evaluate(`(()=>{const e=document.querySelector('[data-testid=stMultiSelect] input[aria-label^="手动排除"]').closest('[data-testid=stMultiSelect]').querySelector('button[aria-label="Open"]');if(!e)throw new Error('No exclusion input');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await call('Input.dispatchMouseEvent',{type:'mousePressed',...inputPoint,button:'left',clickCount:1});
  await call('Input.dispatchMouseEvent',{type:'mouseReleased',...inputPoint,button:'left',clickCount:1});
  await waitFor("!!document.querySelector('[role=listbox]')");
  await evaluate(`(()=>{const list=document.querySelector('[role=listbox]');list.scrollTop=list.scrollHeight;})()`);
  await waitFor("[...document.querySelectorAll('[role=option]')].some(e=>e.innerText.includes('SYNTH_SCREEN_099'))");
  await evaluate(`[...document.querySelectorAll('[role=option]')].find(e=>e.innerText.includes('SYNTH_SCREEN_099')).scrollIntoView({block:'nearest'})`);
  await new Promise(r=>setTimeout(r,300));
  const point=await evaluate(`(()=>{const e=[...document.querySelectorAll('[role=option]')].find(e=>e.innerText.startsWith('SYNTH_SCREEN_099'));const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await call('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1});
  await call('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1});
  await waitFor("!document.body.innerText.includes('合格 N = 100')");
  const cleared=await evaluate(`[...document.querySelectorAll('[data-testid=stDownloadButton]')].filter(e=>e.innerText.startsWith('下载筛选')).length===0`);
  if(!cleared)throw new Error('Stale export');
  await clickButton('查验数据并筛选');
  await waitFor("document.body.innerText.includes('合格 N = 99')");
  await evaluate(`(()=>{[...document.querySelectorAll('h3')].find(e=>e.innerText.includes('数量条件')).scrollIntoView({block:'start'});})()`);
  await screenshot('blocked_n99.png');
  const blocked=await evaluate(`({n99:document.body.innerText.includes('合格 N = 99'),blocked:document.body.innerText.includes('候选产品池过小'),oldExportsCleared:${cleared}})`);
  checks.push(blocked);
  fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify(checks,null,2)+'\n');
  console.log(JSON.stringify(checks));
} finally { ws.close(); }
