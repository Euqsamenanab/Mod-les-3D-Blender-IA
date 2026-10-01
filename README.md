# Modèles 3D Blender

Modèles 3D générés par scripts Python (`bpy`), pour Blender 4.3 et Unity 6 (URP).
Chaque modèle est entièrement procédural : on modifie des paramètres, on relance le
script, et on obtient le `.blend` et les rendus de validation.

## Installation

```bash
python3.11 -m venv ~/.venv-blender
~/.venv-blender/bin/pip install -r requirements.txt
```

`bpy` 4.3 est le module Python officiel de Blender. Les fichiers `.blend` produits
s'ouvrent dans Blender 4.3.x. Les rendus utilisent Cycles en CPU, sans interface.

## Structure

| Dossier | Contenu |
| --- | --- |
| `lib/geom.py` | Géométrie : courbes 2D, ré-échantillonnage, maillage par anneaux, caps en grille de quads |
| `lib/materials.py` | Matériau latex réglable (groupe de nœuds `Latex_Reglages`) |
| `lib/studio.py` | Scène, lumières, caméras, rendu, contrôle qualité du maillage |
| `poche_canine/` | Vagin de poche à vulve canine stylisée (anthro/furry) |
| `output/` | Fichiers `.blend` et rendus générés |

## Vagin de poche (`poche_canine/`)

```bash
~/.venv-blender/bin/python poche_canine/build.py            # .blend + tous les rendus
~/.venv-blender/bin/python poche_canine/build.py --quick    # aperçus rapides basse définition
~/.venv-blender/bin/python poche_canine/build.py --only=01,04 --quick
~/.venv-blender/bin/python poche_canine/build.py --no-render
```

Les dimensions et formes sont dans `PARAMS` (`poche_canine/sleeve.py`).

### Maillage

- Uniquement des quads, maillage fermé, normales cohérentes. Le contrôle qualité est affiché à chaque build.
- Topologie en anneaux concentriques autour de la fente, puis anneaux réguliers le long du canal (pas de 1,25 mm), pour une déformation propre.
- Subdivision Surface : niveau 1 dans la vue, niveau 2 au rendu.
- Dimensions : 11 × 13 × 24 cm ; vulve de 5,7 × 7,3 cm, en saillie de 2 cm ; canal de 18,8 cm.
- Canal de verrouillage : vestibule sous la fente, anneau d'entrée étroit (Ø 11 mm au repos), chambre du nœud (Ø 26 mm, 3–9 cm de profondeur), canal (Ø 15 mm), fond arrondi.

### Shape keys

Toutes vont de 0 (forme de base) à 1, se combinent entre elles et passent dans
Unity sous forme de blend shapes (0 à 100). Chaque réglage dans les deux sens
correspond à une paire de shape keys.

| Shape key | Effet à 1 |
| --- | --- |
| `Vulve_Grande` / `Vulve_Petite` | Vulve entière (contour + fente) agrandie de 20 % / réduite de 20 % |
| `Levres_Gonflees` / `Levres_Fines` | Lèvres plus hautes et pulpeuses, avec débord / plus plates |
| `Fente_Branches_Longues` / `Fente_Branches_Courtes` | Branches du Y : × 1,6 / × 0,45 |
| `Pointe_Allongee` / `Pointe_Arrondie` | Pointe du bas plus longue et fine (+1 cm) / plus courte et ronde (-1 cm) |
| `Anneau_Serre` / `Anneau_Large` | Anneau d'entrée Ø 7 mm (verrouillage franc) / Ø 15 mm (verrouillage souple) |
| `Chambre_Large` / `Chambre_Fine` | Chambre du nœud Ø 36 mm / Ø 18 mm |
| `Canal_Anneaux` | Anneaux dans le canal |
| `Canal_Nervures` | Nervures longitudinales |
| `Canal_Picots` | Picots en quinconce |
| `Canal_Plis` | Plis ondulés |
| `Canal_Anneaux_Picots` | Anneaux et picots alternés |
| `Canal_Nervures_Plis` | Nervures et plis |

Canal lisse : toutes les shape keys `Canal_*` à 0.

Les shape keys sont définies dans `SHAPE_KEYS` (`poche_canine/sleeve.py`) : pour
changer une amplitude, modifier la valeur et relancer le build. Les contours de la
fente et de la vulve ont une paramétrisation fixe : chaque sommet garde sa place
quand une dimension change, donc les réglages se combinent sans artefacts.

### Matériau

Propriétés > Matériau > Surface, groupe `Réglages Latex` :

| Réglage | Rôle |
| --- | --- |
| Couleur | Couleur du latex |
| Transparence | 0 = opaque, 1 = latex clair transparent |
| Reflet | 0 = mat, 1 = très brillant |
| Couleur Vulve / Teinte Vulve | Teinte de la vulve, avec son intensité |
| Couleur Interieur / Teinte Interieur | Teinte de l'intérieur (fente et canal), avec son intensité |

Les zones teintées viennent de l'attribut de couleur `Masques` (R = vulve, G = intérieur).

### Rendus de validation (`output/poche_canine/`)

| Fichier | Vue |
| --- | --- |
| `01` | Face, opaque |
| `02` | Trois-quarts, opaque |
| `03` | Trois-quarts, lèvres gonflées |
| `03b` | Face, lèvres gonflées |
| `04` | Coupe du canal lisse |
| `05` | Planche des variantes du canal |
| `06` | Latex semi-transparent |
| `07`, `08` | Topologie |
| `09` | Profil |
| `09b` | Profil, lèvres gonflées |
| `10` | Planche des réglages de la vulve |
| `11` | Planche des réglages de l'anneau d'entrée et de la chambre |

### À venir

- Jouets de test réglables en Geometry Nodes : lisse, à perles (taille et écartement par perle), à nœud stylisé.
- Tests de déformation : Geometry Nodes (instantané) et simulation physique, avec rigidité réglable.
- UV propres, puis textures 4K/8K (masques de couleur, normal map des petits plis), export FBX pour Unity.
