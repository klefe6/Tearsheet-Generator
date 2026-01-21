'''
Blue Whale Data Update Helper
Simple script to add new monthly data to blue_whale_data.csv
'''
import csv
import os
from datetime import datetime

def add_monthly_data():
    csv_file = 'blue_whale_data.csv'
    
    if not os.path.exists(csv_file):
        print('âŒ Error: blue_whale_data.csv not found!')
        print('   Please ensure the CSV file exists in the same directory.')
        return
    
    print('=' * 60)
    print('   BLUE WHALE MONTHLY DATA ENTRY')
    print('=' * 60)
    print('\nPaste the new month row from the website.')
    print('Example format:')
    print('2025	10	84080202.20	83722106.57	102691.39	0.12	-460787.02	...	0.86')
    print('\nOr enter data manually (comma or tab separated)')
    print('-' * 60)
    
    user_input = input('\nEnter new month data: ').strip()
    
    if not user_input:
        print('âŒ No data entered. Exiting.')
        return
    
    # Parse input - handle both tabs and commas
    if '\t' in user_input:
        parts = user_input.split('\t')
    else:
        parts = user_input.split(',')
    
    # Clean up parts
    parts = [p.strip() for p in parts if p.strip()]
    
    # Extract required fields (year, month, starting_money, net_liquidating, pnl, pl_percent, actual_ror)
    if len(parts) < 7:
        print(f'âŒ Error: Need at least 7 fields, got {len(parts)}')
        print('   Required: Year, Month, Starting Money, Net Liquidating, P&L, PL%, Actual ROR%')
        return
    
    try:
        year = parts[0]
        month = parts[1]
        starting_money = parts[2].replace(',', '')  # Remove commas from numbers
        net_liquidating = parts[3].replace(',', '')
        pnl = parts[4].replace(',', '')
        pl_percent = parts[5]
        
        # Actual ROR might be in different positions depending on copy/paste
        # Try to find it in the last few fields
        actual_ror = None
        for i in range(len(parts)-1, max(5, len(parts)-5), -1):
            try:
                val = float(parts[i].replace(',', ''))
                if -50 < val < 50:  # ROR is usually a reasonable percentage
                    actual_ror = parts[i]
                    break
            except:
                continue
        
        if actual_ror is None:
            actual_ror = input('Enter Actual ROR % (last column): ').strip()
        
        new_row = [year, month, starting_money, net_liquidating, pnl, pl_percent, actual_ror]
        
        print('\n' + '=' * 60)
        print('   PREVIEW NEW ENTRY')
        print('=' * 60)
        print(f'Year:             {year}')
        print(f'Month:            {month}')
        print(f'Starting Money:   ')
        print(f'Net Liquidating:  ')
        print(f'P&L:              ')
        print(f'PL Percent:       {pl_percent}%')
        print(f'Actual ROR:       {actual_ror}%')
        print('=' * 60)
        
        confirm = input('\nAdd this entry to the CSV? (yes/no): ').strip().lower()
        
        if confirm not in ['yes', 'y']:
            print('âŒ Cancelled. No changes made.')
            return
        
        # Append to CSV
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(new_row)
        
        print(f'\nâœ… Successfully added {year}-{month:0>2} to blue_whale_data.csv')
        print(f'ðŸ“… Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print('\nðŸš€ Restart yq_ts.py to see the updated tearsheet!')
        
    except Exception as e:
        print(f'\nâŒ Error processing data: {e}')
        print('   Please check the format and try again.')

if __name__ == '__main__':
    add_monthly_data()
