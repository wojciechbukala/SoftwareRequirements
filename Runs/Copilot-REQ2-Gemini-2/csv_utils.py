import csv
import os

def read_csv(file_path: str, expected_headers: list) -> list[dict]:
    """
    Reads a CSV file, verifies headers, and returns its content as a list of dictionaries.
    """
    data = []
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # Verify headers
        if reader.fieldnames != expected_headers:
            raise ValueError(f"CSV file {file_path} has incorrect headers. Expected {expected_headers}, got {reader.fieldnames}")

        for row in reader:
            data.append(row)
    return data

def write_csv(file_path: str, headers: list, data: list[dict]):
    """
    Writes a list of dictionaries to a CSV file with the specified headers.
    """
    with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
