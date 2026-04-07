# CI/CD Setup Guide

## GitHub Actions Workflows

Four automated workflows are configured in `.github/workflows/`:

### 1. Tests (`tests.yml`)

**Triggers**: Push or PR to `main`/`master`
**Runs on**: Windows (Python 3.11, 3.12, 3.13)
**What it does**:
- Installs all dependencies
- Runs all tests with pytest (including network centrality TDD tests)
- Uploads test results as artifacts

**No secrets required.**

### 2. Lint (`lint.yml`)

**Triggers**: Push or PR to `main`/`master`
**Runs on**: Windows (Python 3.13)
**What it does**:
- Runs `black` for formatting checks
- Runs `isort` for import ordering
- Runs `flake8` for syntax errors
- Runs `pylint` for code quality

**No secrets required.** All checks are advisory (continue-on-error: true) so they won't block PRs.

### 3. Full Crawl (`crawl.yml`)

**Triggers**:
- **Weekly schedule**: Sunday 3am UTC (cron)
- **Manual**: Click "Run workflow" in GitHub Actions tab

**What it does**:
1. Starts Neo4j in Docker
2. Restores checkpoint from cache (resumes from last run)
3. Runs the parallel scraper with configurable workers
4. Saves checkpoint back to cache
5. Exports all data as CSV artifacts
6. Stops Neo4j

**Manual trigger options**:
| Input | Options | Default |
|-------|---------|---------|
| `mode` | incremental, events-only, fighters-only, full-reset | incremental |
| `workers` | 1-50 | 10 |

**Required Secrets** (Settings > Secrets > Actions):

| Secret | Description | Default if missing |
|--------|------------|-------------------|
| `NEO4J_URI` | Neo4j connection (bolt://host:port) | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASS` | Neo4j password | `password` |

**Timeout**: 6 hours (360 minutes)

### 4. Deploy Dashboard (`deploy.yml`)

**Triggers**: Push to `main` with changes to dashboard/data_access/visualizations code
**What it does**:
1. Builds Docker image
2. Tests dashboard file syntax
3. Pushes to GitHub Container Registry (ghcr.io)

**Required**: None (uses `GITHUB_TOKEN` automatically)

---

## First-Time Setup

### 1. Push to GitHub

```bash
git init
git remote add origin https://github.com/YOUR_USERNAME/ufc_stats_scrapper.git
git add .
git commit -m "Initial commit: UFC stats scraper with analytics"
git push -u origin main
```

### 2. Configure Secrets (if using Neo4j AuraDB)

1. Go to your repo on GitHub
2. Settings > Secrets and variables > Actions
3. Add:
   - `NEO4J_URI`: `bolt://your-aura-instance.databases.neo4j.io:7687`
   - `NEO4J_USER`: `neo4j`
   - `NEO4J_PASS`: Your AuraDB password

### 3. Run First Crawl

1. Go to **Actions** tab in your repo
2. Click **"Full UFC Data Crawl"**
3. Click **"Run workflow"**
4. Choose mode: `full-reset` (first time) or `incremental`
5. Set workers: `10` (or more for faster crawl)
6. Click **"Run workflow"**

The crawl will run on GitHub's runners with a 6-hour timeout. Results are saved as downloadable CSV artifacts.

### 4. Verify Dashboard Deployment

1. Push any change to `dashboard/app.py` or `data_access/`
2. Go to **Actions** tab
3. Watch **"Deploy Dashboard"** workflow
4. After success, the image is available at:
   ```
   ghcr.io/YOUR_USERNAME/ufc_stats_scrapper/ufc-dashboard:latest
   ```

---

## Local Development

### Run Tests Locally
```bash
.venv\Scripts\python -m pytest tests/ -v
```

### Run Linting Locally
```bash
pip install flake8 pylint black isort
black . --exclude ".venv|__pycache__"
flake8 . --select=E9,F63,F7,F82 --exclude .venv,__pycache__
```

### Run Crawl Locally
```bash
.venv\Scripts\python parallel_scraper.py --workers 10 --delay 0.8
```

---

## Cost Estimation (GitHub Actions)

| Workflow | Monthly Runs | Minutes/Run | Minutes/Month | Cost |
|----------|-------------|-------------|--------------|------|
| Tests | ~20 (pushes/PRs) | 5 | 100 | Free (2,000 min/mo) |
| Lint | ~20 | 2 | 40 | Free |
| Full Crawl | 4 (weekly) | 180-360 | 720-1440 | $0-$5 |
| Deploy | ~5 | 10 | 50 | Free |

**Total estimated cost**: $0-$5/month (GitHub Free tier includes 2,000 minutes/month)
