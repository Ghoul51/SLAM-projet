"""Catalogue des contrôles (section 3.3.3). Données imposées par le sujet : gravité et mode de correction."""

BLOQUANT, MAJEUR, MINEUR = "Bloquant", "Majeur", "Mineur"
AUTO, MANUELLE = "Automatique", "Manuelle"

DOMAINES = ["Identité", "Matériel", "Système", "Sécurité", "Logiciels", "Environnement", "Journaux"]


def _c(domaine, libelle, gravite, correction, consigne=""):
    return {"domaine": domaine, "libelle": libelle, "gravite": gravite, "correction": correction, "consigne": consigne}


CATALOGUE = {
    "IDENT_MACHINE": _c("Identité", "Nom de la machine conforme à la convention", MAJEUR, AUTO),
    "IDENT_COMPTE_ADMIN": _c(
        "Identité", "Compte d'administration technique présent et actif", BLOQUANT, MANUELLE,
        "Créer le compte local d'administration technique défini dans le profil (« Gestion de l'ordinateur > Utilisateurs et groupes locaux »), "
        "l'ajouter au groupe Administrateurs, vérifier qu'il est activé, puis lui attribuer le mot de passe du service."),
    "IDENT_COMPTE_LOCAL": _c("Identité", "Aucun compte local en dehors de la liste du profil", BLOQUANT, AUTO),
    "MAT_RAM": _c("Matériel", "Mémoire vive au moins égale au seuil", MAJEUR, MANUELLE,
                  "Rajouter de la mémoire vive afin d'atteindre le seuil requis"),
    "MAT_STOCKAGE": _c("Matériel", "Espace disque libre au moins égal au seuil", MAJEUR, MANUELLE,
                       "Rajouter du stockage afin d'atteindre le seuil requis"),
    "MAT_SMART": _c("Matériel", "Santé S.M.A.R.T. du disque correcte", BLOQUANT, MANUELLE,
                    "Suite à l'analyse SMART de votre disque, renvoyer le poste au stock"),
    "MAT_TYPE_SUPPORT": _c("Matériel", "Type de support identifié et entretien adapté effectué", MINEUR, AUTO),
    "SYS_OS_VERSION": _c("Système", "Édition et version de Windows attendues", BLOQUANT, MANUELLE,
                         "Merci d'installer et d'utiliser la bonne édition et version de Windows"),
    "SYS_TURN_ON": _c("Système", "État d'activation conforme à l'exigence du profil", MAJEUR, MANUELLE,
                      "Activer Windows avec une licence valide (« Paramètres > Système > Activation »)"),
    "SYS_SERV_TIME": _c("Système", "Heure synchronisée avec le serveur de temps, écart sous le seuil", MAJEUR, AUTO),
    "SYS_IP": _c("Système", "Adresse IP obtenue par DHCP, aucune adresse fixe résiduelle", MAJEUR, AUTO),
    "SEC_ANTIVIRUS": _c("Sécurité", "Antivirus actif, protection en temps réel", BLOQUANT, MANUELLE,
                        "Veuillez activer votre antivirus"),
    "SEC_SIGN": _c("Sécurité", "Signatures antivirus plus récentes que le seuil", MAJEUR, AUTO),
    "SEC_BITLOCKER": _c("Sécurité", "État de BitLocker conforme à l'exigence du profil", BLOQUANT, MANUELLE,
                        "Activer BitLocker sur le disque système, puis déposer la clé de récupération à l'emplacement indiqué dans la configuration"),
    "SEC_PROFILS": _c("Sécurité", "Les 3 profils du pare-feu actifs", BLOQUANT, AUTO),
    "SEC_MAJ_WINDOWS": _c("Sécurité", "Service de mise à jour de Windows actif et démarrable", BLOQUANT, AUTO),
    "SEC_MAJ": _c("Sécurité", "Mises à jour en attente sous le seuil", MAJEUR, AUTO),
    "LOG_WINGET": _c("Logiciels", "Chaque logiciel du socle géré par winget présent", MAJEUR, AUTO),
    "LOG_FORB": _c("Logiciels", "Aucun logiciel interdit", MAJEUR, MANUELLE,
                   "Désinstaller le logiciel interdit signalé par l'application"),
    "LOG_START": _c("Logiciels", "Services requis démarrés, en démarrage automatique", MINEUR, AUTO),
    "ENV_NUM_PAD": _c("Environnement", "Pavé numérique actif au démarrage", MINEUR, AUTO),
    "ENV_HIDDEN_FILES": _c("Environnement", "Extensions et fichiers cachés visibles, confirmation de suppression active", MINEUR, AUTO),
    "ENV_CHROME_START": _c("Environnement", "Page de démarrage de Chrome imposée par stratégie", MINEUR, AUTO),
    "ENV_PRINT": _c("Environnement", "Imprimante du service présente", MAJEUR, MANUELLE,
                    "Ajouter l'imprimante dont le nom est affiché, avec son chemin réseau s'il est défini dans le profil"),
    "JRN_CRITICAL_EVENT": _c("Journaux", "Nombre d'événements critiques sur les dernières 24 h au plus égal au seuil", MINEUR, MANUELLE,
                             "Consulter la liste affichée des événements critiques des dernières 24 h, en identifier la cause et la corriger"),
}