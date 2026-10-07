| ID | Domaine | Libellé | Gravité | Source | Correction | Consigne |
|---|---|---|---|---|---|---|
| IDENT_MACHINE | Identité | Nom de la machine conforme à la convention PC-EXP-nnn | Majeur | Bibliothèque standard | Automatique : renommage, redémarrage annoncé | ... |
| IDENT_COMPTE_ADMIN | Identité | Compte d'administration technique adm-experty présent et actif | Bloquant | PowerShell avec WMI | Manuelle : le technicien le crée avec le mot de passe du service | Créer le compte local d'administration technique défini dans le profil (« Gestion de l'ordinateur > Utilisateurs et groupes locaux »), l'ajouter au groupe Administrateurs, vérifier qu'il est activé, puis lui attribuer le mot de passe du service. |
| IDENT_COMPTE_LOCAL | Identité | Aucun compte local en dehors de la liste du profil | Bloquant | PowerShell avec WMI | Automatique : désactivation du compte, jamais suppression | ... |
| MAT_RAM | Matériel | Mémoire vive au moins égale au seuil | Majeur | PowerShell avec WMI | Manuelle | Rajouter de la mémoire vive afin d'atteindre le seuil requis | 
| MAT_STOCKAGE | Matériel | Espace disque libre au moins égal au seuil | Majeur | PowerShell avec WMI | Manuelle | Rajouter du stockage afin d'atteindre le seuil requis |
| MAT_SMART | Matériel | Santé S.M.A.R.T. du disque correcte | Bloquant | PowerShell avec WMI | Manuelle : Le poste retourne au stock | Suite à l'analyse SMART de votre disque, renvoyer ce dernier au stock |
| MAT_TYPE_SUPPORT | Matériel | Type de support identifié (plateaux ou mémoire flash) et entretien adapté effectué | Mineur | PowerShell avec WMI | Automatique : Analyse et défragmentation, ou TRIM | ... |
| SYS_OS_VERSION | Système | Édition et version de Windows attendues | Bloquant | PowerShell avec WMI | Manuelle | Merci d'installer et d'utiliser la bonne édition et version de Windows |
| SYS_TURN_ON | Système | État d'activation conforme à l'exigence du profil | Majeur | PowerShell avec WMI | Manuelle | (je ne sais pas) |
| SYS_SERV_TIME | Système | Heure synchronisée avec le serveur de temps, écart sous le seuil | Majeur | PowerShell avec WMI | Automatique : serveur de temps configuré et resynchronisation | ... |
| SYS_IP | Système | Adresse IP obtenue par DHCP, aucune adresse fixe résiduelle | Majeur | PowerShell avec WMI | Automatique : retour au DHCP pour l'adresse et le DNS | ... |
| SEC_ANTIVIRUS | Sécurité | Antivirus actif, protection en temps réel | Bloquant | PowerShell avec WMI | Manuelle | Veuillez activer votre antivirus |
| SEC_SIGN | Sécurité | Signatures antivirus plus récentes que le seuil | Majeur | PowerShell avec WMI | Automatique : mise à jour des signatures | ... |
| SEC_BITLOCKER