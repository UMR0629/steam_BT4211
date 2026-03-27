# Steam Tag Taxonomy Draft

This draft taxonomy is built from `positioning_output/tag_stats.csv` and is intended for positioning analysis rather than storefront browsing.

## Design Principles

- Separate **gameplay**, **mode**, **theme**, **tone**, **presentation**, and **commercial/access** signals.
- Keep highly discriminative tags distinct when they encode clear market identity.
- Treat broad tags like `Action`, `Adventure`, `Indie`, `RPG`, `Strategy`, `Simulation`, `Casual`, `Singleplayer`, and `Multiplayer` as support metadata rather than core positioning anchors.
- Allow one tag to have a **primary home** only, to keep the system stable and easy to model.

## Dimensions

### 1. Core Gameplay
Tags that primarily describe what the player repeatedly does.

Buckets:
- `Combat Action`: `Shooter`, `FPS`, `Third-Person Shooter`, `Hack and Slash`, `Combat`, `Stealth`
- `RPG Systems`: `Action RPG`, `JRPG`, `Dungeon Crawler`, `Character Customization`
- `Strategy & Tactics`: `Tactical`, `Turn-Based Strategy`, `Turn-Based Tactics`, `RTS`, `Management`, `Resource Management`
- `Building & Simulation Systems`: `Sandbox`, `Building`, `Base-Building`, `Crafting`, `Economy`
- `Puzzle & Logic`: `Puzzle`, `Physics`, `Point & Click`
- `Platforming & Traversal`: `Platformer`, `2D Platformer`, `Exploration`, `Open World`
- `Arcade & Reflex`: `Arcade`, `Racing`, `Sports`
- `Roguelite Loop`: `Rogue-like`, `Rogue-lite`, `Procedural Generation`, `Replay Value`
- `Narrative Play`: `Visual Novel`, `Interactive Fiction`, `Choose Your Own Adventure`, `Choices Matter`, `Multiple Endings`

### 2. Mode & Social Structure
Tags that describe who you play with and how sessions are structured socially.

Buckets:
- `Solo`: `Singleplayer`
- `Online Cooperative`: `Co-op`, `Online Co-Op`, `PvE`
- `Local Social`: `Local Co-Op`, `Local Multiplayer`
- `Competitive Multiplayer`: `PvP`, `Massively Multiplayer`
- `Access / Ongoing Service`: `Early Access`, `Free to Play`

### 3. Theme & Setting
Tags that describe fictional world, subject matter, or setting.

Buckets:
- `Fantasy`: `Fantasy`, `Dark Fantasy`, `Magic`, `Medieval`
- `Science Fiction`: `Sci-fi`, `Space`, `Futuristic`
- `War & Military`: `War`, `Military`, `Historical`
- `Horror & Threat`: `Horror`, `Psychological Horror`, `Survival Horror`, `Zombies`, `Post-apocalyptic`
- `Everyday / Life / Family`: `Family Friendly`
- `Mature / Sexual`: `Sexual Content`, `Nudity`, `Mature`, `Violent`, `Gore`

### 4. Tone & Emotional Experience
Tags that describe the emotional promise or experiential feel of the game.

Buckets:
- `Immersive & Moody`: `Atmospheric`, `Dark`, `Mystery`, `Drama`, `Emotional`
- `Narrative Prestige`: `Story Rich`, `Great Soundtrack`
- `Light & Playful`: `Funny`, `Comedy`, `Cute`, `Colorful`, `Cartoony`
- `Comfort & Low Stress`: `Relaxing`, `Family Friendly`
- `Challenge & Intensity`: `Difficult`, `Survival`
- `Romantic / Character Drama`: `Romance`, `Female Protagonist`

### 5. Presentation & Camera
Tags that describe how the game looks or is spatially framed.

Buckets:
- `2D Visual Identity`: `2D`, `Pixel Graphics`, `Hand-drawn`, `Retro`, `Old School`, `1990's`
- `3D Visual Identity`: `3D`, `Stylized`, `Realistic`
- `Camera Perspective`: `First-Person`, `Third Person`, `Top-Down`, `Isometric`
- `Art Style / Cultural Coding`: `Anime`
- `Interface / Input`: `Controller`, `VR`

### 6. Structure & Progression
Tags that describe pacing, run structure, or content organization.

Buckets:
- `Open / Exploratory Structure`: `Open World`, `Exploration`, `Sandbox`
- `Linear / Authored Structure`: `Linear`, `Story Rich`
- `Systemic / Moddable Structure`: `Moddable`, `Immersive Sim`
- `Session Replayability`: `Replay Value`, `Procedural Generation`

## Recommended Handling Rules

### Treat as generic support tags
These are useful as coarse metadata, but they are too broad to carry positioning on their own:

- `Action`
- `Adventure`
- `Indie`
- `Casual`
- `RPG`
- `Strategy`
- `Simulation`
- `Singleplayer`
- `Multiplayer`

### Keep distinct because they are market-signaling
These tags are worth preserving as separate signals even if they could be merged:

- `Open World`
- `Story Rich`
- `Visual Novel`
- `JRPG`
- `Action RPG`
- `FPS`
- `Third-Person Shooter`
- `Survival Horror`
- `Psychological Horror`
- `Rogue-like`
- `Rogue-lite`
- `Turn-Based Strategy`
- `Turn-Based Tactics`
- `VR`
- `Anime`
- `Free to Play`
- `Early Access`

### Candidate merge pairs or families
These are good candidates for later normalization if you want a more compact taxonomy:

- `Funny` + `Comedy`
- `Rogue-like` + `Rogue-lite` (only if you want a coarser gameplay layer)
- `Horror` + `Psychological Horror` + `Survival Horror` into a higher-order horror family
- `Sci-fi` + `Space` + `Futuristic`
- `War` + `Military`
- `Building` + `Base-Building`
- `Co-op` + `Online Co-Op` into a broader co-op family with subtypes

## Suggested Use In Positioning

### Content Positioning Map
Use primarily:

- `Core Gameplay`
- `Theme & Setting`
- `Tone & Emotional Experience`
- `Presentation & Camera`

### Commercial / Market Positioning Map
Use taxonomy outputs together with:

- `owners_bucket`
- `price_usd`
- `is_free`
- `positive_ratio`
- `review_count`
- `release_age_days`

## Next Revision Targets

These tags should be reviewed manually because they are common but semantically slippery:

- `Exploration`
- `Atmospheric`
- `Realistic`
- `Cute`
- `Colorful`
- `Female Protagonist`
- `Controller`
- `Family Friendly`
- `Combat`
- `Survival`
