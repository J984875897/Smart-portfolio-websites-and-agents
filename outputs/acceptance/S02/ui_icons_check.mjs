import fs from 'node:fs';

const stage = process.argv[2] || 'red';
const output = '/Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/outputs/acceptance/S02';
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
await call('Page.enable');
await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1200, deviceScaleFactor: 1, mobile: false });
await call('Page.navigate', { url: 'about:blank' });
while (!(await evaluate('document.URL === "about:blank" && !document.querySelector("[data-testid=stFileUploader]")'))) {
  await new Promise(resolve => setTimeout(resolve, 100));
}
await call('Page.navigate', { url: 'http://127.0.0.1:8501' });
const deadline = Date.now() + 20000;
while (Date.now() < deadline) {
  if (await evaluate('!!document.querySelector("[data-testid=stFileUploader]") && !!document.querySelector("[data-testid=stIconMaterial]")')) break;
  await new Promise(resolve => setTimeout(resolve, 250));
}
await evaluate('document.fonts.ready.then(() => true)');
if (stage === 'green') {
  const readyDeadline = Date.now() + 10000;
  while (Date.now() < readyDeadline) {
    if (await evaluate(`(() => {
      const icons = [...document.querySelectorAll('[data-testid="stIconMaterial"]')];
      return icons.length > 0 && icons.every(el => getComputedStyle(el).fontFamily.includes('Material Symbols Rounded'));
    })()`)) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
}
const snapshot = await evaluate(`(() => {
  const icons = [...document.querySelectorAll('[data-testid="stIconMaterial"]')].map(el => ({
    text: el.textContent,
    font: getComputedStyle(el).fontFamily,
    width: el.getBoundingClientRect().width,
    height: el.getBoundingClientRect().height
  }));
  return {
    title: document.title,
    loaded: document.body.innerText.includes('研究数据工作台'),
    fontLoaded: document.fonts.check('24px "Material Symbols Rounded"'),
    customStyles: [...document.querySelectorAll('style')].map(el => el.textContent).filter(s => s.includes('PingFang')),
    icons,
    passed: icons.length > 0 && icons.every(i => i.font.includes('Material Symbols Rounded'))
  };
})()`);
const screenshot = await call('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync(`${output}/ui_icons_${stage}.png`, Buffer.from(screenshot.data, 'base64'));
if (stage === 'green' && snapshot.passed) {
  await evaluate(`(() => {
    document.querySelectorAll('[data-testid="stExpander"] summary').forEach(el => el.click());
    return true;
  })()`);
  snapshot.expanded = await evaluate(`(() => {
    const details = [...document.querySelectorAll('[data-testid="stExpander"] details')];
    const icons = [...document.querySelectorAll('[data-testid="stIconMaterial"]')];
    return { open: details.filter(el => el.open).length, total: details.length,
      fontsCorrect: icons.every(el => getComputedStyle(el).fontFamily.includes('Material Symbols Rounded')) };
  })()`);
  snapshot.passed = snapshot.passed && snapshot.expanded.open === snapshot.expanded.total && snapshot.expanded.fontsCorrect;
  await call('Emulation.setDeviceMetricsOverride', { width: 720, height: 1100, deviceScaleFactor: 1, mobile: false });
  const narrowScreenshot = await call('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(`${output}/ui_icons_green_expanded_720.png`, Buffer.from(narrowScreenshot.data, 'base64'));
}
fs.writeFileSync(`${output}/ui_icons_${stage}_checks.json`, JSON.stringify(snapshot, null, 2) + '\n');
console.log(JSON.stringify(snapshot, null, 2));
ws.close();
process.exitCode = snapshot.passed ? 0 : 1;
