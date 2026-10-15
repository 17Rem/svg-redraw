'use strict';
const {parseArgs}=require('node:util');
const {chromium}=require('playwright');
const {pathToFileURL}=require('node:url');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {values:o}=parseArgs({options:{html:{type:'string'},chrome:{type:'string'},out:{type:'string'},help:{type:'boolean'}}});
if(o.help){console.log('node verify_studio.cjs --html illustration-demo.html --out build/ui-check [--chrome PATH]');process.exit(0)}
if(!o.html||!o.out)throw Error('--html and --out are required');
async function main(){
 const out=path.resolve(o.out);fs.mkdirSync(out,{recursive:true});const checks=[],errors=[],requests=[];
 const browser=await chromium.launch({...(o.chrome?{executablePath:o.chrome}:{}),headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1600,height:1000},deviceScaleFactor:1,permissions:['clipboard-read','clipboard-write']});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  function pass(name,detail){checks.push({name,result:'pass',detail});console.log('PASS',name)}
  async function click(selector){const e=page.locator(selector);await e.scrollIntoViewIfNeeded();const b=await e.boundingBox();assert(b);await page.mouse.click(b.x+b.width/2,b.y+b.height/2)}
  await page.goto(pathToFileURL(path.resolve(o.html)).href,{waitUntil:'load',timeout:120000});await page.waitForFunction(()=>window.svgStudio);
  const data=await page.evaluate(()=>JSON.parse(document.getElementById('art-data').textContent));assert(data.parts.length>0);
  assert.equal(await page.locator('.layer').count(),data.parts.length);
  const frame=await page.evaluate(()=>{const a=document.getElementById('art-frame').getBoundingClientRect(),v=document.getElementById('viewport').getBoundingClientRect();return {inside:a.bottom<=v.bottom+.5&&a.top>=v.top-.5&&a.left>=v.left-.5&&a.right<=v.right+.5,ratio:a.width/a.height}});assert(frame.inside);assert(Math.abs(frame.ratio-data.width/data.height)<.005);pass('Original aspect ratio and uncropped frame',frame);
  if(data.reference){await page.waitForFunction(()=>[...document.querySelectorAll('.reference-image')].every(i=>i.complete&&i.naturalWidth>0));pass('Local comparison references load')}else{assert.equal(await page.locator('img').count(),0);pass('Native-only mode includes no reference images')}
  await page.screenshot({path:path.join(out,'studio.png')});
  for(const part of data.parts){
   await click(`.layer[data-part="${part.id}"] .layer-select`);assert.equal(await page.evaluate(()=>svgStudio.selectedPart),part.id);
   const [x0,y0,x1,y1]=part.box;assert.equal(await page.locator('.detail-svg').first().getAttribute('viewBox'),`${x0} ${y0} ${x1-x0} ${y1-y0}`);
  }
  assert.equal(await page.locator('#follow').isChecked(),false);pass('Every part updates its local view');
  const part=data.parts.find(p=>p.colors.length&&p.count>0);assert(part);await click(`.layer[data-part="${part.id}"] .layer-select`);
  const expected=await page.locator('.swatch').first().getAttribute('data-color');await click('.swatch:first-child');assert.equal(await page.locator('#color-hex').textContent(),expected.toUpperCase());assert((await page.evaluate(()=>svgStudio.code)).toUpperCase().includes(expected.toUpperCase()));pass('Palette and code reflect real SVG colors');
  await click('#copy-code');assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replaceAll('\r\n','\n'),await page.evaluate(()=>svgStudio.code));pass('Full code copy');
  await click('#focus-part');assert.notEqual(await page.locator('#drawing').getAttribute('viewBox'),'');await click('#zoom-in');await click('#fit');assert.equal(await page.locator('#drawing').getAttribute('viewBox'),`0 0 ${data.width} ${data.height}`);pass('Focus, zoom and fit');
  await click(`.layer[data-part="${part.id}"] .eye`);assert.equal(await page.locator(`.paint[data-part="${part.id}"]`).first().evaluate(n=>getComputedStyle(n).display),'none');await click('#show-all');assert.equal(await page.locator(`.paint[data-part="${part.id}"]`).first().evaluate(n=>getComputedStyle(n).display),'inline');pass('Layer visibility');
  await page.locator('#follow').check();
  const phases=await page.evaluate(()=>{const r=[];for(const t of svgStudio.tasks){drawingPlayer.setTime(t.start+(t.end-t.start)*.61);r.push({part:t.part,actual:svgStudio.selectedPart,code:svgStudio.code.length,color:document.getElementById('color-hex').textContent})}return r});
  for(const q of phases){assert.equal(q.part,q.actual);assert(q.code>0);assert.match(q.color,/^#[0-9A-F]{6}$/)}pass('Live part, palette and code follow all phases',{tasks:phases.length});
  for(const [name,fraction] of [['construction',.035],['linework',.13],['partial',.36]]){await page.evaluate(t=>drawingPlayer.setTime(t),data.duration*fraction);await page.screenshot({path:path.join(out,name+'.png')})}
  await page.evaluate(()=>drawingPlayer.setTime(0));await click('#play');await page.waitForFunction(()=>drawingPlayer.time>Math.min(.4,drawingPlayer.duration*.1));await click('#play');assert.equal(await page.locator('#play').getAttribute('aria-pressed'),'false');await page.locator('#speed').selectOption('2');pass('Playback, pause and speed');
  const slider=await page.locator('#timeline').boundingBox();await page.mouse.click(slider.x+slider.width*.55,slider.y+slider.height/2);assert((await page.evaluate(()=>drawingPlayer.time))>data.duration*.4);await click('#finish');assert.equal(await page.evaluate(()=>drawingPlayer.time),data.duration);pass('Pointer seeking and final frame');
  await click('#expand-compare');assert(await page.locator('#comparison-dialog').evaluate(d=>d.open));await page.screenshot({path:path.join(out,'comparison.png')});await click('#close-dialog');pass('Expanded local comparison');
  await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.getElementById('art-frame').getBoundingClientRect().width<390);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});pass('Responsive layout');
  assert.equal(errors.length,0);assert(!requests.some(r=>/^https?:/.test(r)));pass('No page errors or network assets');
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({checks,errors},null,2));console.log('Verified',checks.length,'workflows');
 }finally{await browser.close()}
}
main().catch(e=>{console.error(String(e.stack||e).slice(0,1400));process.exitCode=1});
