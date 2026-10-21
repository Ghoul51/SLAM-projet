"""Interface Tkinter (F6, F7). Aucune commande système dans ce fichier (§3.4.1)."""
import platform
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from catalogue import AUTO, CATALOGUE, DOMAINES, MANUELLE
from comparaison import CONFORME, ECART, INDETERMINE, NON_EVALUE, calculer_verdict, evaluer_profil
from configuration import ErreurConfiguration, charger_configuration
from profil import ErreurProfil, charger_profil, lister_profils
from systeme import ouvrir_dossier

VERSION_APPLICATION = "0.6"
COULEURS = {CONFORME: "#c8f0c8", ECART: "#f5b5b5", INDETERMINE: "#ffd9a0", NON_EVALUE: "#dddddd"}
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
        self.profil = None           # dernier profil chargé et validé
        self.resultats = {}          # identifiant -> Resultat de la passe en cours
        self.file = queue.Queue()    # le thread de travail y dépose, le thread principal y lit
        self.en_cours = False
        self.tableaux = {}           # titre d'onglet -> Treeview

        self.fenetre = tk.Tk()
        self.fenetre.title("Recette des postes - EXPERTY")
        self.fenetre.geometry("1150x720")
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)   # la croix de la fenêtre passe aussi par quitter()
        self.filtre = tk.StringVar(value=FILTRES[0])              # après Tk() : une StringVar a besoin de la fenêtre

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

    def _charger_profil_choisi(self):
        """Valide le profil sélectionné (RG05) et vide le tableau."""
        if self.en_cours:
            return
        try:
            self.profil = charger_profil(self.chemins[self.choix_profil.get()])
        except ErreurProfil as erreur:
            self.profil = None
            messagebox.showerror("Profil invalide", str(erreur))
        self._vider_tableaux()

    def choisir_profil(self):
        if self.en_cours:
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
        if self.en_cours:
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
        if self.en_cours:
            messagebox.showwarning("Quitter", "Une recette est en cours : attendez la fin avant de quitter.")
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
        if self.en_cours:
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
        self.fenetre.after(INTERVALLE_FILE_MS, self._relever_file)

    # ---------- Thread de travail : NE TOUCHE JAMAIS AUX COMPOSANTS GRAPHIQUES ----------

    def _travail(self, profil):
        def rappel(numero, total, resultat):
            self.file.put(("resultat", numero, resultat))

        try:
            evaluer_profil(profil, self.config.delai_max_secondes, rappel)
        except Exception as erreur:   # le thread ne doit jamais mourir en silence
            self.file.put(("erreur", str(erreur), None))
        self.file.put(("fin", None, None))

    # ---------- FRONTIÈRE : à partir d'ici, thread principal seulement ----------

    def _relever_file(self):
        """Vide la file, met l'écran à jour, puis se reprogramme tant que la recette tourne."""
        try:
            while True:
                type_message, valeur, resultat = self.file.get_nowait()
                if type_message == "resultat":
                    self._afficher_resultat(valeur, resultat)
                elif type_message == "erreur":
                    messagebox.showerror("Erreur pendant la recette", valeur)
                elif type_message == "fin":
                    self._terminer_recette()
        except queue.Empty:
            pass
        if self.en_cours:
            self.fenetre.after(INTERVALLE_FILE_MS, self._relever_file)

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
        verdict = calculer_verdict(list(self.resultats.values()))
        motif = f" ({', '.join(verdict.motifs)})" if verdict.motifs else ""
        self.texte_verdict.config(text=f"Verdict : {verdict.verdict}{motif}")

    # ---------- Affichage ----------

    def _visible(self, resultat):
        """Le résultat doit-il être affiché avec le filtre du menu Affichage ?"""
        choix = self.filtre.get()
        if choix == "Écarts seulement":
            return resultat.etat == ECART
        if choix == "Indéterminés seulement":
            return resultat.etat == INDETERMINE
        return True

    def _inserer_ligne(self, resultat):
        infos = CATALOGUE[resultat.identifiant]
        constate = resultat.constate if resultat.etat in (CONFORME, ECART) else resultat.message
        correction = infos["correction"] if resultat.etat in (ECART, INDETERMINE) else ""
        ligne = (infos["libelle"], resultat.attendu, constate, resultat.etat, correction)
        for tableau in (self.tableaux["Synthèse"], self.tableaux[infos["domaine"]]):
            tableau.insert("", "end", iid=resultat.identifiant, values=ligne, tags=(resultat.etat,))

    def _appliquer_filtre(self):
        """Reconstruit tous les tableaux à partir des résultats, selon le filtre choisi."""
        for tableau in self.tableaux.values():
            tableau.delete(*tableau.get_children())
        for resultat in self.resultats.values():
            if self._visible(resultat):
                self._inserer_ligne(resultat)

    def _vider_tableaux(self):
        self.resultats = {}
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

    def _selection(self, evenement):
        selection = evenement.widget.selection()
        if not selection:
            return
        resultat = self.resultats[selection[0]]
        infos = CATALOGUE[resultat.identifiant]
        self.v_libelle.set(infos["libelle"])
        self.v_message.set(resultat.message)
        a_faire = infos["correction"] == MANUELLE and resultat.etat in (ECART, INDETERMINE)
        self.v_consigne.set(f"Ce qu'il faut faire : {infos['consigne']}" if a_faire else "")
        corrigeable = infos["correction"] == AUTO and resultat.etat == ECART
        self.bouton_corriger.config(state="normal" if corrigeable else "disabled")

    def _corriger(self):
        messagebox.showinfo("Corriger", "Les corrections seront ajoutées en phase 7.")

    def lancer(self):
        self.fenetre.mainloop()