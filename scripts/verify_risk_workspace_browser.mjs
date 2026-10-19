// Offline UI acceptance through the dedicated local Chrome CDP session.
import fs from 'node:fs';
const output = new URL('../outputs/acceptance/S06C/', import.meta.url);
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
  await call('Page.navigate',{url:'http://127.0.0.1:8502'});
  await waitFor("document.body.innerText.includes('候选筛选')");
  await clickRadio('候选筛选');
  await waitFor("document.body.innerText.includes('查验数据并筛选')");
  await clickRadio('SYNTH 相关性与风险演示');
  await waitFor("document.body.innerText.includes('SYNTH人工风险案例')");
  await clickButton('查验数据并筛选');
  await waitFor("document.body.innerText.includes('计算收益与风险')");
  await clickButton('计算收益与风险');
  await waitFor("document.body.innerText.includes('收益估计') && document.querySelectorAll('[role=tab]').length===4");
  const checks=[];
  async function tab(text) {
    await evaluate(`(()=>{const e=[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.trim()===${JSON.stringify(text)});if(!e)throw new Error('Missing tab');e.click();e.scrollIntoView({block:'start'});})()`);
    await new Promise(r=>setTimeout(r,700));
  }
  for (const width of [1440,720,390]) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:1200,deviceScaleFactor:1,mobile:false});
    if(width<1000) await evaluate(`(()=>{const sidebar=document.querySelector('[data-testid=stSidebar]');const b=sidebar?.querySelector('[data-testid=stSidebarCollapseButton] button');if(sidebar?.getAttribute('aria-expanded')==='true'&&b)b.click();})()`);
    await new Promise(r=>setTimeout(r,400));
    for (const [text,name] of [['收益估计','estimates'],['相关性','correlation'],['风险与分散化','risk'],['方法与导出','exports']]) {
      await tab(text);
      await screenshot(`${name}_${width}.png`);
      const state=await evaluate(`({width:innerWidth,bodyWidth:document.body.scrollWidth,exception:!!document.querySelector('[data-testid=stException]'),tabs:[...document.querySelectorAll('[role=tab]')].length,charts:document.querySelectorAll('[data-testid=stVegaLiteChart]').length})`);
      if(state.exception||state.bodyWidth>width||state.tabs!==4) throw new Error(JSON.stringify(state));
      checks.push({tab:text,...state});
    }
  }
  await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:decodeURIComponent(output.pathname)});
  const exported={};
  for (const name of ['correlation.csv','risk_evidence.json','risk_comparison.csv']) {
    const path=new URL(name,output);
    if(fs.existsSync(path))fs.unlinkSync(path);
    await clickButton('下载风险 · '+name);
    const deadline=Date.now()+15000;
    while(!fs.existsSync(path)&&Date.now()<deadline)await new Promise(r=>setTimeout(r,150));
    const content=fs.readFileSync(path,'utf8');
    if(name==='risk_evidence.json') {
      const value=JSON.parse(content);
      if(value.evidence.portfolio_constructed!==false||value.evidence.target_k!==30||value.evidence.positive_weight_count!==100)throw new Error('Wrong preview evidence');
      if(value.sample_metrics.volatility_ann<=0||value.evidence.historical_universe_certified!==false)throw new Error('Wrong risk status');
    }
    if(name==='correlation.csv'&&content.trim().split('\n').length!==101)throw new Error('Wrong correlation dimensions');
    exported[name]={bytes:Buffer.byteLength(content)};
    fs.renameSync(path,new URL('browser_'+name,output));
  }
  // Changing weight mode must remove prior result tabs and all risk exports.
  await clickRadio('上传自定义多头权重 CSV');
  await waitFor("!document.body.innerText.includes('下载风险 ·') && !document.querySelector('[role=tab]')");
  await screenshot('weights_changed_results_cleared.png');
  const ids=Array.from({length:100},(_,i)=>'SYNTH_SCREEN_'+String(i).padStart(3,'0'));
  const good=new URL('browser_weights_valid.csv',output);
  const bad=new URL('browser_weights_invalid.csv',output);
  fs.writeFileSync(good,'asset_id,weight\n'+ids.map((id,i)=>id+','+([1,2].includes(i)?'.5':'0')).join('\n')+'\n');
  fs.writeFileSync(bad,'asset_id,weight\nignored,SYNTH_SCREEN_001,1\n');
  async function upload(path) {
    await evaluate(`(()=>{const box=[...document.querySelectorAll('[data-testid=stFileUploader]')].find(e=>e.innerText.includes('自定义多头权重'));if(!box)throw new Error('Missing weight upload');box.querySelector('input[type=file]').id='ra-browser-upload';})()`);
    const doc=await call('DOM.getDocument');
    const node=await call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#ra-browser-upload'});
    await call('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[decodeURIComponent(path.pathname)]});
  }
  await upload(good);
  await waitFor("document.body.innerText.includes('当前正权重产品数 = 2')");
  await clickButton('计算收益与风险');
  await waitFor("document.querySelectorAll('[role=tab]').length===4");
  await tab('方法与导出');
  const customPath=new URL('risk_evidence.json',output);
  if(fs.existsSync(customPath))fs.unlinkSync(customPath);
  await clickButton('下载风险 · risk_evidence.json');
  await waitFor('true');
  const deadline=Date.now()+15000;
  while(!fs.existsSync(customPath)&&Date.now()<deadline)await new Promise(r=>setTimeout(r,150));
  const custom=JSON.parse(fs.readFileSync(customPath,'utf8'));
  if(custom.evidence.positive_weight_count!==2||Math.abs(custom.sample_metrics.diversification_ratio-1)>1e-10)throw new Error('Custom weight preview mismatch');
  fs.renameSync(customPath,new URL('browser_custom_risk_evidence.json',output));
  await upload(bad);
  await waitFor("document.body.innerText.includes('每行必须恰好两列') && !document.querySelector('[role=tab]') && !document.body.innerText.includes('下载风险 ·')");
  await screenshot('invalid_weights_results_cleared.png');
  fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify({checks,exported,weight_change_clears:true,actual_upload_valid:true,custom_dr_one:true,invalid_upload_clears:true},null,2));
  console.log(JSON.stringify({status:'passed',checks:checks.length,exports:Object.keys(exported),weight_change_clears:true,actual_upload_valid:true,custom_dr_one:true,invalid_upload_clears:true}));
} finally { ws.close(); }
