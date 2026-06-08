# Precursive Browser Agent

> Teaching AI to fill out my timesheet so I don't have to.

Automates entry of work hours into the [Precursive](https://www.precursive.com/) Salesforce timesheet UI by reading rows from a CSV export and driving a real browser session end-to-end — login, date navigation, project/phase selection, task category tagging, and hour entry.

---

## How It Works

1. Reads rows from a Timely CSV export (`Hour Date`, `Project`, `Hour Tags`, `Logged Hours`)
2. Opens a persistent browser session (login + 2FA once, reused across all rows)
3. For each row, instructs a Claude-powered browser agent to:
   - Navigate to the Precursive timesheet page
   - Set the correct date
   - Add a new row and select the right project + phase
   - Select matching task categories
   - Enter the logged hours
4. Logs all output (including timing and token cost) to `run_log.txt`

---

## Project Structure

```
├── main.py        # Original version — new browser session per row
├── main2.py       # Optimised version — single persistent browser session
├── run_log.txt    # Output log (appended on each run)
├── .env           # Credentials (not committed)
└── Timely Data - Yazan - Timely Data - Yazan.csv   # Input data
```

---

## Setup

### 1. Install dependencies

```bash
pip install browser-use python-dotenv
```

### 2. Create a `.env` file

```env
EMAIL=your.email@company.com
PASS=your_password
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Configure the run

At the top of `main2.py`:

```python
CSV_FILE = "Timely Data - Yazan - Timely Data - Yazan.csv"
ROWS = 2       # Process first 2 rows. Set to None for all rows.
```

---

## Running

```bash
python main2.py
```

The browser window will open visibly (`headless=False`). On the first row it will log in and handle 2FA — subsequent rows reuse the same session.

---

## Output

Terminal and `run_log.txt` both receive:

```
--- Row 1/2: 06/04/2026 | Internal ---
Output:  I'm Done Yazan
Row 1 completed in 209.0s | tokens: 135,000 | cost: $0.3150

--- Row 2/2: 07/04/2026 | Internal ---
Output:  I'm Done Yazan
Row 2 completed in 232.1s | tokens: 134,699 | cost: $0.3158

--- Overall ---
Rows processed : 2
Total time     : 441.1s
Total tokens   : 269,699
Total cost     : $0.6308
```

---

## CSV Format

The input CSV must contain these columns (Timely export format):

| Column | Description |
|---|---|
| `Hour Date` | Date in `DD/MM/YYYY` format |
| `Project` | Project name matching Precursive |
| `Hour Tags` | Comma-separated task categories |
| `Logged Hours` | Hours as a decimal number |

---

## Models Used

| Role | Model |
|---|---|
| Agent (reasoning + actions) | `claude-sonnet-4-6` |
| Page extraction | `claude-haiku-4-5-20251001` |
