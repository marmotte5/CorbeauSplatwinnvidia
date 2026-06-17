# Rapport d'Audit — CorbeauSplat v1.0.0

*Date : 2026-06-17*  
*Périmètre : code source complet (Python + shell), sans les assets graphiques*  
*Commit audité : `1befd4f1`*

## Résumé

**Score global : 6,5/10**

Le projet a fait des progrès significatifs depuis l'audit précédent (5/10) : la validation des chemins est maintenant robuste, l'extraction d'archives est protégée contre le Zip Slip, une suite de tests initiale existe et un `pyproject.toml` a été ajouté. Cependant, la politique d'intégrité des téléchargements est actuellement une coquille vide (checksums vides), le script de lancement installe Homebrew via un pipe non vérifié, et l'onglet 4DGS pollue toujours l'interpréteur principal avec `nerfstudio`. Le score reste pénalisé par ces problèmes de sécurité et par une couverture de tests encore très partielle.

| Sévérité | Nombre |
|----------|--------|
| Critique [C] | 0 |
| Haute [H] | 4 |
| Moyenne [M] | 13 |
| Basse [B] | 8 |

---

## 1. Sécurité

### [H] `checksums.json` contient des empreintes vides : la vérification des téléchargements est désactivée
**Fichier :** `app/scripts/checksums.json:1-8`  
**Description :** Toutes les clés de hash (`darwin_brush`, `linux_brush`, `darwin_upscayl`, `linux_upscayl`, `darwin_rustup`, `linux_rustup`) ont une valeur vide. `verify_download()` retourne `True` dès que `expected_hash` est vide (`checksum_verifier.py:26-27`). Par conséquent, les vérifications SHA256 de Brush (`setup_dependencies.py:392-395`), de upscayl (`upscayl_manager.py:156-159`) et de rustup (`setup_dependencies.py:782-785`) sont sans effet.  
**Risque :** Compromission de la chaîne d'approvisionnement : un archive ou un installateur modifié sur le réseau exécute du code natif arbitraire.  
**Recommandation :** Remplir `checksums.json` avec les SHA256 attendus pour chaque plateforme et version, ou refuser l'installation si une entrée attendue est manquante (`verify_download_strict`).

### [H] `run.command` télécharge et exécute l'installateur Homebrew via un pipe
**Fichier :** `run.command:84`  
**Description :** `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` est exécuté sans vérification de signature, de tag ou de checksum.  
**Risque :** Exécution de code arbitraire en cas de compromission du compte GitHub, du CDN ou d'une attaque MITM (CWE-829, CWE-494).  
**Recommandation :** Épingler une release taguée, vérifier le SHA256 de `install.sh` avant exécution, ou documenter que Homebrew doit être installé manuellement.

### [H] `FourDGSTab` installe `nerfstudio` dans l'interpréteur Python principal
**Fichier :** `app/gui/tabs/four_dgs_tab.py:142-162`  
**Description :** `cmd = [sys.executable, "-m", "pip", "install", "nerfstudio"]` est exécuté dans l'environnement actif. Cela modifie l'environnement de l'application en cours d'exécution.  
**Risque :** Conflits de dépendances, downgrades forcés de paquets critiques (PyQt6, numpy), et exécution de code si PyPI est compromis.  
**Recommandation :** Isoler `nerfstudio` dans un venv dédié (comme `.venv_360`) et invoquer `ns-process-data` depuis ce venv.

### [H] `install_rust_toolchain()` télécharge et exécute `rustup.rs` sans vérification effective
**Fichier :** `app/scripts/setup_dependencies.py:772-788`  
**Description :** Le script télécharge `https://sh.rustup.rs`, vérifie un checksum vide (cf. checksums.json), puis exécute l'installateur.  
**Risque :** Même risque de chaîne d'approvisionnement que Homebrew.  
**Recommandation :** Vérifier l'empreinte SHA256 réelle du fichier `rustup-init` ou exiger une installation manuelle de Rustup documentée.

### [M] `AppLifecycle.reset_factory()` génère et exécute un script Python temporaire avec suppression de dossiers sensibles
**Fichier :** `app/gui/managers.py:145-179`  
**Description :** La méthode construit dynamiquement un script de nettoyage via `json.dumps([...])` et `subprocess.Popen([sys.executable, tmp_path], ...)` pour supprimer `.venv`, `.venv_sharp`, `.venv_360`, `engines/` et `config.json`. Aucune validation des chemins cibles n'est faite.  
**Risque :** Si `resolve_project_root()` est manipulé (lien symbolique, cwd), des dossiers système ou utilisateur peuvent être effacés.  
**Recommandation :** Valider que chaque chemin est bien un sous-répertoire du projet racine avec `Path.relative_to()`, supprimer directement en Python sans générer de script externe, et journaliser chaque suppression.

### [M] `ColmapEngine.delete_project_content()` ne valide les chemins que contre `/` et `$HOME`
**Fichier :** `app/core/engine.py:764-785`  
**Description :** Seuls `/` et `Path.home()` sont bloqués. N'importe quel autre dossier existant (par ex. `/Users/frederick/Applications`, `/Volumes/...`) peut être mis à la corbeille via `send2trash`.  
**Risque :** Suppression accidentelle ou malveillante de données utilisateur en dehors du projet.  
**Recommandation :** Restreindre la suppression aux sous-dossiers de `output_path` / `project_root` via `validate_path()` ou `relative_to()`.

### [M] `DropLineEdit` ne valide les chemins déposés que par leur existence
**Fichier :** `app/gui/widgets/drop_line_edit.py:29-34`  
**Description :** `_validate_path()` vérifie uniquement que le chemin résolu existe. Il ne vérifie pas qu'il est contenu dans les répertoires autorisés.  
**Risque :** Un utilisateur peut déposer un chemin sensible (ex. `/etc`) qui sera ensuite passé aux moteurs ; couplé à d'autres bugs, cela peut faciliter le traversal.  
**Recommandation :** Appeler `BaseEngine.validate_path()` (ou une fonction utilitaire partagée) pour restreindre les chemins au projet et au home utilisateur.

### [M] `download_model_files()` télécharge les modèles upscayl sans vérification d'intégrité
**Fichier :** `app/upscayl_manager.py:334-365`  
**Description :** Les fichiers `.bin` et `.param` sont téléchargés depuis des URLs arbitraires sans SHA256 ni signature. Seule une taille minimale de 512 octets est vérifiée.  
**Risque :** Exécution d'un modèle NCNN corrompu ou compromis.  
**Recommandation :** Ajouter les SHA256 des modèles dans `upscayl_models.py` (ou `checksums.json`) et vérifier après téléchargement.

### [L] `setup_dependencies.py` masque les échecs d'installation Homebrew par des `except:` nus
**Fichier :** `app/scripts/setup_dependencies.py:675`, `682`  
**Description :** `install_node_js()` et `install_build_tools()` retournent `False` pour toute exception sans journaliser la cause.  
**Risque :** Diagnostics impossibles en cas d'échec silencieux.  
**Recommandation :** Attraper `(subprocess.CalledProcessError, OSError)` et logger `logger.exception(...)`.

### [L] Les binaires téléchargés reçoivent les permissions `0o755`
**Fichier :** `app/scripts/setup_dependencies.py:448`, `app/upscayl_manager.py:171`  
**Description :** Les exécutables sont lisibles/exécutables par tous les utilisateurs de la machine.  
**Risque :** Fuite d'informations ou exécution par d'autres comptes utilisateurs.  
**Recommandation :** Utiliser `0o700` pour les binaires utilisateur, sauf besoin explicite contraire.

### [L] Appels `subprocess.check_call` sans timeout dans les installations longues
**Fichier :** `app/scripts/setup_dependencies.py` (ex. `661-664`, `819`, `829`, `906-907`)  
**Description :** Aucun `timeout` n'est passé aux appels de compilation (`cmake`, `ninja`, `npm install`).  
**Risque :** Blocage indéfini de l'application en cas de processus gelé.  
**Recommandation :** Ajouter un timeout raisonnable (ex. 1800 s pour `ninja`, 300 s pour `npm install`).

---

## 2. Performance

### [M] `_check_and_normalize_resolution()` lit l'intégralité des images pour construire la carte des tailles
**Fichier :** `app/core/engine.py:405-414`  
**Description :** Toutes les images du dossier sont ouvertes via `cv2.imread()` une première fois pour collecter leurs dimensions. Pour des datasets de plusieurs milliers d'images haute résolution, cela crée une charge I/O et mémoire importante avant même le redimensionnement.  
**Risque :** Lenteur et pics de consommation mémoire sur les gros datasets.  
**Recommandation :** Lire les dimensions via `PIL.Image.open(...).size` (sans charger les pixels) ou utiliser `cv2.imread` avec une stratégie de streaming, puis redimensionner image par image.

### [M] Les exports PLY bouclent point par point en Python pur
**Fichier :** `app/core/export_engine.py:128-135`, `198-209`, `371-379`, `434-475`, `627-664`  
**Description :** Les exports XYZ, OBJ, SPZ et le fallback GLB/assimp utilisent des boucles `for i in range(len(vertex))` avec accès scalaire aux champs.  
**Risque :** Ralentissement sévère sur des nuages de millions de points et gel potentiel de l'interface.  
**Recommandation :** Vectoriser avec NumPy/arrays structurées ; construire les buffers en mémoire avant écriture unique.

### [M] Logique Sharp vidéo dupliquée entre CLI et worker
**Fichier :** `main.py:425-481` et `app/gui/workers.py:465-567`  
**Description :** `_run_sharp_video()` et `SharpVideoWorker.run()` implémentent toutes deux l'extraction FFmpeg + la prédiction frame par frame avec une logique quasi identique.  
**Risque :** Dette technique ; les corrections d'annulation, de nettoyage ou de gestion d'erreurs doivent être appliquées à deux endroits.  
**Recommandation :** Faire de `SharpVideoWorker` l'unique implémentation et l'invoquer depuis `main.py`.

### [L] Thread consommateur de stdout SuperSplat jamais rejoint
**Fichier :** `app/core/superplat_engine.py:69-75`  
**Description :** Un daemon thread est lancé pour consommer la sortie du serveur, mais il n'est jamais arrêté ni joint.  
**Risque :** Fuite de thread si le serveur est démarré/arrêté plusieurs fois.  
**Recommandation :** Ajouter un mécanisme d'événement pour arrêter proprement la boucle de consommation.

### [L] `LogsTab.append_log()` est appelé depuis les workers sans limitation de débit
**Fichier :** `app/gui/tabs/logs_tab.py:36-41`  
**Description :** Chaque ligne de log déclenche `QTextEdit.append()` et repositionne le curseur depuis un thread secondaire via signaux.  
**Risque :** Lenteur de l'interface lors des traitements très verbeux.  
**Recommandation :** Limiter le nombre de lignes affichées ou bufferiser les mises à jour (ex. toutes les 100 ms).

---

## 3. Architecture

### [H] Plusieurs modules dépassent les seuils de maintenabilité
**Fichiers :**  
- `main.py` — 781 lignes
- `app/core/engine.py` — 785 lignes
- `app/scripts/setup_dependencies.py` — 993 lignes
- `app/core/export_engine.py` — 722 lignes
- `app/gui/workers.py` — 604 lignes
- `app/gui/tabs/config_tab.py` — 638 lignes
- `app/gui/tabs/brush_tab.py` — 572 lignes  
**Description :** Ces fichiers restent au-delà de 500 lignes, ce qui complique la revue, les tests et la navigation.  
**Risque :** Charge cognitive élevée, taux de bugs accru, refactors coûteux.  
**Recommandation :** Extraire les sous-classes d'installateurs (`setup_dependencies.py` → `app/scripts/installers/`), les helpers de parsing/export (`export_engine.py`), et les groupes de widgets réutilisables.

### [M] `BrushTab.run_standalone()` contourne `BrushEngine.build_command()` et ignore `build_mode`
**Fichier :** `app/gui/tabs/brush_tab.py:542-571`  
**Description :** La commande standalone est construite manuellement et utilise toujours `--total-steps`, même si le binaire installé est un build source qui attend `--total-train-iters`. Elle ignore aussi `sh_degree`, `refine_every`, etc.  
**Risque :** Échec de lancement ou comportement inattendu selon le build installé.  
**Recommandation :** Réutiliser `BrushEngine.build_command()` pour construire la commande standalone.

### [M] Double source de vérité sur le `build_mode` de Brush
**Fichiers :** `app/gui/tabs/brush_tab.py:47-49`, `app/core/brush_engine.py:56`, `app/core/system.py:143-154`  
**Description :** Le mode de build est déduit du widget `combo_build_mode`, de `config.json`, et du fichier `engines/brush.version`. Ces trois sources peuvent diverger.  
**Risque :** Construction d'une commande Brush incompatible avec le binaire installé.  
**Recommandation :** Faire de `get_brush_build_mode()` (basé sur `engines/brush.version`) la seule source de vérité, et synchroniser le GUI en conséquence.

### [M] Pas de couche centralisée de validation des paramètres numériques/énumérés avant `subprocess`
**Description :** Les paramètres (chemins, entiers, flottants, modèles de caméra) sont passés directement aux commandes externes. Bien que `argparse` valide certains champs en CLI, la voie GUI et les workers n'ont pas de schéma de validation commun.  
**Risque :** Injection indirecte ou passage de valeurs invalides aux moteurs.  
**Recommandation :** Introduire un schéma de validation (Pydantic, dataclasses avec `__post_init__`, ou validators explicites) partagé entre GUI et CLI.

### [M] `AGENTS.md`, `.claude/` et `CLAUDE.md` ne sont pas suivis par Git
**Description :** `git status` montre ces fichiers comme non-tracked (`??`). Ils contiennent des instructions spécifiques aux agents.  
**Risque :** Perte de la convention projet, comportement incohérent des agents sur un clone frais.  
**Recommandation :** Les ajouter au dépôt (si ce sont des conventions actives) ou les ignorer explicitement dans `.gitignore`.

### [L] `manifest.md` référence une version obsolète de `app/__init__.py`
**Fichier :** `manifest.md:33`  
**Description :** Le manifeste indique `VERSION = "0.99.1"` alors que `app/__init__.py` contient `VERSION = "0.99.5"`.  
**Risque :** Confusion sur la version réelle et documentation désynchronisée.  
**Recommandation :** Lire la version dynamiquement depuis `app.VERSION` ou maintenir les deux en synchronisation automatique.

---

## 4. Qualité du code

### [M] Gestion d'exceptions trop large dans `setup_dependencies.py`
**Fichier :** `app/scripts/setup_dependencies.py:675`, `682`  
**Description :** `except: return False` masque les erreurs d'installation de Node.js, CMake et Ninja.  
**Recommandation :** Remplacer par `except (subprocess.CalledProcessError, OSError) as e:` et logger l'erreur.

### [M] `export_engine.py` attrape `Exception` de manière générique dans presque toutes les méthodes
**Fichiers :** `app/core/export_engine.py:94`, `110`, `161`, `262`, `321`, `352`, `395`, `506`, `693`, `716`  
**Description :** Toutes les erreurs d'export sont capturées et simplement loguées. Cela masque les `MemoryError`, `PermissionError`, etc.  
**Recommandation :** Distinguer les erreurs attendues (`ImportError`, `FileNotFoundError`) des erreurs système graves, et propager ou logger différemment.

### [L] `BaseEngine._execute_command()` affiche la commande complète via `' '.join(map(str, cmd))`
**Fichier :** `app/core/base_engine.py:117`  
**Description :** Si un jour des arguments sensibles (tokens, chemins) sont passés, ils apparaissent en clair dans les logs.  
**Recommandation :** Sanitiser les arguments sensibles avant log ou proposer un mode `--verbose-secret` désactivé par défaut.

### [L] `requirements.txt` utilise des plages de versions larges
**Fichier :** `requirements.txt:1-8`  
**Description :** `PyQt6>=6.6,<7`, `numpy>=1.26,<3`, etc. autorisent des mineures non testées.  
**Recommandation :** Épingler les versions mineures testées (ex. `PyQt6==6.8.*`) et commiter un `requirements.lock` généré.

### [L] `run.command` réinstalle des paquets optionnels sans version fixe
**Fichier :** `run.command:203-222`  
**Description :** `PyQt6`, `send2trash`, `plyfile`, `trimesh` sont installés au runtime si absents, sans version ni lockfile.  
**Recommandation :** Centraliser toutes les dépendances dans `requirements.txt`/`pyproject.toml` et installer uniquement depuis le lockfile.

---

## 5. Tests & maintenabilité

### [M] Couverture de tests très partielle malgré l'ajout d'une suite initiale
**Fichiers :** `tests/test_base_engine.py`, `tests/test_brush_engine.py`, `tests/test_export_engine.py`  
**Description :** 39 tests couvrent principalement `BaseEngine.validate_path()`, `BrushEngine.build_command()` et `ExportEngine` pour XYZ/PLY. Aucun test ne couvre les workers, `setup_dependencies.py`, `upscayl_manager.py`, la CLI de `main.py`, ni les scénarios de Zip Slip / path traversal dans les extracteurs.  
**Risque :** Régressions non détectées sur les chemins critiques (téléchargement, extraction, exécution des moteurs).  
**Recommandation :** Ajouter `tests/test_upscayl_manager.py` (extraction sécurisée), `tests/test_workers.py` (mock de `IProcessRunner`), `tests/test_colmap_engine.py` et des tests d'intégration CLI avec `pytest` + `CliRunner`.

### [M] `pyproject.toml` configuré mais les outils ne sont pas exécutés dans l'environnement actuel
**Fichier :** `pyproject.toml:1-21`  
**Description :** `ruff` et `mypy` sont configurés, mais ni l'un ni l'autre n'est installé dans l'environnement Python utilisé pour l'audit.  
**Risque :** La qualité statique n'est pas garantie en l'absence de CI.  
**Recommandation :** Ajouter `ruff` et `mypy` aux dépendances de développement, et un workflow GitHub Actions qui exécute lint + type check + tests à chaque PR.

### [L] `checksums.json` est un placeholder non documenté
**Fichier :** `app/scripts/checksums.json:1-8`  
**Description :** Le fichier est livré vide sans commentaire indiquant comment le remplir.  
**Recommandation :** Documenter la procédure de mise à jour des checksums dans `manifest.md` ou `README.md`, et éventuellement fournir un script de génération.

---

## Bilan

CorbeauSplat v0.99.5 montre une nette amélioration par rapport au précédent audit : la vulnérabilité de path traversal de `validate_path()` est corrigée, l'extraction d'archives est maintenant sécurisée, le fichier `config.json` n'est plus tracké, la classe `BaseWorker` a été nettoyée, et une infrastructure de tests / lint (`pyproject.toml`) a été mise en place.

Les points bloquants actuels sont principalement liés à l'intégrité des téléchargements et à l'isolation des environnements : les checksums sont vides, le script d'installation de Homebrew n'est pas vérifié, et `nerfstudio` est installé dans l'environnement principal. Ces trois points doivent être traités en priorité avant de considérer l'application comme suffisamment sûre pour une distribution.

### Plan d'action recommandé

1. **Remplir `app/scripts/checksums.json`** avec les SHA256 des binaires Brush, upscayl, rustup par plateforme, et refuser toute installation si une empreinte attendue est manquante.
2. **Sécuriser `run.command`** : ne plus installer Homebrew via un pipe non vérifié ; épingler une release et vérifier le checksum, ou rendre l'installation manuelle.
3. **Isoler `nerfstudio`** dans un venv dédié (`.venv_4dgs` ou réutiliser `.venv_360`) et invoquer `ns-process-data` depuis ce venv.
4. **Corriger `BrushTab.run_standalone()`** pour utiliser `BrushEngine.build_command()` et respecter `build_mode`.
5. **Renforcer `AppLifecycle.reset_factory()` et `ColmapEngine.delete_project_content()`** avec des validations de containment strictes.
6. **Ajouter un `requirements.lock`** et pinner les versions dans `requirements.txt` / `pyproject.toml`.
7. **Étendre la suite de tests** : workers, `upscayl_manager`, CLI, scénarios de sécurité (Zip Slip, path traversal), et tests d'intégration.
8. **Mettre en place une CI GitHub Actions** exécutant `ruff`, `mypy`, `pytest` et `pip-audit` sur chaque PR.
9. **Suivre `AGENTS.md` / `.claude/` / `CLAUDE.md`** dans Git ou les ignorer explicitement.
10. **Synchroniser `manifest.md`** avec la version réelle et documenter la politique de checksums.

---

*Outils utilisés : lecture manuelle du code, `pytest` (39 passed), `graphify query`, `git status`.*
