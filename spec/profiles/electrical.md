# Electrical Profile

Profile ID: `electrical@0.1.0`

Depends on: SemaSVG Core 0.1.0

May be combined with: Building profile 0.1.0

## Type namespace

All types defined by this profile use the `electrical:` prefix.

Examples:

```text
electrical:panel
electrical:supply
electrical:circuit
electrical:device
electrical:socket
electrical:protective-device
electrical:terminal
electrical:conductor
electrical:cable
```

The view MUST declare `electrical@0.1.0` in `data-sema-profiles`.

## 1. Purpose

The Electrical profile describes sources, logical electrical systems, cables
and physical representations of electrical equipment.

It supports several very different views without treating them as different universes:

- electrical devices on a house floor plan;
- physical cable routes through the building;
- detailed physical layout of an electrical panel;
- diagrammatic electrical schematic;
- logical circuit overview.

The same entity IDs connect those views.

## 2. Core distinction: logical versus physical

A circuit is not a cable route.

A panel is not its rectangle on the floor plan.

A protective device is not its schematic symbol.

The profile explicitly separates:

```text
entity identity
logical relationship
physical placement
view-specific representation
```

## 3. Recommended view kinds

```text
floor-plan
equipment-layout
schematic
system-overview
detail
```

A view kind describes purpose, while `data-sema-coordinate-mode` determines
whether its coordinates carry physical measurements. In particular, an
`equipment-layout` is physical when coordinates and dimensions describe
verified placement. It MAY be diagrammatic when it communicates organization or
a proposed arrangement without asserting physical dimensions.

### 3.1 Physical views

Examples of physical views:

```text
floor-plan
equipment-layout with verified positions and dimensions
```

Use:

```xml
data-sema-coordinate-mode="physical"
data-sema-unit="mm"
```

### 3.2 Diagrammatic views

Examples:

```text
schematic
system-overview
equipment-layout without verified positions and dimensions
```

Use:

```xml
data-sema-coordinate-mode="diagrammatic"
```

Visual spacing in such views MUST NOT be interpreted as cable length or physical distance.

## 4. Electrical system

An electrical system may be represented by:

```xml
<g
    id="repr-system-electrical"
    data-sema-entity="system-electrical"
    data-sema-type="electrical:system"
    data-sema-state="existing"
>
    ...
</g>
```

### 4.1 Electrical supply

An upstream utility connection or local source uses:

```text
data-sema-type="electrical:supply"
data-sema-supply-kind
```

Recommended supply kinds include `utility`, `generator`, `inverter` and
`battery`. Useful known properties include voltage, frequency and phase count:

```xml
<g
    data-sema-entity="supply-main"
    data-sema-type="electrical:supply"
    data-sema-supply-kind="utility"
    data-sema-voltage-v="230"
    data-sema-frequency-hz="50"
    data-sema-phases="1"
    ...
/>
```

A supply is not the same entity as a panel, meter, isolator or outgoing final
circuit. Conductors and devices make that topology explicit.

## 5. Electrical panel

A panel entity represents the real panel, regardless of view.

Example on a floor plan:

```xml
<rect
    id="repr-panel-main-floor"
    data-sema-entity="panel-main"
    data-sema-type="electrical:panel"
    data-sema-state="existing"
    ...
/>
```

The same entity in an equipment-layout view:

```xml
<g
    id="repr-panel-main-layout"
    data-sema-entity="panel-main"
    data-sema-type="electrical:panel"
>
    ...
</g>
```

Recommended panel attributes when known:

```text
data-sema-phases
data-sema-voltage-v
data-sema-input-limit-a
data-sema-enclosure-model
data-sema-module-capacity
```

Devices or terminals mounted on a DIN rail may declare:

```text
data-sema-rail
data-sema-slot-start
data-sema-module-count
```

Slots are one-based positions within the referenced rail. These attributes
describe intended organization even in a diagrammatic layout; SVG dimensions
remain non-physical unless the view itself is physical.

## 6. Electrical circuit

A logical circuit uses:

```text
data-sema-type="electrical:circuit"
```

Example:

```xml
<g
    id="repr-circuit-hob-overview"
    data-sema-entity="circuit-hob"
    data-sema-type="electrical:circuit"
    data-sema-state="planned"
    data-sema-origin="panel-main"
    data-sema-voltage-v="230"
    data-sema-conductor-mm2="6"
>
    ...
</g>
```

Recommended optional attributes:

```text
data-sema-origin
data-sema-circuit-kind
data-sema-voltage-v
data-sema-phase
data-sema-conductor-mm2
data-sema-conductor-count
data-sema-cable-description
data-sema-protection-a
data-sema-breaker-curve
data-sema-rcd-type
data-sema-residual-current-ma
data-sema-purpose
```

Recommended circuit kinds include `feeder`, `final` and `control`.
`data-sema-phase` identifies an assigned phase such as `L1`, `L2` or `L3` for a
single-phase circuit. A multi-phase circuit uses `data-sema-phases` instead of
pretending that it belongs to one phase.

These fields describe design intent. They do not prove regulatory compliance.
`data-sema-conductor-mm2` describes the intended conductor cross-section of the
circuit. A represented conductor uses `data-sema-cross-section-mm2` for its own
cross-section.

## 7. Circuit membership

A device supplied by a circuit SHOULD reference the circuit entity:

```xml
data-sema-circuit="circuit-hob"
```

## 8. Electrical devices

The profile defines specialized semantic types because direct queries such as "find all sockets" are useful.

Conventional plan symbols are recommended for human readability, but their
strokes are presentation rather than semantics. When a symbol needs several
SVG primitives, place the semantic attributes on one containing `<g>` and keep
its child geometry non-semantic. Consumers MUST use `data-sema-type`, not shape
recognition, as the authoritative classification.

Recommended types include:

```text
device
socket
switch
light
junction-box
appliance
panel
protective-device
busbar
din-rail
terminal
connection-point
```

### 8.1 Socket

Example:

```xml
<g
    id="repr-socket-kitchen-01"
    data-sema-entity="socket-kitchen-01"
    data-sema-type="electrical:socket"
    data-sema-space="room-kitchen"
    data-sema-host="wall-kitchen-east"
    data-sema-circuit="circuit-kitchen-worktop-a"
    data-sema-z-mm="1100"
    data-sema-z-reference="center"
    data-sema-state="planned"
    transform="translate(5200 1750)"
>
    <circle cx="0" cy="0" r="90"/>
    <path d="M-45 -35 L45 -35 M-45 35 L45 35"/>
</g>
```

Useful optional attributes:

```text
data-sema-purpose
data-sema-ip-rating
data-sema-dedicated-line
data-sema-z-mm
data-sema-z-reference
```

### 8.2 Switch

Example:

```xml
<g
    id="repr-switch-bedroom-main"
    data-sema-entity="switch-bedroom-main"
    data-sema-type="electrical:switch"
    data-sema-space="room-bedroom"
    data-sema-host="wall-bedroom-corridor"
    data-sema-controls-entities="light-bedroom-main"
    transform="translate(2450 3550)"
>
    <circle cx="0" cy="0" r="65"/>
    <path d="M35 -35 L125 -125"/>
</g>
```

### 8.3 Light

Example:

```xml
<g
    id="repr-light-bedroom-main"
    data-sema-entity="light-bedroom-main"
    data-sema-type="electrical:light"
    data-sema-space="room-bedroom"
    data-sema-circuit="circuit-lighting-l1"
    transform="translate(3050 2550)"
>
    <circle cx="0" cy="0" r="110"/>
    <path d="M-75 -75 L75 75 M75 -75 L-75 75"/>
</g>
```

### 8.4 Appliance

Electrically important equipment should be explicit:

```xml
<rect
    id="repr-appliance-hob-floor"
    data-sema-entity="appliance-hob"
    data-sema-type="electrical:appliance"
    data-sema-appliance-kind="hob"
    data-sema-manufacturer="Bosch"
    data-sema-model="PID631BB5E"
    data-sema-power-w="7400"
    data-sema-space="room-kitchen"
    data-sema-circuit="circuit-hob"
    data-sema-dedicated-line="true"
    ...
/>
```

When Building and Electrical are both active, an electrically relevant water heater should normally be one
`electrical:appliance` entity with `data-sema-appliance-kind="water-heater"`, represented with the same entity ID and
type in a floor plan and schematic. Add compatible Building space or host relationships when useful. Do not apply
`building:fixture` as a second type or change type by view. A Building-only project may instead use the generic
`building:fixture` classification. This is modeling guidance, not a new validator rule or a general cross-profile
precedence mechanism.

For example, two representations of one water heater retain its entity type:

```xml
<rect
    id="repr-appliance-water-heater-floor"
    data-sema-entity="appliance-water-heater"
    data-sema-type="electrical:appliance"
    data-sema-appliance-kind="water-heater"
    data-sema-space="room-utility"
    data-sema-circuit="circuit-water-heater"
    ...
/>
```

```xml
<g
    id="repr-appliance-water-heater-schematic"
    data-sema-entity="appliance-water-heater"
    data-sema-type="electrical:appliance"
    data-sema-appliance-kind="water-heater"
    data-sema-circuit="circuit-water-heater"
>
    ...
</g>
```

### 8.5 Other electrical devices

Equipment without a more specific Electrical type uses:

```text
data-sema-type="electrical:device"
data-sema-device-kind
```

Typical kinds include `energy-meter`, `main-isolator`, `contactor`, `relay`,
`timer`, `transformer`, `power-supply`, `transfer-switch` and `monitor`.
Producers SHOULD prefer a specialized type such as `socket`, `light` or
`protective-device` when one matches. A meter or isolator MUST NOT be mislabeled
as a protective device merely because it is mounted in the same panel.

## 9. Ports and terminals

A `terminal` or `connection-point` is a first-class connection endpoint.

This is intentionally close to the Core concept of a port and is useful across physical and schematic views.

Example:

```xml
<circle
    id="repr-terminal-rcbo-hob-l-out"
    data-sema-entity="terminal-rcbo-hob-l-out"
    data-sema-type="electrical:terminal"
    data-sema-parent="rcbo-hob"
    data-sema-terminal-kind="power"
    data-sema-conductor-kind="L"
    data-sema-direction="out"
    ...
/>
```

Recommended conductor kinds:

```text
L
N
PE
L1
L2
L3
control
signal
```

The vocabulary may be extended.

## 10. Protective devices

Use:

```text
data-sema-type="electrical:protective-device"
```

with:

```text
data-sema-device-kind
```

Recommended kinds:

```text
mcb
rcd
rcbo
fuse
surge-protection
```

Example:

```xml
<g
    id="repr-rcbo-hob-layout"
    data-sema-entity="rcbo-hob"
    data-sema-type="electrical:protective-device"
    data-sema-device-kind="rcbo"
    data-sema-parent="panel-main"
    data-sema-rated-current-a="32"
    data-sema-breaker-curve="C"
    data-sema-rcd-type="A"
    data-sema-residual-current-ma="30"
    data-sema-poles="1P+N"
>
    ...
</g>
```

If the exact device is not selected, physical width/module count MUST NOT be presented as verified fact.

## 11. DIN rails

A physical panel-layout view may model rails:

```xml
<rect
    id="repr-din-rail-1"
    data-sema-entity="din-rail-1"
    data-sema-type="electrical:din-rail"
    data-sema-parent="panel-main"
    ...
/>
```

DIN rails are physical layout objects, not logical circuits.

## 12. Busbars

Busbars use:

```text
data-sema-type="electrical:busbar"
```

Useful kinds:

```text
phase
neutral
protective-earth
comb
```

Example:

```xml
<rect
    id="repr-busbar-pe"
    data-sema-entity="busbar-pe"
    data-sema-type="electrical:busbar"
    data-sema-busbar-kind="protective-earth"
    data-sema-parent="panel-main"
    ...
/>
```

## 13. Connections and conductors

A logical or physical conductor connection may use:

```text
data-sema-type="electrical:conductor"
```

and should reference endpoint entities:

```xml
data-sema-from="terminal-rcbo-hob-l-out"
data-sema-to="connection-hob-l"
```

Useful attributes:

```text
data-sema-conductor-kind
data-sema-cross-section-mm2
data-sema-color
data-sema-circuit
```

`data-sema-cross-section-mm2` belongs to the represented conductor;
`data-sema-conductor-mm2` on a circuit is circuit-level design intent.

Do not infer electrical function solely from rendered line color.

### 13.1 Multi-conductor cables

A physical cable containing one or more conductors uses:

```text
data-sema-type="electrical:cable"
```

Useful attributes include:

```text
data-sema-from
data-sema-to
data-sema-circuit
data-sema-core-count
data-sema-core-cross-section-mm2
data-sema-cable-description
```

`data-sema-core-cross-section-mm2` is the nominal cross-section of each
current-carrying core when the cable uses one uniform size. Mixed-core cables
SHOULD describe their construction in `data-sema-cable-description` rather
than fabricate one value. Individually modeled `electrical:conductor` entities
may use the cable as their parent.

A cable is the physical assembly. A conductor is an electrical connection or
individual core. A route segment is the cable's placement through space. These
three concepts MUST NOT be conflated.

## 14. Physical cable routes

A logical circuit and physical route are separate.

Physical route segments use:

```text
data-sema-type="electrical:route-segment"
```

Example:

```xml
<polyline
    id="repr-route-hob-01"
    data-sema-entity="route-hob-01"
    data-sema-type="electrical:route-segment"
    data-sema-system="system-electrical"
    data-sema-circuit="circuit-hob"
    data-sema-cable="cable-hob"
    data-sema-from="panel-main"
    data-sema-to="route-node-hob-rise-01"
    data-sema-installation="surface-channel"
    data-sema-z-mm="2300"
    data-sema-route-length-mm="8420"
    ...
/>
```

### 14.1 No teleporting

A physical route MUST be geometrically continuous.

A route MUST NOT jump across a wall, door, floor or other obstacle without an explicit continuation or transition.

### 14.2 Route segmentation

A route SHOULD be split when one of the following changes materially:

- host wall/pathway;
- space;
- level;
- elevation;
- installation method;
- cable/pathway ownership;
- semantic endpoint.

Every physical route segment MUST reference its cable with `data-sema-cable`. Logical-only relationships do not create
route segments. A cable's declared route graph MUST be continuous and nonbranching; model a physical branch as a
separate cable entity. Several cables may share an `electrical:pathway` while remaining separate cable entities.

Use the existing singular `data-sema-host` to reference a pathway only when the whole route segment is hosted by that
pathway. Split a route where it enters or leaves a pathway, rather than assigning a pathway host to a partially hosted
segment.

Ordinary geometric bends do not need separate semantic nodes.

### 14.3 Route nodes

Important transitions may use:

```text
data-sema-type="electrical:route-node"
```

Recommended `data-sema-node-kind` values:

```text
junction
vertical-transition
level-transition
shaft-entry
shaft-exit
```

### 14.4 Pathways

Shared physical infrastructure such as conduit or cable channel may use:

```text
data-sema-type="electrical:pathway"
data-sema-pathway-kind
```

with kinds such as:

```text
conduit
surface-channel
cable-tray
shaft
```

Several circuits may reference the same pathway without pretending their logical circuits are the same.

### 14.5 Penetrations

A deliberate pass-through in a wall or slab may be represented by:

```text
data-sema-type="electrical:penetration"
```

Example:

```xml
<circle
    id="repr-penetration-kitchen-01"
    data-sema-entity="penetration-kitchen-01"
    data-sema-type="electrical:penetration"
    data-sema-host="wall-kitchen-corridor"
    data-sema-system="system-electrical"
    ...
/>
```

This gives an agent a way to distinguish a designed wall crossing from an accidental route collision.

## 15. Equipment-layout view of a panel

A physical panel layout should model:

```text
enclosure
DIN rails
protective devices
other panel devices
busbars
terminals
rail slots and module counts
physical positions
```

In 0.1 the `electrical:panel` representation is also the enclosure boundary;
`data-sema-enclosure-model` identifies the enclosure when known. A separate
enclosure entity is unnecessary unless a future profile establishes an
independent lifecycle or containment contract for it.

Only use millimeter-accurate device widths when the actual hardware or verified module width is known.

Otherwise mark the representation as proposed/estimated or use a diagrammatic
equipment layout. In diagrammatic mode, positions and dimensions are
presentation and MUST NOT be interpreted as physical facts.

## 16. Schematic view of a panel

A schematic is diagrammatic:

```xml
data-sema-view-kind="schematic"
data-sema-coordinate-mode="diagrammatic"
```

It should emphasize:

```text
source
protective devices
terminals
circuits
connections
```

Do not treat diagram coordinates as physical placement inside the panel.

## 17. Same panel across views

Example identity mapping:

```text
panel-main
|
+-- house floor-plan representation
+-- equipment-layout representation
+-- schematic representation
```

The repeated `data-sema-entity="panel-main"` is what makes these one entity.

Likewise, `rcbo-hob` may appear in both layout and schematic views.

## 18. Panel validation possibilities

A future validator can check, depending on available data:

- terminals referenced by conductors exist;
- devices belong to the declared panel;
- supplies, meters, isolators and panels form a connected incoming path;
- circuits originate at a valid panel/device;
- cable endpoints and referenced route segments are consistent;
- a conductor does not connect incompatible endpoint classes;
- panel physical representations do not overlap impossibly;
- rail slots do not overlap or exceed known module capacity;
- module widths fit a declared enclosure when widths are verified;
- schematic and layout contain the same selected protective-device entities;
- circuit metadata is consistent across views.

## 19. Building-profile integration

When combined with the Building profile, electrical devices may use:

```text
data-sema-space
data-sema-host
```

Example:

```xml
data-sema-space="room-kitchen"
data-sema-host="wall-kitchen-east"
```

A floor-plan representation can therefore state both where a device is used and what physical object hosts it.

Electrical physical routes and devices may use `data-sema-z-mm` and
`data-sema-z-reference` without activating the Building profile. When Building
is active, its finished-floor reference convention applies. Otherwise the
project MUST document the vertical reference used by those values.

## 20. Regulatory boundary

The profile can encode values such as conductor cross-section, breaker rating and RCD type, but it does not declare those values legally correct.

Code compliance depends on installation method, local rules, equipment characteristics and verified project details outside the SVG alone.
