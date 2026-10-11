"""Chargement du fichier de configuration recette.ini (section 3.3.2, F2)."""
import configparser
import sys
from dataclasses import dataclass
from pathlib import Path

NOM_FICHIER_CONFIG = "recette.ini"

# Clés obligatoires du fichier : (section, clé)
CLES_OBLIGATOIRES = [
    ("dossiers", "profils"),
    ("dossiers", "pv"),
    ("dossiers", "journal"),
    ("bitlocker", "cles_recuperation"),
    ("operateur", "defaut"),
    ("commandes", "delai_max_secondes"),
]


class ErreurConfiguration(Exception):
    """Erreur à afficher en clair à l'utilisateur, sans trace Python."""


@dataclass
class Configuration:
    dossier_application: Path
    dossier_profils: Path
    dossier_pv: Path
    dossier_journal: Path
    cles_bitlocker: str
    operateur_defaut: str
    delai_max_secondes: int


def dossier_application() -> Path:
    """Dossier de l'exécutable (PyInstaller) ou racine du projet (script)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def charger_configuration() -> Configuration:
    base = dossier_application()
    chemin = base / NOM_FICHIER_CONFIG

    if not chemin.is_file():
        raise ErreurConfiguration(f"Fichier de configuration introuvable : {chemin}")

    lecteur = configparser.ConfigParser()
    try:
        lecteur.read(chemin, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError) as erreur:
        raise ErreurConfiguration(f"Fichier de configuration illisible : {chemin}\n{erreur}")

    for section, cle in CLES_OBLIGATOIRES:
        if not lecteur.has_option(section, cle) or not lecteur.get(section, cle).strip():
            raise ErreurConfiguration(
                f"{chemin} : la clé « {cle} » de la section [{section}] est absente ou vide."
            )

    try:
        delai = int(lecteur.get("commandes", "delai_max_secondes"))
    except ValueError:
        raise ErreurConfiguration(f"{chemin} : « delai_max_secondes » doit être un nombre entier.")
    if delai <= 0:
        raise ErreurConfiguration(f"{chemin} : « delai_max_secondes » doit être supérieur à 0.")

    return Configuration(
        dossier_application=base,
        dossier_profils=base / lecteur.get("dossiers", "profils"),
        dossier_pv=base / lecteur.get("dossiers", "pv"),
        dossier_journal=base / lecteur.get("dossiers", "journal"),
        cles_bitlocker=lecteur.get("bitlocker", "cles_recuperation"),
        operateur_defaut=lecteur.get("operateur", "defaut"),
        delai_max_secondes=delai,
    )