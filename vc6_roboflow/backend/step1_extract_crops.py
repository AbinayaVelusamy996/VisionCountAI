"""
STEP 1 — Extract Person Crops from Your Videos
================================================
This script uses YOLOv8 to find every person in your video
and saves them as individual crop images for labeling.

Usage:
    python step1_extract_crops.py --video myvideo.mp4
    python step1_extract_crops.py --video myvideo.mp4 --every 10

Output:
    dataset/unlabeled/  ← all person crops go here
    Then YOU manually move them into:
    dataset/Male/
    dataset/Female/
"""

import cv2, os, uuid, argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--video",  required=True, help="Path to your video file")
parser.add_argument("--every",  type=int, default=5, help="Sample every N frames (default 5)")
parser.add_argument("--conf",   type=float, default=0.40, help="YOLO confidence (default 0.40)")
parser.add_argument("--min_h",  type=int, default=80, help="Minimum crop height in pixels (default 80)")
parser.add_argument("--out",    default="dataset/unlabeled", help="Output folder")
args = parser.parse_args()

# ── Load YOLO ─────────────────────────────────────────────────────────────
print("Loading YOLOv8m...")
from ultralytics import YOLO
model = YOLO("yolov8m.pt")

# ── Open video ────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(args.video)
if not cap.isOpened():
    print(f"ERROR: Cannot open {args.video}")
    exit(1)

fps   = cap.get(cv2.CAP_PROP_FPS) or 30
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
vw    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
vh    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Video: {vw}x{vh} @ {fps:.0f}fps, {total} frames ({total/fps:.0f}s)")

out_dir = Path(args.out)
out_dir.mkdir(parents=True, exist_ok=True)

# ── Extract crops ─────────────────────────────────────────────────────────
fn = saved = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    if fn % args.every == 0:
        # Run YOLO — classes=[0] means person only
        results = model(frame, conf=args.conf, classes=[0], verbose=False)[0]

        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            x1=max(0,x1); y1=max(0,y1); x2=min(vw,x2); y2=min(vh,y2)
            h_box = y2 - y1
            w_box = x2 - x1

            # Skip tiny crops — too blurry to determine gender
            if h_box < args.min_h or w_box < 30:
                continue

            # Crop upper 70% of the person (head + torso — most informative for gender)
            y2_crop = y1 + int(h_box * 0.70)
            crop = frame[y1:y2_crop, x1:x2]
            if crop.size == 0:
                continue

            # Save with frame number so you know where it came from
            fname = f"f{fn:06d}_{uuid.uuid4().hex[:6]}.jpg"
            cv2.imwrite(str(out_dir / fname), crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
            saved += 1

    fn += 1
    if fn % 100 == 0:
        print(f"  Frame {fn}/{total} — {saved} crops saved so far...")

cap.release()

print(f"\n{'='*50}")
print(f"Done! Extracted {saved} person crops")
print(f"Saved to: {out_dir}/")
print(f"\nNEXT STEP: Manually sort the crops:")
print(f"  Move male images  → dataset/Male/")
print(f"  Move female images → dataset/Female/")
print(f"  Delete unclear/bad crops")
print(f"\nAim for at least 300 per class (500+ is better)")
print(f"Then run: python step2_train.py")
print(f"{'='*50}")
