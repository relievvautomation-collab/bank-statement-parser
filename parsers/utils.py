import re
from datetime import datetime

def clean_amount(amount_str):
    """
    Convert Indian-format amount string (e.g. '14,643.28' or '-15,39,10,967.70') to float.
    Handles leading minus sign.
    """
    if not amount_str or amount_str == '':
        return 0.0
    # Remove commas, then convert
    cleaned = re.sub(r'[^\d.-]', '', str(amount_str))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def extract_ifsc_code(text):
    """
    Extract IFSC code from text.
    IFSC format: 4 letters + 0 + 6 alphanumeric (total 11 chars)
    """
    ifsc_pattern = r'\b([A-Z]{4}0[A-Z0-9]{6})\b'
    match = re.search(ifsc_pattern, text.upper())
    return match.group(1) if match else ''

def extract_account_holder(text, bank):
    """Extract account holder name from first page text."""
    if bank == 'SBI':
        # Personal: "Account Name : MS. VARSHATYAGI"
        match = re.search(r'Account\s*Name\s*:?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Corporate: "Name : FORTUNE MARKETING PVT.LTD."
        match = re.search(r'Name\s*:?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    elif bank == 'HDFC':
        # Format1: "M/S. HISTORIC AUCTIONS PVT LTD ..."
        match = re.search(r'M/?S\.?\s*([A-Za-z0-9\s&.,]+?)(?:\n|JOINT|Account)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Format2: "Fortune Marketing Private Limited" – extract line before "Customer ID"
        match = re.search(r'^([A-Za-z0-9\s&.,]+?)\s*\n\s*Customer\s+ID', text, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ''

def extract_account_number(text, bank):
    """Robust extraction of account number for SBI and HDFC."""
    if bank == 'SBI':
        patterns = [
            r'Account\s*Number\s*:?\s*([\d]+)',
            r'A/?c\s*No\.?\s*:?\s*([\d]+)',
            r'Account\s*No\.?\s*:?\s*([\d]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
    elif bank == 'HDFC':
        patterns = [
            r'Account\s*No\.?\s*:?\s*([\d]+)',
            r'Account\s*Number\s*:?\s*([\d]+)',
            r'A/?c\s*No\.?\s*:?\s*([\d]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
    return ''

def parse_indian_date(date_str):
    """Convert various date formats to DD/MM/YYYY."""
    date_str = date_str.strip()
    # Try dd/mm/yy
    match = re.match(r'(\d{2})/(\d{2})/(\d{2,4})', date_str)
    if match:
        d, m, y = match.groups()
        if len(y) == 2:
            y = '20' + y if int(y) < 50 else '19' + y
        return f"{d}/{m}/{y}"
    # Try dd/mm/yyyy with single digit day/month (e.g., 1/4/2025)
    match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if match:
        d, m, y = match.groups()
        return f"{int(d):02d}/{int(m):02d}/{y}"
    # Try dd Mon yyyy (e.g., 1 Apr 2025)
    match = re.match(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', date_str)
    if match:
        d, m, y = match.groups()
        month_map = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
                     'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'}
        m = month_map.get(m[:3].capitalize(), '01')
        return f"{int(d):02d}/{m}/{y}"
    return date_str

def get_first_last_dates(transactions, date_key):
    """Return (first_date, last_date) from list of transaction dicts using date_key."""
    dates = []
    for txn in transactions:
        d_str = txn.get(date_key, '')
        if d_str:
            d_std = parse_indian_date(d_str)
            dates.append(d_std)
    if not dates:
        return '', ''
    dates.sort(key=lambda d: datetime.strptime(d, '%d/%m/%Y'))
    return dates[0], dates[-1]
