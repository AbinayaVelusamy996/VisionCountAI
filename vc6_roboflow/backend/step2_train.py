"""
STEP 2 — Train Your Gender Classifier
=======================================
Trains MobileNetV3-Small on your labeled dataset.
MobileNetV3 is chosen because:
  - Very fast at inference (runs in ~2ms on CPU per crop)
  - Accurate on person images (~88-94% with good data)
  - Small model size (~10MB)

Folder structure required:
    dataset/
    ├── Male/       ← your male crop images
    └── Female/     ← your female crop images

Usage:
    python step2_train.py
    python step2_train.py --dataset dataset --epochs 30 --batch 32

Output:
    gender_model.pth  ← drop this file into visioncount/backend/
"""

import torch, argparse, time, json
import torch.nn as nn
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader, random_split
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", default="dataset", help="Folder with Male/ Female/ subfolders")
parser.add_argument("--epochs",  type=int, default=25)
parser.add_argument("--batch",   type=int, default=32)
parser.add_argument("--imgsize", type=int, default=112)
parser.add_argument("--lr",      type=float, default=3e-4)
parser.add_argument("--out",     default="gender_model.pth")
args = parser.parse_args()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\n{'='*50}")
print(f" Gender Classifier Training")
print(f"{'='*50}")
print(f" Device   : {device}")
print(f" Dataset  : {args.dataset}")
print(f" Epochs   : {args.epochs}")
print(f" Img size : {args.imgsize}px")
print(f"{'='*50}\n")

# ── Verify dataset structure ───────────────────────────────────────────────
ds_path = Path(args.dataset)
if not ds_path.exists():
    print(f"ERROR: Dataset folder '{args.dataset}' not found")
    print("Create it with Male/ and Female/ subfolders and run step1 first")
    exit(1)

for cls in ["Male","Female"]:
    cls_path = ds_path/cls
    if not cls_path.exists():
        print(f"ERROR: Missing folder: {cls_path}")
        print("Make sure you have dataset/Male/ and dataset/Female/")
        exit(1)
    count = len(list(cls_path.glob("*.jpg")) + list(cls_path.glob("*.png")))
    print(f"  {cls}: {count} images")
    if count < 50:
        print(f"  WARNING: {cls} has fewer than 50 images — accuracy will be low")

# ── Data transforms ────────────────────────────────────────────────────────
# Training: aggressive augmentation to prevent overfitting
train_tf = transforms.Compose([
    transforms.Resize((args.imgsize + 16, args.imgsize + 16)),
    transforms.RandomCrop(args.imgsize),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.3, hue=0.05),
    transforms.RandomRotation(degrees=12),
    transforms.RandomGrayscale(p=0.05),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406], [0.229,0.224,0.225]),
])
# Validation: just resize + normalize
val_tf = transforms.Compose([
    transforms.Resize((args.imgsize, args.imgsize)),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406], [0.229,0.224,0.225]),
])

# ── Load dataset ───────────────────────────────────────────────────────────
full_ds = datasets.ImageFolder(args.dataset)
print(f"\nClass mapping: {full_ds.class_to_idx}")
# ImageFolder sorts alphabetically: Female=0, Male=1

n_val   = max(int(len(full_ds) * 0.15), 30)
n_train = len(full_ds) - n_val
train_ds, val_ds = random_split(full_ds, [n_train, n_val],
                                generator=torch.Generator().manual_seed(42))

# Apply different transforms to each split
class TransformDataset(torch.utils.data.Dataset):
    def __init__(self, subset, transform):
        self.subset = subset
        self.transform = transform
    def __len__(self): return len(self.subset)
    def __getitem__(self, idx):
        img, label = self.subset[idx]
        # img is PIL here because ImageFolder uses default loader
        return self.transform(img), label

# Re-load with transforms applied properly
full_pil = datasets.ImageFolder(args.dataset)
train_pil, val_pil = random_split(full_pil, [n_train, n_val],
                                  generator=torch.Generator().manual_seed(42))
full_pil.transform = train_tf   # will be overridden per split below

train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,  num_workers=0)
val_loader   = DataLoader(val_ds,   batch_size=args.batch, shuffle=False, num_workers=0)

# Apply transforms
train_loader.dataset.dataset.transform = train_tf
val_loader.dataset.dataset.transform   = val_tf

print(f"Train: {n_train}  Val: {n_val}  Classes: {full_ds.classes}\n")

# ── Model: MobileNetV3-Small ───────────────────────────────────────────────
# Pre-trained on ImageNet → fine-tune for Male/Female
model = models.mobilenet_v3_small(weights="IMAGENET1K_V1")
# Replace final classification head
in_features = model.classifier[3].in_features
model.classifier[3] = nn.Linear(in_features, 2)  # 2 classes: Female, Male
model = model.to(device)

total_params = sum(p.numel() for p in model.parameters())
print(f"Model: MobileNetV3-Small  ({total_params/1e6:.1f}M params)")

# ── Optimizer & scheduler ──────────────────────────────────────────────────
# Use different LR for backbone vs head — head learns faster
backbone_params = [p for n,p in model.named_parameters() if 'classifier' not in n]
head_params     = [p for n,p in model.named_parameters() if 'classifier' in n]

optimizer = torch.optim.AdamW([
    {'params': backbone_params, 'lr': args.lr * 0.1},   # slow for backbone
    {'params': head_params,     'lr': args.lr},           # fast for head
], weight_decay=1e-4)

scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer, max_lr=[args.lr*0.1, args.lr],
    epochs=args.epochs, steps_per_epoch=len(train_loader)
)
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

# ── Training loop ──────────────────────────────────────────────────────────
best_val_acc = 0.0
history = []

for epoch in range(args.epochs):
    t0 = time.time()

    # Train
    model.train()
    train_loss = train_correct = train_total = 0
    for imgs, labels in train_loader:
        imgs, labels = imgs.to(device), labels.to(device)
        optimizer.zero_grad()
        logits = model(imgs)
        loss   = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        scheduler.step()
        train_loss    += loss.item()
        train_correct += (logits.argmax(1) == labels).sum().item()
        train_total   += len(labels)

    # Validate
    model.eval()
    val_correct = val_total = 0
    val_preds = []; val_true = []
    with torch.no_grad():
        for imgs, labels in val_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            logits = model(imgs)
            preds  = logits.argmax(1)
            val_correct += (preds == labels).sum().item()
            val_total   += len(labels)
            val_preds.extend(preds.cpu().tolist())
            val_true.extend(labels.cpu().tolist())

    train_acc = train_correct / train_total * 100
    val_acc   = val_correct   / val_total   * 100
    elapsed   = time.time() - t0

    history.append({"epoch": epoch+1, "train_acc": train_acc, "val_acc": val_acc})

    marker = " ← BEST" if val_acc > best_val_acc else ""
    print(f"Epoch {epoch+1:3d}/{args.epochs}  "
          f"loss={train_loss/len(train_loader):.3f}  "
          f"train={train_acc:.1f}%  val={val_acc:.1f}%  "
          f"({elapsed:.1f}s){marker}")

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save({
            "model_state":   model.state_dict(),
            "classes":       full_ds.classes,     # ['Female', 'Male']
            "class_to_idx":  full_ds.class_to_idx,
            "img_size":      args.imgsize,
            "architecture":  "mobilenet_v3_small",
            "val_accuracy":  val_acc,
            "epoch":         epoch + 1,
        }, args.out)

# ── Final summary ──────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f" Training Complete")
print(f"{'='*50}")
print(f" Best validation accuracy : {best_val_acc:.1f}%")
print(f" Model saved to           : {args.out}")
print(f"\nExpected accuracy ranges:")
print(f"  > 90% — Excellent, ready to deploy")
print(f"  85-90% — Good")
print(f"  75-85% — Acceptable, collect more data")
print(f"  < 75%  — Needs more/better labeled data")
print(f"\nNEXT STEP: python step3_test.py --video myvideo.mp4")
print(f"{'='*50}")

# Save training history
with open("training_history.json","w") as f:
    json.dump(history, f, indent=2)
