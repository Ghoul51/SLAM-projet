# Plan de tests

Environnement : poste de développement, Python 3.14.7, tests lancés depuis le dossier `src`.

| N° | État de départ | Action | Résultat attendu | Résultat obtenu |
|---|---|---|---|---|
| T01 | `recette.ini` complet | `python main.py` | La configuration s'affiche | Conforme : la configuration s'affiche, les dossiers profils, pv et journal sont rattachés à la racine du projet, opérateur « Louis », délai 120 s |
| T02 | `recette.ini` renommé | `python main.py` | Message « introuvable », sans trace d'erreur Python | Conforme : « ERREUR : Fichier de configuration introuvable » avec le chemin complet, aucune trace Python |
| T03 | Clé `delai_max_secondes` supprimée de `recette.ini` | `python main.py` | Message qui nomme la clé et la section, sans trace Python | Conforme : « la clé « delai_max_secondes » de la section [commandes] est absente ou vide » |
| T04 | Les 3 profils JSON valides | `python main.py` | Nom, version et empreinte SHA-256 de chaque profil | Conforme : POSTE-ACCUEIL, POSTE-COMPTABLE et POSTE-DIRECTION chargés en version 1.0, avec une empreinte de 64 caractères chacun (POSTE-COMPTABLE : `1a11ccc7...`) |
| T05 | `POSTE-ACCUEIL.json` : virgule supprimée après la version | `python main.py` | Erreur de syntaxe avec le fichier, la ligne et la colonne | Conforme : « erreur de syntaxe JSON, ligne ..., colonne ... », aucune trace Python |
| T06 | `POSTE-COMPTABLE.json` : `"minimum_go": -1` | `python main.py` | Refus avec la clé concernée et « ne peut pas être négatif » | Conforme : refus sur `materiel.MAT_RAM.minimum_go`, « ne peut pas être négatif » |
| T07 | `POSTE-COMPTABLE.json` : `"actif": false` sur `SEC_BITLOCKER` | `python main.py` | Refus : contrôle obligatoire, impossible à désactiver | Conforme : refus sur `securite.SEC_BITLOCKER.actif`, « contrôle obligatoire : il ne peut pas être désactivé » |
| T08 | `POSTE-COMPTABLE.json` : `"maximum": 2` remplacé par `3` pour `SEC_MAJ` | `python main.py` | Profil accepté et empreinte différente de la précédente | Conforme : profil accepté, empreinte changée (`...` au lieu de `1a11ccc7...`) |
| T09 | `powershell.py` et `recette.ini` en place | Commande `Get-CimInstance Win32_OperatingSystem \| Select-Object Caption, Version` | Un résultat structuré (dictionnaire) | Conforme : `Caption` et `Version` renvoyés (poste de développement) |
| T10 | Idem | Commande qui renvoie `'été à Reims'` | Accents corrects | Conforme : `été à Reims` |
| T11 | Idem | `Get-Item C:\dossier-inexistant` | Erreur capturée, message explicite, aucune trace Python | Conforme : « PowerShell a renvoyé une erreur : Get-Item : Impossible de trouver le chemin d'accès... » |
| T12 | Idem, délai fixé à 2 s | `Start-Sleep -Seconds 5` | Message « Délai dépassé », sans blocage | Conforme : « Délai dépassé (2 s) : la commande n'a pas répondu » |
| T13 | `sondes.py` (identité et matériel), poste de développement | `python main.py` | 7 valeurs lues, sans erreur ni plantage | Conforme : 7 sondes renvoient une valeur (nom, compte admin absent, comptes actifs, RAM, espace libre, santé et type du disque). Les résultats qui font foi seront ceux de la VM (voir T-VM) |
| T14 | `sondes.py` (17 sondes), poste de développement, sans droits administrateur | `python main.py` | 17 valeurs ou états indéterminés avec raison, sans plantage | Conforme : 16 valeurs lues ; `SEC_BITLOCKER` indéterminé (accès refusé), sans plantage. Défaut corrigé : source de temps lue dans le registre au lieu du texte de `w32tm` |
| T15 | `sondes.py` (25 sondes), poste de développement, sans droits administrateur | `python main.py` | 25 lignes : valeurs lues ou états indéterminés avec raison, sans plantage | Conforme : 24 valeurs lues ; `SEC_BITLOCKER` indéterminé (accès refusé) ; les 3 emplacements du registre sont lus pour les logiciels |

Les tests T05 à T08 montrent qu'un profil cassé est refusé proprement (RG05) et qu'une modification du profil change son empreinte (section 3.3.11) sans toucher au code.