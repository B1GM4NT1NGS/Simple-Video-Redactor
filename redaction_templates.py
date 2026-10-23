"""Named, resolution-independent fixed redaction layouts stored locally."""
import json, math, os, pathlib, tempfile

def layout(boxes, mode):
    regions=[]
    for box in boxes:
        region={key:float(box[key]) for key in ('x','y','w','h')}
        if not all(math.isfinite(v) for v in region.values()):raise ValueError('Invalid box coordinates.')
        if not (0<=region['x']<1 and 0<=region['y']<1 and region['w']>0 and region['h']>0):raise ValueError('Invalid box area.')
        region['w']=min(region['w'],1-region['x']);region['h']=min(region['h'],1-region['y']);regions.append(region)
    if not regions:raise ValueError('Draw at least one box before saving a template.')
    if mode not in ('keep','hide'):raise ValueError('Invalid redaction mode.')
    return dict(mode=mode,boxes=regions)

def apply_layout(template,duration):
    clean=layout(template['boxes'],template['mode'])
    return [dict(b,start=0.,end=duration) for b in clean['boxes']]

class TemplateStore:
    def __init__(self,path):self.path=pathlib.Path(path)
    def load(self):
        if not self.path.exists():return {}
        data=json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('version')!=1 or not isinstance(data.get('templates'),dict):raise ValueError('Unrecognized template file format.')
        return {name:layout(value['boxes'],value['mode']) for name,value in data['templates'].items()}
    def save(self,templates):
        clean={name:layout(value['boxes'],value['mode']) for name,value in templates.items()}
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix='templates-',suffix='.tmp',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(dict(version=1,templates=clean),stream,indent=2)
            os.replace(temp,self.path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
