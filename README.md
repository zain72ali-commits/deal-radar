# OzBargain Deal Bot

A small bot that checks OzBargain once a day for **live** deals in the categories
you choose, drops anything you've excluded, and publishes them to a mobile-friendly
dashboard ("Deal Radar") on GitHub Pages. It runs free on GitHub Actions, with no
server to manage.

```
GitHub Actions (daily, 7:17am Melbourne)
  job "check" ─ python -m dealbot
       ├─ fetch  /cat/<slug>/feed for each category in config.toml   (fetcher.py)
       ├─ parse  RSS → Deal objects, safely (defusedxml)            (parser.py, pricing.py)
       ├─ filter live only, exclusions, optional price caps         (filters.py)
       ├─ score  community verdict + price history                   (scoring.py)
       ├─ merge  with yesterday's state: new / still live / gone    (pipeline.py)
       └─ write  data/state.json (committed) + site/data/deals.json
  job "deploy" ─ publish site/ to GitHub Pages  →  https://zain72ali-commits.github.io/deal-radar/
```

## What counts as a deal on the dashboard

- **In one of your categories.** Default: Computing, Gaming, Electrical & Electronics,
  Travel, Entertainment, Internet, Mobile. OzBargain has no "Utilities" category, so
  Internet (nbn, broadband) and Mobile (SIM plans) stand in for it.
- **Live.** OzBargain hasn't marked it expired or out of stock, its end date hasn't
  passed, and its start date has arrived.
- **Not excluded.** Not in an excluded category (Alcohol, Pets), and no excluded
  keyword (alcohol, pets, medicare and related words) in its title or tags.
- **Under your price cap**, if you set one for that category.

Deals first seen on today's run are badged **New today**. A deal stays on the dashboard
while it's live, so nothing disappears just because it's a day old. OzBargain's feeds
only list each category's most recent deals, so a deal that drops out of the feed is
kept (badged "Last confirmed <date>") until it expires or 7 days pass
(`keep_unconfirmed_days`). The dashboard also hides deals whose end time passes during
the day. A deal that starts later today appears on the next morning's run.

## Competitiveness: how "is this actually a good price?" is judged

OzBargain feeds have no market-price field. The dashboard shows two signals the data
honestly supports, rather than inventing a market comparison:

1. **Community verdict.** OzBargain members vote on whether a deal beats the market.
   - *Strong*: at least 50 upvotes and under 15% downvotes.
   - *Positive*: at least 10 votes and under 15% downvotes.
   - *Mixed*: 15% or more of the votes are downvotes. Read the comments before buying.
   - *Early*: fewer than 10 votes so far.

   The thresholds are in `[scoring]` in `config.toml`.
2. **Price history.** For deals tied to a single OzBargain product (for example
   `/product/kingston-nv2`), the bot remembers the lowest price it has seen. It then
   flags reposts as **Lowest price seen**, **Matches lowest seen**, or **Was $X on
   <date>**. This history starts empty and becomes more useful the longer the bot runs.

The discount shown (e.g. −29%) comes from a "was" or "RRP" price, an "N% off", or
"1/2 price" in the title. It is the retailer's claim, not an independent check.

**Not included (yet):** comparing against other retailers' live prices, which would
need a price-comparison data source. That could be added later as a separate module.

## Setup (about 10 minutes)

1. **Use a public GitHub repository** (this one is `zain72ali-commits/deal-radar`).
   Free GitHub Pages needs a public repo. The code and the published deal data
   contain no secrets.
2. **Add these files** to the repo, either by uploading them on github.com or by pushing:
   ```bash
   git init && git add . && git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/zain72ali-commits/deal-radar.git
   git push -u origin main
   ```
3. **Check `config.toml`.** Its `user_agent` names this repo, so OzBargain can see
   who is polling. Change it if you fork or rename the repo.
4. **Turn on Pages.** Go to repo **Settings → Pages → Build and deployment → Source**
   and choose **GitHub Actions**.
5. **Run it once.** Go to the **Actions** tab, open **Daily deal check**, and click
   **Run workflow**. After it finishes (about a minute), the run summary links to your
   dashboard. After that it runs every morning.
6. **Put it on your phone.** Open the dashboard link in your phone's browser and use
   "Add to Home Screen".

## Changing what it tracks

Everything is in `config.toml`. Edit it on GitHub and the next run uses it.

| Want to… | Do this |
|---|---|
| Add a category | Add a `[[categories]]` block. The slug is the part after `/cat/` in the OzBargain URL, e.g. `home-garden`. |
| Cap prices | Add `max_price = 300` under that category. Deals with no readable price are still kept while `include_unpriced = true`. |
| Exclude more things | Add words to `exclude_keywords`, or OzBargain category names to `exclude_categories`. |
| Change the run time | Edit the `cron` line in `.github/workflows/daily.yml` (`minute hour * * *`, Melbourne time). |

Keyword matching is whole-word and case-insensitive. `pet` excludes "Pet Insurance"
but not "Petrol". It will also exclude e.g. "PET filament" for 3D printers, so remove
`pet` from the list if that matters to you.

## Run it locally

```bash
python3 -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -r requirements.txt
python -m unittest discover -s tests -t .              # 65 tests, no network needed
python -m dealbot                                      # real run against OzBargain
python -m http.server -d site 8000                     # then open http://localhost:8000
```

## Project layout

```
config.toml               what to track
dealbot/
  __main__.py             entry point: wires I/O to the pipeline
  config.py               loads and validates config.toml
  fetcher.py              polite HTTP: timeout, retries, size cap, same-site check
  parser.py               RSS → Deal (defusedxml)
  pricing.py              price / was-price / discount from the title
  filters.py              live check, exclusions, price caps
  scoring.py              community verdict and price history
  pipeline.py             one run's logic, no I/O (fully unit-tested)
  storage.py              state file and atomic JSON writes
  models.py               Deal and Price
site/                     the static dashboard (index.html, app.js, styles.css)
tests/                    unit tests; fixtures are real OzBargain feed items
data/state.json           created by the first run and committed after each run
```

## Security notes

- **Untrusted XML.** Feeds are parsed with `defusedxml`, which blocks entity-expansion
  and external-entity attacks. Feeds are capped at 5 MB. The bot never follows
  redirects; any redirect counts as a failed fetch.
- **Safe links and images.** The bot only keeps links to `https://www.ozbargain.com.au/node/…`
  and images from `https://files.ozbargain.com.au`, and the dashboard re-checks both.
- **No injected markup.** The dashboard inserts deal text with `textContent` only. A
  Content-Security-Policy allows scripts and styles from the site itself, and images
  only from OzBargain's file host.
- **No secrets.** The workflow uses only the built-in, short-lived `GITHUB_TOKEN`, and
  splits the work across two jobs:
  - The `check` job can write repo contents only. Its token isn't left in
    `.git/config`, so `pip install` and the bot never see it. Only the "Save state"
    step uses it.
  - The `deploy` job alone holds the Pages permissions.
- **Optional hardening.**
  - Pin the actions in `daily.yml` to commit SHAs instead of version tags.
  - Lock the transitive dependencies with hashes, e.g.
    `pip-compile --generate-hashes`, then `pip install --require-hashes`.
    `requirements.txt` pins only the two direct dependencies.

## Being a good citizen

The bot reads only the public category RSS feeds, which OzBargain's `robots.txt` allows.
It never touches `/api/`, `/search/` or `/goto/`, which robots.txt disallows. It makes
one request per category per day, pauses between requests, and sends an honest
User-Agent. Links on the dashboard go to the OzBargain deal page, so the community
discussion stays one tap away.

## Troubleshooting

- **The run failed at "Save state" with a permission or "protected branch" error.**
  The workflow requests write access itself. The usual culprit is branch protection
  or a ruleset on `main` that blocks pushes from GitHub Actions. Allow the
  `github-actions[bot]` push, or relax the rule for `data/state.json`.
- **The dashboard says it couldn't check a category.** That feed failed on the last
  run. The bot keeps the category's last known deals and tries again tomorrow. A
  wrong slug fails every day; check it against the OzBargain URL.
- **Daily runs stopped.** GitHub disables scheduled workflows in public repos after 60
  days with no repository activity. The bot's daily state commits should keep the
  repo active, but GitHub doesn't define exactly what counts as activity. If runs
  stop, re-enable the workflow on the Actions tab.
- **Runs start a few minutes late.** GitHub queues scheduled runs, and they can be
  delayed when the service is busy. This is normal.
