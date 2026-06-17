# CorbeauSplat — New GUI Design Document (newgui.md)

> Version 1.0 — Redesign complet de l'interface pour transformer CorbeauSplat en studio de production 3D.
> Date : 2026-05-18
> Auteur : OpenCode

---

## Table des matières

1. [Diagnostic de l'interface actuelle](#1-diagnostic-de-linterface-actuelle)
2. [Direction design : Pipeline Studio](#2-direction-design--pipeline-studio)
3. [Axes de redesign détaillés](#3-axes-de-redesign-détaillés)
4. [Architecture Qt proposée](#4-architecture-qt-proposée)
5. [Phases d'implémentation](#5-phases-dimplémentation)
6. [Design System (couleurs, typographie, composants)](#6-design-system)
7. [Checklist de migration](#7-checklist-de-migration)

---

## 1. Diagnostic de l'interface actuelle

| Problème | Impact UX | Fichier(s) concerné(s) |
|----------|-----------|------------------------|
| **10 onglets horizontaux** | Surcharge cognitive. L'utilisateur ne sait pas dans quel ordre cliquer. | `gui/tabs/*.py`, `gui/main_window.py` |
| **Chaque engine isolé** | Pas de visibilité globale du pipeline. On ne voit pas où on en est. | `gui/tabs/*.py` |
| **GUI = formulaires empilés** | Lourdeur visuelle. Dépendances entre étapes non visibles. | `gui/tabs/config_tab.py`, `gui/tabs/brush_tab.py`, etc. |
| **Viewer externe** | Rupture de contexte. L'utilisateur quitte l'app pour vérifier le résultat. | `gui/tabs/superplat_tab.py` |
| **Thème sombre basique** | Aspect « outil interne d'entreprise » des années 2010. | `gui/styles.py` |

---

## 2. Direction design : Pipeline Studio

> **Concept central** : *La pipeline n'est plus un concept abstrait, c'est l'interface elle-même.*

Le workflow devient une **timeline visuelle** dans l'en-tête de la fenêtre. Chaque étape est une carte cliquable. Le workspace central s'adapte à l'étape sélectionnée. L'utilisateur navigue dans son projet, pas dans des onglets techniques.

### Parcours utilisateur transformé

| Aujourd'hui | Après redesign |
|-------------|----------------|
| Lancer app → GUI vide avec onglets | Lancer app → **Project Hub** avec projets récents et drag-and-drop |
| Cliquer sur "Config", remplir formulaire | Glisser vidéo → étape "Import" s'active automatiquement |
| Aller dans "Brush", lancer, attendre aveuglément | Sélectionner "Train" → **viewport 3D intégré** montrant la convergence en temps réel |
| Ouvrir terminal pour voir les logs | **Activity Center** en bas avec overlay logs slide-up |
| Exporter, ouvrir finder, chercher le PLY | Pipeline timeline verte jusqu'à "Export", preview comparateur formats |

---

## 3. Axes de redesign détaillés

### 3.1 Pipeline Timeline (en-tête principal)

**Remplace** : la barre d'onglets actuelle (`QTabWidget`).

**Description** :
Une barre horizontale en haut de la fenêtre représentant les étapes du workflow :

```
[ Import ] → [ Extract 360° ] → [ Upscale ] → [ COLMAP ] → [ Train ] → [ Export ]
   🟢         ⚪ (skip)           🟢           🟡 running      ⚪ pending      ⚪
```

- Chaque étape = carte cliquable (`PipelineStepWidget`).
- **Couleurs d'état** : 🟢 OK | 🟡 En cours | 🔴 Erreur | ⚪ Désactivé / À venir | 🔵 Actuellement sélectionnée.
- **Connexions** : flèches animées entre les étapes (style Figma / DaVinci Resolve).
- **Glisser-déposer** : déposer un fichier sur la timeline l'assigne à l'étape "Import" et initialise le projet.
- **Survol** : tooltip récapitulatif (nombre d'images, durée, paramètres clés).
- **Clic droit** : menu contextuel ("Réinitialiser cette étape", "Sauter cette étape", "Voir les logs de cette étape").

**Comportement dynamique** :
- Si l'utilisateur clique sur "Export" alors que "Train" n'est pas terminé, un overlay indique "L'entraînement doit être complété avant l'export" avec bouton "Aller à l'étape Train".
- Les étapes désactivées (ex: pas de vidéo 360°) sont grisées et marquées "skip".

**Fichier(s) à créer/modifier** :
- `gui/widgets/pipeline_timeline.py` (NOUVEAU)
- `gui/main_window.py` (MODIFIER : remplacer `QTabWidget` par intégration de la timeline)

---

### 3.2 Workspace Adaptatif (centre)

**Remplace** : le contenu statique des onglets.

**Description** :
Zone centrale unique dont le contenu change selon l'étape sélectionnée dans la timeline. Utilise un `QStackedWidget` pour basculer entre les différents workspaces.

| Étape timeline | Workspace affiché | Contenu détaillé |
|----------------|-------------------|------------------|
| **Import** | `ImportWorkspace` | Grille d'images sources, drag-and-drop zone, prévisualisation vidéo, métadonnées EXIF |
| **Extract 360°** | `Extract360Workspace` | Sélecteur de mode (équirectangulaire / cubemap), aperçu des faces extraites |
| **Upscale** | `UpscaleWorkspace` | Grille avant/après avec slider de comparaison, sélection modèle, file d'attente |
| **COLMAP** | `ColmapWorkspace` | Visualiseur de couverture (caméras dans l'espace), carte des features détectées, logs structurés |
| **Train** | `TrainWorkspace` | **Viewport 3D intégré** + graphes de convergence (loss, PSNR, SSIM) + contrôles live |
| **Export** | `ExportWorkspace` | Comparateur de formats (PLY / SPZ / GLB / OBJ / XYZ) avec poids estimé, preview 3D, bouton partage |

**Comportement dynamique** :
- Quand une étape est sélectionnée, le workspace glisse en douceur (fade 150ms, translation 30px → 0).
- Le `QSplitter` entre workspace et Inspector permet de redimensionner la colonne de droite.

**Fichier(s) à créer/modifier** :
- `gui/workspaces/__init__.py` (NOUVEAU)
- `gui/workspaces/base_workspace.py` (NOUVEAU : classe abstraite)
- `gui/workspaces/import_workspace.py`, `upscale_workspace.py`, `train_workspace.py`, `export_workspace.py` (NOUVEAUX)
- `gui/main_window.py` (MODIFIER : intégrer `QStackedWidget` central)

---

### 3.3 Inspector Panel (colonne de droite)

**Remplace** : les formulaires dispersés dans chaque onglet.

**Description** :
Panneau de propriétés contextuel fixe à droite, style macOS Inspector / Blender Sidebar. Affiche les paramètres de l'étape actuellement sélectionnée.

```
┌─────────────────────┐
│  🔧 Paramètres      │
│  ─────────────────  │
│  Preset:  [Dense ▼] │
│                     │
│  ┌─ Densification ─┐│
│  │ Opacité:  [━━━] ││
│  │ Densify:  [✓]   ││
│  └─────────────────┘│
│                     │
│  ┌─ Avancé ───────┐│
│  │ LR: 0.01        ││
│  │ ...             ││
│  └─────────────────┘│
│                     │
│  [▶ Démarrer]       │
│  [⏸ Pause] [⏹ Stop] │
└─────────────────────┘
```

**Comportement dynamique** :
- **Groupement par accordéons** (`CollapsibleSection` custom) pour réduire le bruit visuel. Seuls les groupes pertinents sont ouverts par défaut.
- **Tooltips enrichis** : au survol d'un label, une infobulle apparaît avec explication + mini-graphique (ex: « Densification : ajoute des gaussiennes là où le gradient est fort »).
- **Présets animés** : quand on change de preset, les curseurs (`QSlider` / `QDoubleSpinBox`) glissent en douceur (`QPropertyAnimation`) vers leur nouvelle valeur sur 300ms.
- **Validation live** : les champs invalides (ex: LR négatif) deviennent rouges avec message explicatif sous le champ.

**Fichier(s) à créer/modifier** :
- `gui/widgets/inspector_panel.py` (NOUVEAU)
- `gui/widgets/collapsible_section.py` (NOUVEAU)
- `gui/widgets/param_editor.py` (NOUVEAU : widget générique paramètre + label + tooltip)

---

### 3.4 Project Hub (écran d'accueil)

**Remplace** : le lancement direct sur la GUI vide / onglets.

**Description** :
Écran d'accueil affiché quand CorbeauSplat est lancé sans argument CLI ou projet ouvert.

```
┌─────────────────────────────────────────┐
│  CorbeauSplat        [ + New Project ] │
├─────────────────────────────────────────┤
│                                         │
│  📁 Château drone          2h ago   🟢 │
│  📁 Studio intérieur       5h ago   🟡 │
│  📁 Voiture classique     1d ago   🟢 │
│                                         │
│  [ Drag & drop video/images here ]      │
│                                         │
│  Templates :                            │
│  [ 🏛️ Photogrammétrie objet ]          │
│  [ 🌍 Vidéo 360° ]                     │
│  [ 🏠 Scan intérieur ]                  │
│  [ 🎬 Capture cinéma ]                  │
│                                         │
└─────────────────────────────────────────┘
```

**Comportement dynamique** :
- **Projets récents** : affichés sous forme de cartes avec thumbnail (première frame ou aperçu 3D si `.ply` existe). Taille ~200x120px, hover scale 1.02 + ombre.
- **Barre de recherche** : `Ctrl+K` ou `Cmd+K` filtre instantanément les projets par nom.
- **Templates** : clic sur un template pré-remplit certains paramètres (ex: « Scan intérieur » active Undistortion et set le preset « Dense Indoor »).
- **Drag-and-drop** : déposer des fichiers sur la zone crée un nouveau projet auto-configuré.

**Fichier(s) à créer/modifier** :
- `gui/hub/project_hub.py` (NOUVEAU)
- `gui/hub/project_card.py` (NOUVEAU)
- `gui/hub/template_selector.py` (NOUVEAU)

---

### 3.5 Visual Preview / Viewport 3D Intégré

**Remplace** : le recours au viewer externe (`SuperSplatEngine` via `npx serve` séparé).

**Description** :
Viewport 3D embarqué dans le workspace des étapes "Train" et "Export".

- **Technique** : `QWebEngineView` chargant le viewer SuperSplat en local (pas besoin de `npx serve` externe), avec pont JS-Python (`QWebChannel`) pour contrôler la caméra depuis Python.
- **Alternatif léger** : Si intégration web trop lourde, utiliser un widget OpenGL/WGPU minimal pour visualiser le nuage de points / splats en temps réel (par ex. via `pyglet` + `moderngl`, ou intégration du renderer Rust de Brush via FFI).
- **Split-screen** : dans l'étape "Upscale", mode comparaison avant/après avec slider vertical/horizontal.
- **Train live** : pendant l'entraînement Brush, affichage périodique (toutes les 500 itérations) de l'état des gaussiennes. Barre de progression animée.

**Comportement dynamique** :
- **Contrôles de caméra** : Orbit (click-drag), Pan (shift-drag), Zoom (scroll) — standard industrie.
- **HUD** : overlay en coin haut-gauche affichant nombre de gaussiennes, FPS, taille mémoire.

**Fichier(s) à créer/modifier** :
- `gui/widgets/viewport_3d.py` (NOUVEAU)
- `gui/widgets/split_comparison.py` (NOUVEAU : widget avant/après)
- `engines/supersplat/` (MODIFIER : wrapper serveur intégré)

---

### 3.6 Activity Center (barre de statut intelligente)

**Remplace** : la barre de statut standard `QStatusBar` et l'onglet "Logs" séparé.

**Description** :
Barre de statut en bas de fenêtre, inspirée de **Docker Desktop / macOS Menu Bar**.

```
┌─────────────────────────────────────────────────────────────────┐
│ 🟢 COLMAP done (4m 12s)   🟡 Brush training... iter 8400/30000 │
│ [▓▓▓▓░░░░░░░░] 28%                        [ Jobs (2) ] [ Logs ] │
└─────────────────────────────────────────────────────────────────┘
```

**Composants** :
- **File d'attente de jobs** : bouton "Jobs (N)" ouvrant un panneau popover listant les tâches en cours, en pause, échouées. Possibilité d'annuler/reprioriser.
- **Notifications éphémères** : toast slide-in depuis la droite (« Export SPZ terminé — 12 Mo ») avec action "Reveal in Finder".
- **Monitoring GPU** : température / utilisation mémoire unifiée Apple Silicon (via `powermetrics` ou `ioreg`). Affichage compact : icon GPU + "8.2/16 GB".
- **Logs** : bouton "Logs" ouvrant un overlay slide-up depuis le bas (pas de changement de vue). Le contenu est le `QPlainTextEdit` existant mais dans un `QDockWidget` flottant/slide-up.

**Fichier(s) à créer/modifier** :
- `gui/widgets/activity_center.py` (NOUVEAU)
- `gui/widgets/job_popover.py` (NOUVEAU)
- `gui/widgets/notification_toast.py` (NOUVEAU)
- `gui/tabs/logs_tab.py` (MODIFIER : extraire le contenu pour le rendre réutilisable dans l'overlay)

---

### 3.7 Modernisation Visuelle (Design System)

**Remplace** : `gui/styles.py` actuel (thème sombre basique).

**Description** :
Un vrai **design system** Qt avec variables de design cohérentes.

| Élément | Spécification | Technique Qt |
|---------|---------------|--------------|
| **Typographie** | Police système `SF Pro` (macOS) ou `Inter` (fallback), tailles : 11px caption, 13px body, 15px heading, 20px title | `QFontDatabase.addApplicationFont()` + `setStyleSheet` |
| **Boutons principaux** | Fond accent couleur système (`NSColor.controlAccentColor` sur macOS), texte blanc, coins arrondis 6px, padding 8px 16px | Stylesheet `border-radius: 6px; padding: 8px 16px;` |
| **Boutons secondaires** | Fond transparent, bordure 1px gris, texte gris clair, même radius | Stylesheet |
| **Inputs (QLineEdit, QSpinBox)** | Fond `surface` légèrement plus clair que le fond, bordure 1px `divider`, radius 4px. Focus : bordure accent color | Stylesheet `:focus` pseudo-état |
| **Floating labels** | Le placeholder devient petit label au-dessus du champ quand il y a du contenu ou au focus | Sous-classe `QLineEdit` avec `QPropertyAnimation` sur `font-size` et `y` position |
| **Accordéons** | Header avec chevron `▸`/`▾`, fond légèrement différent du workspace, transition d'ouverture 200ms | `QToolButton` + `QWidget` + `QPropertyAnimation` sur `maximumHeight` |
| **Ombres** | Ombres douces sur panneaux flottants : `rgba(0,0,0,0.2) 0px 4px 12px` | `QGraphicsDropShadowEffect` |
| **Transitions** | Changement de workspace : fade 150ms + translation 30px→0 | `QStackedWidget` + `QPropertyAnimation` sur `opacity` et `geometry` |
| **Scrollbars** | Fines 6px, overlay style macOS, auto-hide, couleur `scrollbar` | Stylesheet `QScrollBar:vertical { width: 6px; background: transparent; }` |
| **Sidebar** | Icônes SF Symbols ou Phosphor (`phosphor-py` ou SVG embarqués), labels masquables, largeur 56px (icons only) ou 200px (icons + texte) | `QToolButton` avec `setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)` |

**Palette de couleurs** (dark mode par défaut, light mode optionnel) :

```python
# Fichier : gui/styles/design_tokens.py (NOUVEAU)
DARK_TOKENS = {
    "background": "#0F0F11",        # Fond fenêtre principal
    "surface": "#1C1C1E",           # Fond panneaux (inspector, cards)
    "elevated": "#252528",          # Éléments au-dessus (inputs, buttons hover)
    "divider": "#38383A",           # Lignes de séparation
    "text_primary": "#FFFFFF",
    "text_secondary": "#98989D",
    "text_tertiary": "#636366",
    "accent": "#0A84FF",            # Couleur système macOS (ou fallback bleu)
    "accent_hover": "#409CFF",
    "accent_pressed": "#0066CC",
    "success": "#30D158",
    "warning": "#FFD60A",
    "error": "#FF453A",
    "scrollbar": "#48484A",
}
```

**Fichier(s) à créer/modifier** :
- `gui/styles/design_tokens.py` (NOUVEAU)
- `gui/styles/dark_theme.py` (NOUVEAU : `QApplication.setPalette(...)` + feuille de style globale)
- `gui/styles/light_theme.py` (NOUVEAU : optionnel pour plus tard)
- `gui/styles/animations.py` (NOUVEAU : helpers `fade_widget()`, `slide_widget()`)

---

### 3.8 Command Palette (`Ctrl+Shift+P` / `Cmd+K`)

**Remplace** : rien (nouvelle fonctionnalité).

**Description** :
Palette de commandes inspirée de VS Code / Figma, accessible via `Ctrl+Shift+P` ou `Cmd+K`.

```
┌─────────────────────────────────┐
│  > _________________________   │
│  ─────────────────────────────  │
│  🚀  Start training             │
│  ⏸  Pause current job           │
│  💾  Save project               │
│  📤  Export last result to SPZ  │
│  📂  Reveal project in Finder   │
│  ⚙️  Open preferences          │
│  ❓  Show documentation         │
└─────────────────────────────────┘
```

**Comportement dynamique** :
- Fuzzy matching sur les commandes (ex: « str tr » matche « Start training »).
- Raccourcis affichés à droite de chaque commande.
- Historique des 5 dernières commandes en haut de liste.
- Suggestions contextuelles : si un entraînement est en cours, « Pause current job » apparaît en premier.

**Fichier(s) à créer/modifier** :
- `gui/widgets/command_palette.py` (NOUVEAU : `QDialog` modale centrée, `QListView`, modèle `QStringListModel` + custom delegate)

---

## 4. Architecture Qt proposée

### 4.1 Vue d'ensemble des widgets

```
MainWindow (QMainWindow)
├── MenuBar (QMenuBar)
├── CentralWidget (QWidget)
│   ├── PipelineTimeline (QWidget)        ← Haut, fixe
│   ├── MainSplitter (QSplitter, horizontal)
│   │   ├── Sidebar (QWidget, 56-200px)
│   │   │   └── ToolButtons (Project, Import, Train, Export, Settings)
│   │   ├── ContentArea (QWidget)
│   │   │   ├── StackedWorkspace (QStackedWidget)
│   │   │   │   ├── ProjectHubPage
│   │   │   │   ├── ImportWorkspace
│   │   │   │   ├── UpscaleWorkspace
│   │   │   │   ├── ColmapWorkspace
│   │   │   │   ├── TrainWorkspace
│   │   │   │   └── ExportWorkspace
│   │   │   └── OverlayContainer (QWidget, pour toasts)
│   │   └── InspectorPanel (QWidget, 280px, fixe max)
│   │       └── StackedInspector (QStackedWidget)
│   │           ├── ImportInspector
│   │           ├── UpscaleInspector
│   │           ├── BrushInspector
│   │           └── ExportInspector
│   └── ActivityCenter (QWidget)           ← Bas, fixe
└── CommandPalette (QDialog, hidden)       ← Overlay modale
```

### 4.2 Classes principales à implémenter

```python
# gui/main_window.py
class MainWindow(QMainWindow):
    def __init__(self):
        self.pipeline_timeline = PipelineTimeline(steps=PIPELINE_STEPS)
        self.sidebar = Sidebar()
        self.stacked_workspace = StackedWorkspace()
        self.inspector_panel = InspectorPanel()
        self.activity_center = ActivityCenter()
        
        # Layout
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        layout.addWidget(self.pipeline_timeline)
        
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.sidebar)
        main_splitter.addWidget(self.stacked_workspace)
        main_splitter.addWidget(self.inspector_panel)
        main_splitter.setSizes([60, 800, 280])
        
        layout.addWidget(main_splitter, stretch=1)
        layout.addWidget(self.activity_center)
        
        self.setCentralWidget(central)
        self.command_palette = CommandPalette(self)
```

### 4.3 Signaux / Slots (communication)

| Signal | Émetteur | Slot | Récepteur | Description |
|--------|----------|------|-----------|-------------|
| `step_selected(step_id)` | `PipelineTimeline` | `show_workspace(step_id)` | `MainWindow` | Change le workspace affiché |
| `project_opened(project_path)` | `ProjectHub` | `load_project()` | `SessionManager` | Charge config + met à jour timeline |
| `job_state_changed(job_id, state)` | `BaseEngine` | `update_job_indicator()` | `ActivityCenter` | Met à jour la barre de statut |
| `log_line(level, message)` | `BaseEngine` | `append_log()` | `LogOverlay` | Affiche logs dans overlay |
| `param_changed(key, value)` | `InspectorPanel` | `update_config()` | `SessionManager` | Persiste les paramètres |
| `training_progress(iter, total, loss)` | `BrushWorker` | `update_progress()` | `TrainWorkspace` + `ActivityCenter` | Met à jour viewport + barre |

---

## 5. Phases d'implémentation

### Phase 1 : Fondations (semaine 1-2)
**Objectif** : Poser la structure de fenêtre sans changer la logique métier.

- [ ] **1.1 Créer `gui/styles/design_tokens.py`** avec les constantes de couleur et typographie.
- [ ] **1.2 Réécrire `gui/styles/dark_theme.py`** : une fonction `apply_dark_theme(app: QApplication)` qui applique palette + stylesheet global.
- [ ] **1.3 Créer `gui/widgets/collapsible_section.py`** : widget réutilisable d'accordéon animé.
- [ ] **1.4 Créer `gui/widgets/param_editor.py`** : widget label + input + tooltip unifié.
- [ ] **1.5 Restructurer `gui/main_window.py`** :
  - Remplacer le `QTabWidget` central par un `QSplitter` horizontal (Sidebar | Workspace | Inspector).
  - Le `QTabWidget` existant peut temporairement devenir le contenu du Workspace (mode compatibilité).
  - Ajouter la barre d'activité en bas.
- [ ] **1.6 Tester** : l'application doit fonctionner exactement comme avant mais avec la nouvelle structure de fenêtre.

**Artéfact livré** : Application fonctionnelle avec nouvelle structure visuelle, contenu ancien encore en place.

---

### Phase 2 : Pipeline Timeline (semaine 3)
**Objectif** : Remplacer la navigation par onglets par la timeline.

- [ ] **2.1 Créer `gui/widgets/pipeline_timeline.py`** :
  - Classe `PipelineStepWidget(QFrame)` : icône + label + indicateur d'état.
  - Classe `PipelineTimeline(QWidget)` : layout horizontal de steps + flèches connectrices.
  - Signaux : `step_selected(str)`, `step_context_menu_requested(str, QPoint)`.
- [ ] **2.2 Implémenter la logique d'état** :
  - Charger depuis `SessionManager` l'état de chaque étape (idle, running, completed, error, skipped).
  - Mettre à jour dynamiquement les couleurs quand un job démarre/termine.
- [ ] **2.3 Connecter au workspace** :
  - Clic sur un step → `stacked_workspace.setCurrentIndex(step_index)`.
  - Les onglets existants deviennent les pages du `stacked_workspace`.
- [ ] **2.4 Menu contextuel** : "Skip step", "Reset step", "View logs".

**Artéfact livré** : Navigation complète par timeline. Les anciens onglets ne sont plus visibles (mais le code des tabs est encore là).

---

### Phase 3 : Inspector Panel & Project Hub (semaine 4-5)
**Objectif** : Centraliser les paramètres et améliorer l'expérience d'accueil.

- [ ] **3.1 Créer `gui/widgets/inspector_panel.py`** :
  - `InspectorPanel` hérite de `QScrollArea`.
  - Stacked widget interne pour les paramètres de chaque étape.
  - Extraire les formulaires de `config_tab.py`, `brush_tab.py`, `upscale_tab.py`, `params_tab.py` pour les transformer en sections d'inspector.
- [ ] **3.2 Créer `gui/hub/project_hub.py`** :
  - Écran d'accueil avec grille de projets récents.
  - Lire `config.json` pour la liste des derniers projets.
  - Générer des thumbnails (via Pillow, première frame ou preview 3D si `.ply` existe).
- [ ] **3.3 Créer `gui/hub/template_selector.py`** :
  - Cartes cliquables pour chaque template (Photogrammétrie, 360°, Intérieur, Cinéma).
  - Chaque template = dictionnaire de paramètres par défaut injectés dans `SessionManager`.

**Artéfact livré** : Écran d'accueil fonctionnel + inspector contextuel à droite.

---

### Phase 4 : Workspaces spécialisés (semaine 6-8)
**Objectif** : Transformer chaque étape en workspace riche et dédié.

- [ ] **4.1 `gui/workspaces/import_workspace.py`** :
  - Grille d'images (`QListView` en mode icône).
  - Détection de flou (laplacian variance) pour pré-qualifier les images.
  - Visualiseur de couverture caméra (2D top-down map).
- [ ] **4.2 `gui/workspaces/upscale_workspace.py`** :
  - Grille avant/après avec `SplitComparison` widget.
  - File d'attente d'upscale (batch local).
- [ ] **4.3 `gui/workspaces/train_workspace.py`** :
  - Intégration du viewport 3D (voir Phase 5).
  - Graphes de convergence (loss, PSNR) avec `PyQtGraph` ou `QChart`.
  - Contrôles live (pause/resume, changement LR à la volée si Brush le supporte).
- [ ] **4.4 `gui/workspaces/export_workspace.py`** :
  - Comparateur de formats avec estimations de taille.
  - Preview du modèle dans le viewport.

**Artéfact livré** : Workspaces riches avec UI dédiée par étape.

---

### Phase 5 : Viewport 3D Intégré (semaine 9-10)
**Objectif** : Ne plus jamais quitter l'application pour prévisualiser.

- [ ] **5.1 Créer `gui/widgets/viewport_3d.py`** :
  - Option A (recommandée) : `QWebEngineView` embarquant le viewer SuperSplat (fichiers HTML/JS/CSS locaux dans `engines/supersplat/`).
  - Pont `QWebChannel` pour envoyer des commandes Python → JS (reset cam, load PLY, etc.).
  - Option B (future) : renderer natif WGPU via `wgpu-py` si la performance web est insuffisante.
- [ ] **5.2 Intégrer dans `TrainWorkspace`** :
  - Affichage périodique du modèle en cours d'entraînement (si Brush peut exporter un PLY intermédiaire).
  - Overlay HUD (iter, loss, num gaussians).
- [ ] **5.3 Intégrer dans `ExportWorkspace`** :
  - Preview immédiate après export.

**Artéfact livré** : Viewer 3D natif dans l'application.

---

### Phase 6 : Activity Center & Notifications (semaine 11)
**Objectif** : Donner une vision temps réel de l'activité.

- [ ] **6.1 Créer `gui/widgets/activity_center.py`** :
  - Barre fine en bas avec job en cours, monitoring GPU/CPU, bouton logs.
  - Popover job queue (`JobPopover`) affiché au clic.
- [ ] **6.2 Créer `gui/widgets/notification_toast.py`** :
  - Widget toast slide-in depuis le coin bas-droit.
  - File de toasts (max 3 visibles).
- [ ] **6.3 Extraire l'onglet logs** :
  - Transformer `gui/tabs/logs_tab.py` en widget réutilisable `LogViewer`.
  - L'afficher dans un `QDockWidget` ou un overlay slide-up depuis `ActivityCenter`.

**Artéfact livré** : Barre de statut intelligente + notifications + logs accessibles partout.

---

### Phase 7 : Polish & Animations (semaine 12)
**Objectif** : Faire sentir l'application native et fluide.

- [ ] **7.1 Créer `gui/styles/animations.py`** :
  - Helpers : `fade_widget(widget, duration, target_opacity)`, `slide_in(widget, direction)`.
- [ ] **7.2 Ajouter des transitions** :
  - Changement de workspace : fade 150ms.
  - Ouverture d'accordéon : animation `maximumHeight` 200ms ease-out.
  - Changement de preset : animation des curseurs 300ms.
- [ ] **7.3 Créer `gui/widgets/command_palette.py`** :
  - Palette modale avec fuzzy matching.
  - Liste des commandes statique + commandes dynamiques selon le contexte.
- [ ] **7.4 Optimiser le redimensionnement** :
  - `QSplitter` handles customisés (lignes fines 2px).
  - `sizeHint` et `minimumSize` correctement définis pour chaque workspace.

**Artéfact livré** : Application fluide, animée, avec palette de commandes.

---

### Phase 8 : Cleanup & Tests (semaine 13)
**Objectif** : Retirer le code legacy et valider.

- [ ] **8.1 Supprimer `gui/tabs/` ou marquer `@deprecated`** :
  - Une fois que tous les workspaces et inspectors sont migrés, les anciens onglets peuvent être supprimés.
  - **Note** : Le manifest indique "zéro test coverage". C'est l'occasion d'ajouter des tests d'UI basiques (PyTest-Qt) pour valider que chaque workspace s'affiche sans crash.
- [ ] **8.2 Documenter** :
  - Mettre à jour ce `newgui.md` avec les ajustements réels faits pendant l'implémentation.
- [ ] **8.3 Vérifier i18n** :
  - Toutes les nouvelles chaînes doivent passer par `LanguageManager`. Ajouter les clés dans `assets/locales/en.json` et `fr.json`.

**Artéfact livré** : Code propre, documenté, prêt pour la release v1.0.0.

---

## 6. Design System

### 6.1 Palette de couleurs (Dark Mode — par défaut)

```python
# gui/styles/design_tokens.py

class DesignTokens:
    # Fonds
    BG = "#0F0F11"          # background : fenêtre principale
    SURFACE = "#1C1C1E"     # surface : panneaux, cartes
    ELEVATED = "#252528"    # elevated : inputs, boutons, hover states
    OVERLAY = "#000000"     # overlay : modales, toasts (avec alpha)

    # Texte
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#98989D"
    TEXT_TERTIARY = "#636366"
    TEXT_DISABLED = "#48484A"

    # Bordures & séparation
    DIVIDER = "#38383A"
    DIVIDER_LIGHT = "#48484A"

    # Accent (bleu système macOS, adaptable selon OS)
    ACCENT = "#0A84FF"
    ACCENT_HOVER = "#409CFF"
    ACCENT_PRESSED = "#0066CC"
    ACCENT_BG = "#0A84FF20"  # 20 = 32/255 alpha

    # États sémantiques
    SUCCESS = "#30D158"
    SUCCESS_BG = "#30D15820"
    WARNING = "#FFD60A"
    WARNING_BG = "#FFD60A20"
    ERROR = "#FF453A"
    ERROR_BG = "#FF453A20"

    # Scrollbar & utilitaires
    SCROLLBAR = "#48484A"
    SCROLLBAR_HOVER = "#636366"
```

### 6.2 Typographie

```python
# gui/styles/design_tokens.py (suite)

class Typography:
    FAMILY = "-apple-system, BlinkMacSystemFont, 'SF Pro', 'Inter', 'Segoe UI', sans-serif"
    
    TITLE = "font: 600 20px; letter-spacing: -0.5px;"
    HEADING = "font: 600 15px;"
    BODY = "font: 400 13px;"
    CAPTION = "font: 400 11px;"
    MONOSPACE = "font: 400 12px 'SF Mono', 'Menlo', 'Consolas', monospace;"
```

### 6.3 Rayons de bordure & Espacement

```python
class Dimensions:
    RADIUS_SM = 4   # inputs, badges
    RADIUS_MD = 6   # boutons, petites cartes
    RADIUS_LG = 8   # panneaux, modales
    RADIUS_XL = 12  # grandes cartes, project hub

    PADDING_SM = 4
    PADDING_MD = 8
    PADDING_LG = 12
    PADDING_XL = 16
    PADDING_XXL = 24
```

### 6.4 Ombres (QGraphicsDropShadowEffect)

```python
class Shadows:
    ELEVATED = "0px 4px 12px rgba(0,0,0,0.20)"
    MODAL = "0px 8px 24px rgba(0,0,0,0.40)"
    TOAST = "0px 2px 8px rgba(0,0,0,0.25)"
```

---

## 7. Checklist de migration

### Avant de commencer
- [ ] Sauvegarder une branche `legacy-tabs` depuis `main`.
- [ ] S'assurer que `gui/styles.py` est versionné (sera remplacé).
- [ ] Créer un dossier `gui/new/` ou travailler directement dans `gui/` ? **Recommandation** : créer `gui/v2/` en parallèle, puis renommer à la fin pour éviter les conflits pendant le développement.

### Par phase (voir section 5)
- [ ] Phase 1 : Fondations (design system + structure fenêtre)
- [ ] Phase 2 : Pipeline Timeline
- [ ] Phase 3 : Inspector + Project Hub
- [ ] Phase 4 : Workspaces spécialisés
- [ ] Phase 5 : Viewport 3D
- [ ] Phase 6 : Activity Center
- [ ] Phase 7 : Polish & Command Palette
- [ ] Phase 8 : Cleanup, tests i18n, suppression legacy

### Vérifications finales
- [ ] Toutes les anciennes classes `*Tab` sont soit supprimées, soit référencées dans un fichier `DEPRECATED.md`.
- [ ] Le manifest.md est mis à jour (architecture GUI, nombre de fichiers, nouveaux modules).
- [ ] Les locales JSON (`assets/locales/*.json`) contiennent toutes les nouvelles clés UI.
- [ ] Aucune régression fonctionnelle : le pipeline complet (Import → COLMAP → Brush → Export) fonctionne de bout en bout.
- [ ] Testé sur macOS Apple Silicon (plateforme cible principale).
- [ ] Le thème sombre est cohérent partout (pas de zones encore en Qt native grise).

---

## Annexes

### A. Dépendances Python potentiellement utiles

| Package | Usage | Phase |
|---------|-------|-------|
| `PyQt6` | Déjà présent. Utiliser `QWebEngineView`, `QPropertyAnimation`, `QGraphicsDropShadowEffect`. | Toutes |
| `pyqtgraph` | Graphes temps réel dans `TrainWorkspace` (loss, PSNR). | 4 |
| `phosphor-icons` (ou SVG inline) | Icônes modernes pour sidebar et timeline. | 1 |
| `pillow` | Déjà présent. Génération de thumbnails pour Project Hub. | 3 |
| `watchdog` | Observer les fichiers PLY intermédiaires pour mise à jour live du viewport. | 5 |

### B. Références visuelles recommandées

- **DaVinci Resolve** : timeline de pipeline, viewer central, inspector de droite.
- **Blender 4.x** : workspace adaptatifs, sidebar contextuelle.
- **Apple Final Cut Pro** : magnetic timeline, viewer fluide, HUD discret.
- **Figma** : minimalisme, ombres douces, espacement généreux.
- **Docker Desktop** : activity center, toasts, monitoring ressources.

### C. Note sur PyQt6 vs. autres frameworks

Ce document suppose le maintien de **PyQt6** (stack actuel). Si une migration vers un autre framework est envisagée :
- **Dear PyGui** : très rapide (GPU), mais moins mature pour du web embedding.
- **PySide6** : quasi identique à PyQt6, licence LGPL plus permissive.
- **Tauri + Python backend** : plus lourd à migrer, mais UI web native possible.

**Recommandation** : rester sur PyQt6, moderniser par le design system et les animations.

---

*Document de référence pour le redesign GUI de CorbeauSplat. Dernière mise à jour : 2026-05-18.*
