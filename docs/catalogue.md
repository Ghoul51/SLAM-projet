| ID | Domaine | Libellé | Gravité | Source | Correction | Consigne |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| IDENT_MACHINE | Identité | Nom de la machine conforme à la convention PC-EXP-... | Majeur | Bibliothèque standard | Automatique : renommage, redémarrage annoncé | ... |
| IDENT_COMPTE_ADMIN | Identité | Compte d'administration technique adm-experty présent et actif | Bloquant | PowerShell avec WMI | Manuelle : le technicien le crée avec le mot de passe du service | Créer le compte local d'administration technique défini dans le profil (« Gestion de l'ordinateur > Utilisateurs et groupes locaux »), l'ajouter au groupe Administrateurs, vérifier qu'il est activé, puis lui attribuer le mot de passe du service. |
| IDENT_COMPTE_LOCAL | Identité | Aucun compte local en dehors de la liste du profil | Bloquant | PowerShell avec WMI | Automatique : désactivation du compte, jamais suppression | ... |
| MAT_RAM | Matériel | Mémoire vive au moins égale au seuil | Majeur | PowerShell avec WMI | Manuelle | Rajouter de la mémoire vive afin d'atteindre le seuil requis | 
| MAT_STOCKAGE | Matériel | Espace disque libre au moins égal au seuil | Majeur | PowerShell avec WMI | Manuelle | Rajouter du stockage afin d'atteindre le seuil requis |
| MAT_SMART | Matériel | Santé S.M.A.R.T. du disque correcte | Bloquant | PowerShell avec WMI | Manuelle : Le poste retourne au stock | Suite à l'analyse SMART de votre disque, renvoyer le poste au stock |
| MAT_TYPE_SUPPORT | Matériel | Type de support identifié (plateaux ou mémoire flash) et entretien adapté effectué | Mineur | PowerShell avec WMI | Automatique : Analyse et défragmentation, ou TRIM | ... |
| SYS_OS_VERSION | Système | Édition et version de Windows attendues | Bloquant | PowerShell avec WMI | Manuelle | Merci d'installer et d'utiliser la bonne édition et version de Windows |
| SYS_TURN_ON | Système | État d'activation conforme à l'exigence du profil | Majeur | PowerShell avec WMI | Manuelle | Activer Windows avec une licence valide (« Paramètres > Système > Activation ») |
| SYS_SERV_TIME | Système | Heure synchronisée avec le serveur de temps, écart sous le seuil | Majeur | PowerShell avec WMI | Automatique : serveur de temps configuré et resynchronisation | ... |
| SYS_IP | Système | Adresse IP obtenue par DHCP, aucune adresse fixe résiduelle | Majeur | PowerShell avec WMI | Automatique : retour au DHCP pour l'adresse et les DNS | ... |
| SEC_ANTIVIRUS | Sécurité | Antivirus actif, protection en temps réel | Bloquant | PowerShell avec WMI | Manuelle | Veuillez activer votre antivirus |
| SEC_SIGN | Sécurité | Signatures antivirus plus récentes que le seuil | Majeur | PowerShell avec WMI | Automatique : mise à jour des signatures | ... |
| SEC_BITLOCKER | Sécurité | État de BitLocker conforme à l'exigence du profil | Bloquant | PowerShell avec WMI | Manuelle : activer, et déposer la clé de récupération à l'emplacement indiqué par la configuration | Activer BitLocker sur le disque système, puis déposer la clé de récupération à l'emplacement indiqué dans la configuration |
| SEC_PROFILS | Sécurité | Les 3 profils du pare-feu actifs | Bloquant | PowerShell avec WMI | Automatique | ... |
| SEC_MAJ_WINDOWS | Sécurité | Service de mise à jour de Windows actif et démarrable | Bloquant | PowerShell avec WMI | Automatique : réactivation du service | ... |
| SEC_MAJ | Sécurité | Mises à jour en attente sous le seuil | Majeur | PowerShell avec WMI | Automatique : recherche et installation déclenchées, vert après redémarrage | ... |
| LOG_WINGET | Logiciels | Chaque logiciel du socle géré par winget présent | Majeur | Registre Windows | Automatique : Installation par winget | ... |
| LOG_FORB | Logiciels | Aucun logiciel interdit | Majeur | Registre Windows | Manuelle : Désinstallation par le technicien | Désinstaller le logiciel interdit signalé par l'application |
| LOG_START | Logiciels | Services requis démarrés, en démarrage automatique | Mineur | PowerShell avec WMI |Automatique | ... |
| ENV_NUM_PAD | Environnement | Pavé numérique actif au démarrage | Mineur | Registre Windows | Automatique | ... |
| ENV_HIDDEN_FILES | Environnement | Extensions et fichiers cachés visibles, confirmation de suppression active | Mineur | Registre Windows | Automatique | ... |
| ENV_CHROME_START | Environnement | Page de démarrage de Chrome imposée par stratégie | Mineur | Registre Windows | Automatique | ... |
| ENV_PRINT | Environnement | Imprimante du service présente | Majeur | PowerShell avec WMI | Manuelle : nom affiché, et chemin réseau s'il est défini dans le profil | Ajouter l'imprimante dont le nom est affiché, avec son chemin réseau s'il est défini dans le profil |
| JRN_CRITICAL_EVENT | Journaux | Nombre d'événements critiques sur les dernières 24 h au plus égal au seuil du profil | Mineur | PowerShell avec WMI | Manuelle : La liste des événements est affichée | Consulter la liste affichée des événements critiques des dernières 24 h, en identifier la cause et la corriger |