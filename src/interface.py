"""Interface Tkinter (F6, F7, F8). Aucune commande système dans ce fichier (§3.4.1)."""
import json
import logging
import platform
import queue
import threading
import tkinter as tk
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from catalogue import AUTO, CATALOGUE, DOMAINES, MANUELLE
from comparaison import (CONFORME, ECART, INDETERMINE, NON_EVALUE, Resultat, calculer_verdict,
                         evaluer_controle, evaluer_profil)
from configuration import ErreurConfiguration, charger_configuration
from corrections import ATTENTE, CORRECTIONS, ECHEC, ResultatCorrection, appliquer, confirmation, saisie_requise
from journal import creer_journal
from profil import ErreurProfil, charger_profil, lister_profils
from pv import ContextePV, generer_pv
from session import ErreurSession, Session
from sondes import collecter_etat
from systeme import lire_identite_poste, ouvrir_dossier, ouvrir_fichier

VERSION_APPLICATION = "0.12"
LIBELLE_PV = "Éditer le procès-verbal"
EN_COURS = "En cours"
COULEURS = {CONFORME: "#c8f0c8", ECART: "#f5b5b5", INDETERMINE: "#ffd9a0", NON_EVALUE: "#dddddd", EN_COURS: "#cfe3f7"}
COLONNES = (
    ("controle", "Contrôle", 380),
    ("attendu", "Attendu", 240),
    ("constate", "Constaté", 240),
    ("statut", "Statut", 90),
    ("correction", "Correction", 100),
)
INTERVALLE_FILE_MS = 100
FILTRES = ("Tout", "Écarts seulement", "Indéterminés seulement")


class Application:
    def __init__(self, config, est_admin):
        self.config = config
        self.est_admin = est_admin
        self.chemins = {c.stem: c for c in lister_profils(config.dossier_profils)}
        self.profil = None                  # dernier profil chargé et validé
        self.resultats = {}                 # identifiant -> Resultat de la passe en cours
        self.file = queue.Queue()           # les threads de travail y déposent, le thread principal y lit
        self.en_cours = False               # une recette complète tourne
        self.corrections_en_cours = set()   # identifiants dont une correction tourne
        self.attentes = {}                  # identifiant -> motif de prise en compte (RG07)
        self.boucle_active = False          # la relève de la file est-elle programmée ?
        self.collecte_en_cours = False      # une « Collecte seule » tourne
        self.pv_en_cours = False            # un procès-verbal est en cours d'édition
        self.avancement_avant = 0           # valeur de la barre avant une collecte
        self.id_selectionne = None
        self.tableaux = {}                  # titre d'onglet -> Treeview
        self.session = Session()            # passe initiale + corrections appliquées (F11)

        self.fenetre = tk.Tk()
        self.fenetre.title("Recette des postes - EXPERTY")
        self.fenetre.geometry("1150x720")
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)   # la croix passe aussi par quitter()
        self.filtre = tk.StringVar(value=FILTRES[0])              # après Tk() : une StringVar a besoin de la fenêtre

        # Journal de session (RG06) : sans journal, aucune correction n'est autorisée.
        self.journal_ok = True
        try:
            self.journal = creer_journal(config.dossier_journal)
        except OSError as erreur:
            self.journal_ok = False
            self.journal = logging.getLogger("recette")
            self.journal.addHandler(logging.NullHandler())
            messagebox.showwarning(
                "Journal",
                f"Le journal de session n'a pas pu être créé : {erreur}\n\nLes corrections sont désactivées.")

        self._creer_menu()
        # L'ordre compte : zones du bas d'abord, onglets en dernier (ils prennent la place restante).
        self._creer_bandeau()
        self._creer_barre_etat()
        self._creer_detail()
        self._creer_onglets()
        self._maj_compteurs()
        self._maj_titres()

    # ---------- Création des zones ----------

    def _creer_menu(self):
        barre = tk.Menu(self.fenetre)

        fichier = tk.Menu(barre, tearoff=False)
        fichier.add_command(label="Choisir le profil…", command=self.choisir_profil)
        fichier.add_command(label="Recharger la configuration", command=self.recharger_configuration)
        fichier.add_command(label="Ouvrir le dossier des PV", command=self.ouvrir_dossier_pv)
        fichier.add_separator()
        fichier.add_command(label="Quitter", command=self.quitter)
        barre.add_cascade(label="Fichier", menu=fichier)

        recette = tk.Menu(barre, tearoff=False)
        recette.add_command(label="Lancer la recette", command=self.lancer_recette)
        recette.add_command(label="Rejouer les écarts", command=self.rejouer_ecarts)
        recette.add_command(label="Collecte seule", command=self.collecte_seule)
        recette.add_command(label=LIBELLE_PV, command=self.editer_pv, state="disabled")   # actif après une recette complète
        self.menu_recette = recette
        barre.add_cascade(label="Recette", menu=recette)

        affichage = tk.Menu(barre, tearoff=False)
        for texte in FILTRES:
            affichage.add_radiobutton(label=texte, variable=self.filtre, value=texte,
                                      command=self._appliquer_filtre)
        barre.add_cascade(label="Affichage", menu=affichage)

        aide = tk.Menu(barre, tearoff=False)
        aide.add_command(label="À propos", command=self.a_propos)
        barre.add_cascade(label="Aide", menu=aide)

        self.fenetre.config(menu=barre)

    def _creer_bandeau(self):
        bandeau = ttk.Frame(self.fenetre, padding=8)
        bandeau.pack(side="top", fill="x")

        ttk.Label(bandeau, text=f"Poste : {platform.node()}").pack(side="left")

        ttk.Label(bandeau, text="Profil :").pack(side="left", padx=(15, 3))
        self.choix_profil = ttk.Combobox(bandeau, state="readonly", values=list(self.chemins), width=22)
        if self.chemins:
            self.choix_profil.current(0)
        self.choix_profil.bind("<<ComboboxSelected>>", lambda evenement: self._charger_profil_choisi())
        self.choix_profil.pack(side="left")

        ttk.Label(bandeau, text="Opérateur :").pack(side="left", padx=(15, 3))
        self.operateur = tk.StringVar(value=self.config.operateur_defaut)
        ttk.Entry(bandeau, textvariable=self.operateur, width=18).pack(side="left")

        droits = "oui" if self.est_admin else "non"
        ttk.Label(bandeau, text=f"Droits administrateur : {droits}").pack(side="left", padx=15)

        self.bouton_lancer = ttk.Button(bandeau, text="Lancer la recette", command=self.lancer_recette)
        self.bouton_lancer.pack(side="right")

    def _creer_onglets(self):
        self.onglets = ttk.Notebook(self.fenetre)
        self.onglets.pack(side="top", fill="both", expand=True)
        for titre in ["Synthèse"] + DOMAINES:
            page = ttk.Frame(self.onglets)
            self.tableaux[titre] = self._creer_tableau(page)
            self.onglets.add(page, text=titre)

    def _creer_tableau(self, parent):
        tableau = ttk.Treeview(parent, columns=[c[0] for c in COLONNES], show="headings", selectmode="browse")
        for cle, titre, largeur in COLONNES:
            tableau.heading(cle, text=titre)
            tableau.column(cle, width=largeur, anchor="w")
        for etat, couleur in COULEURS.items():
            tableau.tag_configure(etat, background=couleur)
        defilement = ttk.Scrollbar(parent, orient="vertical", command=tableau.yview)
        tableau.configure(yscrollcommand=defilement.set)
        defilement.pack(side="right", fill="y")
        tableau.pack(side="left", fill="both", expand=True)
        tableau.bind("<<TreeviewSelect>>", self._selection)
        return tableau

    def _creer_detail(self):
        detail = ttk.Frame(self.fenetre, padding=8)
        detail.pack(side="bottom", fill="x")
        self.v_libelle = tk.StringVar()
        self.v_message = tk.StringVar()
        self.v_consigne = tk.StringVar()
        ttk.Label(detail, textvariable=self.v_libelle, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(detail, textvariable=self.v_message, wraplength=1050).pack(anchor="w")
        ttk.Label(detail, textvariable=self.v_consigne, wraplength=1050).pack(anchor="w")
        self.bouton_corriger = ttk.Button(detail, text="Corriger", state="disabled", command=self._corriger)
        self.bouton_corriger.pack(side="left", pady=4)
        self.bouton_relire = ttk.Button(detail, text="Relire ce contrôle", state="disabled", command=self._relire)
        self.bouton_relire.pack(side="left", padx=8, pady=4)

    def _creer_barre_etat(self):
        barre = ttk.Frame(self.fenetre, padding=4)
        barre.pack(side="bottom", fill="x")
        self.avancement = ttk.Progressbar(barre, length=220, maximum=len(CATALOGUE))
        self.avancement.pack(side="left")
        self.texte_compteurs = ttk.Label(barre)
        self.texte_compteurs.pack(side="left", padx=12)
        self.texte_verdict = ttk.Label(barre, font=("Segoe UI", 10, "bold"))
        self.texte_verdict.pack(side="right")

    # ---------- Actions du menu Fichier ----------

    def _occupe(self):
        return self.en_cours or bool(self.corrections_en_cours) or self.collecte_en_cours or self.pv_en_cours

    def _charger_profil_choisi(self):
        """Valide le profil sélectionné (RG05) et vide le tableau."""
        if self._occupe():
            return
        try:
            self.profil = charger_profil(self.chemins[self.choix_profil.get()])
        except ErreurProfil as erreur:
            self.profil = None
            messagebox.showerror("Profil invalide", str(erreur))
        self._vider_tableaux()
        self._nouvelle_session()

    def _nouvelle_session(self):
        """Changer de profil ou de configuration repart de zéro : la passe initiale d'un autre profil n'a aucun sens."""
        self.session = Session()
        self._maj_menu_pv()
        try:
            Session.supprimer(self.config.dossier_journal)   # l'ancien fichier de reprise ne correspond plus
        except OSError as erreur:
            self.journal.warning("fichier de reprise non supprimé : %s", erreur)
        self.journal.info("nouvelle session de recette")

    def _sauvegarder_session(self):
        """Écrit la session sur le disque pour survivre à un redémarrage (RG07, F11)."""
        if not self.session.a_passe_initiale():
            return
        try:
            self.session.sauvegarder(self.config.dossier_journal)
        except OSError as erreur:
            self.journal.warning("session non sauvegardée : %s", erreur)
            messagebox.showwarning("Reprise de session",
                                   f"La session n'a pas pu être enregistrée : {erreur}\n\n"
                                   "Après un redémarrage, la passe initiale serait perdue.")

    def _proposer_reprise(self):
        """Au lancement : si une session a été interrompue (redémarrage), propose de la reprendre."""
        try:
            reprise = Session.charger(self.config.dossier_journal)
        except ErreurSession as erreur:
            messagebox.showwarning("Reprise de session", f"{erreur}\n\nLa session précédente est ignorée.")
            self._abandonner_reprise()   # sinon le même avertissement reviendrait à chaque lancement
            return
        if reprise is None:
            return
        question = (f"Une session de recette est en cours depuis le {reprise.debut.replace('T', ' à ')}.\n"
                    f"Profil : {reprise.profil_nom} (version {reprise.profil_version})\n"
                    f"Corrections appliquées : {len(reprise.corrections)}\n\n"
                    "Reprendre cette session ? Relancez ensuite la recette pour obtenir la passe finale.\n"
                    "Si vous répondez Non, la session sera abandonnée.")
        if reprise.profil_fichier not in self.chemins or not messagebox.askyesno("Reprise de session", question):
            self._abandonner_reprise()
            return
        self.choix_profil.set(reprise.profil_fichier)
        self._charger_profil_choisi()   # charge le profil et crée une session vide (supprime l'ancien fichier)
        if self.profil is None:
            return
        if self.profil.empreinte != reprise.profil_empreinte:
            messagebox.showwarning("Reprise de session",
                                   "Le profil a été modifié depuis la passe initiale : les 2 passes ne seraient pas "
                                   "comparables. La session précédente est abandonnée.")
            return
        self.session = reprise
        self._sauvegarder_session()   # le fichier supprimé par _nouvelle_session est réécrit
        self.journal.info("session reprise : %d correction(s), profil %s", len(reprise.corrections), reprise.profil_nom)

    def _maj_menu_pv(self):
        """« Éditer le procès-verbal » : actif quand une passe initiale existe, que la passe finale est complète et que rien ne tourne."""
        pret = (self.session.a_passe_initiale() and len(self.resultats) == len(CATALOGUE) and not self._occupe())
        self.menu_recette.entryconfig(LIBELLE_PV, state="normal" if pret else "disabled")

    def editer_pv(self):
        """Menu Recette > « Éditer le procès-verbal » (F11) : copie les données ici, le travail se fait dans un thread."""
        if self._occupe() or self.profil is None or not self.session.a_passe_initiale() \
                or len(self.resultats) != len(CATALOGUE):
            return
        if self.profil.empreinte != self.session.profil_empreinte:
            messagebox.showwarning(
                "Procès-verbal",
                "Le profil a été modifié depuis la passe initiale : les 2 passes ne sont pas comparables.\n\n"
                "Rechargez le profil (Fichier > Choisir le profil…) pour repartir d'une nouvelle session.")
            return
        contexte = ContextePV(
            profil=self.profil, operateur=self.operateur.get().strip() or "non renseigné",
            version_application=VERSION_APPLICATION, horodatage=datetime.now(), debut_session=self.session.debut,
            initiale=dict(self.session.initiale), corrections=list(self.session.corrections),
            finale=dict(self.resultats))   # copies : le thread de travail ne lit jamais l'interface
        self.pv_en_cours = True
        self._maj_menu_pv()
        threading.Thread(target=self._travail_pv, args=(contexte, self.config.dossier_pv,
                                                         self.config.delai_max_secondes), daemon=True).start()
        self._demarrer_boucle()

    def _abandonner_reprise(self):
        try:
            Session.supprimer(self.config.dossier_journal)
        except OSError as erreur:
            self.journal.warning("fichier de reprise non supprimé : %s", erreur)

    def choisir_profil(self):
        if self._occupe():
            return
        chemin = filedialog.askopenfilename(
            title="Choisir le profil",
            initialdir=str(self.config.dossier_profils),
            filetypes=[("Profil JSON", "*.json")],
        )
        if not chemin:   # fenêtre fermée sans choix
            return
        chemin = Path(chemin)
        self.chemins[chemin.stem] = chemin
        self.choix_profil.config(values=list(self.chemins))
        self.choix_profil.set(chemin.stem)
        self._charger_profil_choisi()

    def recharger_configuration(self):
        if self._occupe():
            return
        try:
            self.config = charger_configuration()
        except ErreurConfiguration as erreur:
            messagebox.showerror("Configuration", str(erreur))
            return
        self.chemins = {c.stem: c for c in lister_profils(self.config.dossier_profils)}
        self.choix_profil.config(values=list(self.chemins))
        if self.choix_profil.get() not in self.chemins and self.chemins:
            self.choix_profil.current(0)
        self.operateur.set(self.config.operateur_defaut)
        self.profil = None
        self._vider_tableaux()
        self._nouvelle_session()

    def ouvrir_dossier_pv(self):
        try:
            ouvrir_dossier(self.config.dossier_pv)
        except OSError as erreur:
            messagebox.showerror("Dossier des PV", f"Impossible d'ouvrir {self.config.dossier_pv} : {erreur}")

    def quitter(self):
        if self._occupe():
            messagebox.showwarning("Quitter", "Une recette ou une correction est en cours : attendez la fin avant de quitter.")
            return
        self.fenetre.destroy()

    def a_propos(self):
        if self.profil:
            profil = (f"{self.profil.nom} (version {self.profil.version})\n"
                      f"Empreinte SHA-256 : {self.profil.empreinte}")
        else:
            profil = "aucun profil chargé"
        droits = "oui" if self.est_admin else "non"
        messagebox.showinfo(
            "À propos",
            f"Recette des postes - version {VERSION_APPLICATION}\n\nProfil : {profil}\n\nDroits administrateur : {droits}",
        )

    # ---------- Lancement de la recette (thread principal) ----------

    def lancer_recette(self):
        if self._occupe():
            return
        nom = self.choix_profil.get()
        if not nom:
            messagebox.showerror("Profil", "Aucun profil sélectionné.")
            return
        try:
            profil = charger_profil(self.chemins[nom])   # relu à chaque recette : on voit les modifications du fichier
        except ErreurProfil as erreur:
            messagebox.showerror("Profil invalide", str(erreur))
            return
        self.profil = profil

        self._vider_tableaux()
        self.en_cours = True
        self.bouton_lancer.config(state="disabled")
        self.choix_profil.config(state="disabled")
        threading.Thread(target=self._travail, args=(profil,), daemon=True).start()
        self._demarrer_boucle()

    def _demarrer_boucle(self):
        """Programme la relève de la file, une seule boucle à la fois."""
        if not self.boucle_active:
            self.boucle_active = True
            self.fenetre.after(INTERVALLE_FILE_MS, self._relever_file)

    # ---------- Déclenchement d'une correction (F8, RG01) ----------

    def _corriger(self):
        identifiant = self.id_selectionne
        if (identifiant is None or identifiant not in self.resultats or self.profil is None
                or self._occupe() or identifiant not in CORRECTIONS):
            return
        if not self.journal_ok:
            messagebox.showerror("Correction", "Le journal de session n'est pas disponible : correction refusée.")
            return
        parametres = self.profil.controles[identifiant]
        question = saisie_requise(identifiant)   # None : aucune saisie ; sinon le texte à demander (IDENT_MACHINE)
        if question is not None:
            saisie = simpledialog.askstring("Saisie requise", question, parent=self.fenetre)
            if saisie is None:   # « Annuler » ou croix : rien n'est lancé
                return
            parametres = dict(parametres, numero=saisie.strip())   # copie : le profil chargé n'est pas modifié
        texte = confirmation(identifiant, parametres)
        # RG01 : sans ce clic de confirmation, rien n'est modifié sur le poste.
        if not messagebox.askyesno("Confirmer la correction", f"{texte}\n\nVoulez-vous continuer ?"):
            return

        self.corrections_en_cours.add(identifiant)
        self.bouton_corriger.config(state="disabled")
        self._appliquer_filtre()   # la ligne passe en « En cours »
        threading.Thread(target=self._travail_correction, args=(identifiant, parametres), daemon=True).start()
        self._demarrer_boucle()

    def rejouer_ecarts(self):
        """Menu Recette > « Rejouer les écarts » : relit uniquement les lignes en écart ou indéterminées."""
        if self._occupe() or self.profil is None:
            return
        identifiants = [i for i, r in self.resultats.items() if r.etat in (ECART, INDETERMINE)]
        if not identifiants:
            messagebox.showinfo("Rejouer les écarts", "Aucun écart ni contrôle indéterminé à relire.")
            return
        self.corrections_en_cours.update(identifiants)   # lignes « En cours », interface occupée jusqu'à la dernière relecture
        self.bouton_corriger.config(state="disabled")
        self.bouton_relire.config(state="disabled")
        self._appliquer_filtre()
        controles = {i: self.profil.controles[i] for i in identifiants}
        threading.Thread(target=self._travail_rejeu, args=(controles,), daemon=True).start()
        self._demarrer_boucle()

    def collecte_seule(self):
        """Menu Recette > « Collecte seule » : état brut du poste, sans comparaison, dans une fenêtre secondaire."""
        if self._occupe():
            return
        nom = self.choix_profil.get()
        if not nom:
            messagebox.showerror("Profil", "Aucun profil sélectionné.")
            return
        try:
            profil = charger_profil(self.chemins[nom])   # le profil dit quels contrôles sont actifs et leurs paramètres
        except ErreurProfil as erreur:
            messagebox.showerror("Profil invalide", str(erreur))
            return
        self.collecte_en_cours = True
        self.avancement_avant = self.avancement["value"]   # la barre sert à la collecte, on la rétablira ensuite
        self.avancement["value"] = 0
        self.bouton_corriger.config(state="disabled")
        self.bouton_relire.config(state="disabled")
        threading.Thread(target=self._travail_collecte, args=(profil,), daemon=True).start()
        self._demarrer_boucle()

    def _relire(self):
        """« Relire ce contrôle » : relance la sonde d'une seule ligne, sans rien modifier sur le poste."""
        identifiant = self.id_selectionne
        if (identifiant is None or identifiant not in self.resultats or self.profil is None
                or self._occupe() or self.resultats[identifiant].etat == NON_EVALUE):
            return
        self.corrections_en_cours.add(identifiant)   # même mécanisme que pour une correction : ligne « En cours », interface occupée
        self.bouton_corriger.config(state="disabled")
        self.bouton_relire.config(state="disabled")
        self._appliquer_filtre()
        threading.Thread(target=self._travail_relecture,
                         args=(identifiant, self.profil.controles[identifiant]), daemon=True).start()
        self._demarrer_boucle()

    # ---------- Threads de travail : NE TOUCHENT JAMAIS AUX COMPOSANTS GRAPHIQUES ----------

    def _travail(self, profil):
        def rappel(numero, total, resultat):
            self.file.put(("resultat", numero, resultat))

        try:
            evaluer_profil(profil, self.config.delai_max_secondes, rappel, self.journal)
        except Exception as erreur:   # le thread ne doit jamais mourir en silence
            self.file.put(("erreur", str(erreur), None))
        self.file.put(("fin", None, None))

    def _travail_correction(self, identifiant, parametres):
        try:
            resultat = appliquer(identifiant, parametres, self.config.delai_max_secondes, self.journal)
        except Exception as erreur:
            self.journal.exception("%s : erreur inattendue pendant la correction", identifiant)
            resultat = ResultatCorrection(ECHEC, f"Erreur inattendue : {erreur}", motif=str(erreur))
        self.file.put(("correction", identifiant, resultat))

    def _travail_relecture(self, identifiant, parametres):
        try:
            self.journal.info("%s : relecture demandée par l'opérateur", identifiant)
            resultat = evaluer_controle(identifiant, parametres, self.config.delai_max_secondes, self.journal)
            self.journal.info("%s : relecture : %s", identifiant, resultat.etat)
        except Exception as erreur:
            self.journal.exception("%s : erreur inattendue pendant la relecture", identifiant)
            resultat = Resultat(identifiant, "", "", INDETERMINE, f"Erreur inattendue : {erreur}")
        self.file.put(("relecture", identifiant, resultat))

    def _travail_rejeu(self, controles):
        self.journal.info("rejeu des écarts : %d contrôle(s)", len(controles))
        for identifiant, parametres in controles.items():
            self._travail_relecture(identifiant, parametres)   # dépose un message « relecture » par ligne

    def _travail_pv(self, contexte, dossier_pv, delai):
        try:
            poste = lire_identite_poste(delai, self.journal)
            chemin, verdict = generer_pv(dossier_pv, poste, contexte)
            self.journal.info("PV édité : %s (verdict : %s)", chemin, verdict.verdict)
            self.file.put(("pv", (chemin, verdict.verdict), None))
        except Exception as erreur:
            self.journal.exception("erreur pendant l'édition du procès-verbal")
            self.file.put(("pv", None, f"{type(erreur).__name__} : {erreur}"))

    def _travail_collecte(self, profil):
        try:
            self.journal.info("collecte seule demandée par l'opérateur")
            def rappel(numero, total):
                self.file.put(("avancement", numero, None))   # la barre est mise à jour par le thread principal

            etat = collecter_etat(profil, self.config.delai_max_secondes, self.journal, rappel)
            lignes = [f"Collecte seule - poste {platform.node()} - profil {profil.nom} (version {profil.version})",
                      f"{datetime.now():%d/%m/%Y %H:%M:%S}", ""]
            for identifiant, (reussi, valeur) in etat.items():
                lignes.append(f"[{identifiant}] {CATALOGUE[identifiant]['libelle']}")
                if reussi:
                    lignes.append(json.dumps(valeur, ensure_ascii=False, indent=2, default=str))
                else:
                    lignes.append(f"ILLISIBLE : {valeur}")
                lignes.append("")
            texte = "\n".join(lignes)
        except Exception as erreur:
            self.journal.exception("erreur inattendue pendant la collecte seule")
            texte = f"Erreur inattendue pendant la collecte : {erreur}"
        self.file.put(("collecte", texte, None))

    # ---------- FRONTIÈRE : à partir d'ici, thread principal seulement ----------

    def _relever_file(self):
        """Vide la file, met l'écran à jour, puis se reprogramme tant qu'un travail tourne."""
        try:
            while True:
                type_message, valeur, contenu = self.file.get_nowait()
                if type_message == "resultat":
                    self._afficher_resultat(valeur, contenu)
                elif type_message == "erreur":
                    messagebox.showerror("Erreur pendant la recette", valeur)
                elif type_message == "fin":
                    self._terminer_recette()
                elif type_message == "correction":
                    self._terminer_correction(valeur, contenu)
                elif type_message == "relecture":
                    self._terminer_relecture(valeur, contenu)
                elif type_message == "avancement":
                    self.avancement["value"] = valeur
                elif type_message == "collecte":
                    self._terminer_collecte(valeur)
                elif type_message == "pv":
                    self._terminer_pv(valeur, contenu)
        except queue.Empty:
            pass
        if self._occupe():
            self.fenetre.after(INTERVALLE_FILE_MS, self._relever_file)
        else:
            self.boucle_active = False

    def _afficher_resultat(self, numero, resultat):
        self.resultats[resultat.identifiant] = resultat
        if self._visible(resultat):
            self._inserer_ligne(resultat)
        self.avancement["value"] = numero
        self._maj_compteurs()
        self._maj_titres()

    def _terminer_recette(self):
        self.en_cours = False
        self.bouton_lancer.config(state="normal")
        self.choix_profil.config(state="readonly")
        self._maj_verdict()
        self._maj_menu_pv()
        # F11 : la 1re recette COMPLÈTE de la session devient la passe initiale (25 résultats, aucune erreur en route).
        if not self.session.a_passe_initiale() and len(self.resultats) == len(CATALOGUE):
            self.session.enregistrer_initiale(self.resultats, self.profil)
            self.journal.info("passe initiale conservée : %d contrôle(s)", len(self.resultats))
            self._sauvegarder_session()
            self._maj_menu_pv()   # la passe initiale vient d'être créée
        if self.id_selectionne in self.resultats:   # les boutons du panneau de détail étaient bloqués pendant la recette
            self._rafraichir_detail(self.id_selectionne)

    def _terminer_relecture(self, identifiant, resultat):
        """Intègre une relecture : la ligne reflète l'état réel du poste. Une mention RG07 reste tant que l'écart persiste."""
        self.corrections_en_cours.discard(identifiant)
        if identifiant in self.attentes:
            if resultat.etat == ECART:
                resultat = replace(
                    resultat, constate=f"en attente de prise en compte ({self.attentes[identifiant]})",
                    message=f"En attente de prise en compte : {self.attentes[identifiant]}.")
            else:
                del self.attentes[identifiant]
        self.resultats[identifiant] = resultat
        self._appliquer_filtre()
        self._maj_compteurs()
        self._maj_titres()
        self._maj_verdict()
        self._maj_menu_pv()
        if self.id_selectionne in self.resultats:   # lors d'un rejeu, on ne change pas la ligne affichée
            self._rafraichir_detail(self.id_selectionne)

    def _terminer_pv(self, resultat, erreur):
        """Fenêtre secondaire : chemin du PV produit, bouton « Ouvrir » (F11)."""
        self.pv_en_cours = False
        self._maj_menu_pv()
        if erreur:
            messagebox.showerror("Procès-verbal", f"Le procès-verbal n'a pas pu être édité.\n\n{erreur}")
            return
        chemin, verdict = resultat
        self._abandonner_reprise()   # la session est close : plus rien à reprendre après un redémarrage
        fenetre = tk.Toplevel(self.fenetre)
        fenetre.title("Procès-verbal édité")
        fenetre.resizable(False, False)
        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack(fill="both", expand=True)
        ttk.Label(cadre, text=f"Verdict : {verdict}", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(cadre, text="Le procès-verbal a été enregistré ici :").pack(anchor="w", pady=(8, 2))
        saisie = ttk.Entry(cadre, width=90)
        saisie.insert(0, str(chemin))
        saisie.config(state="readonly")   # lisible et copiable, non modifiable
        saisie.pack(fill="x")

        def ouvrir():
            try:
                ouvrir_fichier(chemin)
            except OSError as erreur_ouverture:
                messagebox.showerror("Procès-verbal", f"Impossible d'ouvrir le fichier : {erreur_ouverture}", parent=fenetre)

        boutons = ttk.Frame(cadre)
        boutons.pack(anchor="e", pady=(10, 0))
        ttk.Button(boutons, text="Ouvrir", command=ouvrir).pack(side="left", padx=4)
        ttk.Button(boutons, text="Fermer", command=fenetre.destroy).pack(side="left")

    def _terminer_collecte(self, texte):
        """Affiche l'état brut dans une fenêtre secondaire : texte sélectionnable, bouton « Copier »."""
        self.collecte_en_cours = False
        self._maj_menu_pv()
        self.avancement["value"] = self.avancement_avant   # état de la barre avant la collecte
        if self.id_selectionne in self.resultats:
            self._rafraichir_detail(self.id_selectionne)
        fenetre = tk.Toplevel(self.fenetre)
        fenetre.title("Collecte seule - état brut du poste")
        fenetre.geometry("820x600")
        boutons = ttk.Frame(fenetre, padding=6)
        boutons.pack(side="bottom", fill="x")

        def copier():
            # Même chemin que Ctrl+C (qui fonctionne) : on sélectionne tout le texte puis on déclenche « Copier ».
            zone.tag_add("sel", "1.0", "end-1c")
            zone.event_generate("<<Copy>>")

        ttk.Button(boutons, text="Copier tout", command=copier).pack(side="left")
        ttk.Button(boutons, text="Fermer", command=fenetre.destroy).pack(side="right")
        defilement = ttk.Scrollbar(fenetre, orient="vertical")
        defilement.pack(side="right", fill="y")
        zone = tk.Text(fenetre, wrap="none", font=("Consolas", 10), yscrollcommand=defilement.set)
        defilement.config(command=zone.yview)
        zone.pack(side="left", fill="both", expand=True)
        zone.insert("1.0", texte)
        zone.config(state="disabled")   # lecture seule : la sélection et Ctrl+C restent possibles

    def _terminer_correction(self, identifiant, correction):
        """Intègre le résultat d'une correction : la ligne reflète la relecture du contrôle (RG06, RG07)."""
        self.corrections_en_cours.discard(identifiant)
        self.session.enregistrer_correction(identifiant, correction.statut, correction.message, correction.motif or "")
        self._sauvegarder_session()   # RG07 : si la correction exige un redémarrage, la session est déjà sur le disque
        relu = correction.relecture
        if relu is not None:
            if correction.statut == ATTENTE:
                # RG07 : la valeur est écrite mais pas prise en compte : la ligne reste rouge, avec son motif.
                self.attentes[identifiant] = correction.motif
                relu = replace(
                    relu, etat=ECART,
                    constate=f"en attente de prise en compte ({correction.motif})",
                    message=f"En attente de prise en compte : {correction.motif}.")
            self.resultats[identifiant] = relu
        self._appliquer_filtre()
        self._maj_compteurs()
        self._maj_titres()
        self._maj_verdict()
        self._maj_menu_pv()
        if identifiant in self.resultats:
            self._rafraichir_detail(identifiant, correction.message)
        if correction.statut == ATTENTE:
            messagebox.showinfo("Correction", correction.message)
        elif correction.statut == ECHEC:
            messagebox.showwarning("Correction", correction.message)

    # ---------- Affichage ----------

    def _visible(self, resultat):
        """Le résultat doit-il être affiché avec le filtre du menu Affichage ?"""
        choix = self.filtre.get()
        if choix == "Écarts seulement":
            return resultat.etat == ECART or resultat.identifiant in self.corrections_en_cours
        if choix == "Indéterminés seulement":
            return resultat.etat == INDETERMINE
        return True

    def _inserer_ligne(self, resultat):
        infos = CATALOGUE[resultat.identifiant]
        etat = EN_COURS if resultat.identifiant in self.corrections_en_cours else resultat.etat
        constate = resultat.constate if resultat.etat in (CONFORME, ECART) else resultat.message
        correction = infos["correction"] if resultat.etat in (ECART, INDETERMINE) else ""
        ligne = (infos["libelle"], resultat.attendu, constate, etat, correction)
        for tableau in (self.tableaux["Synthèse"], self.tableaux[infos["domaine"]]):
            tableau.insert("", "end", iid=resultat.identifiant, values=ligne, tags=(etat,))

    def _appliquer_filtre(self):
        """Reconstruit tous les tableaux à partir des résultats, selon le filtre choisi."""
        for tableau in self.tableaux.values():
            tableau.delete(*tableau.get_children())
        for resultat in self.resultats.values():
            if self._visible(resultat):
                self._inserer_ligne(resultat)

    def _vider_tableaux(self):
        self.resultats = {}
        self.attentes = {}
        self.id_selectionne = None
        for tableau in self.tableaux.values():
            tableau.delete(*tableau.get_children())
        self.avancement["value"] = 0
        self.texte_verdict.config(text="")
        self.v_libelle.set("")
        self.v_message.set("")
        self.v_consigne.set("")
        self.bouton_corriger.config(state="disabled")
        self.bouton_relire.config(state="disabled")
        self._maj_compteurs()
        self._maj_titres()
        self._maj_menu_pv()

    def _maj_compteurs(self):
        etats = [r.etat for r in self.resultats.values()]
        self.texte_compteurs.config(
            text=f"Conformes : {etats.count(CONFORME)}   Écarts : {etats.count(ECART)}   "
                 f"Indéterminés : {etats.count(INDETERMINE)}   Non évalués : {etats.count(NON_EVALUE)}"
        )

    def _maj_titres(self):
        ecarts = [r for r in self.resultats.values() if r.etat == ECART]
        self.onglets.tab(0, text=f"Synthèse ({len(ecarts)})")
        for position, domaine in enumerate(DOMAINES, start=1):
            nombre = sum(1 for r in ecarts if CATALOGUE[r.identifiant]["domaine"] == domaine)
            self.onglets.tab(position, text=f"{domaine} ({nombre})")

    def _maj_verdict(self):
        verdict = calculer_verdict(list(self.resultats.values()))
        motif = f" ({', '.join(verdict.motifs)})" if verdict.motifs else ""
        self.texte_verdict.config(text=f"Verdict : {verdict.verdict}{motif}")

    def _selection(self, evenement):
        selection = evenement.widget.selection()
        if not selection:
            return
        self.id_selectionne = selection[0]
        self._rafraichir_detail(self.id_selectionne)

    def _rafraichir_detail(self, identifiant, message=None):
        """Panneau de détail : libellé, message, consigne ou bouton « Corriger » selon la règle de F6."""
        resultat = self.resultats[identifiant]
        infos = CATALOGUE[identifiant]
        self.v_libelle.set(infos["libelle"])
        self.v_message.set(message or resultat.message)
        a_faire = infos["correction"] == MANUELLE and resultat.etat in (ECART, INDETERMINE)
        self.v_consigne.set(f"Ce qu'il faut faire : {infos['consigne']}" if a_faire else "")
        corrigeable = (infos["correction"] == AUTO and resultat.etat == ECART
                       and identifiant in CORRECTIONS and identifiant not in self.attentes
                       and not self._occupe() and self.journal_ok)
        self.bouton_corriger.config(state="normal" if corrigeable else "disabled")
        relisible = (resultat.etat != NON_EVALUE and not self._occupe() and self.profil is not None)
        self.bouton_relire.config(state="normal" if relisible else "disabled")

    def lancer(self):
        self.fenetre.after(300, self._proposer_reprise)   # une fois la fenêtre affichée
        self.fenetre.mainloop()