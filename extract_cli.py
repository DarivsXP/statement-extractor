#!/usr/bin/env python3
"""
CLI Statement to CSV Extractor with Anthropic Claude AI Support & Review Flags.
Usage:
  python3 extract_cli.py <path_to_pdf> [-o <output_csv>] [--api-key <key>] [--audit]
"""
import sys
import os
import argparse
from extractor import parse_statement_pdf, to_csv

def main():
    parser = argparse.ArgumentParser(description="Extract transaction data from credit card and bank statement PDFs into standard CSV (excluding balance).")
    parser.add_argument("pdf_path", help="Path to statement PDF file")
    parser.add_argument("-o", "--output", help="Path to output CSV file (default: stdout)", default=None)
    parser.add_argument("--api-key", help="Anthropic API Key (or set ANTHROPIC_API_KEY environment variable)", default=None)
    parser.add_argument("--model", help="Claude model name", default="claude-3-7-sonnet-20250219")
    parser.add_argument("--audit", help="Include AI Confidence and Review Reason columns in CSV", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"Error: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = parse_statement_pdf(args.pdf_path, api_key=args.api_key, model=args.model)
    transactions = result['transactions']
    validation = result['validation']

    if not transactions:
        print(f"Warning: No valid transactions detected in {args.pdf_path}", file=sys.stderr)

    csv_data = to_csv(transactions, include_confidence=args.audit)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(csv_data)
        print(f"✓ Engine:        {validation.get('engine', 'Unknown')}")
        print(f"✓ Extracted {len(transactions)} transactions to {args.output}")
        print(f"✓ AI Confidence: {validation.get('overall_confidence', 0)}%")
        print(f"✓ Needs Review:  {validation.get('needs_review_count', 0)} transactions")
        print(f"✓ Total Debits:  ${validation.get('total_debits', '0.00')}")
        print(f"✓ Total Credits: ${validation.get('total_credits', '0.00')}")
        if validation.get('status') == 'reconciled':
            print("✓ Reconciliation: MATCHES STATEMENT SUMMARY TOTALS (100% Verified)")
        for msg in validation.get('messages', []):
            print(f"  - {msg}")
    else:
        print(csv_data)
        print("\n# --- VALIDATION REPORT ---", file=sys.stderr)
        print(f"# Engine: {validation.get('engine')}", file=sys.stderr)
        print(f"# Transactions: {len(transactions)} (Review needed: {validation.get('needs_review_count', 0)})", file=sys.stderr)
        print(f"# Overall Confidence: {validation.get('overall_confidence')}%", file=sys.stderr)
        print(f"# Debits: ${validation.get('total_debits')}, Credits: ${validation.get('total_credits')}", file=sys.stderr)
        print(f"# Status: {validation.get('status').upper()}", file=sys.stderr)

if __name__ == '__main__':
    main()
