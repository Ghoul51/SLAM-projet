"""Corrections automatiques (F9). Respecte RG01, RG06, RG07, RG10. Ne connaît pas Tkinter (§3.4.1).

Une correction ne démarre que sur demande de l'opérateur (RG01) : ce module ne décide jamais seul.
Chaque correction passe par `_executer`, qui impose le même déroulement :
  1. relire le contrôle : déjà conforme ? on le dit et on ne touche à rien (RG10) ;
  2. journaliser ce qu'on va faire (RG06) ;
  3. agir ;
  4. relire le contrôle avec la sonde : c'est ce résultat qui décide (RG06) ;
  5. journaliser le résultat et sa durée.
"""
import time
import winreg
from dataclasses import dataclass

from comparaison import CHROME_OUVRIR_LISTE, CONFORME, INDETERMINE, evaluer_controle
from powershell import ErreurPowerShell  # noqa: F401  (utilisé par les corrections PowerShell à venir)

SUCCES, ECHEC, ATTENTE = "Succès", "Échec", "En attente de prise en compte"
SESSION = "nouvelle ouverture de session nécessaire"
REDEMARRAGE = "redémarrage nécessaire"


@dataclass
class ResultatCorrection:
    statut: str            # SUCCES, ECHEC ou ATTENTE
    message: str           # message compréhensible pour le technicien
    motif: str = ""        # ATTENTE : redémarrage ou session ; ECHEC : raison
    relecture: object = None   # Resultat du contrôle relu après la correction


def _executer(identifiant, parametres, delai, journal, prevu, agir, attente="", complement=""):
    """Squelette commun des corrections (RG06, RG07, RG10). `agir` fait le geste et ne renvoie rien."""
    avant = evaluer_controle(identifiant, parametres, delai)
    if avant.etat == CONFORME:
        journal.info("%s : déjà conforme, aucune action.", identifiant)
        return ResultatCorrection(SUCCES, "Ce contrôle est déjà conforme : rien n'a été modifié.", relecture=avant)

    journal.info("%s : AVANT correction : %s", identifiant, prevu)
    debut = time.monotonic()
    try:
        agir()
    except (OSError, ErreurPowerShell) as erreur:
        journal.error("%s : ÉCHEC en %.1f s : %s", identifiant, time.monotonic() - debut, erreur)
        return ResultatCorrection(ECHEC, f"La correction a échoué : {erreur}", motif=str(erreur), relecture=avant)

    apres = evaluer_controle(identifiant, parametres, delai)   # RG06 : on relit, on ne suppose pas
    duree = time.monotonic() - debut
    journal.info("%s : APRÈS correction en %.1f s : relecture = %s (%s)", identifiant, duree, apres.etat, apres.message)

    if apres.etat == CONFORME:
        if attente:   # RG07 : la valeur est écrite, mais pas encore prise en compte
            journal.info("%s : EN ATTENTE de prise en compte : %s", identifiant, attente)
            message = f"Correction appliquée. En attente de prise en compte : {attente}."
            return ResultatCorrection(ATTENTE, message, motif=attente, relecture=apres)
        message = "Correction appliquée et vérifiée : le contrôle est conforme."
        return ResultatCorrection(SUCCES, f"{message} {complement}".strip(), relecture=apres)
    if apres.etat == INDETERMINE:
        return ResultatCorrection(
            ECHEC, f"La correction a été exécutée mais la relecture a échoué : {apres.message}",
            motif=apres.message, relecture=apres)
    return ResultatCorrection(
        ECHEC, f"La correction n'a pas eu l'effet attendu. {apres.message}", motif=apres.message, relecture=apres)


def _ecrire(racine, chemin, nom, valeur, type_valeur):
    """Écrit une valeur de registre ; crée la clé si elle n'existe pas. Relancer ne change rien (RG10)."""
    with winreg.CreateKeyEx(racine, chemin, 0, winreg.KEY_SET_VALUE) as cle:
        winreg.SetValueEx(cle, nom, 0, type_valeur, valeur)


# --- ENV_NUM_PAD : pavé numérique (ruche de l'utilisateur courant) ----------

def decrire_pave(p):
    etat = "activé" if p["attendu"] else "désactivé"
    return f"Le pavé numérique sera {etat} au démarrage, pour l'utilisateur courant.", SESSION


def corriger_pave(parametres, delai, journal):
    chemin = r"Control Panel\Keyboard"

    def agir():
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chemin, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as cle:
            try:
                actuel = int(winreg.QueryValueEx(cle, "InitialKeyboardIndicators")[0])
            except FileNotFoundError:
                actuel = 0
            # Le bit 2 est le pavé numérique ; les autres bits (verrouillage des majuscules...) restent intacts.
            nouveau = (actuel | 2) if parametres["attendu"] else (actuel & ~2)
            winreg.SetValueEx(cle, "InitialKeyboardIndicators", 0, winreg.REG_SZ, str(nouveau))

    prevu = f"HKCU\\{chemin} : InitialKeyboardIndicators, bit 2 = {parametres['attendu']}"
    return _executer("ENV_NUM_PAD", parametres, delai, journal, prevu, agir, attente=SESSION)


# --- ENV_HIDDEN_FILES : réglages de l'explorateur (ruche de l'utilisateur courant) ---

def decrire_explorateur(p):
    visibles = lambda v: "visibles" if v else "masqués"
    confirmation_ = "activée" if p["confirmation_suppression"] else "désactivée"
    texte = (f"Les extensions seront {visibles(p['extensions_visibles'])}, les fichiers cachés "
             f"{visibles(p['fichiers_caches_visibles'])}, et la confirmation de suppression sera {confirmation_}.")
    return texte, SESSION


def corriger_explorateur(parametres, delai, journal):
    avance = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
    explorateur = r"Software\Microsoft\Windows\CurrentVersion\Explorer"
    hkcu, dword = winreg.HKEY_CURRENT_USER, winreg.REG_DWORD

    def agir():
        _ecrire(hkcu, avance, "HideFileExt", 0 if parametres["extensions_visibles"] else 1, dword)
        _ecrire(hkcu, avance, "Hidden", 1 if parametres["fichiers_caches_visibles"] else 2, dword)
        _ecrire(hkcu, explorateur, "ConfirmFileDelete", 1 if parametres["confirmation_suppression"] else 0, dword)

    prevu = (f"HKCU : HideFileExt, Hidden, ConfirmFileDelete d'après le profil "
             f"({parametres['extensions_visibles']}, {parametres['fichiers_caches_visibles']}, "
             f"{parametres['confirmation_suppression']})")
    return _executer("ENV_HIDDEN_FILES", parametres, delai, journal, prevu, agir, attente=SESSION)


# --- ENV_CHROME_START : page de démarrage de Chrome par stratégie (ruche de la machine) ---

def decrire_chrome(p):
    return f"La page de démarrage de Chrome sera imposée par stratégie : {p['url']}", ""


def corriger_chrome(parametres, delai, journal):
    politique = r"SOFTWARE\Policies\Google\Chrome"
    hklm = winreg.HKEY_LOCAL_MACHINE

    def agir():   # écrire dans HKLM exige les droits d'administrateur
        _ecrire(hklm, politique, "RestoreOnStartup", CHROME_OUVRIR_LISTE, winreg.REG_DWORD)
        _ecrire(hklm, politique + r"\RestoreOnStartupURLs", "1", parametres["url"], winreg.REG_SZ)

    prevu = f"HKLM\\{politique} : RestoreOnStartup = {CHROME_OUVRIR_LISTE}, adresse = {parametres['url']}"
    return _executer("ENV_CHROME_START", parametres, delai, journal, prevu, agir,
                     complement="Relancer Chrome pour qu'il applique la stratégie.")


# Table des corrections : identifiant du catalogue -> (description pour la confirmation, correction)
CORRECTIONS = {
    "ENV_NUM_PAD": (decrire_pave, corriger_pave),
    "ENV_HIDDEN_FILES": (decrire_explorateur, corriger_explorateur),
    "ENV_CHROME_START": (decrire_chrome, corriger_chrome),
}


def confirmation(identifiant, parametres):
    """Texte en français de la fenêtre de confirmation (RG01, F8) : ce qui va être fait et ses suites."""
    decrire, _ = CORRECTIONS[identifiant]
    texte, suite = decrire(parametres)
    return f"{texte}\n\nSuite : {suite}." if suite else texte


def appliquer(identifiant, parametres, delai, journal):
    """Lance la correction. À n'appeler qu'après la confirmation de l'opérateur (RG01)."""
    _, correction = CORRECTIONS[identifiant]
    return correction(parametres, delai, journal)