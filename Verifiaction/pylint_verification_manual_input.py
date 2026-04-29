import subprocess
import os
import sys
import shutil

def analyze_specific_files(file_list):
    processed_files = []
    
    for file_path in file_list:
        if not os.path.exists(file_path):
            print(f"File: {file_path} does not exist")
            continue

        if not file_path.endswith(".py"):
            temp_name = f"{file_path}.py"
            shutil.copy2(file_path, temp_name)
            processed_files.append(temp_name)
        else:
            processed_files.append(file_path)

    if not processed_files:
        print("No files to analyze.")
        return


    print(f"--- Analysing {len(processed_files)} files ---")
    pylint_cmd = [
        "pylint", 
        "--msg-template='{path}:{line}: [{msg_id}] {msg}'",
        "--exit-zero"
    ] + processed_files
    
    with open("pylint-report.txt", "w") as f:
        subprocess.run(pylint_cmd, stdout=f)
    
    print("Report saved: pylint-report.txt")

if __name__ == "__main__":
    # Przyjmuje pliki jako argumenty wywołania: python script.py plik1 plik2 plik3
    analyze_specific_files(sys.argv[1:])