"""Preserve selected native SVG geometry and build the linked SVG Studio player."""
import argparse,collections,copy,hashlib,html,json,re,shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image,ImageFilter
from svg_common import NS,GEOMETRY,local,slug,serialize,rgb,bounds,info,assigned_part,read_config,audit_native

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('svg','ref','config','out'):ap.add_argument('--'+key,required=True)
    ap.add_argument('--name',default='illustration');ap.add_argument('--duration',type=float,default=90)
    ap.add_argument('--lineart',action='store_true');ap.add_argument('--comparison',action='store_true',help='Include a local reference only when reference comparison is requested')
    a=ap.parse_args()
    if not np.isfinite(a.duration) or a.duration<=0:raise ValueError('Positive duration required')
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);name=slug(a.name)
    source=Path(a.svg).resolve();reference=Path(a.ref).resolve();im=Image.open(reference).convert('RGB');w,h=im.size
    if source in {out/(name+'.svg'),out/(name+'.html'),out/(name+'-demo.html')}:raise ValueError('Keep selected source separate from deliverables')
    root=ET.parse(source).getroot();existing=audit_native(root)
    if [float(v) for v in root.get('viewBox','').split()]!=[0,0,w,h]:raise ValueError('SVG viewBox must match original reference dimensions')
    cfg=read_config(a.config,w,h);parts=copy.deepcopy(cfg['parts']);pmap={p['id']:p for p in parts}
    title=str(cfg.get('title','参考图重建'));safe_title=html.escape(title);paper=str(cfg.get('paper','#f5f7fc'))
    soft=np.asarray(im.convert('L').filter(ImageFilter.GaussianBlur(max(w,h)/256)))
    defs={n.get('id'):n for n in root.iter() if n.get('id')}
    stats=collections.Counter();palettes=collections.defaultdict(collections.Counter);samples=collections.defaultdict(list)
    phase_bounds={};representatives={};groups=0;sequence=0;path_count=0;skipped=0
    reserved={'drawing','artwork','construction','linework','art-title'}
    if reserved&existing:raise ValueError('Selected SVG uses reserved studio IDs: '+', '.join(sorted(reserved&existing)))
    def new_id(prefix):
        nonlocal sequence
        while True:
            sequence+=1;nid=f'{prefix}-{sequence}'
            if nid not in existing:existing.add(nid);return nid
    def phase_for(n,it):
        if 'data-phase' in n.attrib:
            v=int(n.get('data-phase'))
            if v not in range(4):raise ValueError('data-phase must be 0..3')
            return v
        area=it['area'];c=it['rgb'];near=float(soft[min(h-1,max(0,int(it['y']))),min(w-1,max(0,int(it['x'])))])
        lum=float(c@[.299,.587,.114]) if c is not None else near
        if area/(w*h)>cfg.get('baseAreaRatio',.000167):return 0
        if lum<near-7 and area/(w*h)>.0000083:return 1
        if lum>near+15 and lum>180:return 3
        return 2
    def paint_colors(n):
        fill=n.get('fill','');c=rgb(fill)
        if c is not None:return ['#'+''.join(f'{int(v):02X}' for v in c)]
        m=re.fullmatch(r'url\(#([^)]+)\)',fill)
        if m and m[1] in defs:return [s.get('stop-color').upper() for s in defs[m[1]].iter() if rgb(s.get('stop-color','')) is not None]
        return []
    def register(n,part,phase,unit):
        nonlocal path_count
        for el in n.iter():
            if local(el) not in GEOMETRY:continue
            if not el.get('id'):el.set('id',new_id(part+'-'+local(el)))
            if local(el)=='path':path_count+=1
            stats[part]+=1;it=info(el,w,h) if bounds(el) is not None else unit
            if local(n)=='g' and n.get('transform'):it=unit
            colors=paint_colors(el)
            for c in colors:palettes[part][c]+=min(max(it['area'],1),w*h*.0048)/max(1,len(colors))
            samples[f'{part}-{phase}'].append({'id':el.get('id'),'y':round(it['y'],3),'fill':colors[len(colors)//2] if colors else '#000000'})
            if it['area']>representatives.get(part,{}).get('area',-1):representatives[part]={'id':el.get('id'),'area':it['area']}
    def wrap_children(parent):
        nonlocal groups,skipped
        result=[];active=None;run=None
        for child in list(parent):
            tag=local(child)
            if tag in ('defs','title','desc'):result.append(child);active=None;continue
            if tag=='path' and not child.get('d','').strip():skipped+=1;continue
            if tag=='g' and not child.get('data-part'):
                wrap_children(child);result.append(child);active=None;continue
            it=info(child,w,h);part=assigned_part(child,it,cfg,w,h)
            if part not in pmap:raise ValueError('Unknown data-part: '+part)
            phase=int(pmap[part].get('phase',phase_for(child,it)))
            if phase not in range(4):raise ValueError('Part phase must be 0..3')
            key=f'{part}-{phase}'
            if key!=active:
                groups+=1;run=ET.Element('g',{'id':new_id('layer-'+key),'class':'paint p-'+key,'data-part':part,'data-phase':str(phase)});result.append(run);active=key
            run.append(child);register(child,part,phase,it)
            prev=phase_bounds.get(key,[h,0]);phase_bounds[key]=[max(-4,min(prev[0],it['bbox'][1])),min(h+4,max(prev[1],it['bbox'][3]))]
        parent[:]=result
    wrap_children(root)
    for key,vals in samples.items():
        vals.sort(key=lambda s:s['y']);indices=np.linspace(0,len(vals)-1,min(60,len(vals)),dtype=int)
        samples[key]=[vals[i] for i in sorted(set(indices.tolist()))]
    for p in parts:p.update(box=p['bbox'],count=stats[p['id']],colors=[c for c,_ in palettes[p['id']].most_common(14)])
    inherited={k:v for k,v in root.attrib.items() if k not in ('id','width','height','viewBox','preserveAspectRatio','role','aria-label','aria-labelledby')}
    extra_attrs=' '.join(f'{k}="{html.escape(v,quote=True)}"' for k,v in inherited.items())
    head=f'<svg xmlns="{NS}" id="drawing" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="art-title" {extra_attrs}><title id="art-title">{safe_title}</title>'
    definition=''.join(serialize(n) for n in root if local(n)=='defs')
    body=''.join(serialize(n) for n in root if local(n) not in ('defs','title','desc'))
    painting='<g id="artwork">'+body+'</g>';finished=head+definition+painting+'</svg>'
    audit_native(ET.fromstring(finished));(out/(name+'.svg')).write_text(finished,'utf-8')
    css='html,body{margin:0;background:#eef2f6;min-height:100%}body{display:grid;place-items:center;min-height:100vh}svg{display:block;width:100%;height:auto;max-height:100vh}'
    (out/(name+'.html')).write_text(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title><style>{css}</style></head><body>{finished}</body></html>','utf-8')
    guides=''.join(serialize(ET.Element('path',{'id':'guide-'+slug(g.get('id',i)),'d':g['d'],'pathLength':'1'})) for i,g in enumerate(cfg.get('sketch',[])))
    marks=[]
    if a.lineart:
        import cv2
        gray=cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2GRAY);edge=cv2.Canny(cv2.GaussianBlur(gray,(3,3),.7),45,110)
        contours,_=cv2.findContours(edge,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            if cv2.arcLength(c,False)<max(8,35*w/3840):continue
            q=cv2.approxPolyDP(c,.6,False).reshape(-1,2)
            if len(q)>2:marks.append((float(q[:,1].mean()),'<path d="M'+' L'.join(f'{x} {y}' for x,y in q)+'"/>'))
    marks.sort();batches=[[] for _ in range(36)]
    for i,(_,s) in enumerate(marks):batches[min(35,i*36//len(marks))].append(s)
    sketch=f'<g id="construction" class="editor-only" fill="none" stroke="#53627d" stroke-width="{max(.5,w/1536)}" stroke-linecap="round">{guides}</g>'
    ink=f'<g id="linework" class="editor-only" fill="none" stroke="#283758" stroke-width="{max(.35,w/2743)}" stroke-linecap="round">'+''.join(f'<g class="ink" data-rank="{i/36:.5f}">{"".join(batch)}</g>' for i,batch in enumerate(batches))+'</g>'
    clips=''.join(f'<clipPath id="clip-{key}" clipPathUnits="userSpaceOnUse"><rect id="window-{key}" x="-4" y="-4" width="{w+8}" height="{h+8}"/></clipPath>' for key in samples)
    art=head+definition+'<defs>'+clips+'</defs>'+f'<rect id="paper" width="{w}" height="{h}" fill="{html.escape(paper,quote=True)}"/>'+painting+sketch+ink+'</svg>'
    reference_name=None
    if a.comparison:
        reference_name=name+'-reference'+reference.suffix.lower();target=out/reference_name
        if target.resolve()!=reference:shutil.copyfile(reference,target)
    initial=cfg.get('initialPart',parts[0]['id'])
    if initial not in pmap:raise ValueError('Unknown initialPart')
    data={'width':w,'height':h,'paths':path_count,'elements':sum(stats.values()),'parts':parts,'samples':dict(samples),'phaseBounds':phase_bounds,'representative':representatives,'duration':a.duration,'reference':reference_name,'defaultPart':initial,'hasGuides':bool(guides),'hasLinework':bool(marks)}
    def ref_panel(label):return '<div class="compare-box"><div class="compare-label">原图<span>REFERENCE</span></div><div class="compare-image reference-container"><img class="reference-image" src="'+html.escape(reference_name,quote=True)+'" alt="'+label+'"></div></div>' if reference_name else ''
    values={'TITLE':safe_title,'NAME':name,'WIDTH':str(w),'HEIGHT':str(h),'ART':art,'DATA':json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'),'REF_INLINE':ref_panel('本地参考图对应局部'),'REF_MODAL':ref_panel('本地参考图放大局部'),'COMPARE_CLASS':'' if reference_name else 'solo','COMPARE_TITLE':'局部同步对比' if reference_name else '当前部位预览','REFERENCE_NOTE':'本地原图仅用于对比' if reference_name else '纯 SVG · 离线工作台'}
    template=Path(__file__).with_name('demo_template.html').read_text('utf-8');template=re.sub(r'@@([A-Z_]+)@@',lambda m:values[m[1]],template)
    (out/(name+'-demo.html')).write_text(template,'utf-8')
    report={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'dimensions':[w,h],'artwork_paths':path_count,'artwork_elements':sum(stats.values()),'empty_paths_skipped':skipped,'groups':groups,'guide_paths':len(cfg.get('sketch',[])),'lineart_paths':len(marks),'duration':a.duration,'comparison_reference':reference_name,'outputs':[name+'.svg',name+'.html',name+'-demo.html']}
    (out/(name+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
