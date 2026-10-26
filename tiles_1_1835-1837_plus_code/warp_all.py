import numpy as np, json, cv2, sys
from PIL import Image, ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS=None
sys.path.insert(0,'.')
from pipeline import rot
B=json.load(open('boxes_pipeline.json')); MAN=json.load(open('boxes3.json'))
MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
# year and gauge per quarter, read from the handwritten headers
META={'210012':(1835,['Ulm']*4),'210013':(1836,['Ulm']*4),'210015':(1837,['Ulm']*4),'210018':(1839,['Ulm']*4),
      '210024':(1845,['Ulm','Ulm','Neu-Ulm','Neu-Ulm']),'210027':(1848,['Neu-Ulm']*4),'210028':(1849,['Neu-Ulm']*4),
      '210029':(1850,['Neu-Ulm']*4),'210042':(1862,['Neu-Ulm']*4),'210043':(1863,['Neu-Ulm']*4)}
FORM={'210042':'1862-63 form','210043':'1862-63 form'}
INSERT={('210015',1),('210015',2)}
TW,TH=744,3000; PAD=(232,232,232)
tiles={}; meta=[]
for n,(year,stations) in META.items():
    info=B[n]; full=np.asarray(Image.open(f'/mnt/user-data/uploads/Bay_Landesamt_fuer_Wasserwirtschaft_{n}.tif').convert('RGB'))
    s=full.shape[1]/info['shape'][1]
    rots=[rot(full,h['angle'],h['cx']*s,h['cy']*s,(255,255,255)) if abs(h['angle'])>0.01 else full for h in info['halves']]
    std=[(P['base']-P['top'])*s for i,P in enumerate(info['panels']) if (n,i) not in INSERT]
    ky=TH/np.median(std)
    for pi,P in enumerate(info['panels']):
        img=rots[P['half']]
        if (n,pi) in INSERT: P=dict(MAN[n]['panels'][pi])   # hand-checked boxes for the pasted 1837 sheet
        for mi in range(3):
            m=pi*3+mi
            x0,x1=P['xs'][mi]*s,P['xs'][mi+1]*s; y0,y1=P['top']*s,P['base']*s
            crop=img[int(round(y0)):int(round(y1)),int(round(x0)):int(round(x1))]
            if (n,pi) in INSERT:
                h=int(round((y1-y0)*ky)); tile=np.full((TH,TW,3),PAD,np.uint8); tile[TH-h:]=cv2.resize(crop,(TW,h),interpolation=cv2.INTER_AREA)
                form='pasted 1837 sheet'
            else:
                tile=cv2.resize(crop,(TW,TH),interpolation=cv2.INTER_AREA); form=FORM.get(n,'1830s-50s form')
            tiles[(year,m)]=tile
            Image.fromarray(tile).save(f'out2/tiles/{year}_{m+1:02d}_{MON[m]}.jpg',quality=90)
            meta.append(dict(scan=n,year=year,month=m+1,gauge=stations[pi],form=form,
                deskew_deg=round(info['halves'][P.get('half',0 if pi<2 else 1)]['angle'],2) if (n,pi) not in INSERT else 0.0,
                box_px_fullres_after_deskew=[round(x0),round(y0),round(x1),round(y1)],
                flags=info['panels'][pi].get('flags',[]) + (['hand-checked box (pasted sheet)'] if (n,pi) in INSERT else [])))
    del full,rots
    print('done',n,year)
json.dump(meta,open('out2/month_boxes.json','w'),indent=1)
import pickle; pickle.dump({k:cv2.resize(v,(186,750),interpolation=cv2.INTER_AREA) for k,v in tiles.items()},open('thumbs.pkl','wb'))
