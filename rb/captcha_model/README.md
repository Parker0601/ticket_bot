# Captcha Model (4-char lowercase)

This folder contains the trained lowercase captcha model and scripts:

- `best_lowercase_crnn.pth`
- `final_lowercase_crnn.pth`
- `predict_single.py`
- `train_lowercase_crnn.py`

## Predict one image

```powershell
python .\predict_single.py --image ..\captcha\captcha.png
```

Optional:

```powershell
python .\predict_single.py --image ..\captcha\captcha.png --model .\best_lowercase_crnn.pth
```

## Retrain

Use your dataset project path as `--project-root` (the folder that contains `data/raw` and `data/labels/captchas.csv`):

```powershell
python .\train_lowercase_crnn.py --project-root C:\Users\User\captcha_dataset_project --epochs 5 --batch-size 128
```
