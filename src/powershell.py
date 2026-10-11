"""Fonction unique d'appel à PowerShell (sections 3.3.4 et 3.4.1)."""
import json
import subprocess


class ErreurPowerShell(Exception):
    """Commande en échec, délai dépassé ou sortie illisible."""


def executer_powershell(commande: str, delai_secondes: int):
    """Exécute une commande PowerShell et renvoie son résultat décodé depuis le JSON.

    Renvoie None si la commande ne produit aucune sortie.
    """
    script = (
        # Protection 3 : encodage de sortie forcé en UTF-8
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$ErrorActionPreference = 'Stop'; "
        # Protection 4 : résultat structuré en JSON
        "& { " + commande + " } | ConvertTo-Json -Depth 5 -Compress"
    )
    try:
        resultat = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            # Protection 2 : délai maximal
            timeout=delai_secondes,
            # Protection 1 : aucune fenêtre de console
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        raise ErreurPowerShell(f"Délai dépassé ({delai_secondes} s) : la commande n'a pas répondu.")
    except FileNotFoundError:
        raise ErreurPowerShell("PowerShell est introuvable sur ce poste.")

    if resultat.returncode != 0:
        message = resultat.stderr.strip() or "erreur inconnue"
        raise ErreurPowerShell(f"PowerShell a renvoyé une erreur : {message}")

    sortie = resultat.stdout.strip()
    if not sortie:
        return None
    try:
        return json.loads(sortie)
    except json.JSONDecodeError:
        raise ErreurPowerShell("Sortie PowerShell illisible (JSON attendu).")