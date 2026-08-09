name: Post to Разрушители мифов

on:
  schedule:
    - cron: '0 15 * * 1,3,5'   # Пн, Ср, Пт в 15:00 UTC (18:00 МСК)
  workflow_dispatch: {}         # чтобы можно было запустить руками для теста

permissions:
  contents: write

jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests python-dateutil

      - name: Run poster
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHANNEL_ID: ${{ secrets.TELEGRAM_CHANNEL_ID }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: python poster.py

      - name: Commit used_items.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add used_items.json
          git diff --cached --quiet || git commit -m "update used items [skip ci]"
          git push
