"""Cas reproductible documenté (§3.4.3) : choix de l'entretien du disque selon le type de support.

Sur la machine virtuelle, Windows n'expose souvent pas le type de support (« Unspecified »).
Ce script simule les 3 cas sans rien exécuter sur le poste : il affiche seulement la décision de la correction.
Lancement (VM) : python-tk/python.exe -B banc_essai/test_entretien_disque.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from corrections import commandes_entretien

CAS = [
    ("HDD", "disque à plateaux : analyse puis défragmentation"),
    ("SSD", "mémoire flash : TRIM, aucune défragmentation"),
    ("Unspecified", "type non détecté : la correction refuse"),
    ("", "valeur vide : la correction refuse"),
]

for support, attendu in CAS:
    gestes = commandes_entretien(support)
    print(f"Support « {support} » ({attendu})")
    if gestes is None:
        print("   -> REFUS : rien n'est lancé")
    else:
        for geste in gestes:
            print("   ->", geste)