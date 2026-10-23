"""Journal applicatif : 1 fichier horodaté par session, dans le dossier configuré (§3.2, §3.4.1)."""
import logging
from datetime import datetime
from pathlib import Path


def creer_journal(dossier: Path) -> logging.Logger:
    """Crée le fichier de journal de la session et renvoie le journal (bibliothèque standard `logging`).

    Lève OSError si le dossier ne peut pas être créé ou écrit : l'appelant décide quoi faire.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    nom = datetime.now().strftime("journal_%Y-%m-%d_%H%M%S.log")
    gestionnaire = logging.FileHandler(dossier / nom, encoding="utf-8")
    gestionnaire.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    journal = logging.getLogger("recette")
    journal.setLevel(logging.INFO)
    for ancien in list(journal.handlers):   # une seule session à la fois
        journal.removeHandler(ancien)
        ancien.close()
    journal.addHandler(gestionnaire)
    return journal