import subprocess
from pathlib import Path

def run_analysis(project_dir="."):
    python_files = [
        str(p) for p in Path(project_dir).rglob("*.py") 
        if "venv" not in p.parts and not p.name.startswith(".")
    ]

    if not python_files:
        print("Nie znaleziono plików Pythona do analizy.")
        return
    else:
        print(f"Znaleziono {len(python_files)} plikow Pythona do analizy.")
    
    pylint_cmd = [
        "pylint", 
        "--msg-template='{path}:{line}: [{msg_id}] {msg}'",
        "--exit-zero"
    ] + python_files
    
    with open("pylint-report.txt", "w") as f:
        subprocess.run(pylint_cmd, stdout=f)
    
    print("Report saved: pylint-report.txt")

if __name__ == "__main__":
    run_analysis()
