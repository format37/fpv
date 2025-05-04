import csv
import os

# File paths
base_dir = os.path.dirname(__file__)
default_params_path = os.path.join(base_dir, 'default_parameters.csv')
params_path = os.path.join(base_dir, 'parameters.csv')
output_path = os.path.join(base_dir, 'full_params.csv')

def read_params(file_path):
    params = {}
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            params[row['param_id']] = row
    return params

def main():
    # Read both files
    default_params = read_params(default_params_path)
    params = read_params(params_path)

    # Prepare merged data
    merged = []
    for param_id in sorted(default_params):
        default_row = default_params[param_id]
        actual_row = params.get(param_id, default_row)
        merged.append({
            'param_id': param_id,
            'default': default_row['value'],
            'actual': actual_row['value'],
            'type': default_row['type']
        })

    # Drop unchanged values
    merged = [row for row in merged if row['default'] != row['actual']]

    # Write to full_params.csv
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['param_id', 'default', 'actual', 'type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in merged:
            writer.writerow(row)
    print(f"Merged parameters written to {output_path}")

if __name__ == '__main__':
    main() 