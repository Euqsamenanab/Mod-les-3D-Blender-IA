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
| `lib/nodes.py` | Construction d'arbres Geometry Nodes depuis Python |
| `poche_canine/` | Vagin de poche à vulve canine stylisée (anthro/furry) et sa scène de test |
| `jouets/` | Jouets de test procéduraux en Geometry Nodes |
| `deformation/` | Test d'insertion en Geometry Nodes (déformation instantanée) |
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
Le même matériau sert aux jouets (chacun a son propre matériau, donc ses propres réglages).

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

## Jouets de test (`jouets/`)

Trois jouets procéduraux, réglables en direct dans le modificateur `Generateur`
(Propriétés > Modificateurs). Chaque jouet est un gabarit fixe de 47 040 quads
(après subdivision niveau 1), dont la forme est calculée par Geometry Nodes à partir d'un
profil de révolution : la topologie ne change jamais, quels que soient les réglages.

| Jouet | Réglages |
| --- | --- |
| `Jouet_Lisse` | Longueur (23,5 cm), Diamètre (4,2 cm), Diamètre pointe, base, lissage |
| `Jouet_Perles` | Nombre de perles (1 à 8), diamètre de chaque perle, écart après chaque perle (la longueur suit), diamètre de tige, allongement des perles, longueur du manche, base |
| `Jouet_Noue` | Pointe → centre du nœud (15,5 cm), diamètre et longueur de la pointe effilée, diamètre et renflement de la tige, diamètre (6,2 cm) et longueur du nœud, col, base |

La perle 1 est à la pointe. Les jouets lisse et à perles dépassent la longueur du
canal, pour qu'il y ait une butée au fond.

## Test d'insertion en Geometry Nodes

```bash
~/.venv-blender/bin/python poche_canine/build_test.py            # test_insertion.blend + rendus 20 à 26
~/.venv-blender/bin/python poche_canine/build_test.py --quick --only=24
```

Dans `output/poche_canine/test_insertion.blend`, l'objet `Test_Insertion`
(modificateur du même nom) réunit la poche et le jouet choisi :

| Réglage | Rôle |
| --- | --- |
| Jouet | Jouet à insérer (Jouet_Lisse, Jouet_Perles, Jouet_Noue) |
| Insertion | Profondeur de la pointe depuis la fente ; animée de l'image 1 à 200 (entrée, butée, maintien, retrait) |
| Rigidité poche | 0 = latex très souple, 1 = rigide |
| Rigidité jouet | 0 = jouet très souple, 1 = rigide |
| Diffusion | Étalement de la déformation dans le latex |
| Flexion | Part du tassement d'un jouet souple absorbée en flexion (partie restée dehors) |
| Subdivision | Niveau de subdivision de la poche (1 en travail, 2 pour le rendu) |
| Vue en coupe | Supprime la moitié avant pour voir le canal |

`Poche_Canine_Source` (masqué) est la poche avec ses shape keys : les modifier
(anneau, chambre, canal...) change directement le test. Les réglages des jouets
s'appliquent aussi en direct.

Modèle de déformation, instantané et sans simulation :
- **Contact :** dans chaque direction autour de l'axe, le canal et le jouet se
  rencontrent à un rayon de contact partagé selon leurs rigidités.
- **Dilatation :** le latex se dilate à aire conservée (incompressible). La paroi du
  canal suit le jouet, la matière autour suit, la surface extérieure gonfle et les
  lèvres s'écartent.
- **Diffusion :** la dilatation est étalée le long du latex, plus largement quand
  il est rigide.
- **Butée au fond :** le fond du canal recule d'abord devant la pointe, puis le
  canal se dilate. Un jouet souple se tasse (avec renflement) et fléchit quand au
  moins 3 cm restent dehors.
- **Jouet souple :** un jouet plein est presque incompressible, donc il cède au plus
  35 % du recouvrement en diamètre ; le reste va au latex.

C'est une déformation cinématique : elle ne calcule pas de forces, donc pas de
frottement ni de retenue du nœud. La simulation physique est l'étape suivante.

### Rendus du test (`output/poche_canine/`)

| Fichier | Vue |
| --- | --- |
| `20` | Les trois jouets |
| `21` | Jouets : réglages par défaut et réglages modifiés |
| `22`, `23`, `24` | Insertion en coupe : jouet lisse, à perles, noué |
| `25` | Butée au fond : jouet rigide ou souple, latex souple ou ferme |
| `26` | Jouet noué inséré, latex transparent |

## À venir

- Test de déformation en simulation physique, avec rigidité réglable du latex et des jouets.
- UV propres, puis textures 4K/8K (masques de couleur, normal map des petits plis), export FBX pour Unity.
