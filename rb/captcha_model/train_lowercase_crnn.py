from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import transforms


CHAR_SET = "abcdefghijklmnopqrstuvwxyz"
SEQ_LENGTH = 4
NUM_CLASSES = len(CHAR_SET)
CHAR_TO_IDX = {ch: idx for idx, ch in enumerate(CHAR_SET)}


class CsvCaptchaDataset(Dataset):
    def __init__(self, csv_path: Path, image_dir: Path, transform: transforms.Compose):
        self.items: list[tuple[Path, str]] = []
        self.transform = transform

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = (row.get("filename") or "").strip()
                label = (row.get("label") or "").strip()
                if not filename or not label:
                    continue
                if len(label) != SEQ_LENGTH or any(ch not in CHAR_TO_IDX for ch in label):
                    continue
                image_path = image_dir / filename
                if image_path.exists():
                    self.items.append((image_path, label))

        if not self.items:
            raise ValueError("No valid samples found. Check CSV labels and image files.")

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        image_path, label_str = self.items[idx]
        image = Image.open(image_path).convert("RGB")
        image_tensor = self.transform(image)
        label = torch.tensor([CHAR_TO_IDX[ch] for ch in label_str], dtype=torch.long)
        return image_tensor, label


class CaptchaCRNN(nn.Module):
    def __init__(self, seq_length: int = SEQ_LENGTH, num_classes: int = NUM_CLASSES):
        super().__init__()
        self.seq_length = seq_length
        self.num_classes = num_classes

        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout(0.25),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout(0.25),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout(0.25),
            nn.Conv2d(256, 256, kernel_size=(7, 1)),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.Dropout(0.25),
        )

        self.rnn_input_size = 256
        self.rnn_hidden_size = 512
        self.lstm = nn.LSTM(
            self.rnn_input_size,
            self.rnn_hidden_size,
            num_layers=2,
            bidirectional=True,
            dropout=0.5,
            batch_first=True,
        )
        self.adaptive_pool = nn.AdaptiveAvgPool1d(self.seq_length)
        self.classifier = nn.Linear(self.rnn_hidden_size * 2, self.num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.cnn(x)
        x = x.squeeze(2)
        x = x.permute(0, 2, 1)
        output, _ = self.lstm(x)
        output = output.permute(0, 2, 1)
        output = self.adaptive_pool(output)
        output = output.permute(0, 2, 1)
        output = self.classifier(output.contiguous().view(-1, self.rnn_hidden_size * 2))
        output = output.view(-1, self.seq_length, self.num_classes)
        return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train lowercase 4-char captcha CRNN.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Project root path.",
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--pretrained-path",
        default="external/crnn-captcha-break/captcha_crnn_best_model.pth",
        help="Path to GitHub pretrained weights.",
    )
    parser.add_argument(
        "--output-dir",
        default="models/lowercase_crnn",
        help="Directory to save checkpoints and final model.",
    )
    return parser.parse_args()


def load_pretrained_backbone(model: nn.Module, pretrained_path: Path, device: torch.device) -> int:
    if not pretrained_path.exists():
        print(f"[warn] pretrained file not found: {pretrained_path}")
        return 0

    state = torch.load(pretrained_path, map_location=device)
    model_state = model.state_dict()
    filtered = {
        k: v
        for k, v in state.items()
        if k in model_state and model_state[k].shape == v.shape and not k.startswith("classifier.")
    }
    model_state.update(filtered)
    model.load_state_dict(model_state)
    print(f"[info] loaded {len(filtered)} compatible pretrained tensors from {pretrained_path}")
    return len(filtered)


def step_accuracy(logits: torch.Tensor, labels: torch.Tensor) -> float:
    pred = logits.argmax(dim=2)
    return (pred == labels).all(dim=1).float().mean().item()


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer | None,
    device: torch.device,
) -> tuple[float, float]:
    is_train = optimizer is not None
    model.train(is_train)
    total_loss = 0.0
    total_acc = 0.0
    batches = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)
        logits = model(images)

        loss = 0.0
        for i in range(SEQ_LENGTH):
            loss = loss + criterion(logits[:, i, :], labels[:, i])

        if is_train:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        total_loss += float(loss.item())
        total_acc += step_accuracy(logits, labels)
        batches += 1

    return total_loss / max(1, batches), total_acc / max(1, batches)


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    project_root = Path(args.project_root).resolve()
    csv_path = project_root / "data" / "labels" / "captchas.csv"
    image_dir = project_root / "data" / "raw"
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    transform = transforms.Compose(
        [
            transforms.Grayscale(),
            transforms.Resize((60, 200)),
            transforms.ToTensor(),
        ]
    )
    dataset = CsvCaptchaDataset(csv_path=csv_path, image_dir=image_dir, transform=transform)
    total_len = len(dataset)
    train_len = int(total_len * args.train_ratio)
    val_len = int(total_len * args.val_ratio)
    test_len = total_len - train_len - val_len
    train_set, val_set, test_set = random_split(
        dataset,
        [train_len, val_len, test_len],
        generator=torch.Generator().manual_seed(args.seed),
    )

    train_loader = DataLoader(
        train_set,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
    )
    val_loader = DataLoader(
        val_set,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
    )
    test_loader = DataLoader(
        test_set,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[info] device={device} total={total_len} train={train_len} val={val_len} test={test_len}")

    model = CaptchaCRNN().to(device)
    load_pretrained_backbone(model, project_root / args.pretrained_path, device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_val_acc = 0.0
    best_path = output_dir / "best_lowercase_crnn.pth"

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer, device)
        with torch.no_grad():
            val_loss, val_acc = run_epoch(model, val_loader, criterion, None, device)

        print(
            f"[epoch {epoch}/{args.epochs}] "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_path)
            print(f"[info] saved best checkpoint: {best_path}")

    if best_path.exists():
        model.load_state_dict(torch.load(best_path, map_location=device))
    with torch.no_grad():
        test_loss, test_acc = run_epoch(model, test_loader, criterion, None, device)
    print(f"[final] test_loss={test_loss:.4f} test_acc={test_acc:.4f}")

    final_path = output_dir / "final_lowercase_crnn.pth"
    torch.save(model.state_dict(), final_path)
    print(f"[info] saved final model: {final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
