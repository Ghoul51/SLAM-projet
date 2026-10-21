| N° | Dégradation | Contrôle détecté | Ce que fait le script | Effet visible |
|----|-------------|------------------|-----------------------|---------------|
| 1 | Nom de machine non conforme | IDENT_MACHINE | Renomme la machine en `DESKTOP-K4N2P1` | Après redémarrage |
| 2 | Compte local non prévu | IDENT_COMPTE_LOCAL | Crée le compte `stagiaire` (sans mot de passe) | Immédiat |
| 3 | Adresse IP fixe | SYS_IP | Remplace le DHCP par une adresse IP fixe écrite explicitement | Immédiat |
| 4 | Profil de pare-feu désactivé | SEC_PROFILS | Désactive le profil Public | Immédiat |
| 5 | Logiciel du socle désinstallé | LOG_WINGET | Désinstalle 7-Zip | Immédiat |
| 6 | Logiciel interdit installé | LOG_FORB | Installe qBittorrent | Immédiat |
| 7 | Service arrêté et désactivé | LOG_START | Arrête `Audiosrv` et le met en démarrage désactivé | Immédiat |
| 8 | Pavé numérique inactif | ENV_NUM_PAD | Remet la valeur par défaut dans le registre (HKCU) | Immédiat |
| 9 | Extensions, fichiers cachés, confirmation de suppression remis par défaut | ENV_HIDDEN_FILES | Remet les réglages de l'explorateur par défaut (HKCU) | Immédiat |
| 10 | Page de démarrage de Chrome supprimée | ENV_CHROME_START | Supprime la stratégie Chrome (HKLM) | Immédiat |
| 11 | Imprimante supprimée | ENV_PRINT | Supprime `Imprimante-Comptabilite` | Immédiat |

## Choix notables
- Le service dégradé est `Audiosrv` : arrêter le Spooler rendrait `ENV_PRINT` indéterminé.