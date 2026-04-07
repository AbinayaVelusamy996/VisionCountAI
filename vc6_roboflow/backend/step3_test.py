"""
STEP 3 — Test Your Model on a Real Video
==========================================
Runs your trained gender_model.pth on a video
and saves an annotated output so you can visually
verify predictions before integrating into VisionCount.

Usage:
    python step3_test.py --video myvideo.mp4
    python step3_test.py --video myvideo.mp4 --model gender_model.pth
"""

import cv2, torch, argparse, time
import numpy as np
import torch.nn as nn
from torchvision import transforms, models
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--video",  required=True)
parser.add_argument("--model",  default="gender_model.pth")
parser.add_argument("--conf",   type=float, default=0.35, help="YOLO detection threshold")
parser.add_argument("--out",    default="test_output.mp4")
parser.add_argument("--frames", type=int,   default=300, help="How many frames to test")
args = parser.parse_args()

# ── Load gender model ──────────────────────────────────────────────────────
print(f"Loading gender model: {args.model}")
if not Path(args.model).exists():
    print(f"ERROR: {args.model} not found — run step2_train.py first")
    exit(1)

ckpt     = torch.load(args.model, map_location="cpu")
classes  = ckpt["classes"]    # e.g. ['Female', 'Male']
img_size = ckpt.get("img_size", 112)
print(f"  Classes  : {classes}")
print(f"  Img size : {img_size}")
print(f"  Best val : {ckpt.get('val_accuracy',0):.1f}%")

net = models.mobilenet_v3_small(weights=None)
net.classifier[3] = nn.Linear(net.classifier[3].in_features, 2)
net.load_state_dict(ckpt["model_state"])
net.eval()

tf = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((img_size, img_size)),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
])

def predict_gender(crop_bgr):
    """Returns (label, confidence) e.g. ('Male', 0.92)"""
    try:
        rgb    = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        tensor = tf(rgb).unsqueeze(0)
        with torch.no_grad():
            logits = net(tensor)
            probs  = torch.softmax(logits, dim=1)[0]
            idx    = probs.argmax().item()
            conf   = probs[idx].item()
        label = classes[idx]
        if label.lower() in ('male','man','m'):   label = 'Male'
        if label.lower() in ('female','woman','f'): label = 'Female'
        return label, conf
    except Exception as e:
        return 'Unknown', 0.0

# ── Load YOLO ─────────────────────────────────────────────────────────────
print("Loading YOLOv8m...")
from ultralytics import YOLO
yolo = YOLO("yolov8m.pt")

# ── Process video ──────────────────────────────────────────────────────────
cap = cv2.VideoCapture(args.video)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
vw  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
vh  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"),
                         fps, (vw, vh))

COLORS = {"Male":(255,140,0), "Female":(147,20,255), "Unknown":(120,120,120)}
fn = male_count = female_count = unknown_count = 0

print(f"\nProcessing {min(args.frames, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))} frames...")

while cap.isOpened() and fn < args.frames:
    ret, frame = cap.read()
    if not ret: break

    if fn % 3 == 0:  # run every 3rd frame
        results = yolo(frame, conf=args.conf, classes=[0], verbose=False)[0]
        for box in results.boxes:
            x1,y1,x2,y2 = map(int, box.xyxy[0].tolist())
            x1=max(0,x1); y1=max(0,y1); x2=min(vw,x2); y2=min(vh,y2)
            h_box = y2-y1
            if h_box < 60: continue

            # Crop upper 70% for gender
            y2c  = y1 + int(h_box * 0.70)
            crop = frame[y1:y2c, x1:x2]
            if crop.size == 0: continue

            label, conf = predict_gender(crop)
            color = COLORS[label]

            # Draw box
            cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)

            # Label with confidence
            sym = "♂" if label=="Male" else "♀" if label=="Female" else "?"
            txt = f"{sym} {conf*100:.0f}%"
            (tw,th),_ = cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.55,1)
            cv2.rectangle(frame,(x1,y1-th-8),(x1+tw+6,y1),color,-1)
            cv2.putText(frame,txt,(x1+3,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,0,0),1)

            if label=="Male":    male_count+=1
            elif label=="Female": female_count+=1
            else:                unknown_count+=1

    # Stats overlay
    overlay_txt = [
        f"Frame: {fn}",
        f"Male detections:    {male_count}",
        f"Female detections:  {female_count}",
        f"Unknown:            {unknown_count}",
    ]
    for i,txt in enumerate(overlay_txt):
        cv2.putText(frame,txt,(10,25+i*22),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)

    writer.write(frame)
    fn += 1

cap.release(); writer.release()

total = male_count + female_count + unknown_count
print(f"\n{'='*50}")
print(f" Test Results ({fn} frames)")
print(f"{'='*50}")
print(f" Male detections   : {male_count} ({male_count/max(total,1)*100:.1f}%)")
print(f" Female detections : {female_count} ({female_count/max(total,1)*100:.1f}%)")
print(f" Unknown           : {unknown_count} ({unknown_count/max(total,1)*100:.1f}%)")
print(f"\n Output saved to: {args.out}")
print(f" Open this file to visually verify the predictions!")
print(f"\n If Male % is near 100%: model needs more female training data")
print(f" If predictions look wrong: collect more labeled crops (step1 → relabel → step2)")
print(f"{'='*50}")
