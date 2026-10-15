"""Metadata for staging; approximate bounds never rewrite the selected curves."""
import math,re,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

NS='http://www.w3.org/2000/svg'
NUM=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
GEOMETRY={'path','rect','circle','ellipse','line','polyline','polygon','use','text'}
ET.register_namespace('',NS)
def local(node):return node.tag.rsplit('}',1)[-1]
def slug(value):return re.sub('[^a-zA-Z0-9_-]+','-',str(value)).strip('-') or 'unnamed'
def serialize(node):return ET.tostring(node,encoding='unicode').replace(' xmlns="'+NS+'"','')
def rgb(value):
    if re.fullmatch(r'#[0-9a-fA-F]{6}',value or ''):return np.array([int(value[i:i+2],16) for i in (1,3,5)],float)
    if re.fullmatch(r'#[0-9a-fA-F]{3}',value or ''):return np.array([int(c*2,16) for c in value[1:]],float)
    return None
def union(boxes):
    boxes=[b for b in boxes if b is not None]
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else None
def bounds(node):
    """Bezier control-point bounds. Unsupported transforms return None."""
    if node.get('data-bbox'):
        b=[float(n) for n in re.findall(NUM,node.get('data-bbox'))]
        if len(b)!=4:raise ValueError('data-bbox needs x0,y0,x1,y1')
        return b
    tag=local(node);b=None
    def f(k,default=0):return float(node.get(k,default))
    if tag=='path':
        d=node.get('d','');commands=set(re.findall('[A-Za-z]',re.sub(NUM,'',d)));values=[float(n) for n in re.findall(NUM,d)]
        if values and len(values)%2==0 and commands<=set('MLCQZ'):
            xy=np.array(values).reshape(-1,2);b=[*xy.min(0),*xy.max(0)]
    elif tag=='rect':b=[f('x'),f('y'),f('x')+f('width'),f('y')+f('height')]
    elif tag in ('circle','ellipse'):
        rx=f('r') if tag=='circle' else f('rx');ry=f('r') if tag=='circle' else f('ry');b=[f('cx')-rx,f('cy')-ry,f('cx')+rx,f('cy')+ry]
    elif tag=='line':b=[min(f('x1'),f('x2')),min(f('y1'),f('y2')),max(f('x1'),f('x2')),max(f('y1'),f('y2'))]
    elif tag in ('polygon','polyline'):
        values=[float(n) for n in re.findall(NUM,node.get('points',''))]
        if values and len(values)%2==0:
            xy=np.array(values).reshape(-1,2);b=[*xy.min(0),*xy.max(0)]
    elif tag=='g':b=union([bounds(n) for n in node if local(n) not in ('defs','clipPath','mask')])
    tr=node.get('transform','')
    if b is not None and tr:
        if not re.fullmatch(r'\s*translate\([^)]*\)\s*',tr):return None
        t=[float(v) for v in re.findall(NUM,tr)]
        if len(t)==1:t.append(0)
        if len(t)!=2:return None
        b=[b[0]+t[0],b[1]+t[1],b[2]+t[0],b[3]+t[1]]
    return [float(n) for n in b] if b is not None else None
def info(node,w,h):
    b=bounds(node) or [0,0,w,h]
    return {'bbox':b,'x':(b[0]+b[2])/2,'y':(b[1]+b[3])/2,'area':max(0,(b[2]-b[0])*(b[3]-b[1])),'rgb':rgb(node.get('fill',''))}
def matches(rule,item,w,h):
    if 'bbox' in rule:
        x0,y0,x1,y1=rule['bbox']
        if not(x0<=item['x']<=x1 and y0<=item['y']<=y1):return False
    for key,value in [('minArea',item['area']),('maxArea',item['area']),('minAreaRatio',item['area']/(w*h)),('maxAreaRatio',item['area']/(w*h))]:
        if key in rule and ((key.startswith('min') and value<rule[key]) or (key.startswith('max') and value>rule[key])):return False
    for cond in rule.get('color',[]):
        if item['rgb'] is None:return False
        value=float(np.dot(item['rgb'],cond['coefficients']))
        if 'min' in cond and value<cond['min']:return False
        if 'max' in cond and value>cond['max']:return False
    return True
def assigned_part(node,item,cfg,w,h):
    if node.get('data-part'):return node.get('data-part')
    if cfg.get('rules'):
        for rule in cfg['rules']:
            if matches(rule,item,w,h):return rule['part']
    else:
        candidates=[p for p in cfg['parts'] if matches({'bbox':p['bbox']},item,w,h)]
        if candidates:return min(candidates,key=lambda p:(p['bbox'][2]-p['bbox'][0])*(p['bbox'][3]-p['bbox'][1]))['id']
    return cfg.get('defaultPart',cfg['parts'][0]['id'])
def read_config(path,w,h):
    import json
    cfg=json.loads(Path(path).read_text('utf-8'))
    if not cfg.get('parts'):raise ValueError('Config requires measured parts with id, name, bbox; see pipeline.md')
    ids=[]
    for p in cfg['parts']:
        if slug(p['id'])!=p['id']:raise ValueError('Part IDs must be simple unique slugs')
        b=p['bbox']
        if len(b)!=4 or not all(math.isfinite(v) for v in b) or not(0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h):raise ValueError('Part bbox outside image: '+p['id'])
        p.setdefault('name',p['id']);p.setdefault('icon','◇');ids.append(p['id'])
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate part IDs')
    if cfg.get('defaultPart',ids[0]) not in ids:raise ValueError('Unknown defaultPart')
    for rule in cfg.get('rules',[]):
        if rule['part'] not in ids:raise ValueError('Unknown rule part')
        for c in rule.get('color',[]):
            if len(c['coefficients'])!=3:raise ValueError('Color coefficients need R,G,B weights')
    return cfg
def audit_native(root):
    ids=set()
    for n in root.iter():
        if local(n) in ('image','feImage','foreignObject','script','canvas'):raise ValueError('Non-native or executable SVG element: '+local(n))
        nid=n.get('id')
        if nid:
            if nid in ids:raise ValueError('Duplicate SVG id: '+nid)
            ids.add(nid)
        for key,value in n.attrib.items():
            if key.rsplit('}',1)[-1]=='href' and not value.startswith('#'):raise ValueError('External SVG reference is not allowed')
            if re.search(r'(?:data:|https?:)',value,re.I):raise ValueError('Embedded or external SVG asset is not allowed')
    return ids
