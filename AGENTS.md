# Repository Guidelines

## Project Structure & Module Organization
- `rb/` contains all Python automation code.
- Main bot scripts: `rb/my_ticket_bot.py` (tixcraft flow) and `rb/ibon_ticket_bot.py` (ibon flow).
- CAPTCHA model code and weights live in `rb/captcha_model/` (`train_lowercase_crnn.py`, `predict_single.py`, `*.pth`).
- Training data lives in `rb/captcha_dataset/` (`labels/captchas.csv`, raw images).
- Runtime screenshots and captcha outputs are written to `captcha/`.
- Launcher scripts at repo root (`start_chrome_for_bot.bat`, `start_chrome_ps1.ps1`, `run_my_ticket_bot_with_crnn.*`) are the preferred Windows entry points.

## Build, Test, and Development Commands
- Install core dependency: `pip install selenium`.
- Install OCR/model extras: `pip install Pillow opencv-python pytesseract torch torchvision`.
- Start debug Chrome (PowerShell): `powershell -ExecutionPolicy Bypass -File .\start_chrome_ps1.ps1`.
- Run main bot: `python .\rb\my_ticket_bot.py`.
- Run ibon bot: `python .\rb\ibon_ticket_bot.py`.
- Predict one captcha: `python .\rb\captcha_model\predict_single.py --image .\captcha\captcha.png`.
- Retrain model: `python .\rb\captcha_model\train_lowercase_crnn.py --project-root <dataset_root> --epochs 5 --batch-size 128`.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for configurable constants, and `PascalCase` for classes.
- Keep site-specific selectors grouped at the top of each script for fast maintenance.
- Prefer small helper functions (for click/wait/captcha steps) over long inline blocks.

## Testing Guidelines
- There is no formal automated test suite yet.
- Before opening a PR, run a syntax check: `python -m py_compile .\rb\my_ticket_bot.py .\rb\ibon_ticket_bot.py`.
- Do a smoke test against a non-critical event page and confirm: page navigation, seat selection, captcha capture, and form submission steps.
- If you change model code, include one `predict_single.py` sample result in the PR description.

## Commit & Pull Request Guidelines
- Current history uses short, task-focused messages (mostly Chinese), with occasional Conventional Commit prefixes (for example, `refactor:`).
- Preferred format: `<type>: <brief summary>` (or concise Chinese summary), one logical change per commit.
- PRs should include: purpose, changed files, manual test steps/results, and screenshots/log snippets for selector or captcha-related updates.
- Link related issue/ticket when available.
