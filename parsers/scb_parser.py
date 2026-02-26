import pdfplumber
import re
from .utils import clean_amount, get_first_last_dates, parse_indian_date

def parse_scb_standard(pdf_path):
    """
    Parse Standard Chartered bank statement.
    Output format: Date, Value Date, Description, Cheque, Deposit, Withdrawal, Balance, Page No
    """
    metadata = {
        'bank_name': 'Standard Chartered',
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
        metadata['account_holder'] = extract_account_holder_scb(first_text)
        metadata['account_number'] = extract_account_number_scb(first_text)
        metadata['ifsc_code'] = extract_ifsc_code_scb(first_text)

        previous_balance = None
        in_transaction_table = True
        sentinel_patterns = [
            r'Total\s+[\d,]+\.\d{2}',
            r'REWARD POINTS STATEMENT',
            r'Dear Client,',
            r'Bank deposits are covered',
            r'Stay updated with important',
            r'The Ministry of Home Affairs',
            r'Insurance:',
            r'You may visit',
        ]
        # Pattern to detect column headers that should be ignored
        header_pattern = re.compile(
            r'Date\s+Value Date\s+Description\s+Cheque\s+Deposit\s+Withdrawal\s+Balance',
            re.IGNORECASE
        )
        unwanted_phrase = re.compile(
            r'Value Date Description Cheque Deposit Withdrawal Balance Date',
            re.IGNORECASE
        )

        for page in pdf.pages:
            page_num += 1
            text = page.extract_text() or ''
            lines = text.split('\n')

            i = 0
            while i < len(lines):
                line = lines[i].strip()
                i += 1
                if not line:
                    continue

                # Check for end of transaction table
                if in_transaction_table:
                    for pattern in sentinel_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            in_transaction_table = False
                            break
                if not in_transaction_table:
                    continue

                # Skip page headers/footers
                if re.search(r'Page\s+\d+\s+of\s+\d+', line, re.IGNORECASE):
                    continue
                if re.search(r'^MR|MS|MRS\.?\s+[A-Z]', line) and 'Page' in line:
                    continue
                # Skip any line that looks like the column header
                if header_pattern.search(line):
                    continue
                # Skip any line that contains the unwanted phrase (even if partial)
                if unwanted_phrase.search(line):
                    continue

                # Special handling for BALANCE FORWARD line
                if 'BALANCE FORWARD' in line:
                    match = re.match(
                        r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+BALANCE\s+FORWARD\s+([\d,]+\.\d{2})',
                        line
                    )
                    if match:
                        date_str = match.group(1)
                        value_date_str = match.group(2)
                        balance_str = match.group(3)
                        date = parse_indian_date(date_str)
                        value_date = parse_indian_date(value_date_str)
                        balance = clean_amount(balance_str)
                        previous_balance = balance
                        transactions.append({
                            'date': date,
                            'value_date': value_date,
                            'description': 'BALANCE FORWARD',
                            'cheque': '',
                            'deposit': 0.0,
                            'withdrawal': 0.0,
                            'balance': balance,
                            'page_no': page_num
                        })
                    continue

                # Try to match a line that starts with a date (dd MMM yyyy)
                date_match = re.match(r'^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', line)
                if not date_match:
                    # This line might be continuation of previous description,
                    # but only if we are still in transaction table.
                    if in_transaction_table and transactions:
                        # Append to last transaction's description
                        transactions[-1]['description'] += ' ' + line
                    continue

                # Found a transaction start line
                date_str = date_match.group(1)
                remaining = line[len(date_str):].strip()

                # Extract value date (another date)
                value_date_match = re.match(r'^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', remaining)
                if value_date_match:
                    value_date_str = value_date_match.group(1)
                    remaining = remaining[len(value_date_str):].strip()
                else:
                    value_date_str = ''

                # Find all amounts at the end
                amounts = []
                temp = remaining
                while True:
                    match = re.search(r'(-?[\d,]+\.\d{2})$', temp)
                    if not match:
                        break
                    amounts.insert(0, match.group(1))
                    temp = temp[:match.start()].strip()

                if not amounts:
                    continue
                balance_str = amounts[-1]
                amounts = amounts[:-1]

                deposit = 0.0
                withdrawal = 0.0

                if len(amounts) == 2:
                    deposit = clean_amount(amounts[0])
                    withdrawal = clean_amount(amounts[1])
                elif len(amounts) == 1:
                    if previous_balance is not None:
                        current_balance = clean_amount(balance_str)
                        diff = current_balance - previous_balance
                        if diff > 0:
                            deposit = clean_amount(amounts[0])
                        else:
                            withdrawal = clean_amount(amounts[0])
                    else:
                        if re.search(r'UPI|NEFT|RTGS|IMPS|CREDIT|DEPOSIT', remaining, re.IGNORECASE):
                            deposit = clean_amount(amounts[0])
                        else:
                            withdrawal = clean_amount(amounts[0])

                remaining_for_text = temp
                cheque_match = re.search(r'\b([A-Z0-9]{10,})\b', remaining_for_text)
                if cheque_match:
                    cheque = cheque_match.group(1)
                    remaining_for_text = remaining_for_text.replace(cheque, '').strip()
                else:
                    cheque = ''

                description = re.sub(r'\s+', ' ', remaining_for_text).strip()
                # Remove any leftover unwanted phrase from description
                description = unwanted_phrase.sub('', description).strip()
                # Also remove any stray "Date Value Date ..." if present
                description = re.sub(r'Date\s+Value Date\s+Description\s+Cheque\s+Deposit\s+Withdrawal\s+Balance', '', description, flags=re.IGNORECASE).strip()

                date = parse_indian_date(date_str)
                value_date = parse_indian_date(value_date_str) if value_date_str else ''
                balance = clean_amount(balance_str)
                previous_balance = balance

                transactions.append({
                    'date': date,
                    'value_date': value_date,
                    'description': description,
                    'cheque': cheque,
                    'deposit': deposit,
                    'withdrawal': withdrawal,
                    'balance': balance,
                    'page_no': page_num
                })

    # Set period from transaction dates
    if transactions:
        first, last = get_first_last_dates(transactions, 'date')
        metadata['from_date'] = first
        metadata['to_date'] = last

    return metadata, transactions


def extract_account_holder_scb(text):
    """Extract account holder name from SCB statement (works for corporate and individual)."""
    lines = text.split('\n')
    # Look for line containing account holder name – usually after the first few lines
    # and before "BRANCH ADDRESS" or "ACCOUNT NO"
    for i, line in enumerate(lines):
        if 'M/S' in line or 'PRIVATE LIMITED' in line or 'PVT' in line or 'LTD' in line:
            return line.strip()
        # For individuals, look for MR, MS, MRS (case-insensitive)
        if re.search(r'\b(MR|MS|MRS)\.?\s+[A-Z]', line, re.IGNORECASE):
            return line.strip()
    # Fallback: return first non-empty line that doesn't look like a header
    for line in lines:
        if line and not re.search(r'BRANCH|STATEMENT|ACCOUNT|PAGE', line, re.IGNORECASE):
            return line.strip()
    return ''

def extract_account_number_scb(text):
    """Extract account number from SCB statement."""
    match = re.search(r'ACCOUNT\s*NO\s*:?\s*([\d]+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ''

def extract_ifsc_code_scb(text):
    """Extract IFSC code from SCB statement."""
    match = re.search(r'IFSC\s*:?\s*([A-Z0-9]{11})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ''
