import os
os.makedirs('output', exist_ok=True)

TOP_N = 10  # show only the top 10 items in the brief
from datetime import datetime, timedelta
from dateutil import tz
from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils import load_yaml, get_items_from_rss, get_items_from_page, dedupe, score_item

# --- LLM (OpenAI Responses API) ---
try:
    from openai import OpenAI
    client = OpenAI()
    OPENAI_OK = True
except Exception:
    OPENAI_OK = False

def llm_summarize(system_prompt, user_prompt, model='gpt-4.1-mini'):
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.responses.create(
            model=model,
            input=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":user_prompt}
            ],
            temperature=0.2
        )
        out = resp.output_text
        try:
            data = json.loads(out)
        except Exception:
            data = {"headline":"","summary":out.strip(),"exec_action":"Review","tags":[]}
        return data
    except Exception:
        # Graceful fallback so the job still completes and produces an HTML file
        return {
            "headline": "",
            "summary": "Summary unavailable (LLM not reachable). Link included above.",
            "exec_action": "Skim source; assess relevance",
            "tags": []
        }


def collect_items(sources_cfg, coverage_days, weights):
    collected = []
    for category, entries in sources_cfg.items():
        for s in entries:
            try:
                if s['type'] == 'rss':
                    items = get_items_from_rss(s['name'], s['url'], coverage_days)
                else:
                    items = get_items_from_page(s['name'], s['url'], coverage_days)
                for it in items:
                    it['category'] = category
                    it['weight'] = s.get('weight',1.0)
                collected.extend(items)
            except Exception as e:
                print(f"[warn] {s['name']} – {e}")
    collected = dedupe(collected)
    # Score
    for it in collected:
        impact, urgency = score_item(it, it['category'], weights)
        it['impact'] = impact
        it['urgency'] = urgency
    # Sort by score
    collected.sort(key=lambda x: (x['impact'], {'High':2,'Medium':1,'Low':0}[x['urgency']]), reverse=True)
    return collected

def render_html(items, profile, brief_date):
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape(['html'])
    )
    tpl = env.get_template('brief_template.html')
    coverage_days = profile['meta']['coverage_days']
    tzname = profile['meta'].get('timezone','Asia/Singapore')
    now = datetime.now(tz.gettz(tzname))
    start = (now - timedelta(days=coverage_days)).strftime('%Y-%m-%d')
    end = now.strftime('%Y-%m-%d')

    # LLM prompts
    system_prompt = open('prompts/summarize_system.txt','r',encoding='utf-8').read()
    user_tpl = open('prompts/summarize_user.txt','r',encoding='utf-8').read()

    enriched = []
    for it in items[:TOP_N]:  # take top 10 by score (Impact & Urgency)
        user_prompt = user_tpl.format(
            title=it['title'], date=it.get('date',''), source=it['source'], url=it['link'], snippet=it.get('snippet','')
        )
        summ = llm_summarize(system_prompt, user_prompt)
        it['summary'] = summ.get('summary', it.get('snippet',''))
        it['exec_action'] = summ.get('exec_action','Review relevance and add to backlog.')
        enriched.append(it)

# Show all top-N items in the action grid, and no lower sections
top_actions = enriched           # all 10 cards go here
sections = []                    # keep the brief to just the top 10


    html = tpl.render(
        brief_date=brief_date,
        audience=profile['meta']['audience'],
        org_priorities=profile['meta']['org_priorities'],
        coverage_days=coverage_days,
        coverage_start=start, coverage_end=end,
        top_actions=top_actions,
        sections=sections
    )
    return html

def main():
    profile = load_yaml('config/profile.yaml')
    sources = load_yaml('config/sources.yaml')
    coverage_days = profile['meta']['coverage_days']

    items = collect_items(sources, coverage_days, profile['scoring'])
    brief_date = datetime.now().strftime('%Y-%m-%d')
    html = render_html(items, profile, brief_date)

    out_path = f"output/monthly_intel_{brief_date}.html"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Saved {out_path}")

if __name__ == '__main__':
    main()
