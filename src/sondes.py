"""Sondes : une fonction par contrôle, qui LIT et renvoie la valeur constatée (F4, section 3.3.4).

Une sonde ne juge pas, ne corrige pas, ne dessine rien.
"""
import os
import re
import shutil
import socket

from powershell import ErreurPowerShell, executer_powershell


class ErreurSonde(Exception):
    """La valeur n'a pas pu être lue : le contrôle sera « indéterminé » (RG02)."""


def _lire(commande, delai):
    """Appelle PowerShell et convertit son erreur en erreur de sonde."""
    try:
        return executer_powershell(commande, delai)
    except ErreurPowerShell as erreur:
        raise ErreurSonde(str(erreur))


def _en_liste(valeur):
    """PowerShell renvoie un texte seul s'il n'y a qu'un élément : on veut toujours une liste."""
    if valeur is None:
        return []
    return valeur if isinstance(valeur, list) else [valeur]


def _litteral(texte):
    """Texte entre apostrophes pour PowerShell (une apostrophe se double)."""
    return "'" + texte.replace("'", "''") + "'"


# --- Identité -------------------------------------------------------------

def sonde_nom_machine(parametres, delai):
    return socket.gethostname()


def sonde_compte_admin(parametres, delai):
    nom = _litteral(parametres["compte"])
    compte = _lire(
        f"Get-LocalUser -Name {nom} -ErrorAction SilentlyContinue | Select-Object Name, Enabled",
        delai,
    )
    if compte is None:
        return {"existe": False, "actif": False}
    return {"existe": True, "actif": bool(compte["Enabled"])}


def sonde_comptes_locaux(parametres, delai):
    """Liste des comptes locaux activés."""
    noms = _lire("Get-LocalUser | Where-Object Enabled | Select-Object -ExpandProperty Name", delai)
    return _en_liste(noms)


# --- Matériel -------------------------------------------------------------

def sonde_ram(parametres, delai):
    """Mémoire vive visible par Windows, en Go."""
    octets = _lire("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory", delai)
    if isinstance(octets, bool) or not isinstance(octets, (int, float)):
        raise ErreurSonde("Mémoire vive illisible.")
    return round(octets / 1024**3, 2)


def sonde_stockage(parametres, delai):
    """Espace libre du lecteur système, en Go."""
    try:
        lecteur = os.environ["SystemDrive"] + "\\"
        libre = shutil.disk_usage(lecteur).free
    except (KeyError, OSError) as erreur:
        raise ErreurSonde(f"Espace disque illisible : {erreur}")
    return round(libre / 1024**3, 2)


def sonde_smart(parametres, delai):
    """État de santé de chaque disque physique (texte)."""
    etats = _en_liste(_lire("Get-PhysicalDisk | ForEach-Object { [string]$_.HealthStatus }", delai))
    if not etats:
        raise ErreurSonde("Aucun disque physique détecté.")
    return etats


def sonde_type_support(parametres, delai):
    """Type de chaque disque physique : SSD, HDD ou Unspecified."""
    types = _en_liste(_lire("Get-PhysicalDisk | ForEach-Object { [string]$_.MediaType }", delai))
    if not types:
        raise ErreurSonde("Aucun disque physique détecté.")
    return types


# --- Système --------------------------------------------------------------

def sonde_os(parametres, delai):
    """Édition (Caption) et version de Windows."""
    os_ = _lire("Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version", delai)
    if not isinstance(os_, dict):
        raise ErreurSonde("Édition de Windows illisible.")
    return {"edition": os_["Caption"], "version": os_["Version"]}


def sonde_activation(parametres, delai):
    """True si Windows est activé (LicenseStatus = 1)."""
    statut = _lire(
        "(Get-CimInstance SoftwareLicensingProduct "
        "-Filter \"ApplicationId='55c92734-d682-4d71-983e-d6ec3f16059f' AND PartialProductKey IS NOT NULL\" "
        "| Select-Object -First 1).LicenseStatus",
        delai,
    )
    if statut is None:
        raise ErreurSonde("État d'activation illisible.")
    return statut == 1


def sonde_heure(parametres, delai):
    """Serveur de temps configuré et écart d'horloge (en secondes) avec le serveur du profil."""
    etat = _lire("(Get-Service w32time).Status.ToString()", delai)
    if etat != "Running":
        raise ErreurSonde(f"Le service Windows Time n'est pas démarré (état : {etat}).")
    configure = _lire(
        r"(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters').NtpServer",
        delai,
    )
    if not isinstance(configure, str) or not configure.strip():
        raise ErreurSonde("Aucun serveur de temps n'est configuré.")
    serveur = _litteral(parametres["serveur"])
    lignes = _en_liste(_lire(f"$s = {serveur}; w32tm /stripchart /computer:$s /samples:1 /dataonly", delai))
    texte = " ".join(str(ligne) for ligne in lignes)
    ecarts = re.findall(r"([+-]\d+[.,]\d+)s", texte)
    if not ecarts:
        raise ErreurSonde("Écart d'horloge illisible : " + texte)
    return {"source": configure, "ecart_secondes": abs(float(ecarts[-1].replace(",", ".")))}


def sonde_ip(parametres, delai):
    """État DHCP (Enabled ou Disabled) de chaque interface IPv4 connectée."""
    etats = _lire(
        "Get-NetIPInterface -AddressFamily IPv4 | "
        "Where-Object { $_.ConnectionState -eq 'Connected' -and $_.InterfaceAlias -notlike 'Loopback*' } | "
        "ForEach-Object { [string]$_.Dhcp }",
        delai,
    )
    etats = _en_liste(etats)
    if not etats:
        raise ErreurSonde("Aucune interface réseau connectée.")
    return etats


# --- Sécurité -------------------------------------------------------------

def sonde_antivirus(parametres, delai):
    """Produits antivirus déclarés et état de la protection en temps réel."""
    produits = _en_liste(_lire(
        "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | "
        "ForEach-Object { $_.displayName }",
        delai,
    ))
    temps_reel = _lire("(Get-MpComputerStatus).RealTimeProtectionEnabled", delai)
    if not produits or not isinstance(temps_reel, bool):
        raise ErreurSonde("Antivirus illisible.")
    return {"produits": produits, "temps_reel": temps_reel}


def sonde_signatures(parametres, delai):
    """Âge des signatures de l'antivirus, en jours."""
    age = _lire("(Get-MpComputerStatus).AntivirusSignatureAge", delai)
    if isinstance(age, bool) or not isinstance(age, int):
        raise ErreurSonde("Âge des signatures illisible.")
    return age


def sonde_bitlocker(parametres, delai):
    """True si la protection BitLocker du lecteur système est activée (droits administrateur requis)."""
    statut = _lire("(Get-BitLockerVolume -MountPoint $env:SystemDrive).ProtectionStatus.ToString()", delai)
    if statut is None:
        raise ErreurSonde("État de BitLocker illisible.")
    return statut == "On"


def sonde_pare_feu(parametres, delai):
    """Pour chaque profil du pare-feu : True s'il est activé."""
    profils = _en_liste(_lire(
        "Get-NetFirewallProfile | ForEach-Object { [pscustomobject]@{ Nom = [string]$_.Name; Actif = [string]$_.Enabled } }",
        delai,
    ))
    if not profils:
        raise ErreurSonde("Profils du pare-feu illisibles.")
    return {profil["Nom"]: profil["Actif"] == "True" for profil in profils}


def sonde_service_maj(parametres, delai):
    """État et type de démarrage du service de mise à jour de Windows."""
    nom = _litteral(parametres["service"])
    service = _lire(
        f"Get-Service -Name {nom} | ForEach-Object {{ [pscustomobject]@{{ Etat = [string]$_.Status; Demarrage = [string]$_.StartType }} }}",
        delai,
    )
    if not isinstance(service, dict):
        raise ErreurSonde("Service de mise à jour illisible.")
    return {"etat": service["Etat"], "demarrage": service["Demarrage"]}


def sonde_maj_en_attente(parametres, delai):
    """Nombre de mises à jour en attente (peut durer plusieurs secondes)."""
    nombre = _lire(
        "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()"
        ".Search('IsInstalled=0 and IsHidden=0').Updates.Count",
        delai,
    )
    if isinstance(nombre, bool) or not isinstance(nombre, int):
        raise ErreurSonde("Nombre de mises à jour illisible.")
    return nombre


# --- Logiciels ------------------------------------------------------------

def _noms_logiciels(delai):
    """Noms d'affichage des logiciels installés, lus dans le registre (section 3.3.4).

    Trois emplacements : machine, machine 32 bits, utilisateur courant.
    La classe WMI des produits installés est volontairement évitée (section 3.3.4).
    """
    noms = _lire(
        r"Get-ItemProperty "
        r"'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', "
        r"'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*', "
        r"'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' "
        r"-ErrorAction SilentlyContinue | Where-Object DisplayName | ForEach-Object { $_.DisplayName }",
        delai,
    )
    return sorted(set(_en_liste(noms)))


def sonde_logiciels_requis(parametres, delai):
    """Liste des logiciels installés (la comparaison cherchera les logiciels du socle dedans)."""
    return _noms_logiciels(delai)


def sonde_logiciels_interdits(parametres, delai):
    """Liste des logiciels installés (la comparaison cherchera les logiciels interdits dedans)."""
    return _noms_logiciels(delai)


def sonde_services(parametres, delai):
    """Pour chaque service du profil : état et type de démarrage, ou None s'il n'existe pas."""
    resultat = {}
    for service in parametres["services"]:
        nom = _litteral(service["nom"])
        lu = _lire(
            f"Get-Service -Name {nom} -ErrorAction SilentlyContinue | "
            f"ForEach-Object {{ [pscustomobject]@{{ Etat = [string]$_.Status; Demarrage = [string]$_.StartType }} }}",
            delai,
        )
        resultat[service["nom"]] = None if lu is None else {"etat": lu["Etat"], "demarrage": lu["Demarrage"]}
    return resultat


# --- Environnement (ruche de l'utilisateur courant) -------------------------

def sonde_pave_numerique(parametres, delai):
    """True si le pavé numérique est actif au démarrage (bit 2 de InitialKeyboardIndicators)."""
    valeur = _lire(r"(Get-ItemProperty 'HKCU:\Control Panel\Keyboard').InitialKeyboardIndicators", delai)
    if valeur is None:
        return False
    try:
        return int(valeur) & 2 != 0
    except (TypeError, ValueError):
        raise ErreurSonde(f"Valeur du pavé numérique illisible : {valeur}")


def sonde_explorateur(parametres, delai):
    """Extensions visibles, fichiers cachés visibles, confirmation de suppression."""
    lu = _lire(
        r"$a = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' -ErrorAction SilentlyContinue; "
        r"$e = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer' -ErrorAction SilentlyContinue; "
        r"[pscustomobject]@{ HideFileExt = $a.HideFileExt; Hidden = $a.Hidden; ConfirmFileDelete = $e.ConfirmFileDelete }",
        delai,
    )
    if not isinstance(lu, dict):
        raise ErreurSonde("Réglages de l'explorateur illisibles.")
    return {
        "extensions_visibles": lu["HideFileExt"] == 0,
        "fichiers_caches_visibles": lu["Hidden"] == 1,
        "confirmation_suppression": lu["ConfirmFileDelete"] == 1,
    }


def sonde_chrome(parametres, delai):
    """Page de démarrage de Chrome imposée par stratégie : mode (4 = liste d'adresses) et adresse."""
    lu = _lire(
        r"$p = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Google\Chrome' -ErrorAction SilentlyContinue; "
        r"$u = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Google\Chrome\RestoreOnStartupURLs' -ErrorAction SilentlyContinue; "
        r"[pscustomobject]@{ Mode = $p.RestoreOnStartup; Url = $u.'1' }",
        delai,
    )
    if not isinstance(lu, dict):
        raise ErreurSonde("Stratégie de Chrome illisible.")
    return {"mode": lu["Mode"], "url": lu["Url"]}


def sonde_imprimante(parametres, delai):
    """Noms des imprimantes installées."""
    noms = _lire("Get-Printer | ForEach-Object { $_.Name }", delai)
    return _en_liste(noms)


# --- Journaux -------------------------------------------------------------

def sonde_evenements_critiques(parametres, delai):
    """Nombre d'événements critiques des journaux Système et Application sur les dernières 24 h."""
    nombre = _lire(
        "(Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=1; "
        "StartTime=(Get-Date).AddHours(-24)} -ErrorAction SilentlyContinue | Measure-Object).Count",
        delai,
    )
    if isinstance(nombre, bool) or not isinstance(nombre, int):
        raise ErreurSonde("Nombre d'événements critiques illisible.")
    return nombre


# Table des sondes : identifiant du catalogue -> fonction
SONDES = {
    "IDENT_MACHINE": sonde_nom_machine,
    "IDENT_COMPTE_ADMIN": sonde_compte_admin,
    "IDENT_COMPTE_LOCAL": sonde_comptes_locaux,
    "MAT_RAM": sonde_ram,
    "MAT_STOCKAGE": sonde_stockage,
    "MAT_SMART": sonde_smart,
    "MAT_TYPE_SUPPORT": sonde_type_support,
    "SYS_OS_VERSION": sonde_os,
    "SYS_TURN_ON": sonde_activation,
    "SYS_SERV_TIME": sonde_heure,
    "SYS_IP": sonde_ip,
    "SEC_ANTIVIRUS": sonde_antivirus,
    "SEC_SIGN": sonde_signatures,
    "SEC_BITLOCKER": sonde_bitlocker,
    "SEC_PROFILS": sonde_pare_feu,
    "SEC_MAJ_WINDOWS": sonde_service_maj,
    "SEC_MAJ": sonde_maj_en_attente,
    "LOG_WINGET": sonde_logiciels_requis,
    "LOG_FORB": sonde_logiciels_interdits,
    "LOG_START": sonde_services,
    "ENV_NUM_PAD": sonde_pave_numerique,
    "ENV_HIDDEN_FILES": sonde_explorateur,
    "ENV_CHROME_START": sonde_chrome,
    "ENV_PRINT": sonde_imprimante,
    "JRN_CRITICAL_EVENT": sonde_evenements_critiques,
}