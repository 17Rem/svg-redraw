"""Trace at original dimensions; keep a baseline and tune observed discrepancies."""
import argparse, hashlib, importlib.metadata, json
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--src',required=True);p.add_argument('--out',required=True)
    p.add_argument('--preset',choices=['baseline','detail','fidelity'],default='fidelity')
    p.add_argument('--mode',choices=['spline','polygon','none'],default='spline')
    for flag,kind,default in [('filter-speckle',int,0),('color-precision',int,8),('layer-difference',int,None),('corner-threshold',int,60),('length-threshold',float,3.5),('max-iterations',int,10),('splice-threshold',int,45),('path-precision',int,2)]:
        p.add_argument('--'+flag,type=kind,default=default)
    a=p.parse_args();src=Path(a.src).resolve();out=Path(a.out).resolve()
    if src==out:raise ValueError('Output must not overwrite the reference')
    import vtracer
    out.parent.mkdir(parents=True,exist_ok=True)
    raw=out.with_name(out.stem+'.raw.svg')
    options={k:v for k,v in vars(a).items() if k not in ('src','out','preset')}
    if options['layer_difference'] is None:options['layer_difference']={'baseline':8,'detail':4,'fidelity':1}[a.preset]
    options.update(colormode='color',hierarchical='stacked')
    vtracer.convert_image_to_svg_py(str(src),str(raw),**options)
    ET.register_namespace('','http://www.w3.org/2000/svg')
    tree=ET.parse(raw);root=tree.getroot();before=len(list(root));empty=0
    kept=[]
    for node in root:
        if node.tag.rsplit('}',1)[-1]=='path' and not node.get('d','').strip():
            empty+=1
        else:kept.append(node)
    root[:]=kept
    with Image.open(src) as im:w,h=im.size
    root.set('viewBox',f'0 0 {w} {h}');root.set('preserveAspectRatio','xMidYMid meet')
    tree.write(out,encoding='utf-8',xml_declaration=True)
    report={'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'dimensions':[w,h],
        'preset':a.preset,'vtracer_version':importlib.metadata.version('vtracer'),'parameters':options,
        'raw_elements':before,'empty_paths_removed':empty,'nonempty_paths':sum(n.tag.endswith('path') for n in root)}
    out.with_suffix('.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report))

if __name__=='__main__':main()
