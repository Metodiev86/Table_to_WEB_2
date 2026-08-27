# main.py

import subprocess

scripts = [
    "Аванс за Стока_xlsx.py",
    
]

for script in scripts:
    result = subprocess.run(["python", script])

    if result.returncode != 0:
        print(f"Error in {script}")
        break
    input()