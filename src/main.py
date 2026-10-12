import sys

from configuration import ErreurConfiguration, charger_configuration
from profil import ErreurProfil, charger_profil, lister_profils
from sondes import SONDES, ErreurSonde


def main():
    try:
        config = charger_configuration()
        # Test : le 2e profil par ordre alphabétique (POSTE-COMPTABLE)
        profil = charger_profil(lister_profils(config.dossier_profils)[1])
    except (ErreurConfiguration, ErreurProfil) as erreur:
        print(f"ERREUR : {erreur}")
        sys.exit(1)

    for identifiant, sonde in SONDES.items():
        try:
            valeur = sonde(profil.controles[identifiant], config.delai_max_secondes)
        except ErreurSonde as erreur:
            valeur = f"INDÉTERMINÉ : {erreur}"
        print(f"{identifiant} : {valeur}")


if __name__ == "__main__":
    main()