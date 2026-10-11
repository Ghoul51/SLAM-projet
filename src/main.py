import sys

from configuration import ErreurConfiguration, charger_configuration


def main():
    try:
        config = charger_configuration()
    except ErreurConfiguration as erreur:
        print(f"ERREUR : {erreur}")
        sys.exit(1)
    print(config)


if __name__ == "__main__":
    main()