// Real Chromium acceptance against the local workbench; no market requests.
import fs from 'node:fs';
const output = new URL('../outputs/acceptance/UI_REDESIGN/', import.meta.url);
fs.mkdirSync(output, {recursive:true});
const uiURL = process.env.WORKSPACE_UI_URL || 'http://127.0.0.1:8502/';
const target = await (await fetch('http://127.0.0.1:9224/json/new?about:blank', {method:'PUT'})).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let sequence=0;
const pending=new Map();
ws.onmessage=event=>{
  const data=JSON.parse(event.data);
  if (!pending.has(data.id)) return;
  const {resolve,reject}=pending.get(data.id); pending.delete(data.id);
  data.error ? reject(new Error(JSON.stringify(data.error))) : resolve(data.result);
};
function call(method,params={}) {
  return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
}
async function evaluate(expression) {
  const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(expression) {
  const deadline=Date.now()+45000;
  while(Date.now()<deadline){if(await evaluate(`Boolean(${expression})`))return;await pause(150);}
  throw new Error('Timeout: '+expression+'\n'+await evaluate('document.body.innerText'));
}
async function clickButton(text) {
  await evaluate(`(()=>{const e=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()===${JSON.stringify(text)});if(!e)throw new Error('Missing button '+${JSON.stringify(text)});e.click();})()`);
  await pause(650);
}
async function screenshot(name) {
  const shot=await call('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(new URL(name,output),Buffer.from(shot.data,'base64'));
}
async function expandInputs() {
  await evaluate(`(()=>{for(const d of document.querySelectorAll('details')) if(d.innerText.includes('研究输入与产品范围'))d.open=true;})()`);
}
async function radio(text) {
  await evaluate(`(()=>{const e=[...document.querySelectorAll('[data-testid=stRadio] label')].find(x=>x.innerText.trim()===${JSON.stringify(text)});if(!e)throw new Error('Missing radio');e.click();})()`);
  await pause(700);
}
const checks=[];
async function checkWidths(route) {
  for(const width of [1440,720,390]) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});
    if(width<1000) await evaluate(`(()=>{const sidebar=document.querySelector('[data-testid=stSidebar]');const b=sidebar?.querySelector('[data-testid=stSidebarCollapseButton] button');if(sidebar?.getAttribute('aria-expanded')==='true'&&b)b.click();})()`);
    await pause(350);
    await evaluate(`document.querySelector('[data-testid=stMain]')?.scrollTo(0,0)`);
    const state=await evaluate(`(()=>{const main=document.querySelector('[data-testid=stMain]');const texts=[...main.querySelectorAll('h1,h2,h3,p')].filter(e=>{const r=e.getBoundingClientRect();return e.innerText.trim()&&r.width>0&&r.height>0&&r.top>=0&&r.top<innerHeight;}); const overlaps=[];for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){const a=texts[i],b=texts[j];if(a.contains(b)||b.contains(a))continue;const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();if(Math.min(x.right,y.right)-Math.max(x.left,y.left)>3&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>3)overlaps.push([a.innerText,b.innerText]);}return {width:innerWidth,body_width:document.body.scrollWidth,main_width:main.clientWidth,main_scroll_width:main.scrollWidth,page_overflow:document.body.scrollWidth>innerWidth||main.scrollWidth>main.clientWidth,exception:!!document.querySelector('[data-testid=stException]'),text_overlap:overlaps.length>0,overlaps};})()`);
    await screenshot(`${route}_${width}.png`);
    checks.push({route,...state});
    if(state.exception||state.page_overflow||state.text_overlap) throw new Error(JSON.stringify(state));
  }
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
}
try {
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:uiURL});
  await waitFor("document.body.innerText.includes('本次研究档案')");
  await checkWidths('overview');
  await clickButton('01 准备数据');
  await waitFor("document.querySelector('h1')?.innerText==='准备数据'");
  await checkWidths('prepare_data');
  await clickButton('02 核对资格');
  await waitFor("document.querySelector('h1')?.innerText==='核对资格'");
  await checkWidths('eligibility');
  await clickButton('研究总览');
  await waitFor("document.body.innerText.includes('本次研究档案')");
  await clickButton('试用人工演示');
  await waitFor("document.body.innerText.includes('SYNTH人工风险案例')");
  await checkWidths('screen_candidates');
  await clickButton('查验数据并筛选');
  await waitFor("document.body.innerText.includes('数量条件通过；尚未生成组合')");
  await clickButton('前往收益与风险');
  await waitFor("document.querySelector('h1')?.innerText==='收益与风险'");
  await clickButton('计算收益与风险');
  await waitFor("document.querySelectorAll('[role=tab]').length===4");
  await checkWidths('risk_preview');
  await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:decodeURIComponent(output.pathname)});
  await evaluate(`(()=>{const e=[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText==='方法与导出');e.click();})()`);
  const exportPath=new URL('risk_evidence.json',output);
  if(fs.existsSync(exportPath))fs.unlinkSync(exportPath);
  await clickButton('下载风险 · risk_evidence.json');
  const deadline=Date.now()+15000;
  while(!fs.existsSync(exportPath)&&Date.now()<deadline)await pause(150);
  const exported=JSON.parse(fs.readFileSync(exportPath,'utf8'));
  if(exported.evidence.target_k!==30||exported.evidence.portfolio_constructed!==false)throw new Error('Wrong export');
  checks.push({route:'risk_preview',download:'risk_evidence.json',bytes:fs.statSync(exportPath).size,target_k:30,portfolio_constructed:false});
  await clickButton('研究总览');
  await waitFor("document.body.innerText.includes('研究预览已完成')");
  await screenshot('overview_completed.png');
  await clickButton('04 收益与风险');
  await waitFor("document.querySelectorAll('[role=tab]').length===4");
  checks.push({route:'risk_preview',roundtrip_preserved:true});
  // Use an actual upload, then leave the page so Chromium/Streamlit unmounts it.
  await radio('上传自定义多头权重 CSV');
  const weightsPath=new URL('browser_weights.csv',output);
  const ids=Array.from({length:100},(_,i)=>'SYNTH_SCREEN_'+String(i).padStart(3,'0'));
  fs.writeFileSync(weightsPath,'asset_id,weight\n'+ids.map(id=>id+',0.01').join('\n')+'\n');
  await evaluate(`(()=>{const e=[...document.querySelectorAll('[data-testid=stFileUploader]')].find(e=>e.innerText.includes('自定义多头权重'));e.querySelector('input[type=file]').id='browser-weight-upload';})()`);
  const doc=await call('DOM.getDocument');
  const input=await call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#browser-weight-upload'});
  await call('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[decodeURIComponent(weightsPath.pathname)]});
  await pause(1000);
  await clickButton('计算收益与风险');
  await waitFor("document.querySelectorAll('[role=tab]').length===4");
  await evaluate(`(()=>{const e=document.querySelector('button[aria-label="Remove browser_weights.csv"]');if(!e)throw new Error('Missing native upload removal button');e.click();})()`);
  await waitFor("!document.querySelector('[role=tab]')");
  checks.push({route:'risk_preview',native_upload_removal_invalidates:true});
  const freshDoc=await call('DOM.getDocument');
  const freshInput=await call('DOM.querySelector',{nodeId:freshDoc.root.nodeId,selector:'#browser-weight-upload'});
  const reuploadPath=new URL('browser_weights_reuploaded.csv',output);
  fs.copyFileSync(weightsPath,reuploadPath);
  await call('DOM.setFileInputFiles',{nodeId:freshInput.nodeId,files:[decodeURIComponent(reuploadPath.pathname)]});
  await pause(1000);
  await clickButton('计算收益与风险');
  await waitFor("document.querySelectorAll('[role=tab]').length===4");
  await clickButton('研究总览');
  await waitFor("document.body.innerText.includes('研究预览已完成')");
  await clickButton('04 收益与风险');
  await waitFor("document.body.innerText.includes('本次研究已保留：browser_weights_reuploaded.csv') && document.querySelectorAll('[role=tab]').length===4");
  checks.push({route:'risk_preview',uploaded_weights_roundtrip_preserved:true});
  await clickButton('清除已保留文件');
  await waitFor("!document.querySelector('[role=tab]')");
  checks.push({route:'risk_preview',clear_retained_weights_invalidates:true});
  // Advanced tools are reachable directly from their sidebar group.
  await evaluate(`(()=>{for(const d of document.querySelectorAll('[data-testid=stSidebar] details'))d.open=true;})()`);
  await clickButton('市场数据与缓存');
  await waitFor("document.querySelector('h1')?.innerText==='市场数据与缓存'");
  await checkWidths('downloads');
  if(process.env.WORKSPACE_REAL_VERSION) {
    await clickButton('01 准备数据');
    await waitFor("document.body.innerText.includes('本地版本')");
    await evaluate(`(()=>{const e=[...document.querySelectorAll('[data-testid=stSelectbox]')].find(e=>e.innerText.includes('本地版本'));e.querySelector('button[aria-label=Open]').click();})()`);
    await waitFor("document.querySelector('[role=option]')");
    await evaluate(`(()=>{const e=[...document.querySelectorAll('[role=option]')].find(e=>e.innerText.includes(${JSON.stringify(process.env.WORKSPACE_REAL_VERSION)}));if(!e)throw new Error('Missing real version');e.click();})()`);
    await clickButton('打开此版本');
    await waitFor("document.body.innerText.includes('版本已打开')");
    await clickButton('03 筛选候选');
    await expandInputs();
    await radio('当前已打开导入版本');
    await clickButton('查验数据并筛选');
    await waitFor("document.body.innerText.includes('合格 N = 0')");
    await clickButton('研究总览');
    await waitFor("document.body.innerText.includes('需要月度准备') && document.body.innerText.includes('N = 0')");
    await checkWidths('real_n0_overview');
    checks.push({route:'overview',real_daily_n:0,monthly_preparation_required:true});
  }
  fs.writeFileSync(new URL('browser_checks.json',output),JSON.stringify({date:new Date().toISOString(),checks},null,2));
  console.log(JSON.stringify({checks:checks.length,viewports:[1440,720,390],download_bytes:fs.statSync(exportPath).size}));
} finally {ws.close();}
