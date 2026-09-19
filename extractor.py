import re
import io
import csv
import json
import base64
import os
import pdfplumber

def _load_dotenv():
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v and k not in os.environ:
                        os.environ[k] = v

_load_dotenv()

MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    'january': '01', 'february': '02', 'march': '03', 'april': '04', 'may': '05', 'june': '06',
    'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
}

MONTH_REGEX_STR = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'

def parse_date_to_dmy(date_str, statement_year="2026"):
    """
    Parses various date formats into standard DD/MM/YYYY.
    """
    date_str = date_str.strip().replace(',', '')
    
    # Month name + Day: Jul 8 or Jul 08
    m1 = re.match(rf'^({MONTH_REGEX_STR})\s+(\d{{1,2}})(?:\s+(\d{{2,4}}))?$', date_str, re.IGNORECASE)
    if m1:
        mon = MONTH_MAP.get(m1.group(1).lower()[:3], '01')
        day = f"{int(m1.group(2)):02d}"
        yr = m1.group(3) or statement_year
        if len(yr) == 2:
            yr = "20" + yr
        return f"{day}/{mon}/{yr}"

    # Day + Month name: 8 Jul or 08 July 2026
    m2 = re.match(rf'^(\d{{1,2}})\s+({MONTH_REGEX_STR})(?:\s+(\d{{2,4}}))?$', date_str, re.IGNORECASE)
    if m2:
        day = f"{int(m2.group(1)):02d}"
        mon = MONTH_MAP.get(m2.group(2).lower()[:3], '01')
        yr = m2.group(3) or statement_year
        if len(yr) == 2:
            yr = "20" + yr
        return f"{day}/{mon}/{yr}"

    # Numeric: DD/MM/YYYY or MM/DD/YYYY
    m3 = re.match(r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$', date_str)
    if m3:
        p1, p2, yr = int(m3.group(1)), int(m3.group(2)), m3.group(3)
        if len(yr) == 2:
            yr = "20" + yr
        return f"{p1:02d}/{p2:02d}/{yr}"

    # ISO: YYYY-MM-DD
    m4 = re.match(r'^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$', date_str)
    if m4:
        yr, mon, day = m4.group(1), int(m4.group(2)), int(m4.group(3))
        return f"{day:02d}/{mon:02d}/{yr}"

    return date_str


def reconstruct_lines_from_page(page):
    """
    Reconstruct lines of text in true visual reading order using word bounding boxes.
    """
    words = page.extract_words(x_tolerance=3, y_tolerance=3)
    if not words:
        return []
    
    words_sorted = sorted(words, key=lambda w: (w['top'], w['x0']))
    lines = []
    current_line = []
    current_top = None
    
    for w in words_sorted:
        if current_top is None:
            current_top = w['top']
            current_line.append(w)
        elif abs(w['top'] - current_top) <= 5:
            current_line.append(w)
        else:
            current_line.sort(key=lambda x: x['x0'])
            lines.append((current_top, current_line))
            current_line = [w]
            current_top = w['top']
            
    if current_line:
        current_line.sort(key=lambda x: x['x0'])
        lines.append((current_top, current_line))
        
    return lines


def extract_statement_metadata(all_lines):
    """
    Extracts statement period, statement date, statement year,
    and printed debit/credit totals from statement header and summaries.
    """
    full_text = " \n ".join(" ".join(w['text'] for w in line_words) for _, line_words in all_lines)
    
    year = "2026"
    period_m = re.search(r'Statement (?:Period|Date).*?(\d{4})', full_text, re.IGNORECASE)
    if period_m:
        year = period_m.group(1)
    else:
        y_m = re.search(r'\b(202[0-9])\b', full_text)
        if y_m:
            year = y_m.group(1)

    expected_debits = None
    deb_m = re.search(r'(?:Purchases/charges\s*\+|SUB-TOTAL\s+DEBITS.*?)\s*\$?\s*([\d,]+\.\d{2})', full_text, re.IGNORECASE)
    if deb_m:
        try:
            expected_debits = float(deb_m.group(1).replace(',', ''))
        except Exception:
            pass

    expected_credits = None
    cred_m = re.search(r'(?:Payments/credits\s*-|SUB-TOTAL\s+CREDITS.*?)\s*\$?\s*([\d,]+\.\d{2})', full_text, re.IGNORECASE)
    if cred_m:
        try:
            expected_credits = float(cred_m.group(1).replace(',', ''))
        except Exception:
            pass

    return {
        'year': year,
        'expected_debits': expected_debits,
        'expected_credits': expected_credits
    }


def extract_with_claude(pdf_bytes, api_key, model="claude-sonnet-4-5-20250929"):
    """
    Extracts statement data using Anthropic Claude Messages API with native PDF document block.
    Returns high-accuracy structured JSON with per-row confidence and needs_review flags.
    """
    import anthropic
    
    client = anthropic.Anthropic(api_key=api_key)
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    prompt = """You are a senior financial auditor and automated document data extraction specialist.
Analyze this financial statement PDF (bank, credit card, or merchant account statement) and extract EVERY individual transaction into clean, audit-ready structured data.

CRITICAL EXTRACTION RULES:
1. ROWS TO EXTRACT:
   - Extract every valid debit, purchase, payment, credit, deposit, refund, withdrawal, interest fee, annual fee, or service charge.
   - DO NOT include table summary rows (e.g., "SUB-TOTAL DEBITS", "TOTAL PURCHASES", "PAYMENTS RECEIVED", "PREVIOUS BALANCE", "NEW BALANCE", "BALANCE FORWARD").
   - DO NOT include cardholder section divider lines or account summary widgets.

2. COLUMNS & FORMATTING:
   - "date": Normalized strictly as DD/MM/YYYY. If the statement shows only Month & Day (e.g. "Jul 8"), infer the statement year from the statement header/period.
   - "description": Clean, standardized merchant or narrative text. Remove extraneous row reference numbers or OCR artefacts, but preserve important merchant details (city, store ID).
   - "debit": String formatted with 2 decimal places (e.g. "45.00") if this is an expense, charge, purchase, withdrawal, fee, or money leaving the account. Empty string "" if credit.
   - "credit": String formatted with 2 decimal places (e.g. "120.00") if this is a payment, deposit, refund, reward credit, or money entering the account. Empty string "" if debit.
   - DO NOT output a balance column. Debit and Credit must be positive numbers or empty strings.

3. AI CONFIDENCE & REVIEW AUDITING:
   - "confidence": Integer percentage from 0 to 100 representing your certainty in this row's extraction, date parsing, and debit/credit orientation.
   - "confidence_level": "high" (90-100), "medium" (75-89), or "low" (<75).
   - "needs_review": Boolean. Set to true if human review is advised. Reasons include:
     * Date year had to be inferred or month/day order was ambiguous (e.g. 05/06)
     * Debit vs Credit distinction was unclear in the original statement layout
     * Multi-line description wrapped across a page boundary
     * Possible OCR noise, foreign currency conversion, or atypical fee row
   - "review_reason": Short human-readable explanation if needs_review is true or confidence < 90; otherwise null.

4. STATEMENT METADATA & TOTALS:
   - "institution_name": Bank or card issuer name (e.g., "Scotiabank", "Chase", "American Express", "Barclays", etc.)
   - "statement_period": Text of statement date range or cycle date (e.g. "June 10, 2026 - July 9, 2026")
   - "account_number_masked": Masked account/card number if visible (e.g. "XXXX-XXXX-XXXX-4537")
   - "statement_total_debits": Float of total purchases/debits printed in summary, or null if not explicitly printed.
   - "statement_total_credits": Float of total payments/credits printed in summary, or null if not explicitly printed.
   - "opening_balance": Float or null.
   - "closing_balance": Float or null.

RESPOND ONLY with a single valid JSON object in this exact schema (no markdown preamble, no conversational filler):
{
  "metadata": {
    "institution_name": "string or null",
    "statement_period": "string or null",
    "account_number_masked": "string or null",
    "statement_total_debits": 0.00,
    "statement_total_credits": 0.00,
    "opening_balance": 0.00,
    "closing_balance": 0.00
  },
  "transactions": [
    {
      "date": "08/07/2026",
      "description": "MERCHANT NAME HERE",
      "debit": "45.00",
      "credit": "",
      "confidence": 98,
      "confidence_level": "high",
      "needs_review": false,
      "review_reason": null
    }
  ]
}
"""

    chosen_model = model or "claude-sonnet-4-5-20250929"

    try:
        response = client.messages.create(
            model=chosen_model,
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )
    except Exception as e:
        # Fallback to claude-haiku-4-5-20251001 if chosen model fails
        if chosen_model != "claude-haiku-4-5-20251001":
            chosen_model = "claude-haiku-4-5-20251001"
            response = client.messages.create(
                model=chosen_model,
                max_tokens=8192,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
        else:
            raise e

    content_text = ""
    for block in response.content:
        if getattr(block, 'type', '') == 'text':
            content_text += block.text

    json_match = re.search(r'\{[\s\S]*\}', content_text)
    if not json_match:
        raise ValueError("Could not extract JSON from Claude response.")
    
    parsed = json.loads(json_match.group(0))
    raw_txs = parsed.get('transactions', [])
    meta = parsed.get('metadata', {})

    calc_debits = 0.0
    calc_credits = 0.0
    total_conf = 0
    needs_review_count = 0

    clean_txs = []
    for tx in raw_txs:
        d_str = str(tx.get('debit') or '').strip().replace('$', '').replace(',', '')
        c_str = str(tx.get('credit') or '').strip().replace('$', '').replace(',', '')
        
        d_val = float(d_str) if d_str else 0.0
        c_val = float(c_str) if c_str else 0.0
        
        calc_debits += d_val
        calc_credits += c_val

        conf = int(tx.get('confidence', 95))
        total_conf += conf

        needs_review = bool(tx.get('needs_review', False))
        if conf < 80:
            needs_review = True
        if needs_review:
            needs_review_count += 1

        clean_txs.append({
            'date': str(tx.get('date', '')).strip(),
            'description': str(tx.get('description', '')).strip(),
            'debit': f"{d_val:.2f}" if d_val > 0 else "",
            'credit': f"{c_val:.2f}" if c_val > 0 else "",
            'confidence': conf,
            'confidence_level': tx.get('confidence_level', 'high' if conf >= 90 else ('medium' if conf >= 75 else 'low')),
            'needs_review': needs_review,
            'review_reason': tx.get('review_reason') or ('Confidence score below 80%' if conf < 80 else None)
        })

    avg_conf = round(total_conf / len(clean_txs)) if clean_txs else 0

    expected_deb = meta.get('statement_total_debits')
    expected_cred = meta.get('statement_total_credits')

    reconciled = True
    validation_messages = []

    if expected_deb is not None:
        diff_deb = abs(calc_debits - float(expected_deb))
        if diff_deb > 0.01:
            reconciled = False
            validation_messages.append(f"Debit mismatch: Extracted ${calc_debits:.2f} vs Statement Summary ${float(expected_deb):.2f}")
        else:
            validation_messages.append(f"Debits match statement summary: ${calc_debits:.2f}")

    if expected_cred is not None:
        diff_cred = abs(calc_credits - float(expected_cred))
        if diff_cred > 0.01:
            reconciled = False
            validation_messages.append(f"Credit mismatch: Extracted ${calc_credits:.2f} vs Statement Summary ${float(expected_cred):.2f}")
        else:
            validation_messages.append(f"Credits match statement summary: ${calc_credits:.2f}")

    if not validation_messages:
        validation_messages.append(f"Extracted {len(clean_txs)} transactions.")

    validation_report = {
        'engine': f'{chosen_model}',
        'status': 'reconciled' if reconciled and (expected_deb is not None or expected_cred is not None) else ('warning' if not reconciled else 'verified'),
        'reconciled': reconciled,
        'overall_confidence': avg_conf,
        'needs_review_count': needs_review_count,
        'total_debits': f"{calc_debits:.2f}",
        'total_credits': f"{calc_credits:.2f}",
        'expected_debits': f"{float(expected_deb):.2f}" if expected_deb is not None else None,
        'expected_credits': f"{float(expected_cred):.2f}" if expected_cred is not None else None,
        'messages': validation_messages
    }

    return {
        'transactions': clean_txs,
        'validation': validation_report,
        'metadata': meta
    }


def parse_statement_pdf_heuristic(pdf_source):
    """
    Layout reconstruction & regex-based parser with confidence scoring & review detection.
    Used when no Anthropic API key is provided.
    """
    if isinstance(pdf_source, bytes):
        pdf_file = io.BytesIO(pdf_source)
    else:
        pdf_file = pdf_source

    with pdfplumber.open(pdf_file) as pdf:
        all_page_lines = []
        for p in pdf.pages:
            p_lines = reconstruct_lines_from_page(p)
            all_page_lines.extend(p_lines)

    meta = extract_statement_metadata(all_page_lines)
    year = meta['year']

    row_pattern = re.compile(
        rf'^(?:(?P<ref>\d{{3,4}})\s+)?(?P<date1>{MONTH_REGEX_STR}\s+\d{{1,2}}|\d{{1,2}}[/\-.]\d{{1,2}}(?:[/\-.]\d{{2,4}})?)\s+(?:(?P<date2>{MONTH_REGEX_STR}\s+\d{{1,2}}|\d{{1,2}}[/\-.]\d{{1,2}})\s+)?(?P<rest>.*)$',
        re.IGNORECASE
    )
    amount_pattern = re.compile(r'(\$?\s*[\d,]+\.\d{2})(-|CR)?$', re.IGNORECASE)

    tx_start_keywords = [
        'TRANSACTIONS SINCE YOUR LAST STATEMENT',
        'TRANSACTIONS - CONTINUED',
        'TRANSACTIONS',
        'ACCOUNT ACTIVITY',
        'STATEMENT ACTIVITY',
        'DETAILS OF YOUR TRANSACTIONS'
    ]

    tx_end_keywords = [
        'SUB-TOTAL',
        'SUB TOTAL',
        'TOTAL DEBITS',
        'TOTAL CREDITS',
        'INTEREST CHARGES',
        'ESTIMATE OF THE TIME',
        'SPECIAL OFFERS',
        'ACCOUNT SUMMARY',
        'REWARD POINTS SUMMARY',
        'FEES CHARGED',
        'INTEREST CHARGED'
    ]

    in_transaction_section = False
    transactions = []
    current_tx = None

    for _, line_words in all_page_lines:
        line_text = " ".join(w['text'] for w in line_words).strip()
        upper = line_text.upper()

        if any(k in upper for k in tx_start_keywords):
            in_transaction_section = True
            if current_tx and current_tx.get('amount'):
                transactions.append(current_tx)
                current_tx = None
            continue

        if in_transaction_section and any(upper.startswith(k) for k in tx_end_keywords):
            if current_tx and current_tx.get('amount'):
                transactions.append(current_tx)
                current_tx = None
            in_transaction_section = False
            continue

        if not in_transaction_section:
            if row_pattern.match(line_text) and amount_pattern.search(line_text):
                in_transaction_section = True
            else:
                continue

        if re.search(r'^(REF\.?#|TRANS\.?\s*DATE|POST\s*DATE|DETAILS|AMOUNT|ACCOUNT|CARDMEMBER)', upper):
            continue
        if re.search(r'^[A-Z\s\-]+-\s*\d{4}\s*X+', upper):
            continue
        if upper.startswith('CONTINUED ON PAGE'):
            if current_tx and current_tx.get('amount'):
                transactions.append(current_tx)
                current_tx = None
            continue

        match = row_pattern.match(line_text)
        if match:
            if current_tx and current_tx.get('amount'):
                transactions.append(current_tx)
                current_tx = None

            raw_date = match.group('date1')
            formatted_date = parse_date_to_dmy(raw_date, year)
            rest = (match.group('rest') or '').strip()

            current_tx = {
                'date': formatted_date,
                'desc_lines': [],
                'amount': None,
                'is_credit': False,
                'has_ref': bool(match.group('ref')),
                'raw_date': raw_date
            }

            amt_match = amount_pattern.search(rest)
            if amt_match:
                amt_str = amt_match.group(1).replace('$', '').replace(' ', '').strip()
                is_credit = bool(amt_match.group(2))
                desc = rest[:amt_match.start()].strip()
                if desc:
                    current_tx['desc_lines'].append(desc)
                current_tx['amount'] = amt_str
                current_tx['is_credit'] = is_credit
            else:
                if rest:
                    current_tx['desc_lines'].append(rest)

        elif current_tx:
            amt_match = amount_pattern.search(line_text)
            if amt_match and not current_tx.get('amount'):
                amt_str = amt_match.group(1).replace('$', '').replace(' ', '').strip()
                is_credit = bool(amt_match.group(2))
                desc = line_text[:amt_match.start()].strip()
                if desc:
                    current_tx['desc_lines'].append(desc)
                current_tx['amount'] = amt_str
                current_tx['is_credit'] = is_credit
                transactions.append(current_tx)
                current_tx = None
            else:
                if not re.match(r'^(page\s+\d+|scotiabank|continued)', line_text, re.I):
                    current_tx['desc_lines'].append(line_text)

    if current_tx and current_tx.get('amount'):
        transactions.append(current_tx)

    results = []
    calc_debits = 0.0
    calc_credits = 0.0
    total_conf = 0
    needs_review_count = 0

    for tx in transactions:
        desc = " ".join(tx['desc_lines']).strip()
        desc = re.sub(r'\s+', ' ', desc)
        amt_str = tx.get('amount', '0.00')
        try:
            val = float(amt_str.replace(',', ''))
            formatted_amt = f"{val:.2f}"
        except Exception:
            formatted_amt = amt_str
            val = 0.0

        if tx['is_credit']:
            debit = ""
            credit = formatted_amt
            calc_credits += val
        else:
            debit = formatted_amt
            credit = ""
            calc_debits += val

        # Calculate heuristic confidence & review flags
        conf = 88
        review_reasons = []
        if not tx.get('has_ref'):
            conf -= 5
        if len(tx.get('desc_lines', [])) > 2:
            conf -= 8
            review_reasons.append("Multi-line description joined")
        if re.search(r'\b(refund|payment|cr)\b', desc, re.I) and not tx['is_credit']:
            conf -= 15
            review_reasons.append("Contains 'refund/payment' keyword but classified as debit")
        if tx['is_credit']:
            conf += 2

        conf = max(40, min(96, conf))
        total_conf += conf
        needs_review = conf < 85 or len(review_reasons) > 0
        if needs_review:
            needs_review_count += 1

        results.append({
            'date': tx['date'],
            'description': desc,
            'debit': debit,
            'credit': credit,
            'confidence': conf,
            'confidence_level': 'high' if conf >= 90 else ('medium' if conf >= 75 else 'low'),
            'needs_review': needs_review,
            'review_reason': "; ".join(review_reasons) if review_reasons else None
        })

    expected_deb = meta.get('expected_debits')
    expected_cred = meta.get('expected_credits')

    reconciled = True
    validation_messages = []

    if expected_deb is not None:
        diff_deb = abs(calc_debits - expected_deb)
        if diff_deb > 0.01:
            reconciled = False
            validation_messages.append(f"Debit mismatch: Extracted ${calc_debits:.2f} vs Statement Summary ${expected_deb:.2f}")
        else:
            validation_messages.append(f"Debits match statement summary: ${calc_debits:.2f}")

    if expected_cred is not None:
        diff_cred = abs(calc_credits - expected_cred)
        if diff_cred > 0.01:
            reconciled = False
            validation_messages.append(f"Credit mismatch: Extracted ${calc_credits:.2f} vs Statement Summary ${expected_cred:.2f}")
        else:
            validation_messages.append(f"Credits match statement summary: ${calc_credits:.2f}")

    avg_conf = round(total_conf / len(results)) if results else 0

    validation_report = {
        'engine': 'Rule-Based Parser',
        'status': 'reconciled' if reconciled and (expected_deb is not None or expected_cred is not None) else ('warning' if not reconciled else 'verified'),
        'reconciled': reconciled,
        'overall_confidence': avg_conf,
        'needs_review_count': needs_review_count,
        'total_debits': f"{calc_debits:.2f}",
        'total_credits': f"{calc_credits:.2f}",
        'expected_debits': f"{expected_deb:.2f}" if expected_deb is not None else None,
        'expected_credits': f"{expected_cred:.2f}" if expected_cred is not None else None,
        'messages': validation_messages
    }

    return {
        'transactions': results,
        'validation': validation_report,
        'metadata': meta
    }


def parse_statement_pdf(pdf_source, api_key=None, model="claude-3-7-sonnet-20250219"):
    """
    Unified entry point.
    If an Anthropic API key is provided (or set in ANTHROPIC_API_KEY env), uses Claude.
    Otherwise falls back to the layout-reconstruction heuristic parser.
    """
    key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    
    if isinstance(pdf_source, str):
        with open(pdf_source, 'rb') as f:
            pdf_bytes = f.read()
    elif hasattr(pdf_source, 'read'):
        pdf_bytes = pdf_source.read()
    else:
        pdf_bytes = pdf_source

    if key and key.strip().startswith('sk-ant-'):
        try:
            return extract_with_claude(pdf_bytes, key.strip(), model=model)
        except Exception as e:
            print(f"Anthropic Claude extraction encountered an error: {e}. Falling back to heuristic parser.")
            res = parse_statement_pdf_heuristic(pdf_bytes)
            res['validation']['fallback_reason'] = str(e)
            return res
    else:
        return parse_statement_pdf_heuristic(pdf_bytes)


def _parse_date_for_sort(date_str):
    if not date_str or not isinstance(date_str, str):
        return (9999, 12, 31)
    s = date_str.strip()
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = re.match(r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$', s)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
        if year < 100:
            year += 2000
        return (year, month, day)
    # YYYY-MM-DD or YYYY/MM/DD
    m = re.match(r'^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$', s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (9999, 12, 31)


def to_csv(transactions, include_confidence=False):
    """
    Exports transactions to standard CSV sorted chronologically by date.
    Standard: Date, Description, Debit, Credit (No Balance).
    Optional audit columns: Confidence, Needs Review, Review Reason.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    sorted_txs = sorted(transactions, key=lambda t: _parse_date_for_sort(t.get('date', '')))

    if include_confidence:
        writer.writerow(['Date', 'Description', 'Debit', 'Credit', 'Confidence', 'Needs Review', 'Review Reason'])
        for row in sorted_txs:
            writer.writerow([
                row.get('date', ''),
                row.get('description', ''),
                row.get('debit', ''),
                row.get('credit', ''),
                f"{row.get('confidence', '')}%",
                "YES" if row.get('needs_review') else "NO",
                row.get('review_reason', '') or ''
            ])
    else:
        writer.writerow(['Date', 'Description', 'Debit', 'Credit'])
        for row in sorted_txs:
            writer.writerow([
                row.get('date', ''),
                row.get('description', ''),
                row.get('debit', ''),
                row.get('credit', '')
            ])
            
    return output.getvalue()
