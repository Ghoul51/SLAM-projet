"""Moteur de comparaison : état attendu (profil) contre état constaté (sondes) — F5, RG02, RG03."""
import re
from dataclasses import dataclass

from catalogue import CATALOGUE, MAJEUR, BLOQUANT
from sondes import SONDES, ErreurSonde

CONFORME, ECART, INDETERMINE, NON_EVALUE = "Conforme", "Écart", "Indéterminé", "Non évalué"
V_CONFORME, V_RESERVES, V_NON_CONFORME = "Conforme", "Conforme avec réserves", "Non conforme"

# Valeur technique de la stratégie Chrome « ouvrir une liste d'adresses au démarrage »
CHROME_OUVRIR_LISTE = 4


@dataclass
class Resultat:
    """Résultat d'un contrôle pour une passe (section 3.2)."""
    identifiant: str
    attendu: str
    constate: str
    etat: str
    message: str


@dataclass
class Verdict:
    verdict: str
    motifs: list
    reserves: list


def _contient(attendu, texte):
    return attendu.lower() in texte.lower()


# --- Comparateurs : (paramètres du profil, valeur lue) -> (conforme ?, attendu, constaté) ---

def _machine(p, v):
    return re.search(p["modele"], v) is not None, f"nom conforme à {p['modele']}", v


def _compte_admin(p, v):
    constate = "absent" if not v["existe"] else ("présent et actif" if v["actif"] else "présent mais désactivé")
    return v["existe"] and v["actif"], f"{p['compte']} présent et actif", constate


def _comptes_locaux(p, v):
    autorises = {c.lower() for c in p["comptes_autorises"]}
    en_trop = [c for c in v if c.lower() not in autorises]
    return not en_trop, "comptes actifs : " + ", ".join(p["comptes_autorises"]), ", ".join(v) or "aucun"


def _seuil_min(cle, unite):
    def comparer(p, v):
        return v >= p[cle], f"≥ {p[cle]} {unite}", f"{v} {unite}"
    return comparer


def _seuil_max(cle, unite):
    def comparer(p, v):
        return v <= p[cle], f"≤ {p[cle]} {unite}", f"{v} {unite}"
    return comparer


def _liste_egale(cle):
    def comparer(p, v):
        return all(e == p[cle] for e in v), p[cle], ", ".join(v)
    return comparer


def _os(p, v):
    ok = _contient(p["edition"], v["edition"]) and v["version"] == p["version"]
    return ok, f"{p['edition']} (version {p['version']})", f"{v['edition']} (version {v['version']})"


def _activation(p, v):
    ok = v or not p["activation_exigee"]
    return ok, "activé" if p["activation_exigee"] else "activation non exigée", "activé" if v else "non activé"


def _heure(p, v):
    ok = _contient(p["serveur"], v["source"]) and v["ecart_secondes"] <= p["ecart_max_secondes"]
    return ok, f"{p['serveur']}, écart ≤ {p['ecart_max_secondes']} s", f"{v['source']}, écart {v['ecart_secondes']:.2f} s"


def _ip(p, v):
    ok = all(e == "Enabled" for e in v) if p["dhcp"] else True
    return ok, "DHCP", ", ".join("DHCP" if e == "Enabled" else "adresse fixe" for e in v)


def _antivirus(p, v):
    present = any(_contient(p["produit"], x) for x in v["produits"])
    temps_reel = "actif" if v["temps_reel"] else "inactif"
    return present and v["temps_reel"], f"{p['produit']}, temps réel actif", f"{', '.join(v['produits'])}, temps réel {temps_reel}"


def _bitlocker(p, v):
    ok = v or not p["exige"]
    return ok, "protection activée" if p["exige"] else "BitLocker non exigé", "protection activée" if v else "protection désactivée"


def _pare_feu(p, v):
    inactifs = [nom for nom in p["profils"] if not v.get(nom)]
    constate = ("inactifs : " + ", ".join(inactifs)) if inactifs else "tous actifs"
    return not inactifs, "profils actifs : " + ", ".join(p["profils"]), constate


def _service_maj(p, v):
    return v["demarrage"] != "Disabled", "service actif et démarrable", f"{v['etat']}, démarrage {v['demarrage']}"


def _logiciels_requis(p, v):
    absents = [l["nom"] for l in p["requis"] if not any(_contient(l["nom"], n) for n in v)]
    constate = ("absents : " + ", ".join(absents)) if absents else "tous présents"
    return not absents, "présents : " + ", ".join(l["nom"] for l in p["requis"]), constate


def _logiciels_interdits(p, v):
    presents = [i for i in p["interdits"] if any(_contient(i, n) for n in v)]
    constate = ("présents : " + ", ".join(presents)) if presents else "aucun"
    return not presents, "aucun logiciel interdit", constate


def _services(p, v):
    problemes = []
    for s in p["services"]:
        lu = v.get(s["nom"])
        if lu is None:
            problemes.append(f"{s['nom']} absent")
        elif lu["etat"] != s["etat"] or lu["demarrage"] != s["demarrage"]:
            problemes.append(f"{s['nom']} : {lu['etat']}, {lu['demarrage']}")
    attendu = ", ".join(f"{s['nom']} {s['etat']}/{s['demarrage']}" for s in p["services"])
    return not problemes, attendu, "; ".join(problemes) or "conforme"


def _pave(p, v):
    return v == p["attendu"], "actif" if p["attendu"] else "inactif", "actif" if v else "inactif"


NOMS_EXPLORATEUR = {
    "extensions_visibles": "extensions visibles",
    "fichiers_caches_visibles": "fichiers cachés visibles",
    "confirmation_suppression": "confirmation de suppression",
}


def _explorateur(p, v):
    def texte(valeurs):
        return ", ".join(f"{nom} : {'oui' if valeurs[cle] else 'non'}" for cle, nom in NOMS_EXPLORATEUR.items())
    return all(v[cle] == p[cle] for cle in NOMS_EXPLORATEUR), texte(p), texte(v)


def _chrome(p, v):
    ok = v["mode"] == CHROME_OUVRIR_LISTE and v["url"] == p["url"]
    return ok, f"{p['url']} (stratégie)", v["url"] or "aucune stratégie"


def _imprimante(p, v):
    return p["nom"] in v, p["nom"], ", ".join(v) or "aucune"


COMPARATEURS = {
    "IDENT_MACHINE": _machine,
    "IDENT_COMPTE_ADMIN": _compte_admin,
    "IDENT_COMPTE_LOCAL": _comptes_locaux,
    "MAT_RAM": _seuil_min("minimum_go", "Go"),
    "MAT_STOCKAGE": _seuil_min("libre_minimum_go", "Go"),
    "MAT_SMART": _liste_egale("sante_attendue"),
    "MAT_TYPE_SUPPORT": _liste_egale("type_attendu"),
    "SYS_OS_VERSION": _os,
    "SYS_TURN_ON": _activation,
    "SYS_SERV_TIME": _heure,
    "SYS_IP": _ip,
    "SEC_ANTIVIRUS": _antivirus,
    "SEC_SIGN": _seuil_max("age_max_jours", "jours"),
    "SEC_BITLOCKER": _bitlocker,
    "SEC_PROFILS": _pare_feu,
    "SEC_MAJ_WINDOWS": _service_maj,
    "SEC_MAJ": _seuil_max("maximum", "mise(s) à jour"),
    "LOG_WINGET": _logiciels_requis,
    "LOG_FORB": _logiciels_interdits,
    "LOG_START": _services,
    "ENV_NUM_PAD": _pave,
    "ENV_HIDDEN_FILES": _explorateur,
    "ENV_CHROME_START": _chrome,
    "ENV_PRINT": _imprimante,
    "JRN_CRITICAL_EVENT": _seuil_max("maximum_24h", "événement(s)"),
}


def evaluer_controle(identifiant, parametres, delai, journal=None):
    """Un contrôle : non évalué, indéterminé, conforme ou écart (RG02). `journal` reçoit chaque sonde en erreur (§3.2)."""
    if not parametres["actif"]:
        return Resultat(identifiant, "", "", NON_EVALUE, "Contrôle désactivé dans le profil.")
    try:
        valeur = SONDES[identifiant](parametres, delai)
    except ErreurSonde as erreur:
        raison = str(erreur).splitlines()[0] if str(erreur) else "lecture impossible"
        if journal:
            journal.warning("%s : sonde en erreur : %s", identifiant, raison)
        return Resultat(identifiant, "", "", INDETERMINE, raison)
    try:
        conforme, attendu, constate = COMPARATEURS[identifiant](parametres, valeur)
    except (KeyError, TypeError, ValueError) as erreur:
        if journal:
            journal.warning("%s : valeur lue inattendue : %r", identifiant, erreur)
        return Resultat(identifiant, "", "", INDETERMINE, f"Valeur lue inattendue : {erreur!r}")
    if conforme:
        return Resultat(identifiant, attendu, constate, CONFORME, "Conforme.")
    return Resultat(identifiant, attendu, constate, ECART, f"Attendu : {attendu} ; constaté : {constate}.")


def evaluer_profil(profil, delai, rappel=None, journal=None):
    """Passe complète : un résultat par contrôle du catalogue. `rappel` sert à suivre l'avancement."""
    resultats = []
    identifiants = list(CATALOGUE)
    for numero, identifiant in enumerate(identifiants, start=1):
        resultat = evaluer_controle(identifiant, profil.controles[identifiant], delai, journal)
        resultats.append(resultat)
        if rappel:
            rappel(numero, len(identifiants), resultat)
    return resultats


def calculer_verdict(resultats):
    """Règle à 4 cas de RG03."""
    ecarts = [r for r in resultats if r.etat == ECART]
    indetermines = [r for r in resultats if r.etat == INDETERMINE]
    graves = [r for r in ecarts if CATALOGUE[r.identifiant]["gravite"] in (MAJEUR, BLOQUANT)]
    mineurs = [r.identifiant for r in ecarts if r not in graves]

    motifs = []
    if indetermines:
        motifs.append("contrôle non vérifié")
    if graves:
        motifs.append("écart majeur ou bloquant")
    if motifs:
        return Verdict(V_NON_CONFORME, motifs, mineurs)
    if mineurs:
        return Verdict(V_RESERVES, [], mineurs)
    return Verdict(V_CONFORME, [], [])