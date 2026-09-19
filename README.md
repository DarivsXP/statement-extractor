# StatementFlow (AI-Powered Statement to CSV Extractor)

A smart financial document extraction and reconciliation tool inspired by Dext. It converts credit card and bank statement PDFs from any institution into standard bookkeeping CSVs (**Date, Description, Debit, Credit** with balance excluded).

---

## What Makes It Smart: Anthropic Claude AI

StatementFlow features a dual-engine architecture:
1. **Anthropic Claude Engine (Recommended)**: Powered by Claude 3.7 Sonnet / Claude 3.5 Sonnet / Haiku. Analyzes statements using native visual document reasoning to handle complex multi-column bank layouts, multi-line descriptions, inverted debits/credits, refunds, and foreign exchange lines with extreme precision.
2. **Heuristic Engine**: Layout-reconstruction fallback when running completely offline or without an API key.

### Key Capabilities
- **Confidence Scoring**: Computes calibrated confidence percentages (0-100%) and categorizes transactions into High, Medium, or Low certainty.
- **Audit & "Needs Review" System**: Automatically flags ambiguous entries (e.g., date formats requiring inference, unclear debit/credit signs, OCR noise).
- **Interactive Review Hub**: Filter transactions to only those needing review with one click, inspect the exact reason for flagging, edit in-place, and approve rows.
- **Mathematical Reconciliation**: Cross-checks total extracted debits and credits against statement summary boxes for a 100% verified audit trail.
- **Standard & Audit CSV Exports**: Export standard 4-column CSVs for Xero / QuickBooks / Excel, or an Audit CSV containing confidence scores and review notes.

---

## Quick Start (Web App)

1. Navigate to the project directory:
   ```bash
   cd "/Users/cyril/Project experiments/statement-extractor"
   ```

2. Start the local server:
   ```bash
   ./venv/bin/python3 server.py
   ```

3. Open your browser:
   ```
   http://localhost:8080
   ```

4. **Connect Anthropic Key**:
   - Click **"AI Settings"** (top right) or the engine status badge.
   - Enter your Anthropic API Key (`sk-ant-...`).
   - Select your preferred model (default: **Claude 3.7 Sonnet**).
   - Click **"Test Connection"** and **"Save Settings"**.
   *(Your key is stored in your local browser storage and sent directly to your local Python server).*

5. Upload your bank or credit card statement PDF.
6. Inspect the confidence score, review any flagged rows in the **"Needs Review"** tab, and click **"Export Standard CSV"**.

---

## Command Line Usage (CLI)

You can also run extraction directly from terminal:

```bash
# With Anthropic Claude AI (via flag or ANTHROPIC_API_KEY env)
export ANTHROPIC_API_KEY="sk-ant-..."
./venv/bin/python3 extract_cli.py path/to/statement.pdf -o transactions.csv

# With optional Audit columns (Confidence %, Needs Review, Review Reason)
./venv/bin/python3 extract_cli.py path/to/statement.pdf -o audit.csv --audit

# Offline Heuristic Mode (no API key required)
./venv/bin/python3 extract_cli.py path/to/statement.pdf
```

---

## Output CSV Formats

### Standard Format (Accounting & Bookkeeping Import)
```csv
Date,Description,Debit,Credit
08/07/2026,ORUMA RESTAURANT SCARBOROUGH ON,41.79,
14/07/2026,MEND PHYSIO NORTH VANCOUVBC,110.00,
21/07/2026,ROYAL BANK OF CANADA TORONTO,,241.84
```

### Audit Format (Quality Assurance & Review)
```csv
Date,Description,Debit,Credit,Confidence,Needs Review,Review Reason
08/07/2026,ORUMA RESTAURANT SCARBOROUGH ON,41.79,,98%,NO,
14/07/2026,MEND PHYSIO NORTH VANCOUVBC,110.00,,82%,YES,Multi-line description joined
21/07/2026,ROYAL BANK OF CANADA TORONTO,,241.84,97%,NO,
```
