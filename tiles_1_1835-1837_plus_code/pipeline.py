"""Gauge-chart month alignment pipeline.
detect: python pipeline.py detect SCRATCH scan1,scan2,...  -> SCRATCH/boxes_pipeline.json
Each spread: estimate tilt of left & right page halves, deskew, then per quarter-panel:
  month separators  = 4-line comb fit on column median-darkness (width 214-226 px @3000)
  baseline          = top line of the printed day strip (triple of rulings 12-18/25-36 px apart)
                      with dense grid above and sparse day-number row below
  top               = first strong ruling with dense vertical grid below it
"""
import numpy as np, cv2, json, sys
WS=3000
def angle(g,rng=2.0):
    H,W=g.shape; c=(W/2,H/2); best=None
    for ang in np.arange(-rng,rng+0.001,0.05):
        r=cv2.warpAffine(g,cv2.getRotationMatrix2D(c,ang,1.0),(W,H),borderValue=255)
        prof=r[:,int(W*.05):int(W*.95)].mean(1); sc=np.var(np.diff(prof))
        if best is None or sc>best[0]: best=(sc,ang)
    return float(best[1])
def rot(img,ang,cx,cy,border):
    H,W=img.shape[:2]
    return cv2.warpAffine(img,cv2.getRotationMatrix2D((cx,cy),ang,1.0),(W,H),flags=cv2.INTER_LINEAR,borderValue=border)
def detect_panel(a,p):
    H,W=a.shape[:2]; gi=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY).astype(float)
    y0,y1=int(H*.3),int(H*.72); paper=np.percentile(gi[y0:y1],90)
    colp=paper-np.median(gi[y0:y1],axis=0); cmax=np.maximum.reduce([np.roll(colp,k) for k in (-1,0,1)])
    best=max(((sum(cmax[int(round(x0+k*w))] for k in range(4)),x0,w) for x0 in range(p-30,p+31) for w in np.arange(214,226.5,0.5) if int(round(x0+3*w))<W))
    xs=[int(round(best[1]+k*best[2])) for k in range(4)]; xa,xb=xs[0]+5,xs[3]-5
    rowp=paper-np.median(gi[:,xa:xb],axis=1); rmax=np.maximum.reduce([np.roll(rowp,k) for k in (-1,0,1)])
    bgm=cv2.medianBlur(gi.astype(np.uint8),31).astype(float)
    vv=cv2.morphologyEx(((bgm-gi)>12).astype(np.uint8),cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,9)))
    dens=vv[:,xa:xb].mean(1); ref=np.median(dens[int(H*.4):int(H*.65)])
    cands=[]
    for b in range(int(H*0.75),int(H*0.905)):
        s1=rmax[b]
        if s1<rmax[b-1] or s1<rmax[b+1]: continue
        cands.append((b,min(s1,rmax[b+12:b+19].max(),rmax[b+25:b+37].max()),dens[b-14:b-3].mean(),dens[b+3:b+11].mean()))
    mt=max(c[1] for c in cands)
    ok=[c for c in cands if c[1]>=0.3*mt and c[2]>=0.5*ref and c[3]<0.4*c[2]]
    base=max(ok,key=lambda c:c[0])[0] if ok else max(cands,key=lambda c:c[1])[0]
    up=[b2 for b2 in range(base-18,base-11) if rmax[b2]>=rmax[b2-1] and rmax[b2]>=rmax[b2+1] and rmax[b2]>=0.5*rmax[base] and dens[b2-14:b2-3].mean()>=0.5*ref]
    if up: base=max(up,key=lambda y:rmax[y])
    tb=range(int(H*0.12),int(H*0.32)); mx=max(rmax[y] for y in tb)
    top=next((y for y in tb if rmax[y]>=0.4*mx and rmax[y]>=rmax[y-1] and rmax[y]>=rmax[y+1] and dens[y+5:y+40].mean()>=0.5*ref),int(H*0.19))
    return dict(xs=xs,w=float(best[2]),top=int(top),base=int(base),conf=dict(triple_ok=bool(ok),moved_up=bool(up)),_r=rmax)
def detect(S,names,PRI):
    out={}
    for n in names:
        a=np.load(f'{S}/{n}_small.npy'); H,W=a.shape[:2]
        g=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY).astype(np.float32)
        halves=[]
        for side,(c0,c1) in enumerate([(0,W//2),(W//2,W)]):
            ang=angle(g[:,c0:c1]); cx,cy=(c0+c1)/2,H/2
            halves.append(dict(angle=ang,cx=cx,cy=cy,img=rot(a,ang,cx,cy,(255,255,255))))
        panels=[]
        for i,p in enumerate(PRI[n]):
            h=halves[0 if i<2 else 1]
            P=detect_panel(h['img'],p); P.update(half=0 if i<2 else 1); panels.append(P)
        # spread consistency: shared-form panels should agree on top/base
        for key in ('top','base'):
            m=np.median([P[key] for P in panels])
            for P in panels:
                if abs(P[key]-m)>12:
                    P.setdefault('flags',[]).append(f'{key} deviates {P[key]-m:+.0f}px from spread median')
                    if sum(abs(Q[key]-m)<=12 for Q in panels)>=3:   # majority agrees -> repair
                        r=P['_r']; mm=int(m); rng=range(mm-12,mm+13)
                        if key=='base': new=max(rng,key=lambda b:min(r[b],r[b+12:b+19].max(),r[b+25:b+37].max()))
                        else: new=max(rng,key=lambda y:r[y])
                        P['flags'].append(f'repaired {key} {P[key]}->{new}'); P[key]=int(new)
        for P in panels: P.pop('_r',None)
        out[n]=dict(shape=[H,W],halves=[{k:v for k,v in h.items() if k!='img'} for h in halves],panels=panels)
        vis=halves[0]['img'].copy(); vis[:,W//2:]=halves[1]['img'][:,W//2:]
        for P in panels:
            for i in range(3): cv2.rectangle(vis,(P['xs'][i],P['top']),(P['xs'][i+1],P['base']),(255,0,0),2)
        cv2.imwrite(f'{S}/pbox{n}.png',cv2.cvtColor(cv2.resize(vis,(1800,int(H*1800/W))),cv2.COLOR_RGB2BGR))
        print(n,[round(h['angle'],2) for h in halves],[(P['xs'][0],P['xs'][3],P['w'],P['top'],P['base'],P.get('flags','')) for P in panels])
    return out
if __name__=='__main__':
    S=sys.argv[2]; names=sys.argv[3].split(',')
    PRI=json.load(open(f'{S}/priors.json'))
    res=detect(S,names,PRI)
    try: old=json.load(open(f'{S}/boxes_pipeline.json'))
    except Exception: old={}
    old.update(res); json.dump(old,open(f'{S}/boxes_pipeline.json','w'),indent=1)
