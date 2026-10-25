"""Procès-verbal de recette au format PDF (F11, §3.3.11). Aucune dépendance à Tkinter."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from catalogue import AUTO, CATALOGUE, MANUELLE
from comparaison import (CONFORME, ECART, INDETERMINE, NON_EVALUE, V_CONFORME, V_NON_CONFORME,
                         V_RESERVES, calculer_verdict)

COULEURS_ETAT = {CONFORME: (200, 240, 200), ECART: (245, 181, 181), INDETERMINE: (255, 217, 160), NON_EVALUE: (221, 221, 221)}
COULEURS_VERDICT = {V_CONFORME: (200, 240, 200), V_RESERVES: (255, 217, 160), V_NON_CONFORME: (245, 181, 181)}
LARGEURS = (55, 50, 50, 52, 50, 20)   # total 277 mm : A4 paysage, marges de 10 mm
LONGUEUR_MAX_CELLULE = 150

# Les polices PDF de base ne contiennent pas ces symboles : on les remplace avant d'écrire.
REMPLACEMENTS = {"≥": ">=", "≤": "<=", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                 "œ": "oe", "Œ": "OE", "→": "->", "•": "-"}


@dataclass
class ContextePV:
    """Tout ce qu'il faut au PV, copié par le thread principal : le thread de travail ne lit jamais l'interface."""
    profil: object          # Profil : nom, version, date_validation, empreinte
    operateur: str
    version_application: str
    horodatage: datetime
    debut_session: str
    initiale: dict          # identifiant -> Resultat de la passe initiale
    corrections: list       # CorrectionAppliquee, dans l'ordre
    finale: dict            # identifiant -> Resultat de la passe finale


def texte_pdf(texte):
    """Rend un texte écrivable avec les polices de base (Latin-1) : jamais d'exception, au pire un « ? »."""
    texte = unicodedata.normalize("NFKC", str(texte))
    for ancien, nouveau in REMPLACEMENTS.items():
        texte = texte.replace(ancien, nouveau)
    return texte.encode("latin-1", "replace").decode("latin-1")


def _court(texte, longueur=LONGUEUR_MAX_CELLULE):
    texte = texte_pdf(texte)
    return texte if len(texte) <= longueur else texte[:longueur - 3].rstrip() + "..."


def _valeur(resultat):
    if resultat is None:
        return "-"
    if resultat.etat == NON_EVALUE:
        return "non évalué"
    if resultat.etat == INDETERMINE:
        return f"indéterminé : {resultat.message}"
    return resultat.constate or "-"


def _action(identifiant, ctx):
    """Colonne « correction appliquée ou geste manuel » (§3.3.11)."""
    initial, final = ctx.initiale.get(identifiant), ctx.finale.get(identifiant)
    if final is None or final.etat == NON_EVALUE:
        return "-"
    faites = [c for c in ctx.corrections if c.identifiant == identifiant]
    if faites:
        derniere = faites[-1]
        heure = derniere.heure[11:16]
        motif = f" ({derniere.motif})" if derniere.motif else ""
        return f"Correction automatique à {heure} : {derniere.statut}{motif}"
    if initial is not None and initial.etat == CONFORME:
        return "Aucune action nécessaire" if final.etat == CONFORME else "Aucune correction appliquée"
    if CATALOGUE[identifiant]["correction"] == MANUELLE:
        if final.etat == CONFORME:
            return "Geste manuel effectué, vérifié par relecture"
        return "Geste manuel à faire : " + CATALOGUE[identifiant]["consigne"]
    return "Aucune correction appliquée" if final.etat != CONFORME else "Conforme à la relecture, sans correction de l'application"


class _Document(FPDF):
    def __init__(self, pied):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.pied = texte_pdf(pied)
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(auto=True, margin=14)
        self.alias_nb_pages()

    def footer(self):
        self.set_y(-10)
        self.set_font("helvetica", size=7)
        self.set_text_color(90, 90, 90)
        self.cell(0, 5, f"{self.pied}  -  Page {self.page_no()}/{{nb}}", align="C")
        self.set_text_color(0, 0, 0)


def _entete(pdf, ctx, poste):
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 8, texte_pdf("PROCÈS-VERBAL DE RECETTE"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=9)
    pdf.cell(0, 5, texte_pdf("EXPERTY - Service informatique - recette d'un poste déployé"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    blocs = (
        ("Poste", (f"Nom : {poste['nom']}", f"Numéro de série : {poste['serie']}",
                   f"Modèle : {poste['modele']}", f"Adresse MAC : {poste['mac']}")),
        ("Profil de référence", (f"Nom : {ctx.profil.nom}", f"Version : {ctx.profil.version}",
                                 f"Validé le : {ctx.profil.date_validation}",
                                 f"Empreinte SHA-256 : {ctx.profil.empreinte}")),
        ("Contexte", (f"Date et heure : {ctx.horodatage:%d/%m/%Y à %H:%M}", f"Opérateur : {ctx.operateur}",
                      f"Version de l'application : {ctx.version_application}",
                      f"Session démarrée le : {ctx.debut_session.replace('T', ' à ')}")),
    )
    y_depart = pdf.get_y()
    y_fin = y_depart
    for rang, (titre, lignes) in enumerate(blocs):
        x = 10 + rang * 93
        pdf.set_xy(x, y_depart)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(88, 5, texte_pdf(titre), new_x="LEFT", new_y="NEXT")
        pdf.set_font("helvetica", size=8)
        for ligne in lignes:
            pdf.set_x(x)
            pdf.multi_cell(88, 4, texte_pdf(ligne), align="L", new_x="LEFT", new_y="NEXT")
        y_fin = max(y_fin, pdf.get_y())
    pdf.set_xy(10, y_fin + 4)


def _tableau(pdf, ctx):
    pdf.set_font("helvetica", size=7)
    entetes = ("Contrôle", "Attendu", "Constaté initial", "Correction appliquée ou geste manuel", "Constaté final", "Statut")
    with pdf.table(col_widths=LARGEURS, line_height=3.3, text_align="LEFT",
                   headings_style=FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=(70, 70, 70))) as table:
        ligne = table.row()
        for titre in entetes:
            ligne.cell(texte_pdf(titre))
        for identifiant, fiche in CATALOGUE.items():
            initial, final = ctx.initiale.get(identifiant), ctx.finale[identifiant]
            attendu = (final.attendu or (initial.attendu if initial else "")) or "-"
            ligne = table.row()
            ligne.cell(_court(fiche["libelle"]))
            ligne.cell(_court(attendu))
            ligne.cell(_court(_valeur(initial)))
            ligne.cell(_court(_action(identifiant, ctx)))
            ligne.cell(_court(_valeur(final)))
            ligne.cell(texte_pdf(final.etat), style=FontFace(emphasis="BOLD", fill_color=COULEURS_ETAT[final.etat]))


def _compteurs(resultats):
    etats = [r.etat for r in resultats.values()]
    return (f"{etats.count(CONFORME)} conforme(s), {etats.count(ECART)} écart(s), "
            f"{etats.count(INDETERMINE)} indéterminé(s), {etats.count(NON_EVALUE)} non évalué(s)")


def _conclusion(pdf, ctx, verdict):
    if pdf.get_y() > pdf.h - 75:   # le bloc final (verdict, réserves, signature) ne se coupe pas entre 2 pages
        pdf.add_page()
    pdf.ln(4)
    pdf.set_fill_color(*COULEURS_VERDICT[verdict.verdict])
    pdf.set_font("helvetica", "B", 13)
    pdf.cell(0, 9, texte_pdf(f"VERDICT : {verdict.verdict}"), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=8)
    if verdict.motifs:
        pdf.cell(0, 5, texte_pdf("Motif : " + ", ".join(verdict.motifs)), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, texte_pdf("Passe initiale : " + _compteurs(ctx.initiale)), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, texte_pdf("Passe finale : " + _compteurs(ctx.finale)), new_x="LMARGIN", new_y="NEXT")
    if verdict.reserves:
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(0, 5, texte_pdf("Réserves (écarts mineurs) :"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", size=8)
        for identifiant in verdict.reserves:
            ligne = f"- {CATALOGUE[identifiant]['libelle']} : {ctx.finale[identifiant].constate}"
            pdf.cell(0, 4, _court(ligne, 200), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("helvetica", size=9)
    pdf.cell(95, 6, texte_pdf(f"Opérateur : {ctx.operateur}"))
    pdf.cell(60, 6, texte_pdf(f"Date : {ctx.horodatage:%d/%m/%Y}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(110, 16, texte_pdf("Signature de l'opérateur :"), border=1)


def nom_fichier(nom_poste, horodatage):
    """Convention du sujet : PV_PC-EXP-042_2026-10-08_1435.pdf"""
    nom = re.sub(r"[^A-Za-z0-9_-]", "_", nom_poste)
    return f"PV_{nom}_{horodatage:%Y-%m-%d_%H%M}.pdf"


def _chemin_libre(dossier, nom_poste, horodatage):
    chemin = dossier / nom_fichier(nom_poste, horodatage)
    numero = 2
    while chemin.exists():   # 2 PV dans la même minute : on n'écrase jamais un procès-verbal archivé
        chemin = dossier / nom_fichier(nom_poste, horodatage).replace(".pdf", f"_{numero}.pdf")
        numero += 1
    return chemin


def generer_pv(dossier, poste, ctx):
    """Écrit le PV dans `dossier` ; renvoie (chemin du fichier, verdict)."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    verdict = calculer_verdict(list(ctx.finale.values()))
    pdf = _Document(f"Procès-verbal de recette - {poste['nom']} - {ctx.horodatage:%d/%m/%Y %H:%M}")
    pdf.add_page()
    _entete(pdf, ctx, poste)
    _tableau(pdf, ctx)
    _conclusion(pdf, ctx, verdict)
    chemin = _chemin_libre(dossier, poste["nom"], ctx.horodatage)
    pdf.output(str(chemin))
    return chemin, verdict