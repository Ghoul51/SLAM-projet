"""Session de recette : passes, corrections, fichier de reprise (F11, RG07, §3.2). Aucune dépendance à Tkinter."""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from catalogue import CATALOGUE
from comparaison import Resultat

NOM_FICHIER_REPRISE = "session_en_cours.json"   # le DOSSIER vient de la configuration (RG04), pas le nom
VERSION_FORMAT = 1


class ErreurSession(Exception):
    """Fichier de reprise illisible ou incohérent : à afficher en clair, sans trace Python."""


@dataclass
class CorrectionAppliquee:
    """Une correction lancée par l'opérateur, avec ce qu'elle a renvoyé."""
    identifiant: str
    statut: str
    message: str
    motif: str
    heure: str


@dataclass
class Session:
    debut: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    profil_fichier: str = ""                           # nom du fichier de profil sans extension (valeur de la liste déroulante)
    profil_nom: str = ""
    profil_version: str = ""
    profil_empreinte: str = ""                         # SHA-256 : prouve que le profil n'a pas changé entre les 2 passes
    initiale: dict | None = None                       # identifiant -> Resultat de la 1re recette complète
    corrections: list = field(default_factory=list)    # liste de CorrectionAppliquee, dans l'ordre

    def a_passe_initiale(self):
        return self.initiale is not None

    def enregistrer_initiale(self, resultats, profil):
        """Copie la passe (l'interface vide son dictionnaire à chaque recette) et retient quel profil l'a produite."""
        self.initiale = dict(resultats)
        self.profil_fichier = profil.chemin.stem
        self.profil_nom = profil.nom
        self.profil_version = profil.version
        self.profil_empreinte = profil.empreinte

    def enregistrer_correction(self, identifiant, statut, message, motif):
        heure = datetime.now().isoformat(timespec="seconds")
        self.corrections.append(CorrectionAppliquee(identifiant, statut, message, motif, heure))

    # ---------- Fichier de reprise ----------

    def sauvegarder(self, dossier):
        """Écrit la session dans le dossier configuré. Écriture atomique : fichier temporaire, puis remplacement."""
        dossier = Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        donnees = {
            "format": VERSION_FORMAT,
            "debut": self.debut,
            "profil": {"fichier": self.profil_fichier, "nom": self.profil_nom,
                       "version": self.profil_version, "empreinte": self.profil_empreinte},
            "initiale": {i: asdict(r) for i, r in (self.initiale or {}).items()},
            "corrections": [asdict(c) for c in self.corrections],
        }
        chemin = dossier / NOM_FICHIER_REPRISE
        temporaire = chemin.with_suffix(".tmp")
        temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
        temporaire.replace(chemin)   # un redémarrage en plein milieu laisse l'ancien fichier intact

    @staticmethod
    def charger(dossier):
        """Renvoie la session enregistrée, None s'il n'y en a pas, ou lève ErreurSession si le fichier est inutilisable."""
        chemin = Path(dossier) / NOM_FICHIER_REPRISE
        if not chemin.is_file():
            return None
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
            if donnees["format"] != VERSION_FORMAT:
                raise ValueError(f"format {donnees['format']} non géré")
            inconnus = [i for i in donnees["initiale"] if i not in CATALOGUE]
            if inconnus:
                raise ValueError(f"contrôle inconnu : {inconnus[0]}")
            profil = donnees["profil"]
            session = Session(
                debut=donnees["debut"],
                profil_fichier=profil["fichier"], profil_nom=profil["nom"],
                profil_version=profil["version"], profil_empreinte=profil["empreinte"],
                initiale={i: Resultat(**r) for i, r in donnees["initiale"].items()},
                corrections=[CorrectionAppliquee(**c) for c in donnees["corrections"]],
            )
        except (OSError, ValueError, KeyError, TypeError) as erreur:   # JSONDecodeError et UnicodeDecodeError sont des ValueError
            raise ErreurSession(f"{chemin} : fichier de reprise illisible ({erreur!r})")
        if not session.initiale:
            raise ErreurSession(f"{chemin} : fichier de reprise sans passe initiale")
        return session

    @staticmethod
    def supprimer(dossier):
        (Path(dossier) / NOM_FICHIER_REPRISE).unlink(missing_ok=True)