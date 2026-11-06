#!/usr/bin/env python3
"""Analyse un export Instagram (format JSON) et genere une page HTML
avec le graphique de ton reseau.

Utilisation :
    python analyse_instagram.py chemin/vers/export            (dossier dezippe ou fichier .zip)
    python analyse_instagram.py export --ancien ancien_export (pour comparer deux exports)

La page et tes fichiers personnels sont ecrits dans le dossier mes_donnees/, a ne jamais publier.
Tout reste sur ton ordinateur : rien n'est envoye sur Internet, et le script ne se connecte
jamais a Instagram. Le contenu des messages n'est pas lu, seulement leur nombre et leur date.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
import tempfile
import unicodedata
import zipfile
from collections import Counter, defaultdict

ICI = os.path.dirname(os.path.abspath(__file__))
MODELE = os.path.join(ICI, "modele_reseau.html")


def chemin_long(chemin):
    """Sous Windows, autorise les chemins de plus de 260 caracteres (frequents dans un export)."""
    chemin = os.path.abspath(chemin)
    if os.name == "nt" and not chemin.startswith("\\\\"):
        chemin = "\\\\?\\" + chemin
    return chemin


def lisible(chemin):
    return chemin[4:] if chemin.startswith("\\\\?\\") else chemin


def regle_dossier(dossier):
    """Choisit le dossier ou vont la page generee et tes fichiers personnels (jamais a publier)."""
    global DOSSIER, SORTIE, ALIAS, STORIES, HISTORIQUE, ETIQUETTES
    DOSSIER = chemin_long(dossier)
    SORTIE = os.path.join(DOSSIER, "reseau_instagram.html")
    ALIAS = os.path.join(DOSSIER, "alias.csv")
    STORIES = os.path.join(DOSSIER, "stories_plus.csv")
    HISTORIQUE = os.path.join(DOSSIER, "historique.json")
    ETIQUETTES = os.path.join(DOSSIER, "etiquettes.csv")


regle_dossier(os.path.join(ICI, "mes_donnees"))
GENRES = {"h": "h", "f": "f", "a": "a"}   # premiere lettre de : homme, femme, autre

ENTETE_ETIQUETTES = """\
# Tes etiquettes, a remplir toi-meme (le script ne devine rien sur les gens).
# etiquette : un mot libre, par exemple : pote, famille, malaisant, a garder, a retirer
# genre : h, f ou a (autre), seulement si tu veux voir la repartition de tes abonnements
"""

# Points attribues a chaque type d'interaction pour le score de proximite.
POIDS = {
    "msg_envoyes": 1,
    "msg_recus": 1,
    "likes_posts": 1,
    "likes_stories": 2,
    "reactions": 3,
    "commentaires": 3,
    "stories_vues": 0.25,
    "a_vu_stories": 1,     # la personne a vu une de tes stories (stories_plus.csv)
    "revisionnages": 2,    # la personne a revu une de tes stories (stories_plus.csv)
}

MODELE_STORIES = """\
# Suivi de tes stories avec Instagram Plus. Une ligne par story, a remplir tant que la story est en ligne.
# date : jour de la story (AAAA-MM-JJ ou JJ/MM/AAAA)
# story : un titre pour t'y retrouver
# revisionnages : le total affiche par Instagram Plus sous la story (laisse vide si tu ne l'as pas)
# spectateurs : les pseudos de la liste des spectateurs, separes par des virgules
#   Si Instagram Plus indique combien de fois une personne a vu la story, ecris pseudo:3
# Exemple invente, a ne pas garder (les lignes qui commencent par # sont ignorees) :
# 2026-01-31;Titre de ta story;12;pseudo_ami_1, pseudo_ami_2:3, pseudo_ami_3
date;story;revisionnages;spectateurs
"""
RE_SPECTATEUR = re.compile(r"^@?([\w.]+?)(?:\s*:\s*(\d+)|\s+[x×]\s*(\d+))?$")


PAUSE = 12 * 3600   # au-dela de 12 h de silence, le message suivant lance une nouvelle conversation


def ce_que_sait(racine):
    """Resume ce que l'export revele des donnees qu'Instagram garde sur toi (publicite, lieux, contacts)."""
    def vecs(*chemin):
        out = []
        for it in en_liste(charge(racine, *chemin)):
            for e in it.get("label_values", []):
                if isinstance(e, dict) and e.get("vec"):
                    noms = [corrige(v.get("value", "")) for v in e["vec"] if isinstance(v, dict) and v.get("value")]
                    if noms:
                        out.append({"label": corrige(e.get("label", "")), "noms": noms})
        return out

    def auteurs(*chemin):
        elements = en_liste(charge(racine, *chemin))
        compte = Counter()
        for it in elements:
            a = trouve_auteur(it.get("label_values"))
            if a:
                compte[a[0]] += 1
        ts = [it["timestamp"] for it in elements if it.get("timestamp")]
        return {"n": len(elements), "top": compte.most_common(15),
                "debut": min(ts) if ts else None, "fin": max(ts) if ts else None}

    def nb(*chemin):
        p = os.path.join(racine, *chemin)
        if os.path.isdir(p):
            return sum(len(en_liste(charge(p, f))) for f in os.listdir(p) if f.endswith(".json"))
        return len(en_liste(charge(racine, *chemin)))

    pubs = ("ads_information", "ads_and_topics")
    annonceurs = ("ads_information", "instagram_ads_and_businesses")
    infos = ("personal_information", "information_about_you")
    base = []
    for it in en_liste(charge(racine, *infos, "profile_based_in.json")):
        for e in it.get("label_values", []):
            for x in e.get("dict", []) if isinstance(e, dict) else []:
                if x.get("value"):
                    base.append([corrige(x.get("label", "")), corrige(x["value"])])
    categories = vecs(*annonceurs, "other_categories_used_to_reach_you.json")
    lieux = vecs(*infos, "locations_of_interest.json")
    return {
        "annonceurs": vecs(*annonceurs, "advertisers_using_your_activity_or_information.json"),
        "categories": categories[0]["noms"] if categories else [],
        "pubs": auteurs(*pubs, "ads_viewed.json"),
        "posts": auteurs(*pubs, "posts_viewed.json"),
        "videos": auteurs(*pubs, "videos_watched.json"),
        "lieux": lieux[0]["noms"] if lieux else [],
        "base": base,
        "contacts": nb("connections", "contacts", "synced_contacts.json"),
        "connexions": nb("security_and_login_information", "login_and_profile_creation", "login_activity.json"),
        "recherches": nb("logged_information", "recent_searches"),
        "liens": nb("logged_information", "link_history", "link_history.json"),
    }


def lit_insights(racine):
    """Statistiques de compte professionnel, presentes seulement dans l'export d'un compte pro.

    Lecture generique : chaque fichier devient un tableau, avec les libelles tels qu'Instagram les fournit.
    """
    dossier = os.path.join(racine, "logged_information", "past_instagram_insights")
    if not os.path.isdir(dossier):
        return []

    def valeur(e):
        if e.get("value") not in (None, ""):
            return corrige(e["value"])
        ts = e.get("timestamp_value") or e.get("timestamp")
        if ts:
            return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        if e.get("vec"):
            return ", ".join(corrige(v.get("value", "")) for v in e["vec"] if isinstance(v, dict))
        return ""

    def aplatit(entrees, ligne, prefixe=""):
        for e in entrees or []:
            if not isinstance(e, dict):
                continue
            if "label" in e:
                v = valeur(e)
                if v != "":
                    ligne.setdefault(prefixe + corrige(e["label"]), v)
            if e.get("dict"):
                titre = corrige(e.get("title", ""))
                for sous in e["dict"]:
                    aplatit(sous.get("dict") if isinstance(sous, dict) and "dict" in sous else [sous], ligne,
                            prefixe + (titre + " : " if titre else ""))

    tableaux = []
    for f in sorted(os.listdir(dossier)):
        if not f.endswith(".json"):
            continue
        lignes = []
        for it in en_liste(charge(dossier, f)):
            if not isinstance(it, dict):
                continue
            ligne = {}
            for k, v in (it.get("string_map_data") or {}).items():   # ancien format
                if isinstance(v, dict) and valeur(v) != "":
                    ligne[corrige(k)] = valeur(v)
            aplatit(it.get("label_values"), ligne)                    # nouveau format
            if ligne:
                lignes.append(ligne)
        if lignes:
            tableaux.append({"fichier": f[:-5], "lignes": lignes[:200]})
    return tableaux


def instantane(donnees):
    """Photo des abonnes et abonnements a la date de l'export, gardee dans historique.json."""
    pers = [d for d in donnees["personnes"] if d["pseudo"]]
    return {
        "date": dt.date.fromtimestamp(donnees["fin"]).isoformat(), "fin": donnees["fin"],
        "debut_abonnes": donnees["followback"]["depuis"] if donnees["followback"] else None,
        "abonnes": {d["pseudo"]: d["abonne_depuis"] for d in pers if d["abonne_depuis"]},
        "suivis": {d["pseudo"]: d["suivi_depuis"] for d in pers if d["suivi_depuis"]},
    }


def compare(ancien, nouveau):
    """Ce qui a change entre deux instantanes."""
    debut = nouveau.get("debut_abonnes") or 0
    return {
        "depuis": ancien["date"],
        # Un export partiel ne liste que les abonnes recents : on ne compte comme perdus que
        # ceux qui devraient encore y figurer.
        "abonnes_perdus": sorted(u for u, ts in ancien["abonnes"].items() if u not in nouveau["abonnes"] and ts >= debut),
        "abonnes_gagnes": sorted(u for u, ts in nouveau["abonnes"].items() if u not in ancien["abonnes"] and ts > ancien["fin"]),
        "plus_suivis": sorted(u for u in ancien["suivis"] if u not in nouveau["suivis"]),
        "nouveaux_suivis": sorted(u for u in nouveau["suivis"] if u not in ancien["suivis"]),
    }


def met_a_jour_historique(instantanes):
    """Ajoute les instantanes a historique.json et renvoie la liste complete, du plus ancien au plus recent."""
    histo = []
    if os.path.exists(HISTORIQUE):
        try:
            with open(HISTORIQUE, encoding="utf-8") as f:
                histo = json.load(f).get("instantanes", [])
        except (ValueError, OSError):
            histo = []
    for snap in instantanes:
        histo = [h for h in histo if h.get("date") != snap["date"]] + [snap]
    histo.sort(key=lambda h: h["fin"])
    with open(HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump({"instantanes": histo}, f, ensure_ascii=False)
    return histo


def lit_csv(chemin):
    """Lit un CSV a point-virgule (UTF-8 ou format Excel Windows), sans lignes vides ni lignes #."""
    if not os.path.exists(chemin):
        return []
    with open(chemin, "rb") as f:
        brut = f.read()
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("cp1252", errors="replace")
    lignes = [l for l in texte.splitlines() if l.strip(" ;\t") and not l.lstrip().startswith("#")]
    return list(csv.DictReader(lignes, delimiter=";"))


def lit_date(s):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return int(dt.datetime.strptime((s or "").strip(), fmt).replace(hour=12).timestamp())
        except ValueError:
            pass
    return None

TITRES_AUTEUR = {"Propriétaire", "Owner", "Auteur(ice)", "Author"}
CLES_PSEUDO = {"Nom de profil", "Username"}
CLES_NOM = {"Nom", "Name"}


def corrige(s):
    """Instagram exporte les accents en double encodage : on les repare."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def charge(racine, *chemin):
    p = os.path.join(racine, *chemin)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def en_liste(d):
    """Un fichier peut contenir une liste, un seul element, ou {cle: liste}."""
    if d is None:
        return []
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        if "label_values" in d or "string_map_data" in d:
            return [d]
        for v in d.values():
            if isinstance(v, list):
                return v
    return []


def etiquettes(lv):
    """[{label, value}, ...] -> {label: value}"""
    out = {}
    for e in lv or []:
        if isinstance(e, dict) and "label" in e:
            out.setdefault(corrige(e["label"]), corrige(e.get("value", "")))
    return out


def trouve_auteur(o):
    """Cherche recursivement le bloc 'Proprietaire' -> (pseudo, nom affiche)."""
    if isinstance(o, list):
        for x in o:
            r = trouve_auteur(x)
            if r:
                return r
    elif isinstance(o, dict):
        if corrige(o.get("title", "")) in TITRES_AUTEUR:
            for bloc in o.get("dict", []):
                e = etiquettes(bloc.get("dict", []))
                pseudo = next((e[k] for k in CLES_PSEUDO if e.get(k)), "")
                nom = next((e[k] for k in CLES_NOM if e.get(k)), "")
                if pseudo:
                    return pseudo.lower(), nom
            return None
        for v in o.values():
            if isinstance(v, (list, dict)):
                r = trouve_auteur(v)
                if r:
                    return r
    return None


def normalise(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def mois(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m")


def analyse(racine):
    personnes = {}
    noms_vers_pseudos = defaultdict(set)

    def p(cle, pseudo=None, nom=None):
        d = personnes.get(cle)
        if d is None:
            d = personnes[cle] = {
                "id": cle, "pseudo": pseudo, "nom": nom or "",
                "suivi_depuis": None, "abonne_depuis": None, "ami_proche": False,
                "desabonne": False, "demande_en_attente": False,
                "msg_envoyes": 0, "msg_recus": 0, "premier_msg": None, "dernier_msg": None,
                "attend_reponse": False, "etiquette": "", "genre": "",
                "likes_posts": 0, "likes_stories": 0, "reactions": 0,
                "commentaires": 0, "stories_vues": 0,
                "a_vu_stories": 0, "revisionnages": 0,
                "init_moi": 0, "init_autre": 0, "_rep_moi": [], "_rep_autre": [],
                "msg_mois": Counter(), "pts_mois": Counter(),
                "mois": Counter(), "premiere": None, "derniere": None,
            }
        if nom and not d["nom"]:
            d["nom"] = nom
        return d

    def note(d, champ, ts, n=1):
        d[champ] += n
        if ts:
            d["mois"][mois(ts)] += n
            d["pts_mois"][mois(ts)] += POIDS.get(champ, 0) * n
            d["premiere"] = ts if d["premiere"] is None else min(d["premiere"], ts)
            d["derniere"] = ts if d["derniere"] is None else max(d["derniere"], ts)

    def connu(pseudo, nom):
        if nom:
            noms_vers_pseudos[nom.strip().lower()].add(pseudo)

    # --- Mon profil
    moi = {"pseudo": "moi", "nom": ""}
    prof = charge(racine, "personal_information", "personal_information", "personal_information.json")
    for u in en_liste(prof):
        smd = u.get("string_map_data", {})
        moi["pseudo"] = corrige(smd.get("Username", {}).get("value", "")) or moi["pseudo"]
        moi["nom"] = corrige(smd.get("Name", {}).get("value", ""))
        prive = str(smd.get("Private Account", {}).get("value", "")).strip().lower()
        moi["prive"] = prive in ("true", "vrai", "oui", "yes")

    base = ("connections", "followers_and_following")

    # --- Abonnements (comptes que je suis) et abonnes (comptes qui me suivent)
    def lit_relations(fichiers, champ):
        for f in fichiers:
            for it in en_liste(charge(racine, *base, f)):
                sld = (it.get("string_list_data") or [{}])[0]
                pseudo = corrige(it.get("title") or sld.get("value") or "")
                if not pseudo and sld.get("href"):
                    pseudo = sld["href"].rstrip("/").split("/")[-1]
                if pseudo:
                    p(pseudo.lower(), pseudo.lower())[champ] = sld.get("timestamp")

    dossier = os.path.join(racine, *base)
    fichiers = sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []
    lit_relations([f for f in fichiers if re.match(r"following(_\d+)?\.json$", f)], "suivi_depuis")
    lit_relations([f for f in fichiers if re.match(r"followers(_\d+)?\.json$", f)], "abonne_depuis")

    for f, champ in (("close_friends.json", "ami_proche"),
                     ("recently_unfollowed_profiles.json", "desabonne"),
                     ("pending_follow_requests.json", "demande_en_attente")):
        for it in en_liste(charge(racine, *base, f)):
            e = etiquettes(it.get("label_values"))
            pseudo = next((e[k] for k in CLES_PSEUDO if e.get(k)), "").lower()
            nom = next((e[k] for k in CLES_NOM if e.get(k)), "")
            if pseudo:
                p(pseudo, pseudo, nom)[champ] = True
                connu(pseudo, nom)

    # --- Interactions au format "label_values" (likes, stories, reactions)
    act = "your_instagram_activity"
    sources = [
        ((act, "likes", "liked_posts.json"), "likes_posts"),
        ((act, "story_interactions", "story_likes.json"), "likes_stories"),
        ((act, "story_interactions", "stories_viewed.json"), "stories_vues"),
        ((act, "story_interactions", "emoji_story_reactions.json"), "reactions"),
        ((act, "story_interactions", "story_reaction_sticker_reactions.json"), "reactions"),
        ((act, "story_interactions", "emoji_sliders.json"), "reactions"),
        ((act, "instants", "instants_interactions.json"), "reactions"),
    ]
    for chemin, champ in sources:
        for it in en_liste(charge(racine, *chemin)):
            a = trouve_auteur(it.get("label_values"))
            if a:
                pseudo, nom = a
                note(p(pseudo, pseudo, nom), champ, it.get("timestamp"))
                connu(pseudo, nom)

    # --- Commentaires (posts et stories)
    dossier = os.path.join(racine, act, "comments")
    for f in sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []:
        for it in en_liste(charge(racine, act, "comments", f)):
            smd = it.get("string_map_data", {})
            pseudo = corrige(smd.get("Media Owner", {}).get("value", "")).lower()
            if pseudo:
                note(p(pseudo, pseudo), "commentaires", smd.get("Time", {}).get("timestamp"))

    # --- Correspondances manuelles nom de conversation -> pseudo
    alias = {}
    for ligne in lit_csv(ALIAS):
        if (ligne.get("pseudo") or "").strip() and ligne.get("nom_conversation"):
            alias[ligne["nom_conversation"].strip().lower()] = ligne["pseudo"].strip().lower().lstrip("@")

    pseudos_connus = {d["pseudo"] for d in personnes.values() if d["pseudo"]}
    relies = {d["pseudo"] for d in personnes.values() if d["suivi_depuis"] or d["abonne_depuis"]}
    par_norme = defaultdict(set)
    for u in pseudos_connus:
        par_norme[normalise(u)].add(u)

    def resout(nom):
        """Retrouve le pseudo d'une personne a partir de son nom de conversation."""
        cle = nom.strip().lower()
        if cle in alias:
            return alias[cle]
        if cle in pseudos_connus:
            return cle
        for candidats in (noms_vers_pseudos.get(cle, set()), par_norme.get(normalise(nom), set())):
            if len(candidats) == 1:
                return next(iter(candidats))
            lies = candidats & relies
            if len(lies) == 1:
                return next(iter(lies))
        return None

    # --- Messages prives : on compte, on ne lit pas le contenu
    groupes = []
    non_resolus = {}
    heures, jours = [0] * 24, [0] * 7   # messages recus par heure et par jour (0 = lundi)
    boite = os.path.join(racine, act, "messages", "inbox")
    fils = []
    for nom_fil in sorted(os.listdir(boite)) if os.path.isdir(boite) else []:
        dossier = os.path.join(boite, nom_fil)
        if not os.path.isdir(dossier):
            continue
        participants, messages = [], []
        for nom_fichier in sorted(os.listdir(dossier)):
            if not (nom_fichier.startswith("message_") and nom_fichier.endswith(".json")):
                continue
            with open(os.path.join(dossier, nom_fichier), encoding="utf-8") as fh:
                d = json.load(fh)
            participants = [corrige(x.get("name", "")) for x in d.get("participants", [])]
            messages += [(corrige(m.get("sender_name", "")), m.get("timestamp_ms", 0) // 1000)
                         for m in d.get("messages", [])]
        if messages:
            fils.append((dossier, participants, messages))

    # Mon nom affiche : celui du profil, plus tout nom present dans plus de la moitie des fils.
    presence = Counter(n for _, participants, _ in fils for n in set(participants))
    mes_noms = {n for n, c in presence.items() if len(fils) > 2 and c > len(fils) / 2}
    if moi["nom"]:
        mes_noms.add(moi["nom"])

    for dossier, participants, messages in fils:
        autres = [n for n in participants if n not in mes_noms]

        def fiche(nom):
            pseudo = resout(nom)
            if pseudo:
                return p(pseudo, pseudo, nom)
            cle = "dm:" + os.path.basename(dossier) + ":" + normalise(nom)
            non_resolus[nom] = non_resolus.get(nom, 0) + 1
            return p(cle, None, nom or "Compte supprimé")

        if len(autres) == 1:
            d = fiche(autres[0])
            for expediteur, ts in messages:
                note(d, "msg_envoyes" if expediteur != autres[0] else "msg_recus", ts)
                if ts:
                    d["msg_mois"][mois(ts)] += 1
                if expediteur == autres[0] and ts:
                    quand = dt.datetime.fromtimestamp(ts)
                    heures[quand.hour] += 1
                    jours[quand.weekday()] += 1
            # Dynamique : qui lance la conversation, et en combien de temps chacun repond
            precedent = None
            for expediteur, ts in sorted((m for m in messages if m[1]), key=lambda m: m[1]):
                lui = expediteur == autres[0]
                if precedent is None or ts - precedent[1] > PAUSE:
                    d["init_autre" if lui else "init_moi"] += 1
                elif lui != precedent[0]:
                    d["_rep_autre" if lui else "_rep_moi"].append(ts - precedent[1])
                precedent = (lui, ts)
            ts_all = [t for _, t in messages if t]
            if ts_all:
                # Le dernier message du fil le plus recent vient-il de l'autre personne ?
                dernier = max(messages, key=lambda m: m[1])
                if not d["dernier_msg"] or dernier[1] >= d["dernier_msg"]:
                    d["attend_reponse"] = dernier[0] == autres[0]
                d["premier_msg"] = min(ts_all) if not d["premier_msg"] else min(d["premier_msg"], min(ts_all))
                d["dernier_msg"] = max(ts_all) if not d["dernier_msg"] else max(d["dernier_msg"], max(ts_all))
        elif len(autres) > 1:
            membres = [fiche(n)["id"] for n in autres]
            groupes.append({"membres": membres, "messages": len(messages)})

    # --- Stories suivies a la main avec Instagram Plus (stories_plus.csv)
    stories, avertissements = [], []
    for n, ligne in enumerate(lit_csv(STORIES), 1):
        ts = lit_date(ligne.get("date"))
        if ts is None:
            avertissements.append(f"stories_plus.csv, story n°{n} : date illisible ({ligne.get('date')!r}), ligne ignorée")
            continue
        brut = (ligne.get("revisionnages") or "").strip()
        total = int(brut) if brut.isdigit() else None
        vus = {}
        for jeton in re.split(r"[,;\n]+", ";".join([ligne.get("spectateurs") or ""] + (ligne.get(None) or []))):
            jeton = jeton.strip()
            if not jeton:
                continue
            m = RE_SPECTATEUR.match(jeton)
            if not m:
                avertissements.append(f"stories_plus.csv, story n°{n} : spectateur illisible ({jeton!r}), ignoré")
                continue
            fois = max(1, int(m.group(2) or m.group(3) or 1))
            vus[m.group(1).lower()] = max(vus.get(m.group(1).lower(), 0), fois)
        for pseudo, fois in vus.items():
            d = p(pseudo, pseudo)
            note(d, "a_vu_stories", ts)
            if fois > 1:
                note(d, "revisionnages", ts, fois - 1)
        detail = sum(f - 1 for f in vus.values())
        stories.append({
            "date": ts, "titre": (ligne.get("story") or "").strip(), "spectateurs": len(vus),
            "revisionnages": total if total is not None else (detail or None),
        })
    stories.sort(key=lambda s: s["date"])

    # --- Score et mise en forme
    liste = []
    tous_moi, tous_autre = [], []
    notes = {(l.get("pseudo") or "").strip().lower().lstrip("@"): l for l in lit_csv(ETIQUETTES)}
    for d in personnes.values():
        e = notes.get(d["pseudo"] or "")
        if e:
            d["etiquette"] = (e.get("etiquette") or "").strip()
            d["genre"] = GENRES.get((e.get("genre") or "").strip().lower()[:1], "")
        d["score"] = round(sum(d[k] * w for k, w in POIDS.items()), 1)
        d["mois"] = dict(sorted(d["mois"].items()))
        d["msg_mois"] = dict(sorted(d["msg_mois"].items()))
        d["pts_mois"] = {k: round(v, 2) for k, v in sorted(d["pts_mois"].items())}
        rep_moi, rep_autre = d.pop("_rep_moi"), d.pop("_rep_autre")
        tous_moi += rep_moi
        tous_autre += rep_autre
        d["rep_moi"] = int(statistics.median(rep_moi)) if rep_moi else None
        d["rep_autre"] = int(statistics.median(rep_autre)) if rep_autre else None
        if d["suivi_depuis"] and d["abonne_depuis"]:
            d["lien"] = "mutuel"
        elif d["suivi_depuis"]:
            d["lien"] = "suivi"
        elif d["abonne_depuis"]:
            d["lien"] = "abonne"
        elif d["pseudo"] is None:
            d["lien"] = "inconnu"
        else:
            d["lien"] = "aucun"
        liste.append(d)
    liste.sort(key=lambda d: -d["score"])

    # --- Taux de follow-back observe dans ton historique
    # On ne peut le mesurer que sur la periode ou l'export contient les nouveaux abonnes.
    dates_abonnes = [d["abonne_depuis"] for d in liste if d["abonne_depuis"]]
    followback = None
    if dates_abonnes:
        debut = min(dates_abonnes)
        # "Toi en premier" : tu as suivi le compte et il ne te suivait pas encore une heure apres.
        premier = [d for d in liste if d["suivi_depuis"] and d["suivi_depuis"] >= debut
                   and (not d["abonne_depuis"] or d["abonne_depuis"] - d["suivi_depuis"] > 3600)]
        en_retour = [d for d in liste if d["suivi_depuis"] and d["abonne_depuis"] and d["abonne_depuis"] >= debut
                     and d["suivi_depuis"] - d["abonne_depuis"] >= -3600 and d not in premier]

        def taux(groupe):
            return [sum(1 for d in groupe if d["abonne_depuis"]), len(groupe)]

        avec_dm = [d for d in premier if d["msg_envoyes"] + d["msg_recus"] > 0]
        sans_dm = [d for d in premier if d["msg_envoyes"] + d["msg_recus"] == 0]
        followback = {
            "depuis": debut, "tous": taux(premier), "avec_dm": taux(avec_dm), "sans_dm": taux(sans_dm),
            "suivis_en_retour_par_toi": len(en_retour),
        }

    return {
        "moi": moi,
        "fin": max([d["derniere"] or 0 for d in liste] + dates_abonnes + [0]),
        "heures": heures,
        "jours": jours,
        "followback": followback,
        "conversations": {
            "pause_heures": PAUSE // 3600,
            "init_moi": sum(d["init_moi"] for d in liste), "init_autre": sum(d["init_autre"] for d in liste),
            "rep_moi": int(statistics.median(tous_moi)) if tous_moi else None,
            "rep_autre": int(statistics.median(tous_autre)) if tous_autre else None,
        },
        "sait": ce_que_sait(racine),
        "insights": lit_insights(racine),
        "changements": None,
        "genere_le": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "poids": POIDS,
        "personnes": liste,
        "groupes": groupes,
        "stories": stories,
    }, non_resolus, avertissements


def ecrit_etiquettes(donnees):
    """Tient a jour etiquettes.csv : une ligne par compte lie a toi, sans toucher a ce que tu as deja ecrit."""
    existant = {(l.get("pseudo") or "").strip().lower().lstrip("@"): l for l in lit_csv(ETIQUETTES)}
    lignes = {}
    for d in donnees["personnes"]:
        if d["pseudo"] and d["lien"] in ("mutuel", "suivi", "abonne"):
            e = existant.get(d["pseudo"], {})
            lignes[d["pseudo"]] = [d["pseudo"], d["nom"], (e.get("etiquette") or "").strip(), (e.get("genre") or "").strip()]
    for pseudo, e in existant.items():   # garde les lignes annotees de comptes qui ne sont plus lies
        if pseudo and pseudo not in lignes and ((e.get("etiquette") or "").strip() or (e.get("genre") or "").strip()):
            lignes[pseudo] = [pseudo, e.get("nom") or "", (e.get("etiquette") or "").strip(), (e.get("genre") or "").strip()]
    with open(ETIQUETTES, "w", encoding="utf-8-sig", newline="") as f:
        f.write(ENTETE_ETIQUETTES)
        w = csv.writer(f, delimiter=";")
        w.writerow(["pseudo", "nom", "etiquette", "genre"])
        for pseudo in sorted(lignes):
            w.writerow(lignes[pseudo])


def ecrit_alias(non_resolus):
    """Liste les conversations dont le pseudo n'a pas ete retrouve, a completer a la main."""
    existant = {}
    for ligne in lit_csv(ALIAS):
        if ligne.get("nom_conversation"):
            existant[ligne["nom_conversation"]] = ligne.get("pseudo") or ""
    for nom in non_resolus:
        existant.setdefault(nom, "")
    with open(ALIAS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["nom_conversation", "pseudo"])
        for nom, pseudo in sorted(existant.items(), key=lambda x: x[0].lower()):
            w.writerow([nom, pseudo])


def ouvre_export(chemin, a_garder):
    """Renvoie le dossier de l'export. Accepte le dossier dezippe ou directement le fichier .zip."""
    chemin = chemin.rstrip("\\/")
    if os.path.isfile(chemin) and chemin.lower().endswith(".zip"):
        tmp = tempfile.TemporaryDirectory()
        a_garder.append(tmp)   # supprime a la fin du programme
        with zipfile.ZipFile(chemin) as z:
            for membre in z.namelist():
                if membre.lower().endswith(".json"):   # les photos et videos ne servent pas
                    z.extract(membre, tmp.name)
        chemin = tmp.name
    candidats = [chemin]
    if os.path.isdir(chemin):
        candidats += [os.path.join(chemin, d) for d in sorted(os.listdir(chemin))]
    for c in candidats:
        if os.path.isdir(os.path.join(chemin_long(c), "connections")):
            return chemin_long(c)
    sys.exit("Export Instagram introuvable ou incomplet : " + chemin +
             "\nVérifie que tu as demandé le format JSON (et non HTML) et que le chemin est le bon.")


def main():
    parser = argparse.ArgumentParser(
        description="Analyse un export Instagram (format JSON) et génère une page HTML avec le graphique de ton réseau. "
                    "Tout reste sur ton ordinateur.")
    parser.add_argument("export", help="dossier de l'export Instagram, ou fichier .zip téléchargé")
    parser.add_argument("--ancien", metavar="EXPORT", help="export plus ancien, pour voir tout de suite ce qui a changé")
    parser.add_argument("--sortie", metavar="DOSSIER",
                        help="dossier où écrire la page et tes fichiers personnels (défaut : mes_donnees)")
    args = parser.parse_args()

    a_garder = []
    racine = ouvre_export(args.export, a_garder)
    regle_dossier(args.sortie or DOSSIER)
    os.makedirs(DOSSIER, exist_ok=True)

    if not os.path.exists(STORIES):
        with open(STORIES, "w", encoding="utf-8-sig", newline="") as f:
            f.write(MODELE_STORIES)

    donnees, non_resolus, avertissements = analyse(racine)
    ecrit_alias(non_resolus)
    ecrit_etiquettes(donnees)

    # Historique : chaque lancement garde la liste des abonnes, pour reperer les desabonnements
    # au prochain export. L'option --ancien (export plus ancien) permet de comparer tout de suite.
    instantanes = [instantane(donnees)]
    if args.ancien:
        instantanes.append(instantane(analyse(ouvre_export(args.ancien, a_garder))[0]))
    histo = met_a_jour_historique(instantanes)
    precedents = [h for h in histo if h["fin"] < donnees["fin"] - 86400]
    if precedents:
        donnees["changements"] = compare(precedents[-1], instantanes[0])

    with open(MODELE, encoding="utf-8") as f:
        page = f.read()
    charge_utile = json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")
    page = page.replace("/*__DONNEES__*/null", charge_utile)
    with open(SORTIE, "w", encoding="utf-8") as f:
        f.write(page)

    pers = donnees["personnes"]
    c = Counter(d["lien"] for d in pers)
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        out.reconfigure(encoding="utf-8", errors="replace")
    print(f"Compte : @{donnees['moi']['pseudo']}")
    print(f"Personnes : {len(pers)}  (mutuels {c['mutuel']}, suivis {c['suivi']}, "
          f"abonnés {c['abonne']}, sans lien {c['aucun']}, conversations non identifiées {c['inconnu']})")
    for k in ("msg_envoyes", "msg_recus", "likes_posts", "likes_stories", "reactions", "commentaires", "stories_vues"):
        print(f"  {k:14s} {sum(d[k] for d in pers):6d}   sur {sum(1 for d in pers if d[k])} personnes")
    print(f"Groupes de discussion : {len(donnees['groupes'])}")
    print(f"Stories suivies (stories_plus.csv) : {len(donnees['stories'])}, "
          f"{sum(1 for d in pers if d['a_vu_stories'])} spectateurs différents")
    fb = donnees["followback"]
    if fb:
        print(f"Follow-back quand tu suis en premier : {fb['tous'][0]}/{fb['tous'][1]}  "
              f"(avec messages {fb['avec_dm'][0]}/{fb['avec_dm'][1]}, sans {fb['sans_dm'][0]}/{fb['sans_dm'][1]})")
    print(f"Conversations où le dernier message vient de l'autre : {sum(1 for d in pers if d['attend_reponse'])}")
    ch = donnees["changements"]
    if ch:
        print(f"Depuis l'export du {ch['depuis']} : {len(ch['abonnes_perdus'])} abonnés perdus, "
              f"{len(ch['abonnes_gagnes'])} gagnés, {len(ch['plus_suivis'])} comptes que tu ne suis plus")
    else:
        print("Historique : premier export enregistré, la comparaison apparaîtra au prochain export")
    for a in avertissements:
        print("  Attention :", a)
    print(f"Conversations sans pseudo retrouvé : {len(non_resolus)}  (à compléter dans alias.csv)")
    print("Page générée :", lisible(SORTIE))


if __name__ == "__main__":
    main()
