# InfoKun Telegram Bot

InfoKun is a Telegram bot built with aiogram 3. It provides Uzbek city weather, prayer times, local and international headlines, and admin-managed currency and fuel information.

## Requirements

- Python 3.10 or newer
- A Telegram bot token
- OpenWeatherMap and NewsAPI keys
- Tesseract OCR installed and available on `PATH` for image-based rate entry

## Setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`, fill in your credentials, and set those variables in your shell or deployment environment. The app reads environment variables directly; it does not load `.env` automatically.
4. Set `ADMINS` to comma-separated Telegram user IDs.
5. Start with `python bot.py`.

Example PowerShell configuration (use your own values):

```powershell
$env:BOT_TOKEN = 'your-token'
$env:ADMINS = '123456789'
$env:OPENWEATHER_KEY = 'your-key'
$env:NEWSAPI_KEY = 'your-key'
python bot.py
```

## Features

- `/start` and `/help` show the menu and commands.
- Weather and prayer times are available for listed Uzbek cities and a shared location.
- News combines RSS headlines with NewsAPI results.
- Admins can update rates with `/setrates` followed by rows like `USD,Bank,12450,12510`, set fuel text with `/setfuel`, or upload a rates image after `/setratesimg USD`.

Rates and admin-updated fuel text are held in memory and reset when the process restarts. Image OCR output depends on image quality and Tesseract language data.

## Checks

Run the local tests with `python -m unittest discover -s tests`. The bot is not started by the tests.
