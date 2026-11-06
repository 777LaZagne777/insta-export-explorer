#!/usr/bin/env python3
"""Genere un faux export Instagram, avec des comptes inventes, pour essayer l'outil sans donnees reelles.

    python demo/genere_export_fictif.py
    python analyse_instagram.py demo/export_fictif --sortie demo/sortie

Tous les comptes, noms, marques et lieux sont inventes. Le resultat est identique a chaque lancement.
"""
import csv
import datetime as dt
import json
import os
import random
import shutil
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
JOUR = 86400
FIN = int(dt.datetime(2026, 10, 31, 18, 0).timestamp())   # date fictive de l'export
DEBUT = FIN - 3 * 365 * JOUR
MOI = {"pseudo": "demo.compte", "nom": "Camille Démo"}

PRENOMS = [("Léa", "f"), ("Noah", "h"), ("Inès", "f"), ("Malo", "h"), ("Zoé", "f"), ("Elio", "h"), ("Jade", "f"),
           ("Sacha", "h"), ("Mila", "f"), ("Nino", "h"), ("Lou", "f"), ("Tom", "h"), ("Anaé", "f"), ("Côme", "h"),
           ("Romy", "f"), ("Axel", "h"), ("Nour", "f"), ("Théo", "h"), ("Maya", "f"), ("Yanis", "h"), ("Éline", "f"),
           ("Loris", "h"), ("Clara", "f"), ("Marius", "h"), ("Alix", "a"), ("Charlie", "a")]
NOMS = ["Tournesol", "Mésange", "Glacier", "Comète", "Lagune", "Boussole", "Pivoine", "Granite", "Cascade", "Zéphyr",
        "Corail", "Lanterne", "Chardon", "Brindille", "Falaise", "Girofle", "Noisette", "Écume", "Tilleul", "Orage"]
THEMES = ["atelier", "studio", "rando", "cuisine", "skate", "astro", "jardin", "retro", "vinyle", "bivouac", "pixel", "tricot"]
SUFFIXES = ["quotidien", "club", "labo", "mag", "collectif", "officiel", "media"]
MARQUES = ["Chaussettes Lunaires", "Banque du Lagon", "Vélos Comète", "Café Boussole", "Maison Pivoine", "Granite Outdoor",
           "Écume Cosmétiques", "Tilleul Assurances", "Orage Énergie", "Lanterne Éditions", "Brindille Bio", "Zéphyr Voyages"]
CATEGORIES = ["Utilisation du Wi-Fi", "Voyageurs fréquents", "Amis de personnes fêtant bientôt leur anniversaire",
              "Changement récent d'appareil", "Accès mobile : tous les appareils"]
LIEUX = ["Port-Lagune", "Val-Comète", "Mont-Granite", "Baie-des-Pivoines", "Saint-Zéphyr"]


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def fabrique_comptes(rnd):
    """Invente des comptes : des personnes, puis des comptes de createurs."""
    vus, personnes, createurs = {MOI["pseudo"]}, [], []
    while len(personnes) < 100:
        (prenom, genre), nom = rnd.choice(PRENOMS), rnd.choice(NOMS)
        forme = rnd.choice(["{p}.{n}", "{p}_{n}", "{p}{n}", "{p}.{n}{x:02d}", "{p}_{n}_{x}"])
        pseudo = sans_accents(forme.format(p=prenom, n=nom, x=rnd.randint(1, 99))).lower()
        if pseudo not in vus:
            vus.add(pseudo)
            personnes.append({"pseudo": pseudo, "nom": prenom + " " + nom, "genre": genre})
    while len(createurs) < 35:
        theme, suffixe = rnd.choice(THEMES), rnd.choice(SUFFIXES)
        pseudo = theme + "." + suffixe
        if pseudo not in vus:
            vus.add(pseudo)
            createurs.append({"pseudo": pseudo, "nom": theme.capitalize() + " " + suffixe.capitalize(), "genre": ""})
    return personnes, createurs


def interaction(ts, compte):
    """Un like, une story vue... dans le format de l'export : date + bloc « Propriétaire »."""
    return {"timestamp": ts, "media": [], "fbid": "0", "label_values": [
        {"label": "URL", "value": "https://www.instagram.com/p/FICTIF/", "href": "https://www.instagram.com/p/FICTIF/"},
        {"title": "Propriétaire", "dict": [{"title": "", "dict": [
            {"label": "URL", "value": ""}, {"label": "Nom", "value": compte["nom"]},
            {"label": "Nom de profil", "value": compte["pseudo"]}]}]}]}


def fiche(ts, compte):
    return {"timestamp": ts, "media": [], "fbid": "0", "label_values": [
        {"label": "URL", "value": ""}, {"label": "Nom", "value": compte["nom"]},
        {"label": "Nom de profil", "value": compte["pseudo"]}]}


def conversation(rnd, autre, volume, debut, fin, part_moi):
    """Messages fictifs regroupes en echanges, sans contenu reel."""
    messages, restant = [], volume
    while restant > 0:
        n = min(restant, rnd.randint(2, 18))
        t = rnd.randint(debut, fin)
        qui = MOI["nom"] if rnd.random() < part_moi else autre
        for _ in range(n):
            messages.append({"sender_name": qui, "timestamp_ms": t * 1000, "content": "Message fictif"})
            if rnd.random() < 0.7:
                qui = autre if qui == MOI["nom"] else MOI["nom"]
            t = min(FIN, t + rnd.choice([8, 15, 30, 45, 60, 90, 120, 300, 900, 3600]))
        restant -= n
    return sorted(messages, key=lambda m: -m["timestamp_ms"])


def chemin_long(chemin):
    """Sous Windows, autorise les chemins de plus de 260 caracteres."""
    chemin = os.path.abspath(chemin)
    return "\\\\?\\" + chemin if os.name == "nt" and not chemin.startswith("\\\\") else chemin


def genere(dossier_export=None, dossier_sortie=None):
    dossier_export = chemin_long(dossier_export or os.path.join(ICI, "export_fictif"))
    dossier_sortie = chemin_long(dossier_sortie or os.path.join(ICI, "sortie"))
    rnd = random.Random(7)
    shutil.rmtree(dossier_export, ignore_errors=True)
    os.makedirs(dossier_sortie, exist_ok=True)

    def ecrit(chemin, contenu):
        cible = os.path.join(dossier_export, *chemin.split("/"))
        os.makedirs(os.path.dirname(cible), exist_ok=True)
        with open(cible, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False)

    personnes, createurs = fabrique_comptes(rnd)
    amis, suivis_seuls, abonnes_seuls = personnes[:60], personnes[60:78], personnes[78:86]
    contacts_hors, demandes = personnes[86:91], personnes[91:96]
    crea_suivis, crea_vus = createurs[:25], createurs[25:]

    # --- Abonnements et abonnes
    suivis, abonnes = {}, {}
    for c in amis:
        ts = rnd.randint(DEBUT, FIN - 20 * JOUR)
        suivis[c["pseudo"]] = ts
        abonnes[c["pseudo"]] = ts - rnd.randint(7200, 3 * JOUR) if rnd.random() < 0.6 else min(FIN, ts + rnd.randint(7200, 10 * JOUR))
    for c in suivis_seuls + crea_suivis:
        suivis[c["pseudo"]] = rnd.randint(DEBUT, FIN - 5 * JOUR)
    for c in abonnes_seuls:
        abonnes[c["pseudo"]] = rnd.randint(FIN - 300 * JOUR, FIN - 2 * JOUR)
    url = "https://www.instagram.com/"
    ecrit("connections/followers_and_following/followers_1.json",
          [{"title": "", "media_list_data": [], "string_list_data": [{"href": url + u, "value": u, "timestamp": ts}]} for u, ts in abonnes.items()])
    ecrit("connections/followers_and_following/following.json", {"relationships_following": [
        {"title": u, "string_list_data": [{"href": url + u, "timestamp": ts}]} for u, ts in suivis.items()]})
    ecrit("connections/followers_and_following/close_friends.json", [fiche(FIN - 90 * JOUR, c) for c in amis[:6]])
    ecrit("connections/followers_and_following/pending_follow_requests.json", [fiche(FIN - rnd.randint(1, 40) * JOUR, c) for c in demandes])
    ecrit("connections/followers_and_following/recently_unfollowed_profiles.json", [fiche(FIN - 12 * JOUR, createurs[-1])])
    ecrit("personal_information/personal_information/personal_information.json", {"profile_user": [{
        "title": "", "media_map_data": {}, "string_map_data": {
            "Username": {"href": "", "value": MOI["pseudo"], "timestamp": 0}, "Name": {"href": "", "value": MOI["nom"], "timestamp": 0},
            "Private Account": {"href": "", "value": "False", "timestamp": 0}}}]})

    # --- Likes, stories, commentaires (les premiers amis sont les plus proches)
    likes_posts, likes_stories, stories_vues, reactions, commentaires = [], [], [], [], []
    for i, c in enumerate(amis):
        depuis = max(suivis[c["pseudo"]], FIN - 500 * JOUR)
        poids = 1 / (i + 1) ** 0.6
        likes_stories += [interaction(rnd.randint(depuis, FIN), c) for _ in range(rnd.randint(0, int(14 * poids) + 1))]
        likes_posts += [interaction(rnd.randint(depuis, FIN), c) for _ in range(rnd.randint(0, int(6 * poids) + 1))]
        stories_vues += [interaction(rnd.randint(FIN - 7 * JOUR, FIN), c) for _ in range(rnd.randint(0, 3))]
        if i < 8 and rnd.random() < 0.6:
            reactions.append(interaction(rnd.randint(depuis, FIN), c))
            commentaires.append({"media_list_data": [], "string_map_data": {
                "Comment": {"value": "Commentaire fictif"}, "Media Owner": {"value": c["pseudo"]},
                "Time": {"timestamp": rnd.randint(depuis, FIN)}}})
    for c in crea_suivis + crea_vus:
        depuis = suivis.get(c["pseudo"], FIN - 200 * JOUR)
        likes_posts += [interaction(rnd.randint(depuis, FIN), c) for _ in range(rnd.choice([0, 0, 1, 2, 4, 9]))]
        stories_vues += [interaction(rnd.randint(FIN - 7 * JOUR, FIN), c) for _ in range(rnd.choice([0, 1, 3, 6]))]
    # Un export complet contient de l'activite des le premier abonnement
    tous = {c["pseudo"]: c for c in personnes + createurs}
    premier = min(suivis, key=suivis.get)
    likes_posts.append(interaction(suivis[premier] + 3600, tous[premier]))
    ecrit("your_instagram_activity/likes/liked_posts.json", likes_posts)
    ecrit("your_instagram_activity/story_interactions/story_likes.json", likes_stories)
    ecrit("your_instagram_activity/story_interactions/stories_viewed.json", stories_vues)
    ecrit("your_instagram_activity/story_interactions/emoji_story_reactions.json", reactions)
    ecrit("your_instagram_activity/comments/post_comments_1.json", commentaires)

    # --- Messages prives : quelques grosses conversations, beaucoup de petites
    profils = ["stable", "stable", "hausse", "eteinte", "nouvelle", "baisse"]
    correspondants = amis[:34] + contacts_hors + suivis_seuls[:3] + [{"pseudo": None, "nom": "Surnom Introuvable"}]
    for i, c in enumerate(correspondants):
        volume = max(1, int(700 / (i + 1) ** 1.1))
        debut, profil, part = max(suivis.get(c["pseudo"], FIN - 400 * JOUR), FIN - 700 * JOUR), profils[i % len(profils)], rnd.uniform(0.2, 0.8)
        if profil == "eteinte":
            msgs = conversation(rnd, c["nom"], volume, debut, max(debut + JOUR, FIN - 220 * JOUR), part)
        elif profil == "nouvelle":
            msgs = conversation(rnd, c["nom"], volume, FIN - 80 * JOUR, FIN, part)
        elif profil == "hausse":
            msgs = conversation(rnd, c["nom"], volume // 4 + 1, FIN - 180 * JOUR, FIN - 91 * JOUR, part) + conversation(rnd, c["nom"], volume, FIN - 90 * JOUR, FIN, part)
        elif profil == "baisse":
            msgs = conversation(rnd, c["nom"], volume, FIN - 180 * JOUR, FIN - 91 * JOUR, part) + conversation(rnd, c["nom"], volume // 5 + 1, FIN - 90 * JOUR, FIN, part)
        else:
            msgs = conversation(rnd, c["nom"], volume, debut, FIN, part)
        msgs.sort(key=lambda m: -m["timestamp_ms"])
        ecrit(f"your_instagram_activity/messages/inbox/fil_{i:03d}/message_1.json", {
            "participants": [{"name": c["nom"]}, {"name": MOI["nom"]}], "messages": msgs,
            "title": c["nom"], "is_still_participant": True, "thread_path": f"inbox/fil_{i:03d}"})
    for i, membres in enumerate([amis[2:5], amis[9:12]]):
        ecrit(f"your_instagram_activity/messages/inbox/groupe_{i}/message_1.json", {
            "participants": [{"name": c["nom"]} for c in membres] + [{"name": MOI["nom"]}],
            "messages": [{"sender_name": rnd.choice(membres)["nom"], "timestamp_ms": rnd.randint(FIN - 100 * JOUR, FIN) * 1000, "content": "Message fictif"} for _ in range(40)],
            "title": "Groupe fictif", "is_still_participant": True, "thread_path": f"inbox/groupe_{i}"})

    # --- Ce qu'Instagram sait : annonceurs, categories, lieux, traces
    pubs = "ads_information/instagram_ads_and_businesses/"
    ecrit(pubs + "advertisers_using_your_activity_or_information.json", {"media": [], "fbid": "0", "label_values": [
        {"label": "Annonceurs qui ont importé une liste d’audience contenant des entrées correspondant à votre profil Instagram",
         "vec": [{"value": m} for m in MARQUES] + [{"value": f"Agence fictive n° {k}"} for k in range(1, 41)]},
        {"label": "Annonceurs qui ont importé une liste d’audience correspondant à votre profil en fonction de vos interactions",
         "vec": [{"value": m} for m in MARQUES[:5]]}]})
    ecrit(pubs + "other_categories_used_to_reach_you.json", {"media": [], "fbid": "0", "label_values": [{"label": "Nom", "vec": [{"value": c} for c in CATEGORIES]}]})
    recents = lambda n, comptes: [interaction(rnd.randint(FIN - 6 * JOUR, FIN), rnd.choice(comptes)) for _ in range(n)]
    ecrit("ads_information/ads_and_topics/ads_viewed.json", recents(120, createurs[:12]))
    ecrit("ads_information/ads_and_topics/videos_watched.json", recents(400, createurs))
    ecrit("ads_information/ads_and_topics/posts_viewed.json", recents(90, createurs))
    infos = "personal_information/information_about_you/"
    ecrit(infos + "locations_of_interest.json", {"media": [], "fbid": "0", "label_values": [{"label": "Lieux d’intérêt", "vec": [{"value": v} for v in LIEUX]}]})
    ecrit(infos + "profile_based_in.json", {"media": [], "fbid": "0", "label_values": [{"label": "Lieu", "dict": [
        {"label": "Pays", "value": "Pays imaginaire"}, {"label": "Ville", "value": LIEUX[0]}]}]})
    ecrit("connections/contacts/synced_contacts.json", {"contacts_contact_info": [{"string_map_data": {"First Name": {"value": "Contact fictif"}}} for _ in range(85)]})
    ecrit("security_and_login_information/login_and_profile_creation/login_activity.json", {"account_history_login_history": [{"title": "", "string_map_data": {}} for _ in range(5)]})
    ecrit("logged_information/recent_searches/profile_searches.json", {"searches_user": [{"title": c["pseudo"], "string_list_data": [{"timestamp": FIN - JOUR}]} for c in demandes[:3]]})
    ecrit("logged_information/link_history/link_history.json", [{"timestamp": FIN - k * JOUR, "media": [], "label_values": []} for k in range(4)])

    # --- Statistiques de compte professionnel
    stats = "logged_information/past_instagram_insights/"
    valeurs = lambda d: {k: {"href": "", "value": str(v), "timestamp": 0} for k, v in d.items()}
    ecrit(stats + "audience_insights.json", {"organic_insights_audience": [{"title": "", "media_map_data": {}, "string_map_data": valeurs({
        "Période": "1 août - 31 oct.", "Followers": len(abonnes), "Followers en plus": 9, "Followers en moins": 3})}]})
    ecrit(stats + "profiles_reached.json", {"organic_insights_reach": [{"title": "", "media_map_data": {}, "string_map_data": valeurs({
        "Période": "1 août - 31 oct.", "Comptes touchés": 212, "Followers": 58, "Non-followers": 154, "Impressions": 1630, "Visites du profil": 47})}]})
    ecrit(stats + "stories.json", {"organic_insights_stories": [{"title": "", "media_map_data": {}, "string_map_data": {
        "Timestamp de la création": {"href": "", "value": "", "timestamp": FIN - k * 7 * JOUR - rnd.randint(0, 3) * JOUR},
        **valeurs({"Comptes touchés": rnd.randint(22, 52), "Impressions": rnd.randint(52, 70), "Réponses": rnd.choice([0, 0, 1, 2])})}} for k in range(40)]})

    # --- Fichiers personnels de demonstration, a cote de la page generee
    spectateurs = [u for u in abonnes]
    with open(os.path.join(dossier_sortie, "stories_plus.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "story", "revisionnages", "spectateurs"])
        for k, titre in enumerate(["Concert", "Randonnée", "Anniversaire", "Lever de soleil", "Recette", "Marché"]):
            vus = rnd.sample(spectateurs, rnd.randint(int(0.45 * len(spectateurs)), int(0.7 * len(spectateurs))))
            w.writerow([dt.date.fromtimestamp(FIN - (18 - 3 * k) * JOUR).isoformat(), titre, rnd.randint(4, 15),
                        ", ".join(u + (":" + str(rnd.randint(2, 3)) if rnd.random() < 0.12 else "") for u in vus)])
    with open(os.path.join(dossier_sortie, "etiquettes.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["pseudo", "nom", "etiquette", "genre"])
        for i, c in enumerate(amis + suivis_seuls):
            w.writerow([c["pseudo"], c["nom"], ["pote", "famille", "", "sport", "", "à retirer"][i % 6] if i < 30 else "", c["genre"]])
    with open(os.path.join(dossier_sortie, "alias.csv"), "w", encoding="utf-8-sig", newline="") as f:
        # Correspondances nom de conversation -> pseudo ; deux sont laissees vides pour montrer le cas
        csv.writer(f, delimiter=";").writerows([["nom_conversation", "pseudo"]] + [
            [c["nom"], "" if i in (5, 11) else c["pseudo"]] for i, c in enumerate(correspondants) if c["pseudo"]])
    ancien = FIN - 92 * JOUR
    anciens_abonnes = {u: ts for u, ts in abonnes.items() if ts <= ancien}
    anciens_abonnes.update({c["pseudo"]: ancien - 60 * JOUR for c in personnes[96:99]})   # partis depuis
    anciens_suivis = {u: ts for u, ts in suivis.items() if ts <= ancien}
    anciens_suivis[createurs[-1]["pseudo"]] = ancien - 200 * JOUR                           # plus suivi depuis
    with open(os.path.join(dossier_sortie, "historique.json"), "w", encoding="utf-8") as f:
        json.dump({"instantanes": [{"date": dt.date.fromtimestamp(ancien).isoformat(), "fin": ancien,
                                    "debut_abonnes": min(anciens_abonnes.values()), "abonnes": anciens_abonnes, "suivis": anciens_suivis}]}, f)

    return {"export": dossier_export, "sortie": dossier_sortie, "suivis": len(suivis), "abonnes": len(abonnes),
            "mutuels": len(amis), "conversations": len(correspondants), "partis": 3}


if __name__ == "__main__":
    bilan = genere()
    print("Export fictif écrit dans :", bilan["export"].replace("\\\\?\\", ""))
    print(f"{bilan['suivis']} abonnements, {bilan['abonnes']} abonnés, {bilan['conversations']} conversations, tous inventés.")
    print("Pour générer la page de démonstration :")
    print("    python analyse_instagram.py demo/export_fictif --sortie demo/sortie")
