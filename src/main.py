import sys

from configuration import ErreurConfiguration, charger_configuration
from profil import ErreurProfil, charger_profil, lister_profils


def main():
    try:
        config = charger_configuration()
        for chemin in lister_profils(config.dossier_profils):
            profil = charger_profil(chemin)
            print(profil.nom, profil.version, profil.empreinte)
    except (ErreurConfiguration, ErreurProfil) as erreur:
        print(f"ERREUR : {erreur}")
        sys.exit(1)


if __name__ == "__main__":
    main()