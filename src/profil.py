"""Chargement et validation du profil de référence (F1, RG05, section 3.3.1)."""
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

# Seuls ces 3 contrôles peuvent être désactivés (section 3.3.1)
CONTROLES_DESACTIVABLES = {"MAT_SMART", "MAT_TYPE_SUPPORT", "SYS_TURN_ON"}

TEXTE, REGEX, NOMBRE, ENTIER, BOOLEEN = "texte", "regex", "nombre", "entier", "booleen"
LISTE_TEXTE, SERVICES, LOGICIELS = "liste_texte", "services", "logiciels"

# Format du profil : domaine -> contrôle -> clé -> type attendu
FORMAT = {
    "identite": {
        "IDENT_MACHINE": {"prefixe": TEXTE, "modele": REGEX},
        "IDENT_COMPTE_ADMIN": {"compte": TEXTE},
        "IDENT_COMPTE_LOCAL": {"comptes_autorises": LISTE_TEXTE},
    },
    "materiel": {
        "MAT_RAM": {"minimum_go": NOMBRE},
        "MAT_STOCKAGE": {"libre_minimum_go": NOMBRE},
        "MAT_SMART": {"sante_attendue": TEXTE},
        "MAT_TYPE_SUPPORT": {"type_attendu": TEXTE},
    },
    "systeme": {
        "SYS_OS_VERSION": {"edition": TEXTE, "version": TEXTE},
        "SYS_TURN_ON": {"activation_exigee": BOOLEEN},
        "SYS_SERV_TIME": {"serveur": TEXTE, "ecart_max_secondes": NOMBRE},
        "SYS_IP": {"dhcp": BOOLEEN},
    },
    "securite": {
        "SEC_ANTIVIRUS": {"produit": TEXTE},
        "SEC_SIGN": {"age_max_jours": ENTIER},
        "SEC_BITLOCKER": {"exige": BOOLEEN},
        "SEC_PROFILS": {"profils": LISTE_TEXTE},
        "SEC_MAJ_WINDOWS": {"service": TEXTE},
        "SEC_MAJ": {"maximum": ENTIER},
    },
    "logiciels": {
        "LOG_WINGET": {"requis": LOGICIELS},
        "LOG_FORB": {"interdits": LISTE_TEXTE},
        "LOG_START": {"services": SERVICES},
    },
    "environnement": {
        "ENV_NUM_PAD": {"attendu": BOOLEEN},
        "ENV_HIDDEN_FILES": {
            "extensions_visibles": BOOLEEN,
            "fichiers_caches_visibles": BOOLEEN,
            "confirmation_suppression": BOOLEEN,
        },
        "ENV_CHROME_START": {"url": TEXTE},
        "ENV_PRINT": {"nom": TEXTE},
    },
    "journaux": {
        "JRN_CRITICAL_EVENT": {"maximum_24h": ENTIER},
    },
}

# Clés facultatives : contrôle -> clé -> type attendu
FACULTATIVES = {"ENV_PRINT": {"chemin_reseau": TEXTE}}


class ErreurProfil(Exception):
    """Erreur à afficher en clair, sans trace Python (RG05)."""


@dataclass
class Profil:
    chemin: Path
    nom: str
    version: str
    date_validation: str
    controles: dict  # identifiant du catalogue -> paramètres (dont "actif")
    empreinte: str


def calculer_empreinte(chemin: Path) -> str:
    """Empreinte SHA-256 du fichier de profil (section 3.3.11)."""
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def lister_profils(dossier: Path) -> list:
    """Les fichiers de profil du dossier configuré."""
    return sorted(dossier.glob("*.json"))


def _verifier_valeur(valeur, type_attendu):
    """Renvoie None si la valeur est correcte, sinon le problème en clair."""
    if type_attendu == TEXTE:
        if not isinstance(valeur, str) or not valeur.strip():
            return "doit être un texte non vide"
        if valeur == "A_COMPLETER":
            return "vaut encore « A_COMPLETER » : le profil n'est pas terminé"
    elif type_attendu == REGEX:
        if not isinstance(valeur, str) or not valeur:
            return "doit être un texte non vide"
        try:
            re.compile(valeur)
        except re.error as erreur:
            return f"expression régulière invalide ({erreur})"
    elif type_attendu == NOMBRE:
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            return "doit être un nombre"
        if valeur < 0:
            return "ne peut pas être négatif"
    elif type_attendu == ENTIER:
        if isinstance(valeur, bool) or not isinstance(valeur, int):
            return "doit être un nombre entier"
        if valeur < 0:
            return "ne peut pas être négatif"
    elif type_attendu == BOOLEEN:
        if not isinstance(valeur, bool):
            return "doit valoir true ou false"
    elif type_attendu == LISTE_TEXTE:
        if not isinstance(valeur, list) or not all(isinstance(v, str) and v.strip() for v in valeur):
            return "doit être une liste de textes non vides"
    elif type_attendu == LOGICIELS:
        return _verifier_liste_objets(valeur, ("nom", "winget_id"))
    elif type_attendu == SERVICES:
        return _verifier_liste_objets(valeur, ("nom", "etat", "demarrage"))
    return None


def _verifier_liste_objets(valeur, cles):
    if not isinstance(valeur, list) or not valeur:
        return "doit être une liste non vide"
    for element in valeur:
        if not isinstance(element, dict):
            return "chaque élément doit être un objet"
        for cle in cles:
            probleme = _verifier_valeur(element.get(cle), TEXTE)
            if probleme:
                return f"élément {element} : la clé « {cle} » {probleme}"
    return None


def _valider(donnees, chemin: Path):
    def erreur(cle, probleme):
        raise ErreurProfil(f"{chemin} : clé « {cle} » : {probleme}")

    if not isinstance(donnees, dict):
        raise ErreurProfil(f"{chemin} : le profil doit être un objet JSON.")

    for cle in ("nom", "version", "date_validation"):
        if cle not in donnees:
            erreur(cle, "clé obligatoire absente")
        probleme = _verifier_valeur(donnees[cle], TEXTE)
        if probleme:
            erreur(cle, probleme)

    for domaine, controles in FORMAT.items():
        bloc = donnees.get(domaine)
        if not isinstance(bloc, dict):
            erreur(domaine, "bloc absent ou invalide")
        for identifiant, cles in controles.items():
            chemin_cle = f"{domaine}.{identifiant}"
            parametres = bloc.get(identifiant)
            if not isinstance(parametres, dict):
                erreur(chemin_cle, "contrôle absent")

            actif = parametres.get("actif")
            if not isinstance(actif, bool):
                erreur(f"{chemin_cle}.actif", "doit valoir true ou false")
            if not actif and identifiant not in CONTROLES_DESACTIVABLES:
                erreur(f"{chemin_cle}.actif", "contrôle obligatoire : il ne peut pas être désactivé")

            for cle, type_attendu in cles.items():
                if cle not in parametres:
                    erreur(f"{chemin_cle}.{cle}", "clé obligatoire absente")
                probleme = _verifier_valeur(parametres[cle], type_attendu)
                if probleme:
                    erreur(f"{chemin_cle}.{cle}", probleme)

            for cle, type_attendu in FACULTATIVES.get(identifiant, {}).items():
                if cle in parametres:
                    probleme = _verifier_valeur(parametres[cle], type_attendu)
                    if probleme:
                        erreur(f"{chemin_cle}.{cle}", probleme)


def charger_profil(chemin: Path) -> Profil:
    if not chemin.is_file():
        raise ErreurProfil(f"Profil introuvable : {chemin}")
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erreur:
        raise ErreurProfil(
            f"{chemin} : erreur de syntaxe JSON, ligne {erreur.lineno}, colonne {erreur.colno} : {erreur.msg}"
        )
    except UnicodeDecodeError:
        raise ErreurProfil(f"{chemin} : fichier illisible (encodage UTF-8 attendu).")

    _valider(donnees, chemin)

    controles = {
        identifiant: donnees[domaine][identifiant]
        for domaine, ids in FORMAT.items()
        for identifiant in ids
    }
    return Profil(
        chemin=chemin,
        nom=donnees["nom"],
        version=donnees["version"],
        date_validation=donnees["date_validation"],
        controles=controles,
        empreinte=calculer_empreinte(chemin),
    )