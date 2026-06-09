import subprocess
from pathlib import Path

def find_package_dirs(project_dir):
    """Detect directories with pip-installed packages by presence of *.dist-info folders."""
    pkg_dirs = set()
    for dist_info in Path(project_dir).rglob("*.dist-info"):
        if dist_info.is_dir():
            pkg_dirs.add(dist_info.parent)
    return pkg_dirs

def run_analysis(project_dir="."):
    pkg_dirs = find_package_dirs(project_dir)
    python_files = [
        str(p) for p in Path(project_dir).rglob("*.py")
        if not p.name.startswith(".")
        and not any(pkg in p.parents for pkg in pkg_dirs)
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
