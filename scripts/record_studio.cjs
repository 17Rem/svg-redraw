/* Record the ready SVG Studio through Chromium's PNG screencast. No Canvas. */
'use strict';
const {parseArgs}=require('node:util');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
const {values:o}=parseArgs({options:{html:{type:'string'},out:{type:'string'},chrome:{type:'string'},width:{type:'string',default:'1440'},height:{type:'string',default:'900'},speed:{type:'string',default:'2'},hold:{type:'string',default:'2'},view:{type:'string',default:'studio'},ffmpeg:{type:'string',default:'ffmpeg'},ffprobe:{type:'string',default:'ffprobe'},help:{type:'boolean'}}});
if(o.help){console.log('node record_studio.cjs --html demo.html --out drawing.mp4 [--chrome PATH --speed 2 --view studio|artwork --width 1440 --height 900 --ffmpeg PATH --ffprobe PATH]');process.exit(0)}
if(!o.html||!o.out)throw Error('--html and --out are required');
const input=path.resolve(o.html),output=path.resolve(o.out),width=+o.width,height=+o.height,speed=+o.speed,hold=+o.hold;
if(input===output||![width,height].every(n=>Number.isInteger(n)&&n>0&&n%2===0)||![.5,1,2,4].includes(speed)||!(hold>=0)||!['studio','artwork'].includes(o.view))throw Error('Invalid output, dimensions, speed or view');
fs.mkdirSync(path.dirname(output),{recursive:true});const work=fs.mkdtempSync(path.join(path.dirname(output),'.svg-record-'));
async function command(exe,args,binary=false){
 return new Promise((resolve,reject)=>{const p=spawn(exe,args,{windowsHide:true,stdio:['ignore','pipe','pipe']});const chunks=[];let stderr='';p.stdout.on('data',s=>chunks.push(s));p.stderr.on('data',s=>stderr+=s);p.on('error',reject);p.on('close',code=>{const data=Buffer.concat(chunks);code===0?resolve(binary?data:data.toString('utf8')):reject(Error(stderr||`${exe} exited ${code}`))})});
}
async function main(){
 let browser=null,encoder=null,timer=null,cdp=null;
 try{
  browser=await chromium.launch({...(o.chrome?{executablePath:o.chrome}:{}),headless:true});
  const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(input).href+'?view='+o.view,{waitUntil:'load',timeout:120000});
  await page.waitForFunction(()=>window.drawingPlayer&&window.svgStudio);
  const data=await page.evaluate(async speed=>{
   drawingPlayer.pause();drawingPlayer.setTime(0);svgStudio.setFollowing(true);
   const s=document.getElementById('speed');s.value=[...s.options].find(o=>Number(o.value)===speed).value;s.dispatchEvent(new Event('change'));
   await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()));
   await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
   return {duration:drawingPlayer.duration,reference:svgStudio.reference};
  },speed);
  if(!(Number.isFinite(data.duration)&&data.duration>0))throw Error('Invalid player duration');
  // Start only after the complete UI is ready. PNG avoids range metadata from a
  // JPEG-to-WebM intermediate; FFmpeg performs a single explicit RGB-to-YUV conversion.
  cdp=await context.newCDPSession(page);let latest=null,received=0,firstResolve,frozen=false;
  const firstFrame=new Promise(resolve=>firstResolve=resolve);
  cdp.on('Page.screencastFrame',event=>{
   if(!frozen)latest=Buffer.from(event.data,'base64');received++;firstResolve();
   void cdp.send('Page.screencastFrameAck',{sessionId:event.sessionId}).catch(()=>{});
  });
  await cdp.send('Page.startScreencast',{format:'png',maxWidth:width,maxHeight:height,everyNthFrame:1});
  let firstTimeout;try{await Promise.race([firstFrame,new Promise((_,reject)=>{firstTimeout=setTimeout(()=>reject(Error('No Chromium screencast frames')),20000)})])}finally{clearTimeout(firstTimeout)}
  fs.writeFileSync(path.join(work,'start.png'),latest);
  encoder=spawn(o.ffmpeg,['-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate','25','-i','pipe:0','-an','-vf','scale=out_color_matrix=bt709:out_range=tv','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-r','30','-movflags','+faststart',output],{windowsHide:true,stdio:['pipe','ignore','pipe']});
  let stderr='',fatal=null,sent=0,pumping=false,pumpPromise=Promise.resolve();
  encoder.stderr.on('data',s=>stderr+=s);encoder.stdin.on('error',e=>{fatal=e});
  const finished=new Promise(resolve=>{encoder.once('close',code=>resolve(code));encoder.once('error',e=>{fatal=e;resolve(-1)})});
  const started=Date.now();
  const pump=()=>{
   if(pumping||fatal)return;pumping=true;
   pumpPromise=(async()=>{
    const target=Math.floor((Date.now()-started)/40)+1;
    while(sent<target){
     if(!encoder.stdin.write(latest))await Promise.race([once(encoder.stdin,'drain'),finished.then(code=>{throw Error(`Encoder stopped (${code}): ${stderr}`)})]);
     sent++;
    }
   })().catch(e=>{fatal=e}).finally(()=>{pumping=false});
  };
  pump();timer=setInterval(pump,40);await page.waitForTimeout(500);
  await page.evaluate(()=>drawingPlayer.play());
  console.log(JSON.stringify({recording:true,timelineSeconds:data.duration,playbackSpeed:speed,view:o.view}));
  await page.waitForFunction(()=>drawingPlayer.time>=drawingPlayer.duration,{},{timeout:Math.max(30000,(data.duration/speed+30)*1000)});
  // A static completion can arrive after the last screencast update. Hold the
  // actual completed browser screenshot so the video never ends at 98 or 99 percent.
  const expected=path.join(work,'end.png'),completed=await page.screenshot({path:expected});
  frozen=true;latest=completed;
  await cdp.send('Page.stopScreencast');await cdp.detach();cdp=null;
  await page.waitForTimeout(hold*1000);
  clearInterval(timer);timer=null;await pumpPromise;if(fatal)throw fatal;
  pump();await pumpPromise;if(fatal)throw fatal;
  encoder.stdin.end();const code=await finished;encoder=null;if(code||fatal)throw fatal||Error(stderr);
  if(errors.length)throw Error('Page errors: '+errors.join('; '));
  await browser.close();browser=null;
  const probe=JSON.parse(await command(o.ffprobe,['-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,r_frame_rate,color_range,color_space','-of','json',output]));
  if(probe.streams[0]?.width!==width||probe.streams[0]?.height!==height||Number(probe.format.duration)<data.duration/speed-1)throw Error('Recorded video dimensions or duration are incomplete');
  await command(o.ffmpeg,['-hide_banner','-loglevel','error','-i',output,'-f','null','-']);
  const decoded=path.join(work,'end-decoded.png');
  await command(o.ffmpeg,['-hide_banner','-loglevel','error','-y','-sseof','-0.04','-i',output,'-frames:v','1',decoded]);
  const pixels=await Promise.all([expected,decoded].map(file=>command(o.ffmpeg,['-v','error','-i',file,'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],true)));
  if(pixels[0].length!==width*height*3||pixels[0].length!==pixels[1].length)throw Error('End-frame comparison dimensions differ');
  let difference=0;for(let i=0;i<pixels[0].length;i++)difference+=Math.abs(pixels[0][i]-pixels[1][i]);
  const assets={html:crypto.createHash('sha256').update(fs.readFileSync(input)).digest('hex')};
  if(data.reference)assets.reference=crypto.createHash('sha256').update(fs.readFileSync(path.resolve(path.dirname(input),data.reference))).digest('hex');
  const report={input,output,method:'Chromium PNG screencast of actual playback',timelineSeconds:data.duration,playbackSpeed:speed,captureCadence:'browser-dependent; 25 Hz sampling and 30 fps output may repeat frames',receivedFrames:received,framesSampled:sent,endFrameMae:difference/pixels[0].length,assets,video:probe};
  fs.writeFileSync(output+'.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{
  if(timer)clearInterval(timer);
  if(cdp)await cdp.send('Page.stopScreencast').catch(()=>{});
  if(browser)await browser.close().catch(()=>{});
  if(encoder){encoder.stdin.destroy();encoder.kill()}
 }
}
main().catch(e=>{console.error(String(e.stack||e).slice(0,1600));process.exitCode=1});
