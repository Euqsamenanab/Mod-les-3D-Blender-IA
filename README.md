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
| `poche_canine/` | Vagin de poche à vulve canine stylisée (anthro/furry), ses variantes (`variantes.py`) et sa scène de test |
| `jouets/` | Jouets de test procéduraux en Geometry Nodes (`build.py` : fichier des jouets seuls) |
| `deformation/` | Test d'insertion en Geometry Nodes (déformation instantanée) |
| `lib/uv.py`, `lib/bake.py` | Coutures et dépliage UV, cuisson de textures (Cycles) |
| `unity/` | Export FBX pour Unity 6 URP |
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

## Variantes du vagin de poche

```bash
~/.venv-blender/bin/python poche_canine/build_variantes.py                  # 4 .blend + planche 50
~/.venv-blender/bin/python poche_canine/build_variantes.py --only=Poche_Oeuf_Bulbe --no-render
~/.venv-blender/bin/python poche_canine/build_textures.py --variante=Poche_Oeuf_Bulbe --res=4096
```

| Variante (`output/poche_canine/variantes/`) | Forme | Entrée | Shape keys |
| --- | --- | --- | --- |
| `Poche_Oeuf_Bulbe` | Œuf, 12,4 x 13,6 x 23,5 cm | Vulve en bulbe à 3 lobes, sombre | 18 |
| `Poche_Sablier_Coeur` | Sablier, 11,6 x 13,6 x 24 cm | Vulve en cœur charnu, Y entrouvert | 20 |
| `Poche_Fessier_Double` | Mini fessier, 17,6 x 17,6 x 20 cm | Petite fente + anus, deux canaux | 33 |
| `Poche_Sablier_Anus` | Sablier | Anus seul | 13 |

Toutes les variantes gardent les principes du modèle d'origine : 100 % quads, maillage
fermé, topologie fixe pour les shape keys, UV, masques, matériau latex réglable.

### Formes extérieures (`FORMES` dans `poche_canine/variantes.py`)

- **Œuf :** face avant en dôme, la plus large près de l'avant, arrière effilé et long.
- **Sablier :** taille resserrée à 83 % vers le milieu pour la prise en main, bouts renflés.
- **Mini fessier :** deux fesses rondes séparées par un sillon arrondi.
  - La face s'aplanit sous l'anus pour qu'il ne soit pas plié par le sillon.
  - La vulve est en bas, entre le bas des fesses, et l'anus au-dessus, dans le sillon.

### Styles de lèvres (`LEVRES`)

- **Bulbe à 3 lobes :** vulve ronde et très saillante. Les branches du Y vont presque
  jusqu'au bord et découpent trois coussinets. La teinte est sombre par défaut.
- **Cœur charnu :** contour en cœur, avec un creux en haut et une pointe en bas, et des
  lèvres épaisses.
  - Le Y est entrouvert à la jonction et laisse voir l'intérieur rose.
  - Shape keys `Fente_Ouverte` et `Fente_Fermee`.
- **Petite fente :** vulve ovale plus petite et plus plate, fente entrouverte en
  lentille, petits plis à la pointe basse. Shape keys `Fente_Ouverte` et `Fente_Fermee`.
- **Classique :** le style du modèle d'origine.

Les shape keys de la vulve (`Vulve_*`, `Levres_*`, `Fente_Branches_*`, `Pointe_*`) et du
canal (`Anneau_*`, `Chambre_*`, `Canal_*`) existent sur toutes les variantes à vulve.
Elles sont relatives au style : `Levres_Gonflees` multiplie la hauteur des lèvres par 1,3.

### Anus

- **Forme de base :** anneau gonflé, avec un cratère autour d'une petite ouverture et un
  bourrelet rond à mi-rayon.
- **`Anus_Plisse` :** passe à l'anus plissé en étoile, en losange vertical avec 10 plis
  rayonnants. La topologie ne change pas, donc on peut mélanger les deux formes.
- **Autres shape keys :**
  - `Anus_Gonfle` : bourrelet plus haut et plus large ;
  - `Anus_Ouvert` : ouverture entrouverte ;
  - `Anus_Anneau_Serre` et `Anus_Anneau_Large` : anneau d'entrée ;
  - `Anus_Chambre_Large` et `Anus_Chambre_Fine` : chambre du nœud ;
  - `Anus_Canal_*` : mêmes 6 variantes de canal que le vagin.
- **Canal anal :** plus étroit que le vagin, avec un anneau d'entrée serré et une
  chambre qui retient aussi un nœud.
  - Anus seul : 15,7 cm.
  - Double entrée : 14,3 cm.

### Double entrée (mini fessier)

- **Construction :** trois maillages en anneaux, fusionnés sans triangle : la région de
  la vulve, celle de l'anus et le corps.
- **Bords communs :** les deux régions partagent un bord horizontal entre les deux
  entrées. Ces bords sont fixés par la forme de base, donc toutes les shape keys restent
  compatibles.
- **Canaux :** deux canaux parallèles et séparés. Celui du vagin fait 18,9 cm, celui de
  l'anus 14,3 cm, avec son axe 7,2 cm au-dessus de celui du vagin.

### Créer une autre combinaison

`parametres(forme, levres, anus)` dans `poche_canine/variantes.py` donne les paramètres
et les shape keys de n'importe quelle combinaison :
- `forme` : `cylindre`, `oeuf`, `sablier` ou `fessier` ;
- `levres` : `classique`, `bulbe`, `coeur` ou `fente` ;
- `anus` : `None`, `"seul"` ou `"double"`.

Pour l'ajouter aux fichiers générés, il suffit d'ajouter une entrée à `VARIANTES` (avec
les couleurs de son matériau). Le mini fessier n'existe qu'en double entrée.

### Aperçus (`output/poche_canine/50_variantes.png`)

Quatre vues rapides par variante (face, trois-quarts, profil, coupe), en latex opaque.

## Jouets de test (`jouets/`)

Trois jouets procéduraux, réglables en direct dans le modificateur `Generateur`
(Propriétés > Modificateurs). Chaque jouet est un gabarit fixe de 47 040 quads
(après subdivision niveau 1), dont la forme est calculée par Geometry Nodes à partir d'un
profil de révolution : la topologie ne change jamais, quels que soient les réglages.

| Jouet | Réglages |
| --- | --- |
| `Jouet_Lisse` | Longueur (23,5 cm), Diamètre (4,2 cm), Diamètre pointe, base, lissage |
| `Jouet_Perles` | Nombre de perles (1 à 8), diamètre de chaque perle, écart après chaque perle (la longueur suit), diamètre de tige, allongement des perles, longueur du manche, base |
| `Jouet_Noue` | Pointe → centre du nœud (15,5 cm), petite pointe (diamètre, longueur), gland en obus (diamètre, longueur, bourrelet), tige (diamètre côté gland et côté nœud), sillon de l'urètre (profondeur, largeur), nœud en deux lobes (diamètre des lobes, écart, longueur), col, base |

La perle 1 est à la pointe. Les jouets lisse et à perles dépassent la longueur du
canal, pour qu'il y ait une butée au fond.

Le jouet noué (canin stylisé) n'est pas de révolution : le profil répartit les
anneaux le long de l'axe, puis chaque sommet reçoit un rayon selon son angle
(sillon de l'urètre sur le dessous, côté +Y local ; lobes du nœud de chaque côté,
±X). Gabarit de 160 sommets par anneau pour garder le sillon et les veines nets.

**Veines du jouet noué :**
- **Intensité :** shape key `Veines` (Propriétés > Données de l'objet > Shape Keys),
  curseur de 0 (aucune veine) à 2 (relief doublé).
- **Forme :** dans le modificateur `Generateur` :
  - nombre de veines (jusqu'à 5 veines et 2 ramifications) ;
  - épaisseur et relief ;
  - sinuosité ;
  - « graine », qui donne un autre tracé aléatoire.
- **Placement :** les veines courent sur le dessus et les flancs de la tige, entre
  le gland et le nœud, sans toucher au sillon de l'urètre.
- **Fonctionnement :** la shape key décale le gabarit de +1 en X, et le générateur
  lit ce décalage comme intensité.
- **Unity :** à l'export, le jouet est figé avec une vraie blend shape `Veines`
  (voir « Export Unity 6 URP »).

```bash
~/.venv-blender/bin/python jouets/build.py     # output/jouets/jouets.blend + vues du jouet noué
```

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

## Simulation physique

```bash
~/.venv-blender/bin/python poche_canine/build_physique.py            # test_physique.blend + rendus 30, 31 + GIF
~/.venv-blender/bin/python poche_canine/build_physique.py --no-render
```

Dans `output/poche_canine/test_physique.blend`, l'animation fait un cycle de 11,3 s :
entrée, butée au fond, maintien, retrait, retour au repos. Le fichier est généré à
30 images par seconde.

Options de génération :

| Option | Effet |
| --- | --- |
| `--fps=24`, `30` ou `60` | Cadence ; la durée reste la même |
| `--boucles=N` | N cycles enchaînés ; première et dernière image identiques, la vidéo boucle sans à-coup |
| `--vitesse=2` | Mouvement deux fois plus rapide |

### Rendu vidéo fluide (sur ton PC, avec GPU)

La lecture directe dans la vue 3D n'est pas fluide : chaque image recalcule la
simulation, les jouets procéduraux et la subdivision. Pour voir le résultat final,
il faut cuire la simulation puis rendre une vidéo :

1. Ouvrir `test_physique.blend`.
2. Afficher `Poche_Proxy` dans l'Outliner, puis Propriétés > Physique > Cloth > Cache > **Bake**.
   La cuisson prend environ 1 minute. Ensuite, la lecture dans la vue est déjà plus fluide.
3. Moteur de rendu, au choix :
   - **Cycles** : laisser Cycles et activer le GPU (Préférences > Système > Cycles Render
     Devices : OptiX ou CUDA, ou HIP). Comptez quelques secondes par image en 1080p.
   - **EEVEE** : environ 1 seconde par image ; activer *Raytracing* pour la transparence du latex.
4. Choisir la caméra :
   - `Cam_Exterieur` (active par défaut) : vue d'ensemble, latex transparent ;
   - `Cam_Coupe` : vue du canal. Clic droit > *Set Active Camera*, puis cocher
     « Vue en coupe » dans le modificateur `Vue_en_coupe` de `Poche_Canine` et mettre
     Transparence à 0 dans le matériau `Latex_Poche`.
5. Rendu > **Render Animation** (Ctrl+F12). La sortie est déjà réglée : MP4 H.264
   1920 x 1080, dans le dossier `rendu/` à côté du `.blend`.

Rendu sans interface (CPU, lent : environ 40 s par image en 720p) :

```bash
~/.venv-blender/bin/python poche_canine/build_physique.py --video --res=1920x1080 --samples=64
~/.venv-blender/bin/python poche_canine/build_physique.py --video --png --res=1280x720 --debut=1 --fin=170   # par tranches
~/.venv-blender/bin/python poche_canine/build_physique.py --assembler --res=1280x720                       # PNG -> MP4
```

**Fonctionnement (hybride, stable et propre) :**
- **Collision pure, écartée :** un Cloth classique qui heurte le jouet donne des parois
  froissées et traversées, quand un canal de 15 mm doit s'ouvrir à 42 mm à partir
  d'une fente fermée.
- **Poche_Proxy (masquée, environ 4 200 sommets) :**
  - le modificateur `Cible` calcule la forme propre de la déformation, avec le même
    modèle que le test Geometry Nodes, à partir de la vraie position animée du jouet ;
  - le `Cloth` en mode *Dynamic Mesh* suit cette cible avec l'inertie, le retard et les
    ondulations du latex ;
  - le rappel vers la cible (groupe `Maintien`) est faible dans le canal et les lèvres,
    et fort sur la surface extérieure tenue en main. Il n'y a pas de gravité.
- **Poche_Canine :** la poche détaillée suit le proxy (Surface Deform), puis la
  subdivision et la vue en coupe s'appliquent.
- **Jouets :** animés le long de l'axe. Le modificateur `Cible_Jouet` les tasse et les
  fléchit selon les rigidités. Il est calculé contre `Poche_Repos`, copie figée de la
  poche, pour éviter les dépendances circulaires.

**Réglages (objet `Reglages_Physique`, propriétés personnalisées) :**

| Propriété | Effet |
| --- | --- |
| Rigidité latex | Raideur du Cloth et rappel vers la cible (0 : latex très souple, qui ondule et traîne ; 1 : ferme), diffusion de la déformation |
| Rigidité jouet | 0 : jouet très souple, qui se tasse et fléchit en butée ; 1 : rigide |
| Flexion | Part du tassement d'un jouet souple absorbée en flexion |

**Changer de jouet :**
1. Dans le modificateur `Cible` de `Poche_Proxy`, choisir le jouet.
2. Afficher ce jouet et masquer les autres.
3. Relancer la simulation.

**Après une modification des shape keys de la poche :** refaire la liaison
(`Suivi_Simulation` > Unbind puis Bind, à l'image 1), puis relancer la simulation.
Le proxy garde la forme de base : régénérer avec le script pour un proxy adapté.

| Fichier | Contenu |
| --- | --- |
| `30` | Séquence avec le jouet noué (entrée, nœud, butée, retrait), en coupe |
| `31` | Rigidités : latex souple, latex ferme, jouet souple, jouet rigide |
| `physique_noue.gif` | Animation de la séquence |

## UV et textures

```bash
~/.venv-blender/bin/python poche_canine/build_textures.py --res=4096   # textures 4K + rendus 40 à 43
~/.venv-blender/bin/python poche_canine/build_textures.py --res=8192 --no-render
```

### UV du vagin de poche

Les UV sont créés automatiquement par `make_sleeve` (`poche_canine/objet.py`), donc
présents dans tous les fichiers.

**Coutures**, posées sur la structure en anneaux, aux endroits peu visibles :
- la ligne du dessous, de la fente jusqu'au fond, qui passe sous la pointe de la vulve ;
- le bord de la fente ;
- le contour de la vulve ;
- le bord de la face avant ;
- les deux fonds ;
- une coupe dans le canal, après la chambre du nœud.

**Îlots :** lèvres, face avant, flancs et dos, entrée du canal (vestibule et chambre),
canal, fond du canal, fond de la poche. Dépliage *angle based*, densité égalisée puis
empaquetage, avec 71 % d'occupation.

**Densité :** la vulve a une résolution doublée (×2 en longueur) et la face avant est
×1,2. En 4K, un pixel couvre environ 0,11 mm sur l'extérieur et 0,055 mm sur la vulve.

### Textures (`output/poche_canine/textures/`, en 4K et 8K)

| Carte | Contenu | Espace couleur | Unity URP Lit |
| --- | --- | --- | --- |
| `Poche_Canine_BaseColor_*` | Latex clair, teinte de la vulve, intérieur rose | sRGB | Base Map |
| `Poche_Canine_Normal_*` | Petits plis autour de la pointe basse de la vulve, grain fin des lèvres (tangente, OpenGL) | Non-Color | Normal Map (type *Normal map*) |
| `Poche_Canine_AO_*` | Occlusion ambiante (fente, contour, canal) | Non-Color | Occlusion Map |
| `Poche_Canine_Masques_*` | R = vulve, G = intérieur (pour recolorer dans un shader) | Non-Color | — |

- **Cuisson :** sur la poche subdivisée (niveau 2). Les couleurs sont celles du
  matériau latex par défaut.
- **Après une modification des couleurs du matériau :** relancer le script pour
  recuire les cartes.
- **Fichiers `poche_canine_textures.blend` (4K) et `poche_canine_textures_8k.blend` :**
  la poche avec ses UV et un 2ᵉ matériau, `Latex_Poche_Textures`, qui utilise les
  cartes, comme dans Unity. Les chemins des textures sont relatifs (`//textures/...`).
- **AO du canal :** le canal est presque noir dans la carte AO, car c'est un tube
  fermé. Si le latex est transparent dans Unity, baisser la force de l'occlusion pour
  garder l'intérieur visible.

### UV des jouets

- **Principe :** les UV sont posés sur le gabarit, donc ils restent valides quels que
  soient les réglages du générateur.
- **Disposition :** la tige forme une bande (U = tour, V = longueur), coupée sur une
  génératrice ; la base et la pointe ont chacune leur îlot.
- **Limite :** sur les perles et les lobes, la bande s'étire en largeur. C'est sans
  conséquence pour des couleurs unies, mais pas idéal pour des motifs.

| Fichier | Contenu |
| --- | --- |
| `40` | Damier UV sur la poche |
| `41` | Disposition UV colorée par zone |
| `42` | Rendus avec les textures cuites, et gros plan des plis |
| `43` | Aperçu des 4 cartes |

## Export Unity 6 URP (`output/unity/`)

```bash
~/.venv-blender/bin/python unity/export_fbx.py                       # tous les FBX
~/.venv-blender/bin/python unity/export_fbx.py --only=Poche_Fessier_Double
~/.venv-blender/bin/python unity/export_fbx.py --only=noue --subdiv-jouets=1
```

### Fichiers

| FBX | Sommets | Blend shapes |
| --- | --- | --- |
| `Poche_Canine.fbx` | 85 634 (subdivision 1) | Les 18 shape keys de la poche |
| `Jouet_Lisse.fbx` | 47 042 (subdivision 1) | `Epais`, `Fin`, `Long`, `Court` |
| `Jouet_Perles.fbx` | 47 042 (subdivision 1) | `Perles_Grosses`, `Perles_Petites`, `Ecarts_Grands`, `Perles_Allongees`, `Tige_Epaisse` |
| `Jouet_Noue.fbx` | 51 042 (gabarit déjà dense) | `Veines`, `Noeud_Gros`, `Noeud_Petit`, `Gland_Gros`, `Epais`, `Fin`, `Long`, `Court` |
| `Poche_Oeuf_Bulbe.fbx` | 84 098 (subdivision 1) | 18 |
| `Poche_Sablier_Coeur.fbx` | 85 634 (subdivision 1) | 20 |
| `Poche_Fessier_Double.fbx` | 143 958 (subdivision 1) | 33 (vulve, canal, anus, canal anal) |
| `Poche_Sablier_Anus.fbx` | 74 114 (subdivision 1) | 13 (anus, canal anal) |

- **Objets figés :** les modificateurs (Geometry Nodes, Subdivision) sont appliqués, et
  chaque blend shape est recalculée à travers eux.
- **Réglages des jouets :** les réglages du générateur deviennent des blend shapes, car
  la topologie du gabarit ne change jamais. À 0 % et à 100 %, la forme est exacte. Entre
  les deux, Unity interpole en ligne droite : l'écart avec le vrai réglage est inférieur à
  1 mm en moyenne, et va jusqu'à 4,6 mm sur le nœud à 50 %.
- **Ajouter un réglage :** compléter `VARIANTES_JOUETS` dans `unity/export_fbx.py`.
- **Contenu :** UV `UVMap` dans tous les FBX. La poche a en plus les couleurs de
  sommets `Masques` (R = vulve, G = intérieur, en linéaire).
- **Repère :** mètres, Y en haut, rotation et échelle déjà appliquées.
  - Poche : pivot au centre de l'entrée du canal. La vulve regarde +Z (l'avant de
    l'objet), et le canal s'enfonce vers -Z sur 18,8 cm.
  - Variantes : même repère. En double entrée, le pivot est à l'entrée du vagin, et
    l'axe de l'anus est 7,2 cm au-dessus (+Y).
  - Jouets : pivot au centre de la base, pointe vers +Y.

### Import dans Unity (onglet Model de l'inspecteur)

- **Scale Factor :** 1, avec *Convert Units* coché. *Bake Axis Conversion* est inutile.
- **Import BlendShapes :** coché.
- **Normals :** *Import*.
- **Blend Shape Normals :** *Calculate*. Le FBX ne contient pas de normales de blend
  shapes. Si Unity ne propose pas *Calculate* avec *Normals: Import*, passer *Normals*
  en *Calculate* avec un *Smoothing Angle* de 180.
- **Tangents :** *Calculate Mikktspace*.
- **Mesh Compression :** *Off*.
- **Index Format :** *Auto*. Il passe en 32 bits pour plus de 65 535 sommets.
- **Read/Write :** à cocher seulement si un script déforme le maillage.
- **Blend shapes :** se règlent dans le *SkinnedMeshRenderer* (0 à 100), ou par script
  avec `SetBlendShapeWeight`.
  - Les paires opposées sont à utiliser une à la fois (`Vulve_Grande` / `Vulve_Petite`).
  - Un seul `Canal_*` à la fois : les mélanges `Canal_Anneaux_Picots` et
    `Canal_Nervures_Plis` sont déjà fournis.

### Textures de la poche (`output/poche_canine/textures/`)

**Max Size :** à mettre à 4096 ou 8192. Le défaut de Unity (2048) réduirait les cartes.

| Carte | Réglages d'import | Matériau URP Lit |
| --- | --- | --- |
| `BaseColor` | *Default*, sRGB coché | *Base Map* |
| `Normal` | *Normal map* (convention OpenGL, comme Unity) | *Normal Map* |
| `AO` | *Default*, sRGB décoché | *Occlusion Map* (force 0,3 à 0,6 si transparent) |
| `Masques` | *Default*, sRGB décoché | Non utilisée par URP Lit (prévue pour un shader sur mesure) |

### Matériaux URP

- **Poche, shader *Universal Render Pipeline/Lit* :**
  - *Surface Type* : Transparent, *Blending Mode* : Alpha, *Preserve Specular Lighting* coché ;
  - *Render Face* : Front ;
  - couleur de la Base Map : blanc, alpha 0,3 à 0,5 pour la transparence (1 = opaque) ;
  - *Metallic* : 0, *Smoothness* : 0,85 pour le reflet.
- **Reflet plus marqué :** le shader *Complex Lit* ajoute un *Clear Coat*, comme le
  vernis du matériau Blender.
- **Jouets :** *Lit* opaque, avec la couleur du jouet et une *Smoothness* de 0,8.
- **Limite de URP Lit :** les teintes de la vulve et de l'intérieur sont cuites dans la
  BaseColor. Pour les régler à part dans Unity, il faudra un shader sur mesure qui lit
  les `Masques`.

## À venir

- Shader URP sur mesure : couleur, transparence, reflet, teintes de la vulve et de
  l'intérieur réglables à part (avec les `Masques`).
- Déformation à l'insertion dans Unity.
- Version torse (onahole) de la poche.
