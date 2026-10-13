import sys

from comparaison import calculer_verdict, evaluer_profil
from configuration import ErreurConfiguration, charger_configuration
from profil import ErreurProfil, charger_profil, lister_profils


def main():
    try:
        config = charger_configuration()
        # Test : le 2e profil par ordre alphabétique (POSTE-COMPTABLE)
        profil = charger_profil(lister_profils(config.dossier_profils)[1])
    except (ErreurConfiguration, ErreurProfil) as erreur:
        print(f"ERREUR : {erreur}")
        sys.exit(1)

    resultats = evaluer_profil(profil, config.delai_max_secondes)
    for r in resultats:
        print(f"[{r.etat}] {r.identifiant} | {r.message}")
    verdict = calculer_verdict(resultats)
    print(f"\nVERDICT : {verdict.verdict} {verdict.motifs} | réserves : {verdict.reserves}")


if __name__ == "__main__":
    main()