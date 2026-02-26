import pdfplumber
import re
from .utils import clean_amount, extract_account_holder, extract_account_number, extract_ifsc_code, get_first_last_dates, parse_indian_date

def parse_sbi(pdf_path, format_type):
    """
    Unified SBI parser for both corporate (8 columns) and personal (7 columns) formats.
    """
    metadata = {
        'bank_name': 'SBI',
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
        metadata['account_holder'] = extract_account_holder(first_text, 'SBI')
        metadata['account_number'] = extract_account_number(first_text, 'SBI')
        metadata['ifsc_code'] = extract_ifsc_code(first_text)

        for page in pdf.pages:
            page_num += 1
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 7:
                        continue
                    row = [str(cell).strip() if cell else '' for cell in row]

                    # Check if first column is a date
                    date_match = re.match(r'(\d{1,2}[/\s][A-Za-z0-9/]+|\d{2}/\d{2}/\d{4})', row[0])
                    if date_match:
                        txn_date = parse_indian_date(row[0])
                        if format_type == 'corporate' and len(row) >= 8:
                            value_date = parse_indian_date(row[1]) if len(row)>1 and row[1] else ''
                            description = row[2] if len(row)>2 else ''
                            ref_no = row[3] if len(row)>3 else ''
                            debit = clean_amount(row[5]) if len(row)>5 else 0.0
                            credit = clean_amount(row[6]) if len(row)>6 else 0.0
                            balance = clean_amount(row[7]) if len(row)>7 else 0.0
                        else:
                            value_date = parse_indian_date(row[1]) if len(row)>1 and row[1] else ''
                            description = row[2] if len(row)>2 else ''
                            ref_no = row[3] if len(row)>3 else ''
                            debit = clean_amount(row[4]) if len(row)>4 else 0.0
                            credit = clean_amount(row[5]) if len(row)>5 else 0.0
                            balance = clean_amount(row[6]) if len(row)>6 else 0.0

                        transactions.append({
                            'txn_date': txn_date,
                            'value_date': value_date,
                            'description': description,
                            'ref_no': ref_no,
                            'debit': debit,
                            'credit': credit,
                            'balance': balance,
                            'page_no': page_num
                        })

    # Merge multi-line descriptions
    merged = []
    skip_next = False
    for i in range(len(transactions)):
        if skip_next:
            skip_next = False
            continue
        curr = transactions[i]
        if i+1 < len(transactions) and not re.match(r'\d{2}/\d{2}/\d{4}', transactions[i+1]['txn_date']):
            curr['description'] += ' ' + transactions[i+1]['description']
            skip_next = True
        merged.append(curr)

    # Set period from transaction dates
    if merged:
        first, last = get_first_last_dates(merged, 'txn_date')
        metadata['from_date'] = first
        metadata['to_date'] = last

    return metadata, merged

def parse_sbi_corporate(pdf_path):
    return parse_sbi(pdf_path, 'corporate')

def parse_sbi_personal(pdf_path):
    return parse_sbi(pdf_path, 'personal')
