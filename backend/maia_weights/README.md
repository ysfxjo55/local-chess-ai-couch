# Maia weights

Not committed (see `.gitignore`) — download with:

```bash
cd backend/maia_weights
for lvl in 1100 1200 1300 1400 1500 1600 1700 1800 1900; do
  curl -sS -L -o "maia-$lvl.pb.gz" \
    "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-$lvl.pb.gz"
done
```

Requires `lc0` (`brew install lc0`). Used by `backend/app/services/sparring.py`.
