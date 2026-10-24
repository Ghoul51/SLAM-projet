"""Interface Tkinter (F6, F7, F8). Aucune commande système dans ce fichier (§3.4.1)."""
import logging
import platform
import queue
import threading
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from catalogue import AUTO, CATALOGUE, DOMAINES, MANUELLE
from comparaison import CONFORME, ECART, INDETERMINE, NON_EVALUE, calculer_verdict, evaluer_profil
from configuration import ErreurConfiguration, charger_configuration
from corrections import ATTENTE, CORRECTIONS, ECHEC, ResultatCorrection, appliquer, confirmation, saisie_requise
from journal import creer_journal
from profil import ErreurProfil, charger_profil, lister_profils
from systeme import ouvrir_dossier

VERSION_APPLICATION = "0.7"
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
        self.id_selectionne = None
        self.tableaux = {}                  # titre d'onglet -> Treeview

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
        recette.add_command(label="Rejouer les écarts", state="disabled")        # rejeu : phase 8
        recette.add_command(label="Collecte seule", state="disabled")            # à venir
        recette.add_command(label="Éditer le procès-verbal", state="disabled")   # PV : phase 8
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
        self.bouton_relire = ttk.Button(detail, text="Relire ce contrôle", state="disabled")
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
        return self.en_cours or bool(self.corrections_en_cours)

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

    # ---------- Threads de travail : NE TOUCHENT JAMAIS AUX COMPOSANTS GRAPHIQUES ----------

    def _travail(self, profil):
        def rappel(numero, total, resultat):
            self.file.put(("resultat", numero, resultat))

        try:
            evaluer_profil(profil, self.config.delai_max_secondes, rappel)
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

    def _terminer_correction(self, identifiant, correction):
        """Intègre le résultat d'une correction : la ligne reflète la relecture du contrôle (RG06, RG07)."""
        self.corrections_en_cours.discard(identifiant)
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
        self._maj_compteurs()
        self._maj_titres()

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

    def lancer(self):
        self.fenetre.mainloop()