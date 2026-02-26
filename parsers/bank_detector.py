import re
from .utils import extract_ifsc_code

def detect_bank_and_format(first_page_text):
    """
    Returns (bank_name, format_name)
    bank_name: 'SBI', 'HDFC', or 'SCB'
    format_name: for SBI -> 'corporate' or 'personal'
                 for HDFC -> 'format1' or 'format2'
                 for SCB -> 'standard'
    """
    # First, try to detect by IFSC code
    ifsc = extract_ifsc_code(first_page_text)
    if ifsc:
        bank_code = ifsc[:4].upper()
        if bank_code == 'SBIN':
            bank = 'SBI'
        elif bank_code == 'HDFC':
            bank = 'HDFC'
        elif bank_code == 'SCBL':
            bank = 'SCB'
        else:
            bank = None
    else:
        # Fallback to text detection
        text = first_page_text.upper()
        if 'STATE BANK OF INDIA' in text or 'SBIN' in text:
            bank = 'SBI'
        elif 'HDFC BANK' in text or 'HDFC' in text:
            bank = 'HDFC'
        elif 'STANDARD CHARTERED' in text or 'SCBL' in text:
            bank = 'SCB'
        else:
            return None, None

    # Determine format
    if bank == 'SBI':
        if 'CORPORATE' in first_page_text.upper() or 'LIMITED' in first_page_text.upper() or 'PVT' in first_page_text.upper() or 'OD AGST DEPOSITS' in first_page_text.upper():
            return 'SBI', 'corporate'
        else:
            return 'SBI', 'personal'
    elif bank == 'HDFC':
        if 'WITHDRAWAL AMT.' in first_page_text.upper() and 'DEPOSIT AMT.' in first_page_text.upper():
            return 'HDFC', 'format1'
        elif 'WITHDRAWALS' in first_page_text.upper() and 'DEPOSITS' in first_page_text.upper() and 'CLOSING BALANCE' in first_page_text.upper():
            return 'HDFC', 'format2'
        else:
            return 'HDFC', 'format1'
    elif bank == 'SCB':
        return 'SCB', 'standard'
    else:
        return None, None
