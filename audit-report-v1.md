# Rapport d'Audit — CorbeauSplat v1.0.0

*Date : 2026-06-17*  
*Périmètre : code source complet (Python + shell), sans les assets graphiques*  
*Commit audité : HEAD*

## Résumé

**Score global : 7,5/10**

**Progression : +1,0 point par rapport à v0.99.5 (était 6,5/10)**

Le refactoring massif entre v0.99.5 et v1.0.0 est une réussite architecturale notable : `main.py` et `setup_dependencies.py` ont été décomposés de manière propre, `nerfstudio` est isolé dans `.venv_4dgs`, la logique Sharp vidéo est unifiée, et la suite de tests est passée de 39 à 209 tests collectés. Cependant, plusieurs points de sécurité de la chaîne d'approvisionnement restent ouverts (Homebrew via pipe, rustup sans checksum, modèles upscayl sans intégrité), et la suite de tests présente une régression bloquante en exécution collective.

| Sévérité | v0.99.5 | v1.0.0 |
|----------|---------|--------|
| Critique | 0 | 0 |
| Haute | 4 | 2 |
| Moyenne | 13 | 11 |
| Basse | 8 | 7 |

---

## Progression vs v0.99.5

### ✅ Problèmes résolus

1. **`main.py` refactorisé (753 → 13 lignes)**  
   `app/cli/parser.py`, `app/cli/commands.py`, `app/cli/launcher.py` et `app/cli/__init__.py` constituent une CLI modulaire et testable. `python main.py --help` expose les 8 sous-commandes attendues. — **RÉSOLU**

2. **`setup_dependencies.py` refactorisé (993 → 100 lignes)**  
   Les installateurs sont maintenant dans `app/scripts/installers/` (`brush.py`, `upscayl.py`, `mapping.py`, `sharp.py`, `supersplat.py`, `extractor_360.py`, `base.py`, `tools.py`). `setup_dependencies.py` ne fait plus qu'orchestrer et réexporter pour la compatibilité. — **RÉSOLU**

3. **`FourDGSTab` / `FourDGSEngine` isolent `nerfstudio` dans `.venv_4dgs`**  
   Le code n'installe plus `nerfstudio` dans l'interpréteur principal. `four_dgs_engine.py:10`, `four_dgs_tab.py:17-30`, `four_dgs_tab.py:160-188`. — **RÉSOLU**

4. **Logique Sharp vidéo unifiée dans `SharpEngine.process_video_frames()`**  
   `app/core/sharp_engine.py:103-225` centralise l'extraction FFmpeg + prédiction frame par frame. Le CLI délègue via `_run_sharp_video()` (`app/cli/commands.py:178-206`). — **RÉSOLU**

5. **`BrushTab.run_standalone()` utilise `BrushEngine.build_command()`**  
   `app/gui/tabs/brush_tab.py:562-565` construit la commande via `engine.build_command()` et respecte donc `build_mode`, `sh_degree`, `refine_every`, etc. — **RÉSOLU**

6. **`checksums.json` partiellement rempli et documenté**  
   Les empreintes darwin de Brush (`7742e8ac...`), upscayl (`b7f54f36...`) et Glomap (`23c7983e...`) sont renseignées, et un champ `_instructions` explique comment les générer. — **PARTIEL** (voir persistance)

7. **`AppLifecycle.reset_factory()` supprime directement en Python avec validation `relative_to()`**  
   `app/gui/managers.py:144-199` ne génère plus de script temporaire externe et vérifie que chaque cible est contenue dans `root_dir`. — **PARTIEL** (voir persistance)

8. **`manifest.md` synchronisé avec `app/__init__.py`**  
   Ligne 33 de `manifest.md` indique désormais `VERSION = "1.0.0"`. — **RÉSOLU**

9. **Couverture de tests considérablement élargie**  
   11 fichiers de test couvrent CLI, COLMAP, upscayl, Sharp, 4DGS, setup dependencies, managers, workers (skipés sans PyQt6), base engine, brush engine et export engine. — **PARTIEL** (voir régression ci-dessous)

### 🔶 Problèmes persistants

#### Sécurité

1. **`run.command` télécharge et exécute Homebrew via un pipe non vérifié** — `run.command:84`  
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` est toujours exécuté sans vérification de tag ni de checksum.  
   **Verdict : PERSISTANT** — Haute  
   **Correction suggérée :** Épingler une release taguée, vérifier le SHA256 de `install.sh` avant exécution, ou rendre l'installation manuelle obligatoire.

2. **`install_rust_toolchain()` télécharge `rustup.rs` sans vérification effective** — `app/scripts/installers/tools.py:121-148`  
   Le checksum attendu (`darwin_rustup` / `linux_rustup`) est vide dans `checksums.json`, donc `verify_download()` retourne `True` d'office.  
   **Verdict : PERSISTANT** — Haute  
   **Correction suggérée :** Remplir `checksums.json` pour rustup ou refuser l'installation automatique de Rust.

3. **`DropLineEdit` ne valide les chemins déposés que par leur existence** — `app/gui/widgets/drop_line_edit.py:29-34`  
   `_validate_path()` vérifie uniquement `p.exists()`. Aucune vérification de containment dans le projet ou le home.  
   **Verdict : PERSISTANT** — Moyenne  
   **Correction suggérée :** Appeler `BaseEngine.validate_path()` ou une fonction utilitaire partagée pour restreindre les chemins autorisés.

4. **`download_model_files()` télécharge les modèles upscayl sans vérification d'intégrité** — `app/upscayl_manager.py:334-365`  
   Seule une taille minimale de 512 octets est vérifiée. Aucun SHA256 ni signature.  
   **Verdict : PERSISTANT** — Moyenne  
   **Correction suggérée :** Ajouter les SHA256 des modèles dans `upscayl_models.py` ou `checksums.json` et vérifier après téléchargement.

5. **`checksums.json` incomplet pour les plateformes Linux et rustup** — `app/scripts/checksums.json:4-10`  
   `linux_brush`, `linux_upscayl`, `linux_glomap`, `darwin_rustup`, `linux_rustup` sont vides. Sur Linux, les vérifications SHA256 de Brush, upscayl et Glomap sont sans effet.  
   **Verdict : PERSISTANT (partiellement corrigé)** — Haute  
   **Correction suggérée :** Remplir toutes les entrées attendues par plateforme, ou refuser l'installation si une empreinte est manquante (`verify_download_strict`).

6. **`ColmapEngine.delete_project_content()` accepte encore n'importe quel sous-dossier de `$HOME`** — `app/core/engine.py:764-808`  
   La validation permet la suppression dans `project_root` **ou** `Path.home()`. N'importe quel dossier utilisateur (ex. `~/Applications`, `~/Documents`) peut être mis à la corbeille.  
   **Verdict : PERSISTANT (partiellement corrigé)** — Moyenne  
   **Correction suggérée :** Restreindre la suppression aux sous-dossiers de `project_root` uniquement.

7. **`AppLifecycle.reset_factory()` vulnérable aux symlinks sortants** — `app/gui/managers.py:163-165`  
   `(root_dir / rel).resolve()` est appelé avant `relative_to()`. Si une cible est un symlink pointant hors du projet, `.resolve()` suit le symlink et la cible résolue peut échapper au `root_dir`.  
   **Verdict : PERSISTANT (partiellement corrigé)** — Moyenne  
   **Correction suggérée :** Vérifier `relative_to()` sur le chemin non résolu ou utiliser `os.path.realpath()` avec précaution ; journaliser chaque suppression.

8. **`install_node_js()` et `install_build_tools()` masquent les échecs par des `except:` nus** — `app/scripts/installers/tools.py:105-118`  
   Les exceptions ne sont pas journalisées ni typées.  
   **Verdict : PERSISTANT** — Basse  
   **Correction suggérée :** Attraper `(subprocess.CalledProcessError, OSError)` et logger `logger.exception(...)`.

9. **Binaires téléchargés reçoivent les permissions `0o755`** — `app/scripts/installers/brush.py:209`, `app/upscayl_manager.py:171`  
   Les exécutables sont lisibles/exécutables par tous les utilisateurs.  
   **Verdict : PERSISTANT** — Basse  
   **Correction suggérée :** Utiliser `0o700` pour les binaires utilisateur.

10. **Appels `subprocess.check_call` sans timeout dans les installations longues** — `app/scripts/installers/tools.py:108-116`, `brush.py:259-260`, `mapping.py:126-127`  
    Aucun `timeout` n'est passé à `cmake`, `ninja`, `npm install`, `cargo install`.  
    **Verdict : PERSISTANT** — Basse  
    **Correction suggérée :** Ajouter un timeout raisonnable (ex. 1800 s pour compilation, 300 s pour npm).

#### Performance

11. **`_check_and_normalize_resolution()` lit l'intégralité des images avec `cv2.imread()`** — `app/core/engine.py:405-414`  
    Toutes les images sont chargées en mémoire uniquement pour collecter leurs dimensions.  
    **Verdict : PERSISTANT** — Moyenne  
    **Correction suggérée :** Lire les dimensions via `PIL.Image.open(...).size` sans charger les pixels.

12. **Les exports PLY bouclent point par point en Python pur** — `app/core/export_engine.py:128-135`, `198-209`, `371-379`, `434-475`  
    Les exports XYZ, OBJ, SPZ et le fallback GLB/assimp utilisent des boucles `for i in range(len(vertex))`.  
    **Verdict : PERSISTANT** — Moyenne  
    **Correction suggérée :** Vectoriser avec NumPy/arrays structurées et écrire les buffers en une seule passe.

13. **Thread consommateur de stdout SuperSplat jamais rejoint** — `app/core/superplat_engine.py:69-75`  
    Un daemon thread est lancé mais jamais arrêté ni joint.  
    **Verdict : PERSISTANT** — Basse  
    **Correction suggérée :** Ajouter un mécanisme d'événement pour arrêter proprement la boucle de consommation.

14. **`LogsTab.append_log()` sans limitation de débit** — `app/gui/tabs/logs_tab.py:36-41`  
    Chaque ligne de log déclenche `QTextEdit.append()` et repositionne le curseur.  
    **Verdict : PERSISTANT** — Basse  
    **Correction suggérée :** Bufferiser les mises à jour (ex. toutes les 100 ms) ou limiter le nombre de lignes affichées.

#### Architecture

15. **Plusieurs modules dépassent les seuils de maintenabilité (>500 lignes)**  
    - `app/core/engine.py` — 808 lignes  
    - `app/core/export_engine.py` — 721 lignes  
    - `app/gui/workers.py` — 526 lignes  
    - `app/gui/tabs/config_tab.py` — 638 lignes  
    - `app/gui/tabs/brush_tab.py` — 569 lignes  
    **Verdict : PERSISTANT** — Moyenne  
    **Correction suggérée :** Continuer l'extraction des sous-classes et helpers (exports, workers, onglets).

16. **Double source de vérité sur le `build_mode` de Brush**  
    `BrushEngineDep.install()` lit `config.json` (`brush.py:69-72`) tandis que `get_brush_build_mode()` (`app/core/system.py:143-154`) et `BrushEngine.build_command()` (`brush_engine.py:56`) se basent sur `engines/brush.version`. L'interface conserve probablement un troisième widget `combo_build_mode`.  
    **Verdict : PERSISTANT (partiellement corrigé)** — Moyenne  
    **Correction suggérée :** Faire de `engines/brush.version` la seule source de vérité et synchroniser le GUI/CLI en conséquence.

17. **Pas de couche centralisée de validation des paramètres numériques/énumérés**  
    Les paramètres sont passés directement aux commandes externes. `argparse` valide en CLI mais pas la voie GUI.  
    **Verdict : PERSISTANT** — Moyenne  
    **Correction suggérée :** Introduire un schéma de validation partagé (Pydantic ou dataclasses avec `__post_init__`).

18. **`AGENTS.md` et `CLAUDE.md` ne sont pas suivis par Git**  
    `git status` les montre comme `??`. Ils contiennent des instructions pour les agents.  
    **Verdict : PERSISTANT** — Moyenne  
    **Correction suggérée :** Les ajouter au dépôt ou les ignorer explicitement dans `.gitignore`.

#### Qualité du code

19. **`export_engine.py` attrape `Exception` de manière générique** — `app/core/export_engine.py:94`, `110`, `161`, `262`, `321`, `352`, `395`, `506`, `693`, `716`  
    Toutes les erreurs d'export sont capturées et loguées sans distinction.  
    **Verdict : PERSISTANT** — Moyenne  
    **Correction suggérée :** Distinguer erreurs attendues (`ImportError`, `FileNotFoundError`) et erreurs système graves (`MemoryError`, `PermissionError`).

20. **`BaseEngine._execute_command()` affiche la commande complète** — `app/core/base_engine.py:117`  
    `' '.join(map(str, cmd))` pourrait exposer des arguments sensibles dans les logs.  
    **Verdict : PERSISTANT** — Basse  
    **Correction suggérée :** Sanitiser les arguments sensibles ou proposer un mode verbose sécurisé.

21. **`requirements.txt` utilise des plages de versions larges** — `requirements.txt:1-8`  
    `PyQt6>=6.6,<7`, `numpy>=1.26,<3`, etc. autorisent des mineures non testées.  
    **Verdict : PERSISTANT** — Basse  
    **Correction suggérée :** Épingler les versions mineures testées et commiter un `requirements.lock`.

22. **`run.command` réinstalle des paquets optionnels sans version fixe** — `run.command:203-222`  
    `PyQt6`, `send2trash`, `plyfile`, `trimesh` sont installés au runtime sans version ni lockfile.  
    **Verdict : PERSISTANT** — Basse  
    **Correction suggérée :** Centraliser dans `requirements.txt` / `pyproject.toml` et installer depuis un lockfile.

#### Tests & maintenabilité

23. **`pyproject.toml` configuré mais les outils ne sont pas installés**  
    `ruff`, `mypy` et `pip-audit` ne sont pas présents dans l'environnement actif.  
    **Verdict : PERSISTANT** — Moyenne  
    **Correction suggérée :** Ajouter les outils aux dépendances de développement et un workflow CI (lint + type check + tests + `pip-audit`).

### 🆕 Nouveaux problèmes détectés

1. **`tests/test_managers.py::TestAppLifecycleRestart::test_restart_with_save_callback` tente d'exécuter `os.execv` sans le patcher** — `tests/test_managers.py:207-214`  
    Le test appelle `AppLifecycle.restart()`, qui tente `os.execv(python, args)` (`app/gui/managers.py:130-132`). Comme `os.execv` n'est pas mocké dans ce test, il remplace le processus pytest par `python /tmp/.../main.py` (fichier inexistant), ce qui bloque/fait échouer la suite en exécution collective.  
    **Verdict : NOUVEAU — Moyenne**  
    **Correction suggérée :** Patcher `os.execv` comme dans `test_restart_normal` (`tests/test_managers.py:167`), ou isoler le test avec `pytest.mark.forked`.

2. **20 tests de workers sont skipés en l'absence de PyQt6** — `tests/test_workers.py:20 skipped`  
    Si l'environnement de CI n'installe pas PyQt6, la couverture des workers est nulle. Bien que documenté comme attendu, cela constitue un trou de couverture sur une couche critique.  
    **Verdict : NOUVEAU (connu) — Moyenne**  
    **Correction suggérée :** Ajouter PyQt6 aux dépendances de test ou exécuter les tests GUI dans un job dédié avec PyQt6 installé.

3. **`run.command` ne vérifie plus la version de `PyQt6`/`send2trash`/`plyfile`/`trimesh`** — `run.command:201-222`  
    Le script installe la dernière version disponible sans tenir compte de `requirements.txt`, ce qui peut créer un écart entre l'environnement de développement et celui de production.  
    **Verdict : NOUVEAU (amplification d'un problème existant) — Basse**

---

## Vérifications pratiques

| Commande | Résultat |
|----------|----------|
| `python main.py --help` | ✅ 8 sous-commandes affichées (pipeline, colmap, brush, sharp, view, upscale, 4dgs, extract360) |
| `python -c "from app.cli import main; from app.scripts.installers.brush import BrushEngineDep; print('OK')"` | ✅ OK |
| `python -m pytest tests/ --ignore=tests/test_workers.py --ignore=tests/test_managers.py -q` | ✅ 171 passed |
| `python -m pytest tests/test_workers.py -q` | ⚠️ 20 skipped (PyQt6 absent) |
| `python -m pytest tests/test_managers.py -q` | ❌ Blocage/échec en exécution collective (`test_restart_with_save_callback` exécute `os.execv`) |

---

## Bilan et recommandations

CorbeauSplat v1.0.0 montre une avancée structurelle majeure : la décomposition de la CLI et du gestionnaire de dépendances améliore la testabilité et la lisibilité, l'isolation de `nerfstudio` élimine un risque important de pollution de l'environnement, et la multiplication des tests renforce la confiance sur les moteurs critiques.

Les points bloquants restent concentrés sur la **chaîne d'approvisionnement** : l'installateur Homebrew via pipe non vérifié, les checksums vides pour Linux et rustup, et l'absence d'intégrité sur les modèles upscayl. Le **plan d'action prioritaire** ci-dessous vise à fermer ces trous et à stabiliser la suite de tests.

### Plan d'action recommandé

1. **Sécuriser `run.command`** : ne plus installer Homebrew via un pipe non vérifié ; épingler une release et vérifier le SHA256, ou rendre l'installation manuelle.
2. **Compléter `app/scripts/checksums.json`** : remplir `linux_brush`, `linux_upscayl`, `linux_glomap`, `darwin_rustup`, `linux_rustup`, ou refuser l'installation si une empreinte attendue est manquante.
3. **Corriger `tests/test_managers.py::test_restart_with_save_callback`** : patcher `os.execv` pour éviter le remplacement de processus pendant la suite de tests.
4. **Restreindre `ColmapEngine.delete_project_content()`** au `project_root` uniquement (supprimer l'autorisation sur `Path.home()`).
5. **Renforcer `AppLifecycle.reset_factory()`** contre les symlinks sortants et journaliser chaque suppression.
6. **Ajouter la validation de containment dans `DropLineEdit._validate_path()`**.
7. **Ajouter des SHA256 pour les modèles upscayl** dans `upscayl_models.py` ou `checksums.json` et vérifier après téléchargement.
8. **Remplacer les `except:` nus** dans `install_node_js()` et `install_build_tools()` par des exceptions typées et du logging.
9. **Ajouter un `requirements.lock`** et pinner les versions dans `requirements.txt` / `pyproject.toml` ; faire installer `run.command` depuis ce lockfile.
10. **Mettre en place une CI GitHub Actions** exécutant `ruff`, `mypy`, `pytest` (avec PyQt6 installé) et `pip-audit` sur chaque PR.
11. **Suivre `AGENTS.md` et `CLAUDE.md`** dans Git ou les ignorer explicitement dans `.gitignore`.
12. **Continuer la découpe des gros fichiers** (`engine.py`, `export_engine.py`, `workers.py`, `config_tab.py`, `brush_tab.py`).
13. **Unifier la source de vérité du `build_mode` Brush** sur `engines/brush.version`.
14. **Vectoriser les exports PLY** (XYZ/OBJ/SPZ/fallback GLB) avec NumPy pour supporter les nuages de millions de points.

---

*Outils utilisés : lecture manuelle du code, `pytest`, `graphify query`, `git status`, `wc -l`.*
