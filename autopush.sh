#!/bin/bash
cd /Users/boxodir/it/uy_bot

# O'zgarish bormi tekshir
if [[ -n $(git status --porcelain | grep -v __pycache__ | grep -v .pyc | grep -v .DS_Store | grep -v uy_bot.db | grep -v bot.log) ]]; then
    git add config.py database/db.py handlers/ keyboards/ utils/ main.py 2>/dev/null
    git commit -m "auto: $(date '+%d.%m.%Y %H:%M')"
    git push origin main
fi
