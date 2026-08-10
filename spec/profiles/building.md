# Building and Site Profile

Profile ID: `building@0.1.0`

Depends on: SemaSVG Core 0.1.0

## Type namespace

All types defined by this profile use the `building:` prefix.

Examples:

```text
building:site
building:building
building:level
building:space
building:vertical-connection
building:column
building:slab
building:roof
building:wall
building:opening
building:fence
```

The view MUST declare `building@0.1.0` in `data-sema-profiles`.

## 1. Purpose

The Building profile describes physical sites, buildings, levels, spaces,
lightweight structural elements, vertical connections, boundaries, openings
and relevant fixed or movable objects.

It supports both:

- territory around a building, including yard, parcel, fence and gate;
- internal floor plans with rooms, walls, doors, windows and fixtures;
- building sections with columns, slabs, roofs, stairs and shafts.

The profile is intentionally 2D-first with lightweight vertical metadata.

## 2. Recommended view kinds

```text
site-plan
floor-plan
roof-plan
elevation
section
detail
```

For normal house plans, physical coordinates in millimeters are recommended:

```xml
data-sema-coordinate-mode="physical"
data-sema-unit="mm"
```

## 3. Site hierarchy

A typical project can be understood as:

```text
site-main
|
+-- parcel-main
+-- yard-main
+-- fence-*
+-- gate-*
+-- building-main
    |
    +-- level-ground
    +-- level-first
    +-- level-attic
```

This hierarchy is semantic, not necessarily identical to SVG DOM nesting.

## 4. Site

A site represents the overall property context.

Example:

```xml
<polygon
    id="repr-site-main"
    data-sema-entity="site-main"
    data-sema-type="building:site"
    data-sema-state="existing"
    ...
/>
```

A site boundary should only be modeled when its geometry is known or intentionally approximate.

Do not invent a parcel shape merely to surround a building visually.

## 5. Parcel

A parcel represents a legal or project property area.

Example:

```xml
<polygon
    id="repr-parcel-main"
    data-sema-entity="parcel-main"
    data-sema-type="building:parcel"
    data-sema-state="existing"
    data-sema-certainty="measured"
    ...
/>
```

A parcel is not the same entity as a fence.

A fence may be offset from the parcel boundary.

## 6. Outdoor spaces

Exterior areas can be modeled as spaces.

Examples:

```text
yard
garden
driveway
terrace
patio
public-road
service-area
```

Example:

```xml
<polygon
    id="repr-yard-main"
    data-sema-entity="yard-main"
    data-sema-type="building:space"
    data-sema-space-kind="outdoor"
    data-sema-purpose="yard"
    data-sema-state="existing"
    ...
/>
```

Outdoor space is not a fake indoor room. The `data-sema-space-kind` distinguishes it.

`data-sema-space-kind` is the broad physical or topological class of a space, such as `room`, `corridor`, `outdoor`, `stairwell`, `shaft`, or `void`. `data-sema-purpose` records its functional use, such as `kitchen`, `laundry`, `terrace`, or `service-area`. A utility room is therefore `data-sema-space-kind="room"` with `data-sema-purpose="laundry"`; these values intentionally remain open rather than being profile enums.

## 7. Building

A building is a physical building entity.

In a site plan it is normally represented by its footprint:

```xml
<polygon
    id="repr-building-main-site"
    data-sema-entity="building-main"
    data-sema-type="building:building"
    data-sema-parent="site-main"
    ...
/>
```

The same `building-main` entity is the parent of floor levels in floor-plan views.

## 8. Levels

A level represents a floor or vertically distinct building plane.

Examples:

```text
level-basement
level-ground
level-first
level-attic
level-roof
```

A level SHOULD declare elevation when known:

```xml
<g
    id="repr-level-ground"
    data-sema-entity="level-ground"
    data-sema-type="building:level"
    data-sema-parent="building-main"
    data-sema-elevation-mm="0"
>
    ...
</g>
```

Optional attributes:

```text
data-sema-elevation-mm
data-sema-floor-height-mm
data-sema-ceiling-height-mm
```

### 8.1 Multiple levels

The profile supports multiple levels from the beginning.

For editing, separate SVG files per physical level are recommended when the plans are substantial:

```text
site.svg
ground-floor.svg
first-floor.svg
attic.svg
```

Each file references the same building entity and its own level entity.

This is usually easier than stacking all floors visually in one Inkscape document.

### 8.2 Vertical connections

Connections between levels should be explicit when relevant.

Examples:

```text
stair
ramp
elevator
ladder
shaft
vertical-passage
```

A stair, ramp, elevator or ladder is represented as:

```text
data-sema-type="building:vertical-connection"
data-sema-vertical-connection-kind
data-sema-connects-levels
```

Recommended kinds are `stair`, `ramp`, `elevator` and `ladder`. A vertical
connection SHOULD reference every level that it serves:

```xml
data-sema-connects-levels="level-ground level-first"
```

A shaft is normally a `building:space` with `data-sema-space-kind="shaft"` or
`void`, because it describes a volume rather than a means of circulation. An
electrical cable changing floor is handled by the Electrical profile, but may
reference that building space.

A vertical passage through a slab is a `building:opening` with
`data-sema-opening-kind="passage"`, the slab as `data-sema-host`, and the
served levels in `data-sema-connects-levels`. It is not a stair unless a
separate vertical-connection entity establishes circulation.

## 9. Spaces

Rooms, corridors, storage areas and exterior usable areas are modeled as `space` entities.

Core attributes:

```text
data-sema-type="building:space"
data-sema-space-kind
data-sema-purpose
data-sema-name
```

`data-sema-name` is a human-readable name. It is presentation-independent but
MUST NOT be used as entity identity; `data-sema-entity` remains authoritative.

Recommended `data-sema-space-kind` values:

```text
room
corridor
outdoor
stairwell
shaft
void
```

`data-sema-purpose` may be more specific:

```text
bedroom
kitchen
guest-room
bathroom
storage
laundry
yard
terrace
garden
public-road
pedestrian-path
service-area
```

### 9.1 Space geometry

A space geometry represents usable floor area, normally bounded by finished internal wall surfaces.

For rectangular spaces, prefer `<rect>`.

For polygonal spaces, prefer `<polygon>`.

Use `<path>` only when necessary.

### 9.2 Space area

Geometry is authoritative.

A source or cached area MAY be stored:

```xml
data-sema-area-m2="12.01"
```

A validator SHOULD warn when it differs materially from computed geometry.

### 9.3 Space overlap

Ordinary usable spaces SHOULD NOT overlap unintentionally.

Constraint overlays should use `zone`, not overlapping fake rooms.

## 10. Zones

A zone is an overlay representing a planning or engineering region.

Examples:

```text
wet
no-drill
clearance
preferred-route
prohibited-route
worktop
service
```

Example:

```xml
<polygon
    id="repr-zone-bathroom-wet"
    data-sema-entity="zone-bathroom-wet"
    data-sema-type="building:zone"
    data-sema-zone-kind="wet"
    data-sema-space="room-bathroom"
    ...
/>
```

Zones may intentionally overlap spaces, walls and other zones.

## 11. Structural elements

The lightweight Building profile defines three directly useful structural
objects without attempting structural analysis:

```text
building:column
building:slab
building:roof
```

A column is an isolated vertical support and a physical planning obstacle. A
slab is a horizontal floor or roof-supporting element that may host a
penetration. A roof represents the building covering or a separately useful
roof plane.

These entities SHOULD use physical geometry and `data-sema-z-min-mm` and
`data-sema-z-max-mm` when their vertical extent is known. A roof may use the
open token `data-sema-roof-kind`; useful values include `flat`, `pitched`,
`gable`, `hip` and `shed`.

Load capacity, reinforcement, structural material models and engineering
verification are outside this profile and belong in a future Structural
profile.

## 12. Walls

Walls are physical objects independent from spaces.

A shared wall MUST NOT be duplicated once for each neighboring room merely to express ownership.

Walls SHOULD normally be represented as geometry with real thickness:

```xml
<rect
    id="repr-wall-bedroom-east"
    data-sema-entity="wall-bedroom-east"
    data-sema-type="building:wall"
    data-sema-state="existing"
    data-sema-z-min-mm="0"
    data-sema-z-max-mm="2700"
    ...
/>
```

Optional wall classification uses:

```text
data-sema-wall-kind
```

Recommended values include `exterior`, `interior`, `retaining` and
`freestanding`. This classification is useful in partial views where adjacency
cannot be derived, but geometry remains authoritative when they conflict.

A floor plan that presents a complete building SHOULD represent its exterior
wall shell with semantic wall entities. A visible space outline MUST NOT be
treated as a substitute for an exterior wall. Partial plans MAY omit parts of
the shell when their scope or incompleteness is explicit.

Preferred primitives:

```text
rect
polygon
```

### 12.1 Wall segmentation

One continuous masonry wall MAY be split into semantic wall segments when useful for:

- different neighboring spaces;
- different construction properties;
- routing references;
- renovation work;
- openings or transitions.

A semantic split does not imply a construction joint.

### 12.2 Wall adjacency

Wall-to-space adjacency should normally be derived from geometry.

The profile deliberately does not require duplicated `adjacent rooms` metadata.

A derived adjacency cache may exist, but it is non-authoritative.

## 13. Fences and boundaries

A fence is a physical boundary element:

```xml
<polyline
    id="repr-fence-east"
    data-sema-entity="fence-east"
    data-sema-type="building:fence"
    data-sema-parent="site-main"
    ...
/>
```

A property/parcel boundary is represented by the parcel geometry, not by the fence entity.

## 14. Openings

Doors, windows, passages and gates are modeled as `opening` entities.

Specific kind is stored in:

```text
data-sema-opening-kind
```

SemaSVG Building 0.1.0 defines these kinds:

```text
door
window
passage
gate
```

`data-sema-opening-kind` MUST use one of these values.

An opening may also declare:

```text
data-sema-opening-operation
data-sema-traversable
data-sema-swing-space
```

Recommended `data-sema-opening-operation` values include `fixed`, `hinged`,
`sliding`, `folding`, `revolving`, `tilt` and `tilt-turn`. The token vocabulary
is open because real products use additional mechanisms.

`data-sema-traversable` states whether the opening is intended for ordinary
human passage when normally operated. It does not describe a temporary lock or
open/closed state. Missing traversability means unknown.

`data-sema-connects` identifies spaces or regions on opposite sides of the
opening. Connectivity alone MUST NOT be interpreted as human traversability: a
window may connect a room and an outdoor space while remaining non-traversable.

For a swinging leaf or sash, `data-sema-swing-space` references the space that
the moving element occupies when open. This provides an unambiguous semantic
direction without viewpoint-dependent `left` or `right` terminology.

Example:

```xml
<rect
    id="repr-opening-bedroom-door"
    data-sema-entity="opening-bedroom-door"
    data-sema-type="building:opening"
    data-sema-opening-kind="door"
    data-sema-opening-operation="hinged"
    data-sema-host="wall-bedroom-corridor"
    data-sema-connects="room-bedroom space-corridor"
    data-sema-traversable="true"
    data-sema-swing-space="room-bedroom"
    data-sema-z-min-mm="0"
    data-sema-z-max-mm="2100"
    ...
/>
```

### 14.1 Semantic subtraction

An opening MAY geometrically overlap its host wall.

The wall does not have to be boolean-cut into complicated SVG geometry.

For semantic reasoning, the opening removes or traverses the relevant host region within the opening's vertical range.

This convention keeps manual editing robust.

### 14.2 Window example

A window uses the same opening model. Its vertical minimum and maximum are the
sill and head elevations, so separate cached height attributes are unnecessary:

```xml
<rect
    id="repr-window-kitchen-north"
    data-sema-entity="window-kitchen-north"
    data-sema-type="building:opening"
    data-sema-opening-kind="window"
    data-sema-opening-operation="tilt-turn"
    data-sema-host="wall-exterior-north"
    data-sema-connects="room-kitchen yard-main"
    data-sema-traversable="false"
    data-sema-swing-space="room-kitchen"
    data-sema-z-min-mm="1000"
    data-sema-z-max-mm="2100"
    ...
/>
```

### 14.3 Gate example

A gate in a fence follows the same model:

```xml
<rect
    id="repr-gate-main"
    data-sema-entity="gate-main"
    data-sema-type="building:opening"
    data-sema-opening-kind="gate"
    data-sema-opening-operation="sliding"
    data-sema-host="fence-front"
    data-sema-connects="yard-main space-public-road"
    data-sema-traversable="true"
    ...
/>
```

This is how the profile supports a yard and entrance gate without creating a separate special format.

## 15. Opening direction and exact leaf geometry

Door leaves, window sashes and swing arcs are optional geometry.

`data-sema-swing-space` is the authoritative 0.1 semantic statement about the
side into which a hinged or tilting element moves. Producers SHOULD provide it
when the direction is known and materially affects planning.

SemaSVG 0.1.0 does not standardize `left` or `right` handedness because the
current model has no opening-local directed axis or observer viewpoint. Exact
leaf and clearance geometry MAY be added when known, but producers MUST NOT
invent handedness from appearance alone.

## 16. Vertical dimensions

The profile is primarily XY plus lightweight Z.

Physical objects may use:

```text
data-sema-z-min-mm
data-sema-z-max-mm
```

Values are relative to the finished floor of the containing level unless
documented otherwise. A physical view containing objects that span levels MAY
declare a shared level datum on its root:

```xml
data-sema-z-datum="level-ground"
```

The referenced level's finished-floor elevation is Z zero for the view. This is
appropriate for sections and elevations; producers MUST NOT mix local-level and
shared-datum Z values without documenting which convention applies.

Point-mounted objects may use:

```text
data-sema-z-mm
data-sema-z-reference
```

Recommended `data-sema-z-reference` values:

```text
center
bottom
top
```

## 17. Fixtures

Fixed building-related equipment may use:

```text
data-sema-type="building:fixture"
data-sema-fixture-kind
```

`building:fixture` is the generic Building classification. In a Building-only project it may validly classify a water
heater. When the Electrical profile is also active and the water heater is electrically relevant, prefer one
`electrical:appliance` entity with `data-sema-appliance-kind="water-heater"`. Keep that entity ID and type in both
floor-plan and schematic representations, and add compatible Building space or host relationships as needed. Do not
apply both types or change type by view. This is modeling guidance; type-specific applicability remains open.

Examples:

```text
sink
toilet
bath
shower
water-heater
kitchen-unit
worktop
```

Example:

```xml
<rect
    id="repr-fixture-kitchen-sink"
    data-sema-entity="fixture-kitchen-sink"
    data-sema-type="building:fixture"
    data-sema-fixture-kind="sink"
    data-sema-space="room-kitchen"
    ...
/>
```

## 18. Furniture

Furniture SHOULD be semantic when its geometry materially affects planning.

Typical examples include:

```text
bed
wardrobe
desk
cabinet
sofa
tv-stand
table
```

Example:

```xml
<rect
    id="repr-furniture-bedroom-bed"
    data-sema-entity="furniture-bedroom-bed"
    data-sema-type="building:furniture"
    data-sema-furniture-kind="bed"
    data-sema-space="room-bedroom"
    data-sema-state="existing"
    ...
/>
```

Useful planning questions include:

- will a socket become inaccessible behind a wardrobe?
- are workstation outlets located near the desk?
- does furniture obstruct a proposed route or service point?
- is an electrical appliance associated with the space where it is actually used?

Furniture geometry is not automatically a structural obstacle. A domain-specific planner decides which furniture is fixed, movable, ignorable or relevant to a particular analysis.

Movable furniture MAY be omitted when it has no planning relevance.

## 19. Generic space and host relationships

The profile defines two important relationships.

### 19.1 Functional space

```xml
data-sema-space="room-kitchen"
```

This identifies the space where an object is located, used or accessible.

### 19.2 Physical host

```xml
data-sema-host="wall-kitchen-east"
```

This identifies the physical element hosting another object.

A wall-mounted electrical socket may legitimately have both relationships.

This resolves shared-wall ambiguity cleanly.

## 20. Site-plan validation

A Building-profile validator SHOULD be able to warn about:

- overlapping normal spaces;
- invalid room polygons;
- openings far from their declared hosts;
- space objects extending materially through walls without explanation;
- gates not intersecting their host fence;
- levels missing a building parent;
- vertical connections referencing fewer than two levels;
- slab passages missing their slab host or connected levels;
- inconsistent elevation data;
- cached areas differing from geometric areas.

Geometric tolerances must be configurable.
