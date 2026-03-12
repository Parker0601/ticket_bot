from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms


CHAR_SET = "abcdefghijklmnopqrstuvwxyz"
SEQ_LENGTH = 4
NUM_CLASSES = len(CHAR_SET)
IDX_TO_CHAR = {idx: ch for idx, ch in enumerate(CHAR_SET)}


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
    parser = argparse.ArgumentParser(description="Predict 4-char lowercase captcha from one image.")
    parser.add_argument("--image", required=True, help="Path to input image.")
    parser.add_argument(
        "--model",
        default="best_lowercase_crnn.pth",
        help="Path to trained model weights.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    image_path = Path(args.image).resolve()
    model_arg = Path(args.model)
    model_path = model_arg if model_arg.is_absolute() else (script_dir / model_arg)
    model_path = model_path.resolve()

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    transform = transforms.Compose(
        [
            transforms.Grayscale(),
            transforms.Resize((60, 200)),
            transforms.ToTensor(),
        ]
    )

    image = Image.open(image_path).convert("RGB")
    image_tensor = transform(image).unsqueeze(0).to(device)

    model = CaptchaCRNN().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

    with torch.no_grad():
        logits = model(image_tensor)
        pred_idx = logits.argmax(dim=2).squeeze(0).tolist()

    pred_text = "".join(IDX_TO_CHAR[i] for i in pred_idx)
    print(pred_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
