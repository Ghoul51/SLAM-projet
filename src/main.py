import ctypes
import sys
import tkinter as tk
from tkinter import messagebox

from configuration import ErreurConfiguration, charger_configuration
from interface import Application


def est_administrateur():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def afficher_erreur(message):
    racine = tk.Tk()
    racine.withdraw()
    messagebox.showerror("Recette des postes", message)
    racine.destroy()


def main():
    try:
        config = charger_configuration()
    except ErreurConfiguration as erreur:
        afficher_erreur(str(erreur))
        sys.exit(1)
    Application(config, est_administrateur()).lancer()


if __name__ == "__main__":
    main()