"""
VisionCount v6 — Roboflow Gender Detection
===========================================
Gender: Roboflow model (gender_model/1) detects Male/Female directly
Other classes: YOLOv8m detects vehicles, animals, bicycles
"""

import uuid, cv2, math, json, queue, threading, shutil, time, base64
import numpy as np
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

BASE   = Path(__file__).parent
UPLOAD = BASE/"uploads";  UPLOAD.mkdir(exist_ok=True)
FRAMES = BASE/"frames";   FRAMES.mkdir(exist_ok=True)
OUTPUT = BASE/"outputs";  OUTPUT.mkdir(exist_ok=True)

# ── Roboflow client ────────────────────────────────────────────────────────
try:
    from inference_sdk import InferenceHTTPClient
    RF_CLIENT = InferenceHTTPClient(
        api_url="https://detect.roboflow.com",
        api_key="JeSjx6JSeqnV3dzhu8nX"
    )
    RF_MODEL_ID  = "gender_model/1"
    USE_ROBOFLOW = True
    print("[VC6] Roboflow client ready ✓  model:", RF_MODEL_ID)
except ImportError:
    USE_ROBOFLOW = False
    print("[VC6] inference-sdk not installed — run: pip install inference-sdk")
    print("[VC6] Falling back to local gender model")

YOLO_MODEL    = "yolov8m.pt"
YOLO_IMGSZ    = 640
YOLO_CONF     = 0.20
YOLO_IOU      = 0.45
FRAME_SKIP    = 3
LIVE_EVERY    = 5
WARMUP_FRAMES = 15
GENDER_EVERY  = 8
MIN_CROP_H    = 50
MAX_GALLERY   = 40
CANVAS_W, CANVAS_H = 800, 450

MODEL        = None
MODEL_READY  = False
MODEL_ERROR  = None
GENDER_FN    = None
GENDER_READY = False

# ── YOLO loader ────────────────────────────────────────────────────────────
def _load_yolo():
    global MODEL, MODEL_READY, MODEL_ERROR
    try:
        print(f"\n[VC6] Loading {YOLO_MODEL}...")
        t0 = time.time()
        from ultralytics import YOLO
        MODEL = YOLO(YOLO_MODEL)
        dummy = np.zeros((640,640,3), dtype=np.uint8)
        MODEL(dummy, verbose=False); MODEL(dummy, verbose=False)
        MODEL_READY = True
        print(f"[VC6] YOLO ready {time.time()-t0:.1f}s ✓")
    except Exception as e:
        MODEL_ERROR = str(e); print(f"[VC6] YOLO FAIL: {e}")

# ── Gender loader (fallback only — used if Roboflow not available) ─────────
def _load_gender():
    global GENDER_FN, GENDER_READY

    if USE_ROBOFLOW:
        # Roboflow handles gender directly in detection — no separate classifier needed
        GENDER_FN    = lambda _: "Unknown"
        GENDER_READY = True
        print("[VC6] Gender: Roboflow API (direct detection) ✓")
        return

    # Fallback 1: Your trained gender_model.pth
    custom = BASE / "gender_model.pth"
    if custom.exists():
        try:
            import torch, torch.nn as nn
            from torchvision import transforms, models
            ckpt    = torch.load(str(custom), map_location="cpu")
            classes = ckpt["classes"]
            imgsz   = ckpt.get("img_size", 112)
            net     = models.mobilenet_v3_small(weights=None)
            net.classifier[3] = nn.Linear(net.classifier[3].in_features, 2)
            net.load_state_dict(ckpt["model_state"])
            net.eval()
            tf = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((imgsz, imgsz)),
                transforms.ToTensor(),
                transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
            ])
            def _custom(crop):
                try:
                    if crop.shape[0] < MIN_CROP_H or crop.shape[1] < 20:
                        return "Unknown"
                    rgb    = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    tensor = tf(rgb).unsqueeze(0)
                    with torch.no_grad():
                        probs = torch.softmax(net(tensor), dim=1)[0]
                        idx   = probs.argmax().item()
                        conf  = probs[idx].item()
                    if conf < 0.65: return "Unknown"
                    lbl = classes[idx]
                    if lbl.lower() in ("male","man"):     return "Male"
                    if lbl.lower() in ("female","woman"): return "Female"
                    return "Unknown"
                except Exception:
                    return "Unknown"
            GENDER_FN    = _custom
            GENDER_READY = True
            print(f"[VC6] Gender: trained model {classes} acc={ckpt.get('val_accuracy',0):.1f}% ✓")
            return
        except Exception as e:
            print(f"[VC6] Trained model error: {e}")

    # Fallback 2: InsightFace
    try:
        import warnings
        warnings.filterwarnings("ignore")
        from insightface.app import FaceAnalysis
        fa = FaceAnalysis(name="buffalo_sc",
                          allowed_modules=["detection","genderage"],
                          providers=["CPUExecutionProvider"])
        fa.prepare(ctx_id=0, det_size=(160,160))
        def _insightface(crop_bgr):
            try:
                faces = fa.get(crop_bgr)
                if not faces: return "Unknown"
                face = max(faces, key=lambda f:(f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))
                return "Male" if face.gender == 1 else "Female"
            except Exception:
                return "Unknown"
        GENDER_FN    = _insightface
        GENDER_READY = True
        print("[VC6] Gender: InsightFace ✓")
        return
    except Exception:
        pass

    print("[VC6] No gender model — install inference-sdk for Roboflow")
    GENDER_FN    = lambda _: "Unknown"
    GENDER_READY = True

@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_load_yolo,   daemon=True).start()
    threading.Thread(target=_load_gender, daemon=True).start()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/frames",  StaticFiles(directory=str(FRAMES)),  name="frames")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT)),  name="outputs")

# YOLO class → category (person excluded — Roboflow handles it)
CAT_MAP = {
    "bicycle":"Bicycle","motorbike":"Bicycle","motorcycle":"Bicycle",
    "cat":"Animal","dog":"Animal","horse":"Animal","cow":"Animal","sheep":"Animal",
    "bird":"Animal","elephant":"Animal","bear":"Animal",
    "car":"Vehicle","truck":"Vehicle","bus":"Vehicle","train":"Vehicle",
    # person kept for fallback when Roboflow not available
    "person":"Person",
}

CATS = ["Male","Female","Bicycle","Animal","Vehicle"]
CMETA = {
    "Male":    {"icon":"Male",   "color":"#3b82f6","bgr":(255,140,0)},
    "Female":  {"icon":"Female", "color":"#ec4899","bgr":(147,20,255)},
    "Bicycle": {"icon":"Bicycle","color":"#fbbf24","bgr":(36,191,251)},
    "Animal":  {"icon":"Animal", "color":"#a78bfa","bgr":(250,139,167)},
    "Vehicle": {"icon":"Vehicle","color":"#4ade80","bgr":(100,220,100)},
    "Unknown": {"icon":"",       "color":"#6b7280","bgr":(80,80,80)},
    "Person":  {"icon":"Person", "color":"#06b6d4","bgr":(200,150,0)},
}

# ── Tracker ────────────────────────────────────────────────────────────────
class Track:
    def __init__(self, tid, cx, cy, cat, box):
        self.tid=tid; self.cx=cx; self.cy=cy
        self.raw_cat=cat; self.bbox=box
        self.lost=0; self.age=0
        self.prev_sd=None; self.crossed=False
        self.cls=cat if cat not in ('Person',) else 'Unknown'
        self.gender_frame=-(GENDER_EVERY)

    @property
    def display_cls(self):
        if self.raw_cat == 'Person':
            return self.cls if self.cls in ('Male','Female') else 'Unknown'
        if self.raw_cat in ('Male','Female'):
            return self.raw_cat
        return self.raw_cat

class Tracker:
    def __init__(self):
        self.tracks=[]; self.nid=0
    def update(self, dets):
        for t in self.tracks: t.lost+=1
        matched=set()
        for t in self.tracks:
            bd,bi=1e9,-1
            for i,(cx,cy,*_) in enumerate(dets):
                if i in matched: continue
                d=math.hypot(cx-t.cx,cy-t.cy)
                if d<bd: bd,bi=d,i
            if bi>=0 and bd<150:
                d=dets[bi]; t.cx,t.cy=d[0],d[1]
                t.raw_cat=d[2]; t.bbox=(d[3],d[4],d[5],d[6])
                # Update cls directly for Roboflow detections
                if d[2] in ('Male','Female'): t.cls=d[2]
                t.lost=0; t.age+=1; matched.add(bi)
        for i,d in enumerate(dets):
            if i not in matched:
                tk=Track(self.nid,d[0],d[1],d[2],(d[3],d[4],d[5],d[6]))
                if d[2] in ('Male','Female'): tk.cls=d[2]
                self.tracks.append(tk); self.nid+=1
        self.tracks=[t for t in self.tracks if t.lost<=35]
        return self.tracks

# ── Gender inference (fallback only) ──────────────────────────────────────
def run_gender(frame, track, fn):
    if USE_ROBOFLOW: return  # Roboflow already classified
    if not GENDER_READY or track.raw_cat != 'Person': return
    if fn - track.gender_frame < GENDER_EVERY: return
    x1,y1,x2,y2 = track.bbox
    h_box = y2-y1
    if h_box < MIN_CROP_H: return
    y2c = y1 + int(h_box * 0.65)
    crop = frame[max(0,y1):y2c, max(0,x1):max(0,x2)]
    if crop.size==0 or crop.shape[0]<20 or crop.shape[1]<20: return
    result = GENDER_FN(crop)
    if result in ('Male','Female'): track.cls = result
    track.gender_frame = fn

# ── Drawing ────────────────────────────────────────────────────────────────
def signed_dist(lx1,ly1,lx2,ly2,px,py):
    dx,dy=lx2-lx1,ly2-ly1; L=math.sqrt(dx*dx+dy*dy)
    if L<1: return 0.0
    return(-dy*(px-lx1)+dx*(py-ly1))/L

def dash_line(img,p1,p2,col=(0,212,170),thick=3):
    x1,y1=p1; x2,y2=p2; L=math.hypot(x2-x1,y2-y1)
    if L<1: return
    dx,dy=(x2-x1)/L,(y2-y1)/L; pos,draw=0.0,True
    while pos<L:
        end=min(pos+(18 if draw else 9),L)
        if draw: cv2.line(img,(int(x1+dx*pos),int(y1+dy*pos)),
                              (int(x1+dx*end),int(y1+dy*end)),col,thick)
        pos,draw=end,not draw

def annotate(frame, tracks, lx1,ly1,lx2,ly2, counters, warmup=False):
    h,w=frame.shape[:2]
    lc=(80,80,80) if warmup else (0,212,170)
    dash_line(frame,(lx1,ly1),(lx2,ly2),lc,3)
    cv2.circle(frame,(lx1,ly1),8,lc,-1); cv2.circle(frame,(lx2,ly2),8,lc,-1)
    dx,dy=lx2-lx1,ly2-ly1; L=math.hypot(dx,dy) or 1
    nx,ny=-dy/L,dx/L; mx,my=(lx1+lx2)//2,(ly1+ly2)//2
    if warmup:
        cv2.putText(frame,"INITIALIZING...",(int(mx-70),int(my-18)),
                    cv2.FONT_HERSHEY_SIMPLEX,0.6,(80,80,80),2)
    else:
        cv2.putText(frame,"IN",(int(mx+nx*56),int(my+ny*56)+5),
                    cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,212,170),2)
        cv2.putText(frame,"OUT",(int(mx-nx*72),int(my-ny*72)+5),
                    cv2.FONT_HERSHEY_SIMPLEX,0.65,(80,80,255),2)

    for t in tracks:
        if t.lost>0: continue
        cls  = t.display_cls
        meta = CMETA.get(cls, CMETA["Unknown"])
        bgr  = meta["bgr"]
        x1,y1,x2,y2 = t.bbox
        cv2.rectangle(frame,(x1,y1),(x2,y2),bgr,2)
        cv2.circle(frame,(t.cx,t.cy),4,bgr,-1)
        # Label — plain text, no unicode symbols
        icon = meta.get("icon","")
        lbl  = icon if icon else cls
        (tw,th),_=cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.55,2)
        cv2.rectangle(frame,(x1,y1-th-10),(x1+tw+6,y1),(20,20,20),-1)
        cv2.putText(frame,lbl,(x1+3,y1-5),cv2.FONT_HERSHEY_SIMPLEX,0.55,bgr,2)

    # Counter overlay
    pw,ph=230,30+len(CATS)*22+8; px0,py0=w-pw-8,8
    ov=frame.copy(); cv2.rectangle(ov,(px0,py0),(px0+pw,py0+ph),(8,12,16),-1)
    cv2.addWeighted(ov,0.80,frame,0.20,0,frame)
    cv2.rectangle(frame,(px0,py0),(px0+pw,py0+ph),(0,212,170),1)
    cv2.putText(frame,"VISIONCOUNT",(px0+7,py0+18),cv2.FONT_HERSHEY_SIMPLEX,0.42,(0,212,170),1)
    for i,cat in enumerate(CATS):
        y=py0+32+i*22; bgr=CMETA[cat]["bgr"]
        cv2.putText(frame,cat,(px0+7,y),cv2.FONT_HERSHEY_SIMPLEX,0.38,bgr,1)
        cv2.putText(frame,f"IN:{counters[cat]['IN']}  OUT:{counters[cat]['OUT']}",
            (px0+90,y),cv2.FONT_HERSHEY_SIMPLEX,0.38,(220,220,220),1)
    return frame

def sse(ev,data): return f"event: {ev}\ndata: {json.dumps(data)}\n\n"
jobs={}

def run_detection(job_id, cx1,cy1, cx2,cy2, start_frame):
    import tempfile, os as _os
    job=jobs[job_id]; q=job["queue"]
    vw,vh=job["vid_w"],job["vid_h"]; fps=job["fps"]; total=job["total_frames"]
    out_w=min(vw,1280); out_h=min(vh,720)

    lx1=int(cx1*out_w/CANVAS_W); ly1=int(cy1*out_h/CANVAS_H)
    lx2=int(cx2*out_w/CANVAS_W); ly2=int(cy2*out_h/CANVAS_H)
    print(f"[VC6] Line:({lx1},{ly1})→({lx2},{ly2}) start={start_frame} {out_w}x{out_h}")

    init_c={c:{"IN":0,"OUT":0} for c in CATS}
    q.put(sse("frame",{"frame":start_frame,"progress":0,"img":"",
                       "fps_proc":0,"dets":0,"warmup":True,"counters":init_c}))

    tracker=Tracker(); counters={c:{"IN":0,"OUT":0} for c in CATS}
    frames_left=total-start_frame
    opath=OUTPUT/f"{job_id}_output.mp4"
    writer=cv2.VideoWriter(str(opath),cv2.VideoWriter_fourcc(*"mp4v"),fps,(out_w,out_h))
    cap=cv2.VideoCapture(job["video_path"])
    if start_frame>0: cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    fn=0; last_dets=[]; total_crossings=0; t0=time.time()

    try:
        while cap.isOpened():
            ret,frame=cap.read()
            if not ret: break
            frame=cv2.resize(frame,(out_w,out_h))
            in_warmup=(fn<WARMUP_FRAMES)

            if fn%FRAME_SKIP==0:
                last_dets=[]

                # ── Roboflow: detect Male/Female directly ─────────────────
                if USE_ROBOFLOW:
                    _fd,_tmp=tempfile.mkstemp(suffix=".jpg")
                    _os.close(_fd)
                    cv2.imwrite(_tmp, frame, [cv2.IMWRITE_JPEG_QUALITY,85])
                    try:
                        _res=RF_CLIENT.infer(_tmp, model_id=RF_MODEL_ID)
                        for pred in _res.get("predictions",[]):
                            _label=pred["class"].lower().strip()
                            _conf=float(pred.get("confidence",0))
                            if _conf < 0.30: continue
                            _cx=int(pred["x"]); _cy=int(pred["y"])
                            _w=int(pred["width"]); _h=int(pred["height"])
                            x1b=max(0,_cx-_w//2); y1b=max(0,_cy-_h//2)
                            x2b=min(out_w,_cx+_w//2); y2b=min(out_h,_cy+_h//2)
                            if "female" in _label:   cat="Female"
                            elif "male" in _label:   cat="Male"
                            else: continue
                            last_dets.append((_cx,_cy,cat,x1b,y1b,x2b,y2b))
                    except Exception as _e:
                        print(f"[RF] Error: {_e}")
                    finally:
                        try: _os.unlink(_tmp)
                        except: pass

                # ── YOLO: detect vehicles, animals, bicycles ──────────────
                res=MODEL(frame,verbose=False,imgsz=YOLO_IMGSZ,conf=YOLO_CONF,iou=YOLO_IOU)[0]
                for box in res.boxes:
                    name=MODEL.names[int(box.cls[0])]
                    # Skip person if Roboflow is handling it
                    if USE_ROBOFLOW and name=="person": continue
                    cat=CAT_MAP.get(name)
                    if not cat: continue
                    x1b,y1b,x2b,y2b=map(int,box.xyxy[0].tolist())
                    x1b=max(0,x1b);y1b=max(0,y1b);x2b=min(out_w,x2b);y2b=min(out_h,y2b)
                    last_dets.append(((x1b+x2b)//2,(y1b+y2b)//2,cat,x1b,y1b,x2b,y2b))

            tracks=tracker.update(last_dets)

            # Gender fallback (only when Roboflow not available)
            for t in tracks:
                if t.lost==0: run_gender(frame,t,fn)

            # Crossing detection
            new_crossings=[]
            for t in tracks:
                if t.lost>0: continue
                sd=signed_dist(lx1,ly1,lx2,ly2,t.cx,t.cy)
                if t.prev_sd is None:
                    t.prev_sd=sd
                elif not t.crossed and not in_warmup and t.age>=3 and t.prev_sd*sd<0:
                    direction="IN" if t.prev_sd<0 else "OUT"
                    cls=t.display_cls
                    if cls in counters:
                        counters[cls][direction]+=1
                    t.crossed=True; total_crossings+=1
                    new_crossings.append({
                        "cat":cls,"direction":direction,"tid":t.tid,
                        "frame":start_frame+fn,
                        "timestamp":round((start_frame+fn)/max(fps,1),2),
                    })
                    print(f"[VC6] CROSS {cls} {direction} tid={t.tid}")
                if in_warmup: t.prev_sd=sd; continue
                t.prev_sd=sd

            for c in new_crossings:
                q.put(sse("crossing",{**c,"counters":{k:dict(v)for k,v in counters.items()}}))

            ann=annotate(frame.copy(),tracks,lx1,ly1,lx2,ly2,counters,warmup=in_warmup)
            writer.write(ann)

            if fn%LIVE_EVERY==0:
                elapsed=time.time()-t0
                ok,buf=cv2.imencode('.jpg',ann,[cv2.IMWRITE_JPEG_QUALITY,60])
                b64=base64.b64encode(buf).decode() if ok else ""
                q.put(sse("frame",{
                    "frame":start_frame+fn,
                    "progress":min(int(fn/max(frames_left,1)*100),99),
                    "counters":{k:dict(v)for k,v in counters.items()},
                    "fps_proc":round(fn/elapsed if elapsed>0 else 0,1),
                    "dets":len(last_dets),"img":b64,"warmup":in_warmup,
                }))
            fn+=1

    except Exception as e:
        import traceback; tb=traceback.format_exc()
        print(f"[VC6] ERR:{e}\n{tb}")
        q.put(sse("error",{"message":str(e),"trace":tb}))
        jobs[job_id].update({"status":"error","error":str(e)}); return
    finally:
        cap.release(); writer.release()

    elapsed=time.time()-t0
    print(f"[VC6] Done {fn} frames, {total_crossings} crossings, {elapsed:.1f}s")
    analytics={
        "classes":[{"name":c,"in":counters[c]["IN"],"out":counters[c]["OUT"],
                    "icon":CMETA[c]["icon"],"color":CMETA[c]["color"]} for c in CATS],
        "meta":{"model":YOLO_MODEL,"gender":"Roboflow API" if USE_ROBOFLOW else "local model",
            "conf":str(YOLO_CONF),"frame_skip":str(FRAME_SKIP),
            "frames_processed":str(fn),"start_frame":str(start_frame),
            "fps":f"{fps:.0f}","resolution":f"{out_w}x{out_h}",
            "total_crossings":str(total_crossings),"proc_time":f"{elapsed:.1f}s",
            "proc_fps":f"{fn/elapsed:.1f}"if elapsed>0 else"0"}
    }
    jobs[job_id].update({"analytics":analytics,"output_url":f"/outputs/{job_id}_output.mp4","status":"done"})
    q.put(sse("done",{"analytics":analytics,"output_url":f"/outputs/{job_id}_output.mp4"}))
    q.put(None)

# ── Routes ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return{"status":"ok","model_ready":MODEL_READY,"model_error":MODEL_ERROR,
           "model":YOLO_MODEL,"gender_ready":GENDER_READY,
           "roboflow":USE_ROBOFLOW}

@app.get("/api/warmup")
def warmup():
    return{"model_ready":MODEL_READY,"model_error":MODEL_ERROR,"gender_ready":GENDER_READY}

@app.get("/api/frame/{job_id}/{frame_idx}")
async def get_frame(job_id:str, frame_idx:int):
    from fastapi.responses import Response
    job=jobs.get(job_id)
    if not job: raise HTTPException(404)
    cap=cv2.VideoCapture(job["video_path"])
    if not cap.isOpened(): raise HTTPException(400)
    idx=max(0,min(frame_idx,job["total_frames"]-1))
    cap.set(cv2.CAP_PROP_POS_FRAMES,idx)
    ret,frame=cap.read(); cap.release()
    if not ret: raise HTTPException(404)
    frame=cv2.resize(frame,(640,360))
    ok,buf=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,82])
    if not ok: raise HTTPException(500)
    return Response(content=buf.tobytes(),media_type="image/jpeg",
        headers={"Cache-Control":"public, max-age=3600"})

@app.post("/api/upload")
async def upload(file:UploadFile=File(...)):
    ext=Path(file.filename).suffix.lower()
    if ext not in(".mp4",".mov",".avi",".mkv",".webm"):
        raise HTTPException(400,f"Unsupported:{ext}")
    jid=str(uuid.uuid4())[:8]; vpath=UPLOAD/f"{jid}{ext}"
    with open(vpath,"wb") as f: shutil.copyfileobj(file.file,f)
    cap=cv2.VideoCapture(str(vpath))
    if not cap.isOpened(): raise HTTPException(400,"Cannot open video")
    fps=cap.get(cv2.CAP_PROP_FPS) or 30; total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vw=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); vh=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ivl=max(1,total//MAX_GALLERY); jfd=FRAMES/jid; jfd.mkdir(exist_ok=True)
    meta=[]; fi=saved=0
    while cap.isOpened() and saved<MAX_GALLERY:
        ret,frm=cap.read()
        if not ret: break
        if fi%ivl==0:
            fn_=f"frame_{saved:03d}.jpg"
            if cv2.imwrite(str(jfd/fn_),cv2.resize(frm,(640,360)),[cv2.IMWRITE_JPEG_QUALITY,82]):
                m,s=divmod(int(fi/fps),60)
                meta.append({"id":f"F{saved+1:03d}","filename":fn_,
                             "url":f"/frames/{jid}/{fn_}",
                             "timestamp":f"{m:02d}:{s:02d}","frame_idx":fi})
                saved+=1
        fi+=1
    cap.release()
    jobs[jid]={"video_path":str(vpath),"frames":meta,"fps":fps,"total_frames":total,
               "vid_w":vw,"vid_h":vh,"duration":round(total/fps,2),
               "status":"ready","queue":None,"analytics":None,"output_url":None}
    return{"job_id":jid,"frames":meta,"fps":round(fps,2),
           "duration":round(total/fps,2),"total_frames":total,"resolution":f"{vw}x{vh}"}

class ProcReq(BaseModel):
    job_id:str; x1:int; y1:int; x2:int; y2:int; start_frame:int=0

@app.post("/api/process")
async def process(req:ProcReq):
    if not MODEL_READY: raise HTTPException(503,"YOLO loading")
    job=jobs.get(req.job_id)
    if not job: raise HTTPException(404)
    if job["status"]=="processing": return{"status":"already_processing"}
    sf=max(0,min(req.start_frame,job["total_frames"]-1))
    q=queue.Queue(maxsize=8000)
    jobs[req.job_id].update({"queue":q,"status":"processing"})
    threading.Thread(target=run_detection,
        args=(req.job_id,req.x1,req.y1,req.x2,req.y2,sf),daemon=True).start()
    return{"status":"processing","job_id":req.job_id,"start_frame":sf}

@app.get("/api/stream/{job_id}")
async def stream(job_id:str):
    job=jobs.get(job_id)
    if not job: raise HTTPException(404)
    q=job.get("queue")
    if q is None: raise HTTPException(400)
    def gen():
        yield sse("connected",{"job_id":job_id})
        while True:
            try:
                item=q.get(timeout=30)
                if item is None: break
                yield item
            except queue.Empty: yield ": keepalive\n\n"
        yield sse("closed",{"job_id":job_id})
    return StreamingResponse(gen(),media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no",
                 "Connection":"keep-alive","Access-Control-Allow-Origin":"*"})

@app.get("/api/job/{job_id}")
def get_job(job_id:str):
    job=jobs.get(job_id)
    if not job: raise HTTPException(404)
    return{"status":job["status"],"analytics":job["analytics"],
           "output_url":job["output_url"],"error":job.get("error")}

@app.delete("/api/job/{job_id}")
def del_job(job_id:str):
    job=jobs.pop(job_id,None)
    if job:
        try:
            Path(job["video_path"]).unlink(missing_ok=True)
            shutil.rmtree(FRAMES/job_id,ignore_errors=True)
        except: pass
    return{"deleted":job_id}

@app.get("/")
def root():
    return{"status":"VisionCount v6","model_ready":MODEL_READY,
           "roboflow":USE_ROBOFLOW}
