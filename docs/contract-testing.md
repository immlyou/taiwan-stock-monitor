# Frontend/backend contract checks

`cd frontend && npm run test:e2e:contract`

Requires frontend dependencies, Playwright Chromium, and a Python runtime with
`requirements-api.txt` installed. Set `PLAYWRIGHT_PYTHON` if Python is not named
`python3`. Ports default to 41737 (Next.js) and 41738 (FastAPI); override with
`PLAYWRIGHT_CONTRACT_PORT` / `PLAYWRIGHT_API_PORT`. Do not run concurrently with
another Next.js dev server in the same checkout.

The runner starts real production routers, API authentication, a real Next.js
proxy and browser UI. The only fixtures are external market data and temporary
storage; it does not replay hand-written API responses. Auth.js session cookies
are test-generated, so this verifies authenticated application behavior, not
Google's external consent flow. No test login bypass is added to production.

The CI `contract` job is blocking and uses zero retries. Existing mocked E2E
remains useful for deterministic outages, but is not a substitute for this job.
Repository branch-protection requirements must include the new check before
it can enforce merge protection; changing those remote settings is separate.

## Product semantics

- Manual predictions use subsequent completed daily closes, through the chosen
  calendar deadline. Intraday highs/lows do not count. A price reached after the
  deadline cannot turn a missed prediction into a win. Stale price data leaves
  the prediction pending. Legacy global strategy/model tracking is separate.
- Alerts manual evaluation records a preview, not a delivered notification.
  Successful delivery is tracked per account/rule/stock/channel independently
  of the last 1,000 history entries. Failures retry while conditions still match,
  with exponential backoff from 60 to 900 seconds. This is not an exactly-once
  transport: an external provider accepting a message immediately before a
  process crash can cause a retry because the provider offers no transactional
  acknowledgement shared with local storage.
- The refresh preference is a minimum delay for five quote-consuming screens;
  existing rate limits and market-closed delays take precedence. Taiwan market
  timezone/hours are fixed. Automatic backtesting is explicitly unavailable.
