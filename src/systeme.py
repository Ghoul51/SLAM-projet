"""Actions et lectures sur le système Windows, hors interface (§3.4.1)."""
import os
from pathlib import Path

from powershell import ErreurPowerShell, executer_powershell

NON_DISPONIBLE = "non disponible"

# Identité du poste pour le procès-verbal (§3.3.11) : nom, modèle, numéro de série, adresse MAC.
# Win32_ComputerSystem, Win32_BIOS et Get-NetAdapter sont des noms Windows, pas des valeurs du profil (RG04).
COMMANDE_IDENTITE = (
    "$cs = Get-CimInstance Win32_ComputerSystem; "
    "$bios = Get-CimInstance Win32_BIOS; "
    "$carte = Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object Status -eq 'Up' | Select-Object -First 1; "
    "if (-not $carte) { $carte = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object Status -eq 'Up' | Select-Object -First 1 }; "
    "[pscustomobject]@{ nom = $env:COMPUTERNAME; modele = $cs.Model; serie = $bios.SerialNumber; mac = $carte.MacAddress }"
)


def ouvrir_dossier(dossier: Path):
    """Ouvre le dossier dans l'explorateur ; le crée s'il n'existe pas encore."""
    dossier.mkdir(parents=True, exist_ok=True)
    os.startfile(dossier)


def ouvrir_fichier(chemin: Path):
    """Ouvre un fichier avec le programme associé par Windows (le PDF dans le lecteur PDF)."""
    os.startfile(chemin)


def lire_identite_poste(delai, journal=None):
    """Renvoie {nom, modele, serie, mac}. Une valeur illisible devient « non disponible » : le PV doit pouvoir être édité."""
    try:
        valeur = executer_powershell(COMMANDE_IDENTITE, delai)
    except ErreurPowerShell as erreur:
        if journal:
            journal.warning("identité du poste illisible : %s", str(erreur).splitlines()[0])
        valeur = None
    if not isinstance(valeur, dict):
        valeur = {}
    return {cle: (str(valeur.get(cle) or "").strip() or NON_DISPONIBLE) for cle in ("nom", "modele", "serie", "mac")}