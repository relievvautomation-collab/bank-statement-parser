import pdfplumber
import re
import fitz  # PyMuPDF (for Format 2)
from .utils import clean_amount, extract_account_holder, extract_account_number, extract_ifsc_code, get_first_last_dates, parse_indian_date

# ----------------------------------------------------------------------
# HDFC Format 1 (Corporate)
# Columns: Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance
# PDF lines are concatenated without spaces. We split carefully.
# Now includes closing balance validation to correct swapped withdrawal/deposit.
# ----------------------------------------------------------------------
def parse_hdfc_format1(pdf_path):
    metadata = {
        'bank_name': 'HDFC',
        'account_holder': '',
        'account_number': '',
        'ifsc_code': '',
        'from_date': '',
        'to_date': ''
    }
    transactions = []
    page_num = 0

    with pdfplumber.open(pdf_path) as pdf:
        # Extract metadata from first page
        first_text = pdf.pages[0].extract_text() or ''
        metadata['account_holder'] = extract_account_holder(first_text, 'HDFC')
        metadata['account_number'] = extract_account_number(first_text, 'HDFC')
        metadata['ifsc_code'] = extract_ifsc_code(first_text)

        # Try to extract opening balance from first page
        opening_balance = None
        ob_match = re.search(r'Opening\s*Balance\s*:?\s*([\d,]+\.\d{2})', first_text, re.IGNORECASE)
        if ob_match:
            opening_balance = clean_amount(ob_match.group(1))
        # If not found, we'll use None and first transaction's closing as base.

        prev_closing = opening_balance  # will be updated after first transaction

        for page in pdf.pages:
            page_num += 1
            text = page.extract_text() or ''
            lines = text.split('\n')

            for line in lines:
                line = line.strip()
                # Skip headers and summary lines
                if not line or 'Date' in line or 'Narration' in line or 'STATEMENT SUMMARY' in line:
                    continue

                # Check if line starts with a date (dd/mm/yy or dd/mm/yyyy)
                date_match = re.match(r'^(\d{2}/\d{2}/\d{2,4})', line)
                if not date_match:
                    continue

                txn_date = parse_indian_date(date_match.group(1))
                remaining = line[len(date_match.group(1)):]

                # --- Extract amounts (they are at the end) ---
                amount_pattern = r'([\d,]+\.\d{2})'
                amounts = re.findall(amount_pattern, remaining)
                if len(amounts) < 2:
                    continue  # Not enough amounts, skip

                # --- Remove amounts from the line to isolate narration + ref no + value date ---
                remaining_for_text = remaining
                for amt in amounts:
                    remaining_for_text = remaining_for_text.replace(amt, '')
                remaining_for_text = remaining_for_text.strip()

                # --- Extract Value Date (at the end) ---
                value_date_match = re.search(r'(\d{2}/\d{2}/\d{2,4})\s*$', remaining_for_text)
                value_date = parse_indian_date(value_date_match.group(1)) if value_date_match else ''
                if value_date_match:
                    remaining_for_text = remaining_for_text[:value_date_match.start()].strip()

                # --- Extract Chq./Ref.No. (long numeric string >= 10 digits) ---
                ref_match = re.search(r'\b(\d{10,})\b', remaining_for_text)
                if ref_match:
                    ref_no = ref_match.group(1)
                    # Remove it from remaining to get pure narration
                    remaining_for_text = remaining_for_text[:ref_match.start()] + remaining_for_text[ref_match.end():]
                else:
                    ref_no = ''

                # --- Clean up narration ---
                narration = re.sub(r'\s+', ' ', remaining_for_text).strip()

                # --- Determine correct assignment of amounts using closing balance validation ---
                # We have a list of amount strings (as extracted, in order of appearance).
                # We'll try possible assignments and pick the one that yields the correct closing balance.

                # Possible assignments:
                # If 3 amounts: (w, d, c) or (d, w, c) – we swap first two.
                # If 2 amounts: (w, c) with d=0, or (d, c) with w=0.
                # We'll compute expected closing from previous closing and candidate (w, d).
                # Then choose assignment where |expected - c| is minimal (within tolerance).

                candidates = []
                if len(amounts) == 3:
                    # candidate1: w = amounts[0], d = amounts[1], c = amounts[2]
                    cand1 = {
                        'w': clean_amount(amounts[0]),
                        'd': clean_amount(amounts[1]),
                        'c': clean_amount(amounts[2])
                    }
                    # candidate2: w = amounts[1], d = amounts[0], c = amounts[2] (swap first two)
                    cand2 = {
                        'w': clean_amount(amounts[1]),
                        'd': clean_amount(amounts[0]),
                        'c': clean_amount(amounts[2])
                    }
                    candidates = [cand1, cand2]
                elif len(amounts) == 2:
                    # candidate1: w = amounts[0], d = 0, c = amounts[1]
                    cand1 = {
                        'w': clean_amount(amounts[0]),
                        'd': 0.0,
                        'c': clean_amount(amounts[1])
                    }
                    # candidate2: w = 0, d = amounts[0], c = amounts[1]
                    cand2 = {
                        'w': 0.0,
                        'd': clean_amount(amounts[0]),
                        'c': clean_amount(amounts[1])
                    }
                    candidates = [cand1, cand2]

                # If we have a previous closing, use it to pick best candidate
                if prev_closing is not None:
                    best_candidate = None
                    best_diff = float('inf')
                    for cand in candidates:
                        expected = prev_closing - cand['w'] + cand['d']
                        diff = abs(expected - cand['c'])
                        if diff < best_diff:
                            best_diff = diff
                            best_candidate = cand
                    # Use best candidate if difference is small, otherwise maybe fallback to default
                    if best_diff < 0.1:  # tolerance
                        withdrawal = best_candidate['w']
                        deposit = best_candidate['d']
                        closing = best_candidate['c']
                    else:
                        # If no good match, fallback to simple heuristic based on credit indicators
                        if 'CR' in line.upper() or 'BY TRANSFER' in line.upper() or 'IMPS CR' in line.upper() or 'NEFT CR' in line.upper() or 'RTGS CR' in line.upper():
                            # Assume it's a credit: first amount is deposit, second is closing (if two) or swap for three?
                            if len(amounts) == 3:
                                withdrawal = clean_amount(amounts[1])
                                deposit = clean_amount(amounts[0])
                                closing = clean_amount(amounts[2])
                            else:
                                withdrawal = 0.0
                                deposit = clean_amount(amounts[0])
                                closing = clean_amount(amounts[1])
                        else:
                            # Assume debit: first amount is withdrawal, second is closing
                            if len(amounts) == 3:
                                withdrawal = clean_amount(amounts[0])
                                deposit = clean_amount(amounts[1])
                                closing = clean_amount(amounts[2])
                            else:
                                withdrawal = clean_amount(amounts[0])
                                deposit = 0.0
                                closing = clean_amount(amounts[1])
                else:
                    # First transaction: use heuristic (or just take first candidate)
                    # We'll use credit indicator heuristic as fallback
                    if 'CR' in line.upper() or 'BY TRANSFER' in line.upper() or 'IMPS CR' in line.upper() or 'NEFT CR' in line.upper() or 'RTGS CR' in line.upper():
                        if len(amounts) == 3:
                            withdrawal = clean_amount(amounts[1])
                            deposit = clean_amount(amounts[0])
                            closing = clean_amount(amounts[2])
                        else:
                            withdrawal = 0.0
                            deposit = clean_amount(amounts[0])
                            closing = clean_amount(amounts[1])
                    else:
                        if len(amounts) == 3:
                            withdrawal = clean_amount(amounts[0])
                            deposit = clean_amount(amounts[1])
                            closing = clean_amount(amounts[2])
                        else:
                            withdrawal = clean_amount(amounts[0])
                            deposit = 0.0
                            closing = clean_amount(amounts[1])

                # Update prev_closing for next transaction
                prev_closing = closing

                transactions.append({
                    'date': txn_date,
                    'narration': narration,
                    'chq_ref': ref_no,
                    'value_date': value_date,
                    'withdrawal': withdrawal,
                    'deposit': deposit,
                    'closing_balance': closing,
                    'page_no': page_num
                })

    # Merge multi-line narrations (if any – though in this format each transaction is one line)
    merged = []
    skip = False
    for i in range(len(transactions)):
        if skip:
            skip = False
            continue
        curr = transactions[i]
        if i+1 < len(transactions) and not re.match(r'\d{2}/\d{2}/\d{4}', transactions[i+1]['date']):
            curr['narration'] += ' ' + transactions[i+1]['narration']
            skip = True
        merged.append(curr)

    # Set period from transaction dates
    if merged:
        first, last = get_first_last_dates(merged, 'date')
        metadata['from_date'] = first
        metadata['to_date'] = last

    return metadata, merged


# ----------------------------------------------------------------------
# HDFC Format 2 (Fortune) – unchanged from previous working version
# Columns: Txn Date | Narration (multi-line) | Withdrawals | Deposits | Closing Balance
# ----------------------------------------------------------------------
def parse_hdfc_format2(pdf_path):
    metadata = {
        'bank_name': 'HDFC',
        'account_holder': '',
        'account_number': '',
        'ifsc_code': '',
        'from_date': '',
        'to_date': ''
    }
    transactions = []

    doc = fitz.open(pdf_path)

    # Extract metadata from first page
    first_page_text = doc[0].get_text()
    metadata['account_holder'] = extract_account_holder(first_page_text, 'HDFC')
    metadata['account_number'] = extract_account_number(first_page_text, 'HDFC')
    metadata['ifsc_code'] = extract_ifsc_code(first_page_text)

    in_table = False
    current_txn = None  # dict with fields: date, narration_lines, page

    # Regex to detect amount line: three numbers separated by spaces, each possibly with minus and commas
    amount_line_pattern = re.compile(
        r'^(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})$'
    )

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect table header
            if re.search(r'Txn Date\s+Narration\s+Withdrawals\s+Deposits\s+Closing Balance', line, re.IGNORECASE):
                in_table = True
                continue

            if not in_table:
                continue

            # Check if line starts with a date (dd/mm/yyyy)
            date_match = re.match(r'^(\d{2}/\d{2}/\d{4})', line)
            if date_match:
                # If we were building a transaction and didn't get its amount line yet, it's incomplete – discard.
                # This should not happen in well-formed PDF.
                current_txn = {
                    'date': parse_indian_date(date_match.group(1)),
                    'narration_lines': [],
                    'page': page_num + 1
                }
                # The rest of this line might be part of narration
                rest = line[len(date_match.group(1)):].strip()
                if rest:
                    current_txn['narration_lines'].append(rest)
            else:
                # Not a date line – could be continuation of narration or amount line
                if current_txn:
                    # Check if this line is the amount line
                    amount_match = amount_line_pattern.match(line)
                    if amount_match:
                        # It is the amount line – finalize transaction
                        withdrawals = clean_amount(amount_match.group(1))
                        deposits = clean_amount(amount_match.group(2))
                        closing = clean_amount(amount_match.group(3))

                        # Concatenate all narration lines
                        narration = ' '.join(current_txn['narration_lines'])
                        narration = re.sub(r'\s+', ' ', narration).strip()

                        transactions.append({
                            'txn_date': current_txn['date'],
                            'narration': narration,
                            'withdrawals': withdrawals,
                            'deposits': deposits,
                            'closing_balance': closing,
                            'page_no': current_txn['page']
                        })

                        # Reset current_txn
                        current_txn = None
                    else:
                        # It's a narration line
                        current_txn['narration_lines'].append(line)

        # End of page – if a transaction is incomplete, it will continue on next page; current_txn persists.

    doc.close()

    # Set period from transaction dates
    if transactions:
        first, last = get_first_last_dates(transactions, 'txn_date')
        metadata['from_date'] = first
        metadata['to_date'] = last

    return metadata, transactions
