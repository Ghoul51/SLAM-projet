"""Corrections automatiques (F9). Respecte RG01, RG06, RG07, RG10. Ne connaît pas Tkinter (§3.4.1).

Une correction ne démarre que sur demande de l'opérateur (RG01) : ce module ne décide jamais seul.
Chaque correction passe par `_executer`, qui impose le même déroulement :
  1. relire le contrôle : déjà conforme ? on le dit et on ne touche à rien (RG10) ;
  2. journaliser ce qu'on va faire (RG06) ;
  3. agir ;
  4. relire le contrôle avec la sonde : c'est ce résultat qui décide (RG06) ;
  5. journaliser le résultat et sa durée.
"""
import base64
import re
import time
import winreg
from dataclasses import dataclass

from comparaison import CHROME_OUVRIR_LISTE, CONFORME, INDETERMINE, _contient, evaluer_controle
from powershell import ErreurPowerShell, executer_powershell
from sondes import ErreurSonde, _litteral, _noms_logiciels

SUCCES, ECHEC, ATTENTE = "Succès", "Échec", "En attente de prise en compte"
SESSION = "nouvelle ouverture de session nécessaire"
REDEMARRAGE = "redémarrage nécessaire"


@dataclass
class ResultatCorrection:
    statut: str            # SUCCES, ECHEC ou ATTENTE
    message: str           # message compréhensible pour le technicien
    motif: str = ""        # ATTENTE : redémarrage ou session ; ECHEC : raison
    relecture: object = None   # Resultat du contrôle relu après la correction


def _executer(identifiant, parametres, delai, journal, prevu, agir, attente="", complement="", declenche=False):
    """Squelette commun des corrections (RG06, RG07, RG10). `agir` fait le geste et ne renvoie rien.

    `declenche` : le geste lance un travail qui ne sera effectif que plus tard (renommage, installation
    en arrière-plan). La relecture ne peut pas encore être conforme : on renvoie « en attente » (RG07).
    """
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
    if declenche and apres.etat != INDETERMINE:   # RG07 : lancé, pas encore effectif
        journal.info("%s : EN ATTENTE de prise en compte : %s", identifiant, attente)
        message = f"Correction lancée. En attente de prise en compte : {attente}."
        return ResultatCorrection(ATTENTE, message, motif=attente, relecture=apres)
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


# --- SEC_PROFILS : profils du pare-feu (PowerShell) -------------------------

def decrire_pare_feu(p):
    return "Les profils du pare-feu Windows suivants seront activés : " + ", ".join(p["profils"]) + ".", ""


def corriger_pare_feu(parametres, delai, journal):
    noms = ",".join(_litteral(nom) for nom in parametres["profils"])   # 'Domain','Private','Public'
    commande = f"Set-NetFirewallProfile -Profile {noms} -Enabled True"

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    prevu = "Set-NetFirewallProfile -Enabled True pour les profils : " + ", ".join(parametres["profils"])
    return _executer("SEC_PROFILS", parametres, delai, journal, prevu, agir)


# --- SEC_MAJ_WINDOWS : service de mise à jour de Windows (PowerShell, RG09) ---

def decrire_maj_windows(p):
    return (f"Le service Windows Update ({p['service']}) sera réactivé : son type de démarrage "
            f"repassera en « Manuel », réglage normal de Windows. Les mises à jour ne sont jamais "
            f"désactivées par cette application."), ""


def corriger_maj_windows(parametres, delai, journal):
    service = _litteral(parametres["service"])
    commande = f"Set-Service -Name {service} -StartupType Manual -ErrorAction Stop"

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    prevu = f"Set-Service {parametres['service']} -StartupType Manual (réactivation, jamais l'inverse : RG09)"
    return _executer("SEC_MAJ_WINDOWS", parametres, delai, journal, prevu, agir)


# --- LOG_START : services requis démarrés, en démarrage automatique (PowerShell) ---

def decrire_services(p):
    lignes = []
    for service in p["services"]:
        ligne = f"{service['nom']} (démarrage {service['demarrage']}"
        ligne += ", puis démarré)" if service["etat"] == "Running" else ")"
        lignes.append(ligne)
    return "Les services requis seront réglés d'après le profil : " + ", ".join(lignes) + ".", ""


def corriger_services(parametres, delai, journal):
    gestes = []
    for service in parametres["services"]:
        nom = _litteral(service["nom"])
        # D'abord le type de démarrage : un service désactivé ne peut pas être démarré.
        gestes.append(f"Set-Service -Name {nom} -StartupType {_litteral(service['demarrage'])} -ErrorAction Stop")
        if service["etat"] == "Running":   # on démarre, on n'arrête jamais un service
            gestes.append(f"Start-Service -Name {nom} -ErrorAction Stop")
    commande = "; ".join(gestes)

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    prevu = "services du profil : " + ", ".join(f"{s['nom']} -> {s['demarrage']}/{s['etat']}" for s in parametres["services"])
    return _executer("LOG_START", parametres, delai, journal, prevu, agir)


# --- SYS_IP : retour au DHCP pour l'adresse et les DNS (PowerShell) ---

def decrire_ip(p):
    return ("Les interfaces réseau connectées qui ont une adresse IP fixe repasseront en DHCP : l'adresse fixe, "
            "la passerelle fixe et les serveurs DNS fixes seront retirés. La connexion réseau peut être "
            "interrompue quelques secondes."), ""


def corriger_ip(parametres, delai, journal):
    # Mêmes interfaces que la sonde, mais seulement celles dont le DHCP est désactivé.
    commande = (
        "Get-NetIPInterface -AddressFamily IPv4 | "
        "Where-Object { $_.ConnectionState -eq 'Connected' -and $_.InterfaceAlias -notlike 'Loopback*' "
        "-and $_.Dhcp -eq 'Disabled' } | "
        "ForEach-Object { "
        "$n = $_.InterfaceIndex; "
        "Set-NetIPInterface -InterfaceIndex $n -Dhcp Enabled -ErrorAction Stop; "
        "Get-NetRoute -InterfaceIndex $n -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
        "Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue; "
        "Get-NetIPAddress -InterfaceIndex $n -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
        "Where-Object { $_.PrefixOrigin -eq 'Manual' } | "
        "Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue; "
        "Set-DnsClientServerAddress -InterfaceIndex $n -ResetServerAddresses -ErrorAction Stop }"
    )

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    prevu = "Set-NetIPInterface -Dhcp Enabled, retrait de l'adresse et de la passerelle fixes, DNS remis en automatique"
    return _executer("SYS_IP", parametres, delai, journal, prevu, agir)


# --- SYS_SERV_TIME : serveur de temps et resynchronisation (PowerShell, w32tm) ---

def decrire_heure(p):
    return (f"Le serveur de temps {p['serveur']} sera configuré comme source de l'heure, puis l'horloge sera "
            f"resynchronisée. Le service Windows Time sera démarré s'il est arrêté."), ""


def corriger_heure(parametres, delai, journal):
    serveur = _litteral(parametres["serveur"])
    commande = (
        f"$s = {serveur}; "
        "if ((Get-Service -Name w32time).Status -ne 'Running') { Start-Service -Name w32time -ErrorAction Stop }; "
        "$sortie = w32tm /config /manualpeerlist:$s /syncfromflags:manual /update 2>&1 | Out-String; "
        "if ($LASTEXITCODE -ne 0) { throw $sortie }; "
        "$sortie = w32tm /resync /rediscover 2>&1 | Out-String; "
        "if ($LASTEXITCODE -ne 0) { throw $sortie }"   # le message de Windows est restitué tel quel (F8)
    )

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    prevu = f"w32tm /config /manualpeerlist:{parametres['serveur']} puis w32tm /resync /rediscover"
    return _executer("SYS_SERV_TIME", parametres, delai, journal, prevu, agir)


# --- IDENT_COMPTE_LOCAL : désactivation des comptes non prévus, jamais suppression (RG08) ---

def decrire_comptes(p):
    return ("Les comptes locaux actifs qui ne figurent pas dans la liste du profil ("
            + ", ".join(p["comptes_autorises"]) + ") seront désactivés. Aucun compte ne sera supprimé "
            "et aucun fichier ne sera touché."), ""


def corriger_comptes(parametres, delai, journal):
    autorises = ",".join(_litteral(compte) for compte in parametres["comptes_autorises"])
    commande = (
        f"$autorises = @({autorises}); "
        "Get-LocalUser | Where-Object { $_.Enabled -and ($autorises -notcontains $_.Name) } | "
        "ForEach-Object { "
        # Garde-fou : on ne désactive pas le compte qui fait tourner l'application.
        "if ($_.Name -eq $env:USERNAME) { throw ('Désactivation refusée, compte de la session en cours : ' + $_.Name) }; "
        "Disable-LocalUser -Name $_.Name -ErrorAction Stop }"
    )

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    prevu = "Disable-LocalUser (jamais Remove-LocalUser : RG08) pour les comptes actifs hors liste : " + ", ".join(parametres["comptes_autorises"])
    return _executer("IDENT_COMPTE_LOCAL", parametres, delai, journal, prevu, agir)


# --- SEC_SIGN : mise à jour des signatures de l'antivirus (PowerShell) ---

def decrire_signatures(p):
    return (f"Les signatures de l'antivirus seront mises à jour depuis Internet "
            f"(âge maximal du profil : {p['age_max_jours']} jours). Cela peut durer un moment."), ""


def corriger_signatures(parametres, delai, journal):
    def agir():
        executer_powershell("Update-MpSignature -ErrorAction Stop", delai)

    return _executer("SEC_SIGN", parametres, delai, journal, "Update-MpSignature", agir)


# --- SEC_MAJ : recherche et installation des mises à jour (en arrière-plan, vert après redémarrage) ---

# Script lancé dans un PowerShell séparé : l'installation dure plusieurs minutes, on ne l'attend pas.
SCRIPT_INSTALLATION_MAJ = (
    "$s = New-Object -ComObject Microsoft.Update.Session; "
    "$r = $s.CreateUpdateSearcher().Search('IsInstalled=0 and IsHidden=0'); "
    "if ($r.Updates.Count -gt 0) { "
    "foreach ($u in $r.Updates) { if (-not $u.EulaAccepted) { $u.AcceptEula() } }; "
    "$d = $s.CreateUpdateDownloader(); $d.Updates = $r.Updates; $null = $d.Download(); "
    "$i = $s.CreateUpdateInstaller(); $i.Updates = $r.Updates; $null = $i.Install() }"
)


def decrire_maj(p):
    return (f"La recherche puis l'installation des mises à jour Windows seront lancées en arrière-plan "
            f"(plusieurs minutes ; seuil du profil : {p['maximum']}). Le contrôle ne passera au vert "
            f"qu'après la fin de l'installation et un redémarrage."), REDEMARRAGE


def corriger_maj(parametres, delai, journal):
    # -EncodedCommand : le script est passé en base64 (UTF-16), sans souci de guillemets.
    encode = base64.b64encode(SCRIPT_INSTALLATION_MAJ.encode("utf-16-le")).decode("ascii")
    commande = (
        f"$enc = '{encode}'; "
        # RG10 : si cette installation tourne déjà, on n'en lance pas une 2e.
        "$deja = Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | "
        "Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like ('*' + $enc + '*') }; "
        "if (-not $deja) { Start-Process -FilePath powershell.exe -WindowStyle Hidden "
        "-ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $enc }"
    )

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    prevu = "installation des mises à jour Windows lancée en arrière-plan (API Microsoft.Update.Session)"
    return _executer("SEC_MAJ", parametres, delai, journal, prevu, agir,
                     attente="installation en cours en arrière-plan, puis redémarrage nécessaire", declenche=True)


# --- MAT_TYPE_SUPPORT : entretien du disque adapté au support (F9, F10) ---

LECTEUR_SYSTEME = "$l = $env:SystemDrive.TrimEnd(':'); "
DETECTER_SUPPORT = (LECTEUR_SYSTEME + "$n = (Get-Partition -DriveLetter $l).DiskNumber; "
                    "[string](Get-PhysicalDisk | Where-Object { [string]$_.DeviceId -eq [string]$n }).MediaType")


def commandes_entretien(type_support):
    """Entretien adapté au support (F10) : analyse puis défragmentation sur plateaux, TRIM sur mémoire flash.

    Renvoie None si le type n'est pas détecté : la correction refuse (§3.3.9).
    Fonction pure, sans effet : elle sert aussi au cas de test reproductible du banc d'essai.
    """
    if type_support == "HDD":
        return ["Optimize-Volume -DriveLetter $l -Analyze -ErrorAction Stop",
                "Optimize-Volume -DriveLetter $l -Defrag -ErrorAction Stop"]
    if type_support == "SSD":
        return ["Optimize-Volume -DriveLetter $l -ReTrim -ErrorAction Stop"]
    return None


def decrire_type_support(p):
    return ("Le support du disque système sera détecté, puis l'entretien adapté sera lancé : analyse et "
            "défragmentation sur un disque à plateaux, TRIM sur un disque à mémoire flash. "
            "Si le type n'est pas détecté, rien ne sera lancé."), ""


def corriger_type_support(parametres, delai, journal):
    def agir():
        detecte = executer_powershell(DETECTER_SUPPORT, delai)
        gestes = commandes_entretien(detecte)
        if gestes is None:
            raise OSError(f"Type de support non détecté ({detecte or 'inconnu'}) : entretien refusé, rien n'a été lancé.")
        journal.info("MAT_TYPE_SUPPORT : support détecté %s : %s", detecte, " ; ".join(gestes))
        executer_powershell(LECTEUR_SYSTEME + "; ".join(gestes), delai)

    return _executer("MAT_TYPE_SUPPORT", parametres, delai, journal,
                     "détection du support du disque système puis entretien adapté", agir)


# --- IDENT_MACHINE : renommage (numéro saisi par l'opérateur, redémarrage annoncé) ---

# Contrôles qui demandent une saisie à l'opérateur avant la confirmation (utilisé par l'interface).
SAISIE_REQUISE = {"IDENT_MACHINE": "Numéro du poste (3 chiffres)"}


def saisie_requise(identifiant):
    """Texte à demander à l'opérateur, ou None si la correction n'a besoin d'aucune saisie."""
    return SAISIE_REQUISE.get(identifiant)


def nom_machine(parametres, numero):
    """Préfixe du profil + numéro saisi, validé par l'expression régulière du profil. Renvoie (nom, erreur)."""
    nom = f"{parametres['prefixe']}-{str(numero).strip()}"
    if re.fullmatch(parametres["modele"], nom) is None:
        return None, f"Le nom {nom} ne respecte pas la convention du profil ({parametres['modele']})."
    return nom, ""


def decrire_machine(p):
    if "numero" not in p:
        return f"La machine sera renommée avec le préfixe {p['prefixe']} : le numéro du poste vous sera demandé.", REDEMARRAGE
    nom, erreur = nom_machine(p, p["numero"])
    if nom is None:
        return erreur, ""
    return f"La machine va être renommée {nom}.", REDEMARRAGE


def corriger_machine(parametres, delai, journal):
    # `parametres["numero"]` est ajouté par l'interface après la saisie : dict(parametres, numero="042").
    nom, erreur = nom_machine(parametres, parametres.get("numero", ""))
    if nom is None:
        journal.warning("IDENT_MACHINE : renommage refusé : %s", erreur)
        return ResultatCorrection(ECHEC, erreur, motif=erreur)
    commande = f"Rename-Computer -NewName {_litteral(nom)} -Force -WarningAction SilentlyContinue -ErrorAction Stop"

    def agir():   # exige les droits d'administrateur
        executer_powershell(commande, delai)

    return _executer("IDENT_MACHINE", parametres, delai, journal, f"Rename-Computer -NewName {nom}", agir,
                     attente=REDEMARRAGE, declenche=True)


# --- LOG_WINGET : installation des logiciels du socle manquants (winget, vérifiée dans le registre) ---

def decrire_winget(p):
    noms = ", ".join(logiciel["nom"] for logiciel in p["requis"])
    return f"Les logiciels du socle qui manquent parmi : {noms} seront installés par winget, en silence.", ""


def corriger_winget(parametres, delai, journal):
    def agir():   # exige les droits d'administrateur
        try:
            installes = _noms_logiciels(delai)
        except ErreurSonde as erreur:
            raise OSError(f"Liste des logiciels illisible : {erreur}")
        manquants = [l for l in parametres["requis"] if not any(_contient(l["nom"], n) for n in installes)]
        if not manquants:
            return
        journal.info("LOG_WINGET : logiciels à installer : %s", ", ".join(l["winget_id"] for l in manquants))
        gestes = ["Get-Command winget -ErrorAction Stop | Out-Null"]   # winget peut manquer sur une image ancienne
        for logiciel in manquants:
            gestes.append(f"winget install --id {_litteral(logiciel['winget_id'])} -e --silent "
                          "--accept-package-agreements --accept-source-agreements | Out-Null")
        gestes.append("$global:LASTEXITCODE = 0")   # le code de retour de winget n'est pas fiable : c'est la relecture qui décide
        executer_powershell("; ".join(gestes), delai)

    prevu = "winget install des logiciels du socle manquants : " + ", ".join(l["winget_id"] for l in parametres["requis"])
    return _executer("LOG_WINGET", parametres, delai, journal, prevu, agir)


# Table des corrections : identifiant du catalogue -> (description pour la confirmation, correction)
CORRECTIONS = {
    "ENV_NUM_PAD": (decrire_pave, corriger_pave),
    "ENV_HIDDEN_FILES": (decrire_explorateur, corriger_explorateur),
    "ENV_CHROME_START": (decrire_chrome, corriger_chrome),
    "SEC_PROFILS": (decrire_pare_feu, corriger_pare_feu),
    "SEC_MAJ_WINDOWS": (decrire_maj_windows, corriger_maj_windows),
    "LOG_START": (decrire_services, corriger_services),
    "SYS_IP": (decrire_ip, corriger_ip),
    "SYS_SERV_TIME": (decrire_heure, corriger_heure),
    "IDENT_COMPTE_LOCAL": (decrire_comptes, corriger_comptes),
    "SEC_SIGN": (decrire_signatures, corriger_signatures),
    "SEC_MAJ": (decrire_maj, corriger_maj),
    "MAT_TYPE_SUPPORT": (decrire_type_support, corriger_type_support),
    "IDENT_MACHINE": (decrire_machine, corriger_machine),
    "LOG_WINGET": (decrire_winget, corriger_winget),
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