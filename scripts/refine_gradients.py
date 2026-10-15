"""Fit measured smooth fields as native gradients; all regions are image-specific."""
import argparse,copy,hashlib,json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from svg_common import local,info,assigned_part,read_config,audit_native,rgb

def hex_color(c):return '#'+''.join(f'{v:02X}' for v in np.clip(np.round(c),0,255).astype(int))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('svg','ref','config','out'):p.add_argument('--'+key,required=True)
    p.add_argument('--render',help='Same-size raster of this exact SVG, required for surface fitting')
    a=p.parse_args();src=Path(a.svg).resolve();out=Path(a.out).resolve();reference=Path(a.ref).resolve()
    if out in {src,reference}:raise ValueError('Keep the unmodified source and baseline')
    im=np.asarray(Image.open(reference).convert('RGB')).astype(np.float32);h,w=im.shape[:2]
    cfg=read_config(a.config,w,h);edits=cfg.get('refinements',{})
    root=ET.parse(src).getroot();audit_native(root)
    if [float(v) for v in root.get('viewBox','').split()]!=[0,0,w,h]:raise ValueError('Reference dimensions differ from SVG')
    originals=list(root)
    if any(local(n) not in ('path','title','desc','defs') for n in originals):raise ValueError('Gradient fitting expects the direct-path trace, before emission')
    definitions=ET.Element('defs');before=[];after={};removed=set();notes=[]
    for field in edits.get('radial',[]):
        nid=field['id'];cx,cy=field['center'];rx,ry=field['radii'];stride=int(field.get('stride',3))
        if min(rx,ry,stride)<=0:raise ValueError('Positive radial radii and stride required')
        yy,xx=np.mgrid[:h:stride,:w:stride];sample=im[::stride,::stride];safe=np.zeros(xx.shape,bool)
        for x0,y0,x1,y1 in field['sampleRects']:safe|=(xx>=x0)&(xx<x1)&(yy>=y0)&(yy<y1)
        radius=np.sqrt(((xx-cx)/rx)**2+((yy-cy)/ry)**2)
        lo,hi=field.get('sampleRange',[0,1]);measured=[];window=float(field.get('sampleWindow',.004))
        for t in np.linspace(lo,hi,field.get('sampleBins',149)):
            colors=sample[safe&(abs(radius-t)<window)]
            if len(colors)>field.get('minSamples',20):measured.append((t,np.median(colors,axis=0)))
        if len(measured)<3:raise ValueError('Not enough unobstructed samples for '+nid)
        ts=np.array([v[0] for v in measured]);cs=np.array([v[1] for v in measured]);stops=[]
        for t in np.linspace(0,1,field.get('stops',101)):
            if t<ts[0] and field.get('extrapolateInner',False):
                m=ts<field.get('extrapolateFitUntil',ts[0]+.1)
                if m.sum()<2:raise ValueError('Not enough samples for inner extrapolation')
                co=np.linalg.lstsq(np.column_stack([ts[m],np.ones(m.sum())]),cs[m],rcond=None)[0];color=np.array([t,1.])@co
            else:color=np.array([np.interp(t,ts,cs[:,j]) for j in range(3)])
            stops.append((float(t),hex_color(color)))
        g=ET.SubElement(definitions,'radialGradient',{'id':nid,'gradientUnits':'userSpaceOnUse','cx':'0','cy':'0','r':'1','gradientTransform':f'translate({cx} {cy}) scale({rx} {ry})'})
        for i,(t,c) in enumerate(stops):ET.SubElement(g,'stop',{'id':f'{nid}-stop-{i}','offset':str(t),'stop-color':c})
        part=field['part'];group=ET.Element('g',{'id':nid+'-surface','data-part':part,'data-phase':str(field.get('phase',0)),'data-bbox':f'0 0 {w} {h}'})
        ET.SubElement(group,'rect',{'id':nid+'-rect','width':str(w),'height':str(h),'fill':f'url(#{nid})'})
        before.append(group)
        drop=[]
        if field.get('replacePart'):
            for i,n in enumerate(originals):
                if local(n)=='path' and assigned_part(n,info(n,w,h),cfg,w,h)==field['replacePart']:removed.add(i);drop.append(i)
        notes.append({'id':nid,'type':'radial','measuredRange':[float(ts[0]),float(ts[-1])],'stops':len(stops),'replacedSourceIndices':drop})
    fields=edits.get('surfaces',[])
    if fields:
        if not a.render:raise ValueError('--render of the selected trace is required for surface fitting')
        import cv2
        rendered=np.asarray(Image.open(a.render).convert('RGB'))
        if rendered.shape!=im.shape:raise ValueError('Rendered trace dimensions differ from reference')
    for field in fields:
        nid=field['id'];index=int(field['clipSourceIndex']);target=originals[index]
        if index in removed or local(target)!='path':raise ValueError('Surface clip must select a retained path')
        x0,y0,x1,y1=map(int,field['bbox'])
        if not(0<=x0<x1<=w and 0<=y0<y1<=h):raise ValueError('Surface bbox outside reference')
        source=im[y0:y1,x0:x1];old=rendered[y0:y1,x0:x1];base=rgb(field['baseFill'])
        if base is None:raise ValueError('Surface baseFill must be a hex RGB color')
        if target.get('fill','').upper()!=field['baseFill'].upper():raise ValueError('clipSourceIndex no longer selects the measured base fill; remeasure it')
        valid=np.max(np.abs(old.astype(float)-base),axis=2)<=field.get('matchTolerance',0)
        for condition in field.get('sampleColor',[]):
            values=source@np.array(condition['coefficients'])
            if 'min' in condition:valid&=values>=condition['min']
            if 'max' in condition:valid&=values<=condition['max']
        if valid.sum()<16:raise ValueError('Not enough visible base-fill pixels for '+nid)
        def smooth(sigma):
            weights=cv2.GaussianBlur(valid.astype(np.float32),(0,0),sigma)
            values=cv2.GaussianBlur(source*valid[:,:,None],(0,0),sigma)/np.maximum(weights[:,:,None],1e-7)
            return values,weights
        tight,weight=smooth(float(field['sigma']));wide,wide_weight=smooth(float(field.get('fallbackSigma',field['sigma']*5)))
        colors=np.where((weight>.02)[:,:,None],tight,wide)
        colors=np.where((wide_weight>.0001)[:,:,None],colors,base)
        clip=ET.SubElement(definitions,'clipPath',{'id':nid+'-clip','clipPathUnits':'userSpaceOnUse'});boundary=copy.deepcopy(target)
        boundary.attrib.pop('id',None);clip.append(boundary)
        group=ET.Element('g',{'id':nid+'-surface','clip-path':f'url(#{nid}-clip)','data-part':field['part'],'data-phase':str(field.get('phase',0)),'data-bbox':f'{x0} {y0} {x1} {y1}'})
        container=group
        if field.get('bandBlur',0)>0:
            f=ET.SubElement(definitions,'filter',{'id':nid+'-smooth','x':'-5%','y':'-5%','width':'110%','height':'110%','color-interpolation-filters':'sRGB'})
            ET.SubElement(f,'feGaussianBlur',{'stdDeviation':f'0 {field["bandBlur"]}'})
            container=ET.SubElement(group,'g',{'filter':f'url(#{nid}-smooth)'})
        step_x,step_y=map(int,field.get('step',[25,20]));bands=0
        if min(step_x,step_y)<=0:raise ValueError('Positive gradient sampling steps required')
        xs=list(range(x0,x1,step_x))+[x1]
        for bands,yy in enumerate(range(y0,y1,step_y),1):
            grad=f'{nid}-tone-{bands}';g=ET.SubElement(definitions,'linearGradient',{'id':grad,'gradientUnits':'userSpaceOnUse','x1':str(x0),'y1':'0','x2':str(x1),'y2':'0'})
            for xx in xs:
                c=colors[min(yy+step_y//2-y0,y1-y0-1),min(xx-x0,x1-x0-1)]
                ET.SubElement(g,'stop',{'offset':str((xx-x0)/(x1-x0)),'stop-color':hex_color(c)})
            ET.SubElement(container,'rect',{'id':f'{nid}-band-{bands}','x':str(x0),'y':str(yy),'width':str(x1-x0),'height':str(min(step_y,y1-yy)),'fill':f'url(#{grad})'})
        after.setdefault(index,[]).append(group)
        notes.append({'id':nid,'type':'surface','clipSourceIndex':index,'samplePixels':int(valid.sum()),'bands':bands})
    art=[]
    for i,n in enumerate(originals):
        if local(n) in ('defs','title','desc'):continue
        if i not in removed:art.append(n)
        art.extend(after.get(i,[]))
    art=before+art
    blur=float(edits.get('edgeBlur',0))
    if blur>0:
        f=ET.SubElement(definitions,'filter',{'id':'refinement-edge-softness','x':'-1%','y':'-1%','width':'102%','height':'102%','color-interpolation-filters':'sRGB'})
        ET.SubElement(f,'feGaussianBlur',{'stdDeviation':str(blur)})
        group=ET.Element('g',{'id':'refined-painting','filter':'url(#refinement-edge-softness)'});group.extend(art);art=[group]
    root[:]=[n for n in originals if local(n) in ('defs','title','desc')]+[definitions]+art
    audit_native(root);out.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(root).write(out,encoding='utf-8',xml_declaration=True)
    report={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(Path(a.config).read_bytes()).hexdigest(),'refinements':notes,'edgeBlur':blur,'removedPathsReplacedByNativeFields':len(removed)}
    out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
