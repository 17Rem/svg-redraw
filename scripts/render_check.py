"""Compare an SVG rasterization to its reference; metrics are not an acceptance gate."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageColor

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ref',required=True);p.add_argument('--render',required=True)
    p.add_argument('--out',required=True);p.add_argument('--crop',action='append',default=[])
    p.add_argument('--matte',default='#ffffff');a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    def load(path):
        im=Image.open(path).convert('RGBA');bg=Image.new('RGBA',im.size,ImageColor.getrgb(a.matte)+(255,));return Image.alpha_composite(bg,im).convert('RGB')
    ref,render=load(a.ref),load(a.render)
    if ref.size!=render.size:raise ValueError(f'Dimension mismatch: {ref.size} vs {render.size}')
    def compare(x,y,name):
        d=np.abs(np.asarray(x).astype(float)-np.asarray(y).astype(float))
        pair=Image.new('RGB',(x.width*2,x.height));pair.paste(x,(0,0));pair.paste(y,(x.width,0));pair.save(out/(name+'-side.png'))
        return {'mae_0_255':float(d.mean()),'rmse_0_255':float(np.sqrt((d*d).mean())),'any_channel_over_25_fraction':float((d.max(2)>25).mean()),'pixel_identical':bool(not d.any())}
    result={'dimensions':ref.size,'matte':a.matte,'full':compare(ref,render,'full'),'crops':{}}
    d=np.abs(np.asarray(ref).astype(float)-np.asarray(render).astype(float))
    Image.fromarray(np.uint8(np.clip(d*4,0,255))).save(out/'difference-4x.png')
    for entry in a.crop:
        name,coords=entry.split(':',1);box=tuple(map(int,coords.split(',')))
        if len(box)!=4 or not(0<=box[0]<box[2]<=ref.width and 0<=box[1]<box[3]<=ref.height):raise ValueError('Crop outside reference')
        safe=''.join(c for c in name if c.isalnum() or c in '-_')
        if not safe:raise ValueError('Crop needs a name')
        result['crops'][name]=compare(ref.crop(box),render.crop(box),safe)
    (out/'metrics.json').write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result))

if __name__=='__main__':main()
