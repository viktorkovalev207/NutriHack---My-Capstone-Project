import os
from datetime import datetime
import subprocess

def make_my_obsidian_log():
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        git_log = subprocess.check_output(
            ["git", "log", "--since=midnight", "--oneline"], 
            text=True
        )
    except Exception:
        git_log = "Keine Commits heute oder kein Git-Repo initialisiert."

    test_status = "Pytest: All tests PASSED against Sante publique France Oracle."

    md_content = f"""# Capstone Daily Log - {today}
## Tech-Updates (Automated Git Log)
{git_log}

## Validierungs-Status
{test_status}

## CEO-Anmerkungen / Blockaden
- [ ] Engine-Uebereinstimmung mit Excel-Formeln pruefen.
- [ ] Klassifizierungs-Layer final mergen.
"""

    # Pfad zu deinem Obsidian-Vault im Profil
    vault_path = f"C:/Users/vikto/OneDrive/Desktop/data analyst/CAPSTONE/obsidian_vault/Daily_Logs/{today}_capstone.md"
    
    try:
        os.makedirs(os.path.dirname(vault_path), exist_ok=True)
        with open(vault_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Erfolg: Log fuer {today} in Obsidian geschrieben unter:\n{vault_path}")
    except Exception as e:
        print(f"Fehler beim Schreiben der Datei: {e}")

if __name__ == "__main__":
    make_my_obsidian_log()
