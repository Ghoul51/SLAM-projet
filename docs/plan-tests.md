# Plan de tests

Environnement : poste de développement, Python 3.14.7, tests lancés depuis le dossier `src`.

| N° | État de départ | Action | Résultat attendu | Résultat obtenu |
|---|---|---|---|---|
| T01 | `recette.ini` complet | `python main.py` | La configuration s'affiche | Conforme : la configuration s'affiche, les dossiers profils, pv et journal sont rattachés à la racine du projet, opérateur « Louis », délai 120 s |
| T02 | `recette.ini` renommé | `python main.py` | Message « introuvable », sans trace d'erreur Python | Conforme : « ERREUR : Fichier de configuration introuvable » avec le chemin complet, aucune trace Python |
| T03 | Clé `delai_max_secondes` supprimée de `recette.ini` | `python main.py` | Message qui nomme la clé et la section, sans trace Python | Conforme : « la clé « delai_max_secondes » de la section [commandes] est absente ou vide » |
| T04 | Les 3 profils JSON valides | `python main.py` | Nom, version et empreinte SHA-256 de chaque profil | (à remplir) |
| T05 | Profil avec une virgule supprimée | `python main.py` | Erreur de syntaxe avec le fichier, la ligne et la colonne | (à remplir) |
| T06 | Profil avec `"minimum_go": -1` | `python main.py` | Refus avec la clé concernée et « ne peut pas être négatif » | (à remplir) |
| T07 | Profil avec `"actif": false` sur `SEC_BITLOCKER` | `python main.py` | Refus : contrôle obligatoire, impossible à désactiver | (à remplir) |
| T08 | Profil valide, une valeur modifiée | `python main.py` | L'empreinte SHA-256 change | (à remplir) |

## Tests à ajouter au fil du projet (section 3.4.3)

- Instantané « conforme » : tous les contrôles actifs verts, les désactivés en gris, aucun bouton « Corriger » actif
- Instantané « dégradé » : chaque écart introduit par le script est détecté, et aucun autre
- Chaque correction automatique applicable au banc, une par une, avec relecture du contrôle
- Chaque correction manuelle applicable au banc, faite à la main puis relue
- Cas d'erreur : commande qui dépasse son délai, droits d'administrateur
- Idempotence (RG10) : une correction lancée deux fois ne change rien