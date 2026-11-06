"""Tests sur l'export fictif : aucun fichier personnel n'est necessaire.

    python -m unittest discover tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "demo"))

import analyse_instagram as outil          # noqa: E402
import genere_export_fictif as fictif      # noqa: E402


class TestSurExportFictif(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.bilan = fictif.genere(os.path.join(cls.tmp, "export"), os.path.join(cls.tmp, "sortie"))
        outil.regle_dossier(cls.bilan["sortie"])
        cls.donnees, cls.non_resolus, cls.avertissements = outil.analyse(cls.bilan["export"])
        cls.personnes = cls.donnees["personnes"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_abonnements_et_abonnes(self):
        self.assertEqual(sum(1 for p in self.personnes if p["suivi_depuis"]), self.bilan["suivis"])
        self.assertEqual(sum(1 for p in self.personnes if p["abonne_depuis"]), self.bilan["abonnes"])
        self.assertEqual(sum(1 for p in self.personnes if p["lien"] == "mutuel"), self.bilan["mutuels"])

    def test_profil(self):
        self.assertEqual(self.donnees["moi"]["pseudo"], "demo.compte")
        self.assertFalse(self.donnees["moi"]["prive"])

    def test_score_egal_a_la_somme_des_points_par_mois(self):
        for p in self.personnes:
            self.assertAlmostEqual(sum(p["pts_mois"].values()), p["score"], delta=0.2)

    def test_messages_et_conversations(self):
        self.assertGreater(sum(p["msg_envoyes"] + p["msg_recus"] for p in self.personnes), 1000)
        conv = self.donnees["conversations"]
        self.assertGreater(conv["init_moi"], 0)
        self.assertGreater(conv["init_autre"], 0)
        self.assertEqual(len(self.donnees["groupes"]), 2)

    def test_aucun_contenu_de_message_dans_les_donnees(self):
        import json
        self.assertNotIn("Message fictif", json.dumps(self.donnees, ensure_ascii=False))

    def test_stories_et_etiquettes(self):
        self.assertEqual(len(self.donnees["stories"]), 6)
        self.assertTrue(any(p["a_vu_stories"] for p in self.personnes))
        self.assertTrue(any(p["etiquette"] for p in self.personnes))
        self.assertEqual(self.avertissements, [])

    def test_follow_back_coherent(self):
        fb = self.donnees["followback"]
        self.assertEqual(fb["tous"][0], fb["avec_dm"][0] + fb["sans_dm"][0])
        self.assertEqual(fb["tous"][1], fb["avec_dm"][1] + fb["sans_dm"][1])

    def test_insights_et_donnees_instagram(self):
        self.assertEqual({t["fichier"] for t in self.donnees["insights"]}, {"audience_insights", "profiles_reached", "stories"})
        self.assertGreater(len(self.donnees["sait"]["annonceurs"]), 0)

    def test_comparaison_de_deux_exports(self):
        ancien = {"date": "2026-05-01", "fin": 100, "debut_abonnes": 10, "abonnes": {"a": 20, "b": 30, "vieux": 5}, "suivis": {"x": 1, "y": 2}}
        nouveau = {"date": "2026-11-01", "fin": 200, "debut_abonnes": 15, "abonnes": {"a": 20, "c": 150, "deja_la": 60}, "suivis": {"x": 1, "z": 3}}
        self.assertEqual(outil.compare(ancien, nouveau), {
            "depuis": "2026-05-01", "abonnes_perdus": ["b"], "abonnes_gagnes": ["c"], "plus_suivis": ["y"], "nouveaux_suivis": ["z"]})

    def test_dates_acceptees(self):
        self.assertEqual(outil.lit_date("2026-11-06"), outil.lit_date("06/11/2026"))
        self.assertIsNone(outil.lit_date("pas une date"))

    def test_le_script_complet_fonctionne_aussi_sur_un_zip(self):
        archive = os.path.join(self.tmp, "export.zip")
        export = self.bilan["export"]
        with zipfile.ZipFile(archive, "w") as z:
            for dossier, _, fichiers in os.walk(export):
                for f in fichiers:
                    chemin = os.path.join(dossier, f)
                    z.write(chemin, os.path.join("instagram-demo", os.path.relpath(chemin, export)))
        sortie = os.path.join(self.tmp, "sortie_zip")
        r = subprocess.run([sys.executable, os.path.join(RACINE, "analyse_instagram.py"), archive, "--sortie", sortie],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(outil.chemin_long(os.path.join(sortie, "reseau_instagram.html")), encoding="utf-8") as f:
            page = f.read()
        self.assertNotIn("/*__DONNEES__*/null", page)
        self.assertIn("demo.compte", page)


if __name__ == "__main__":
    unittest.main()
