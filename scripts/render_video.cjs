/* Capture the exact demo timeline in bounded browser sessions, then concatenate. */
'use strict';
const {parseArgs}=require('node:util');
const {chromium}=require('playwright');
const {spawn,spawnSync}=require('node:child_process');
const {once}=require('node:events');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url');
const {values:o}=parseArgs({options:{html:{type:'string'},out:{type:'string'},chrome:{type:'string'},width:{type:'string',default:'1440'},height:{type:'string',default:'900'},'capture-fps':{type:'string',default:'12'},fps:{type:'string',default:'30'},segment:{type:'string',default:'8'},hold:{type:'string',default:'2'},speed:{type:'string',default:'2'},view:{type:'string',default:'studio'},ffmpeg:{type:'string',default:'ffmpeg'},ffprobe:{type:'string',default:'ffprobe'},help:{type:'boolean'}}});
if(o.help){console.log('node render_video.cjs --html demo.html --out drawing.mp4 [--chrome PATH --speed 2 --view studio|artwork --width 1440 --height 900 --capture-fps 12 --fps 30 --segment 8 --hold 2]');process.exit(0)}
if(!o.html||!o.out)throw Error('--html and --out are required');
const input=path.resolve(o.html),output=path.resolve(o.out);
if(input===output)throw Error('Output must differ from the HTML');
const width=Number(o.width),height=Number(o.height),capture=Number(o['capture-fps']),fps=Number(o.fps),segment=Number(o.segment),hold=Number(o.hold),speed=Number(o.speed);
if(![width,height,capture,fps].every(n=>Number.isInteger(n)&&n>0)||width%2||height%2||!(segment>0)||!(hold>=0)||!(speed>0)||!['studio','artwork'].includes(o.view))throw Error('Invalid render dimensions/timing/view');
const segmentFrames=Math.round(segment*capture);if(!segmentFrames)throw Error('Segment is too short');
const viewport={width,height};
const sourceHtml=fs.readFileSync(input,'utf8'),hasher=crypto.createHash('sha256').update(sourceHtml).update(JSON.stringify({renderer:3,...o}));
for(const asset of new Set([...sourceHtml.matchAll(/<img\b[^>]*\bsrc="([^"]+)"/g)].map(m=>m[1]))){if(/^(?:[a-z]+:|\/\/)/i.test(asset))throw Error('Offline video requires local comparison images');hasher.update(asset).update(fs.readFileSync(path.resolve(path.dirname(input),asset)))}
const hash=hasher.digest('hex').slice(0,20);
const cache=path.join(path.dirname(output),'.'+path.basename(output)+'.segments',hash);fs.mkdirSync(cache,{recursive:true});
function probe(file){
 const r=spawnSync(o.ffprobe,['-v','error','-show_entries','format=duration:stream=codec_name,width,height,r_frame_rate','-of','json',file],{encoding:'utf8',windowsHide:true});
 if(r.error)throw r.error;if(r.status)return null;try{return JSON.parse(r.stdout)}catch{return null}
}
async function open(){
 const b=await chromium.launch({...(o.chrome?{executablePath:o.chrome}:{}),headless:true,args:['--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files']});
 try{const p=await b.newPage({viewport,deviceScaleFactor:1});await p.goto(pathToFileURL(input).href+'?view='+o.view,{waitUntil:'load',timeout:120000});await p.waitForFunction(()=>!!window.drawingPlayer);await p.evaluate(speed=>{window.drawingPlayer.pause();window.svgStudio?.setFollowing(true);const s=document.getElementById('speed');if(s){const option=[...s.options].find(o=>Number(o.value)===speed);if(option){s.value=option.value;s.dispatchEvent(new Event('change'))}}},speed);return {b,p}}
 catch(e){await b.close();throw e}
}
async function main(){
 let current=await open(),encoder=null;
 try{
  const duration=await current.p.evaluate(()=>window.drawingPlayer.duration);
  if(!(Number.isFinite(duration)&&duration>0))throw Error('Player has invalid duration');
  const frames=Math.ceil((duration/speed+hold)*capture),chunks=Math.ceil(frames/segmentFrames);const paths=[];
  for(let chunk=0;chunk<chunks;chunk++){
   const first=chunk*segmentFrames,count=Math.min(segmentFrames,frames-first),file=path.join(cache,`part-${String(chunk).padStart(4,'0')}.mp4`);paths.push(file);
   const old=fs.existsSync(file)?probe(file):null;
   if(old&&Math.abs(Number(old.format.duration)-count/capture)<1/fps+.001&&old.streams[0]?.codec_name==='h264'&&old.streams[0]?.width===width&&old.streams[0]?.height===height){console.log(JSON.stringify({segment:chunk+1,total:chunks,resumed:true}));continue}
   if(!current)current=await open();
   encoder=spawn(o.ffmpeg,['-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate',String(capture),'-i','pipe:0','-vf',`scale=out_color_matrix=bt709:out_range=tv,fps=${fps}`,'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',file],{windowsHide:true,stdio:['pipe','ignore','pipe']});
   let stderr='',processError=null;encoder.stderr.on('data',d=>stderr+=d);encoder.stdin.on('error',e=>{processError=e});
   const finished=new Promise(resolve=>{encoder.once('close',code=>resolve(code));encoder.once('error',e=>{processError=e;resolve(-1)})});
   for(let i=0;i<count;i++){
    const t=Math.min(duration,(first+i)/capture*speed);let buffer;
    for(let attempt=0;attempt<2;attempt++){
     try{await current.p.evaluate(t=>window.drawingPlayer.setTime(t),t);buffer=await current.p.screenshot({type:'png',timeout:20000});break}
     catch(e){await current.b.close().catch(()=>{});current=null;if(attempt===1)throw e;console.log(JSON.stringify({retryAt:t}));current=await open()}
    }
    if(processError)throw processError;
    if(!encoder.stdin.write(buffer))await Promise.race([once(encoder.stdin,'drain'),finished.then(code=>{throw Error(`Encoder stopped (${code}): ${stderr}`)})]);
   }
   encoder.stdin.end();const code=await finished;encoder=null;
   if(processError||code)throw processError||Error(stderr);
   await current.b.close();current=null;
   console.log(JSON.stringify({segment:chunk+1,total:chunks,percent:Math.round((chunk+1)/chunks*100)}));
  }
  // The list lives next to its segments, so no shell quoting or absolute-path escaping is needed.
  const list=path.join(cache,'concat.txt');fs.writeFileSync(list,paths.map(f=>`file '${path.basename(f)}'`).join('\n'));
  const merge=spawnSync(o.ffmpeg,['-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',list,'-c','copy','-movflags','+faststart',output],{encoding:'utf8',windowsHide:true});
  if(merge.error||merge.status)throw merge.error||Error(merge.stderr);
  const result=probe(output);if(!result||Math.abs(Number(result.format.duration)-frames/capture)>chunks/fps+.1)throw Error('Final duration verification failed');
  const decode=spawnSync(o.ffmpeg,['-hide_banner','-loglevel','error','-i',output,'-f','null','-'],{encoding:'utf8',windowsHide:true});
  if(decode.error||decode.status)throw decode.error||Error(decode.stderr);
  const report={input,output,sourceAndOptionsHash:hash,view:o.view,playbackSpeed:speed,captureFps:capture,outputFps:fps,framesCaptured:frames,video:result};
  fs.writeFileSync(output+'.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{if(current)await current.b.close().catch(()=>{});if(encoder){encoder.stdin.destroy();encoder.kill()}}
}
main().catch(e=>{console.error(e);process.exitCode=1});
