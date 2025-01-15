import json
from pathlib import Path

def initialize_counter_file():
    default_data = {
        'quote_number': 999,
        'invoice_number': 999,
        'deleted_numbers': []
    }
    with open('counter.json', 'w') as f:
        json.dump(default_data, f)

def get_next_quote_number():
    try:
        with open('counter.json', 'r') as f:
            data = json.load(f)
            current_number = data.get('quote_number', 999)
            deleted_numbers = data.get('deleted_numbers', [])
    except (FileNotFoundError, json.JSONDecodeError):
        initialize_counter_file()
        current_number = 999
        deleted_numbers = []
    
    if deleted_numbers:
        new_number = deleted_numbers.pop(0)
    else:
        new_number = current_number + 1
    
    with open('counter.json', 'w') as f:
        json.dump({
            'quote_number': new_number,
            'invoice_number': data.get('invoice_number', 999),
            'deleted_numbers': deleted_numbers
        }, f)
    
    return f"{new_number:04d}"

def get_next_invoice_number():
    try:
        with open('counter.json', 'r') as f:
            data = json.load(f)
            current_invoice = data.get('invoice_number', 999)
            deleted_numbers = data.get('deleted_numbers', [])
    except (FileNotFoundError, json.JSONDecodeError):
        initialize_counter_file()
        current_invoice = 999
        deleted_numbers = []
        data = {'quote_number': 999, 'invoice_number': 999, 'deleted_numbers': []}

    new_number = current_invoice + 1
    
    with open('counter.json', 'w') as f:
        json.dump({
            'quote_number': data.get('quote_number', 999),
            'invoice_number': new_number,
            'deleted_numbers': deleted_numbers
        }, f)
    
    return f"{new_number:04d}"