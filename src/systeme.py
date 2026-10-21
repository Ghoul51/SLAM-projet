"""Actions sur le système Windows, hors interface (§3.4.1)."""
import os
from pathlib import Path


def ouvrir_dossier(dossier: Path):
    """Ouvre le dossier dans l'explorateur ; le crée s'il n'existe pas encore."""
    dossier.mkdir(parents=True, exist_ok=True)
    os.startfile(dossier)