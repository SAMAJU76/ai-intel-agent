# AI Intelligence Brief Agent (Banking/FS)

A small Python agent that monitors curated sources, summarizes the most relevant items for banking technology executives, and renders a clean HTML brief.

## 1) Prereqs

- Python 3.10+
- An OpenAI API key (set `OPENAI_API_KEY` in your environment)

## 2) Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Configure

Edit `config/sources.yaml` and `config/profile.yaml` to suit your priorities.
Add/remove feeds as needed.

## 4) Run

```bash
python main.py
```

Find the output in `output/monthly_intel_YYYY-MM-DD.html`

## 5) Automate (GitHub Actions)

- Push this repo to GitHub.
- In *Settings → Secrets and variables → Actions*, add a secret named `OPENAI_API_KEY`.
- The included workflow `.github/workflows/monthly.yml` runs on the **16th at 02:00 UTC** (10:00 SGT). You can trigger it on demand, too.

## Notes
- Some sources (e.g., Gartner, MAS, ServiceNow press) may not provide RSS. Leave them as `type: page` and switch to site-specific scraping (or email digests).
- Always respect terms of use. Keep to brief excerpts and link back to originals.
- 
