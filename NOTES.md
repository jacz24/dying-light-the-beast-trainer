# Dying Light: The Beast — memory study (ESP and aimbot), notes for the next session

Last updated: 2026-11-08 (session 9). Start with "End of session 9"; the resume prompt is at the bottom. Read this file first. Everything below was measured in the game, not guessed, except where it says "guess".

## End of session 9 (2026-11-04 evening; the user's last message 2026-11-08): where to resume

- **Done, in the app:** NoClip (F3; the user: works) and flying (F2; the user: "It's all working!", but see open item 1). The teleports and the flight are in `movement.py` (a mixin). The F8 fall-through: the cause is found (see session 9); no fix, by the user's choice: NoClip and flying are the way out. The app now ends when the game ends.
- **Open, in this order:**
  1. **Flying and a game crash?** The log shows "flying on", then within about 10 s the game freed its memory (the scans read 9.4, 6.0, 1.7, 0 GB): a crash or a close. Ask the user. If a crash: fly again with a recorder of the position and both speeds.
  2. The ice cream truck markers (`lootstate.no_item()`): asked at the end of session 9; write the answer here.
  3. Loot after a long jump: no clean run yet (the user moved or jumped again each time).
  4. **Release on GitHub** (the user's wish: public, with the source, as a resume project and an open alternative to closed trainers). Done locally (session 9, 2026-11-08): a git repository on `main`; `README.md` (single-player only, the co-op note, unofficial, takedown on request), MIT `LICENSE`, `requirements.txt`, `.gitignore` (run data, `*.exe`); the cheat table and the dead-end data deleted; the research scripts in `research/`. The user's name for it: "Dying Light: The Beast Trainer" (repo name proposed: `dying-light-the-beast-trainer`, account `jacz24`). **Not pushed.** Open before the push: NOTES.md public or not, the commit email (public on GitHub), a release binary (PyInstaller, not installed yet).
  5. Hardening across game versions: field offsets inside objects are still constants (the self-checks catch a move, but do not find the new place). Candidates: code signatures per field (as for `playervars.GETTER`), or an automatic re-learn by behaviour.
  6. Optional: the light delay; aim at the head centre.

## Session 9 (2026-11-04, from 5 PM)

- **Split:** `movement.py` (a mixin, like `cheats.py`): `teleport_keys()`, `go()`, `go_waypoint()`, `long_jump()`, `flight()`. `overlay.py` 475 lines.
- **F8 falls (goal 1), `fallrec.py`** (now 20 s after a jump, runs 1 h): 8 long jumps of 449 to 1307 m.
  - The game holds the player still for about 1 s after a long jump (0.8 to 1.3 s; 0.25 s after a 44 m jump): its own wait for the area.
  - On open ground the ground was 0.2 to 0.4 m above the waypoint height 4 times (inside the 1 m margin), and once 3.65 m below it.
  - **Fall 1, a tall building** (the user set the waypoint on it): waypoint height 42.5, the player fell 50 m into water. A second teleport to the same point from 3.8 m away (area loaded) fell again: no surface under that point, so a higher arrival point cannot fix it.
  - **Fall 2, open ground**, 577 m jump, arrival 3.9: through the ground at about 160 m/s to -328, held there 3 s by the game, then on to -475; the next F8 got out. After it the player could not move (the user quit to the menu).
  - The user's choice: no F8 fix; NoClip and flying are the way out.
- **Loot after a long jump (goal 2): no clean run.** 831 m: at once 323 (old area still in memory), full scan at 10 s 268, at about 30 s 259 to 270, an independent full scan at 60 s 252 (the user moved 100 m). 727 m: at once 134, full scan at 10 s 390, rescan at 30 s 390 (then two more jumps).
- **Velocity (goal 4), `velfind.py`** (read-only, 45 s of walks and jumps) and `velprobe.py` (one write): in `CBulletPhysicsCharacter`
  - `+0x1328` the up speed, **the source**: a write of 8 in the air gave a second lift of 1.70 m (predicted 1.7); on the ground the game sets it to 0 each frame. Its x and z neighbours are always 0. `+0x1300`/`+0x1304`: the same one frame later.
  - `+0xfc4`/`+0xfcc` the level speed (`+0xfc8` always 0); equal to the rigid body's while walking.
  - btRigidBody (`+0x158`) `+0x2f0..+0x2f8` (x, up, z) in the same frame, `+0x3a0` a copy, `+0x3e4` gravity -9.81 or 0. `+0x3f8..+0x400`: a copy every third frame.
  - The player's gravity is about 18.4 m/s² (the up speed drops 0.185 m/s a frame at about 100 frames a second). The layout looks like a Bullet kinematic character controller.
  - Pitfall: the btRigidBody sat 0x400 bytes before a page that cannot be read; `velfind.py` reads up to `region_size()`.
- **NoClip (F3), the user: works.** Each frame: the held position moved by the keys along the view (`fly_step()`, with asserts), written to `+0xfd0`, both speeds 0. Dry run: 10.3 m/s along the view, 10 m/s up with Space, the same level direction as the walk. F8 and F10 move the held position too (`go()`).
- **Flying (F2).** Each frame only the speeds: level = (view direction x keys x speed), up the same; the physics moves the player, so walls should stop it (not confirmed). On the ground the game zeroes the up speed: Space (the game's jump) takes off. Dry run: all speeds right (10 m/s, 14.1 with a side key, 40 with Shift). Real run: see open item 1.
- The user's choices: F2 flying, F3 NoClip; W/S along the view, A/D level sideways, Space up, Ctrl down; 10 m/s, Shift x4. `python overlay.py --dry-fly`: both modes only print.
- **Self-check "noclip"** (11 checks now): the up speed's x and z neighbours are 0, and the level speed equals the rigid body's while the player walks (it waits for a walk, so two zeros cannot pass it).
- **App fix:** after the game closed, the app ran 16,151 empty full scans in 2.7 minutes. `mem.Process.running()` (`GetExitCodeProcess`); `tick()` ends the app when the game has ended. Tested on a short-lived process, not on the game.
- Keys now: F1 end, F2 flying, F3 NoClip, F6 overlay, F7 nuke, F8 waypoint, F9 mark, F10 to the mark, F11 aim. `velprobe.py` uses F12.

## End of session 8 (2026-11-04, about 5 AM): where to resume

- **Done, in the app:** version safety (vtables and player variables by name, the getter signature, a self-check per feature: all checks passed live); two false-loot fixes (loot never placed in the world, confirmed by the user; taken pickups that the game set back to state 1, not confirmed yet); the nuke on bandits (the user: it works; one-hit melee killed `Human_1h` and `Baron_Rifleman` too).
- **The app that runs at the end (started 04:37) has every session 8 change except the 30 s rescan** (built later, not run yet). The next start of `overlay.py` has it.
- **Open, in this order:**
  1. **F8 falls through the map** (the user, after long jumps). Each later F8 showed the same distance again (979 m x 11, 767 m x 11), so the game seems to put the player back at the last safe position after the fall. One reading at height -375. Two causes are possible: the waypoint height is below the ground (fix: a larger margin), or the ground of the new area is not loaded at the arrival (fix: hold the player in the air for a few seconds; the base of flying). Test first: `python fallrec.py` (read-only), one F8, no second press. The user asked for a higher arrival point; the arrival is now 1 m above the waypoint height.
  2. **Loot after a long jump:** re-test the 30 s rescan: one long F8, stand still for 1 minute, then compare the app's count with a full scan (`python rtti.py instances Container ComplexContainer BodyContainer CollectableObject`).
  3. Ask the user: are the 5 markers in the ice cream truck gone (`lootstate.no_item()`)?
  4. NoClip and flying (not started). `overlay.py` is at 500 lines: split first. Ask the user for the keys and the speed; find the velocity field first; dry run first.
  5. Optional: the light delay; aim at the head centre.

## End of session 7 (2026-11-04): where to resume

- **Done and confirmed by the user, all in the app:** cheats off at the end; super jump and speed sliders; always day / always night; immortality; one-hit melee; no fall damage; fast rescans; boxes on gunfire ambushers (AI heap grew to 80 MB); **the restart test passed** (open since session 2); **the Volatile aim** (head dots and aim on Volatiles: "great its working!").
- **Later in session 7, in the app ("it seems to be working pretty well"):** `overlay.py` split (480 lines; the cheats are in `cheats.py`, a mixin); **F8 / panel button = teleport to the map waypoint** (`waypoint.py`); **"Infinite fury"** switch (beast mode at any time, never ends). A crash after the first F8 is fixed (see below).
- **Still open:** the nuke on bandits (`Baron_Rifleman` seen, nuke not tried: blue boxes, the nuke kills them, never green NPCs); NoClip and flying (the user's "ultimate two": no game switch exists; plan: write the teleport source each frame); loot after a long teleport (a rescan 1 s after F8 found 121 loot objects, a full scan later 755: guess: the area had not streamed in yet; fix idea: one full scan about 10 s after a jump over 200 m); the light delay (optional).
- Optional: aim at the head centre, between `helper_head_bottom` and `helper_head_top` (Volatile: 0.06 m above the `head` bone). Not checked on human meshes.

## Session 8 (2026-11-04, from 4:00 AM)

- **Version safety (goal 1), in the app; `selfcheck.py` (new).**
  - **Player variables by name (1a):** `playervars.resolve_offsets()` at the start reads each variable's offset from the game's registration code (`names()`); `CHEATS` and `SCALED` hold names only. `check()` refuses a name that is missing (or found twice), and `apply()`/`scale()` check every variable of a cheat before the first write, so a refused cheat writes nothing (test with a fake write handle: 0 writes). This closes the unsafe case (the guard checked only the class).
  - **Vtables by class name (1b):** `rtti.resolve_vtables()` checks each constant by its class name (`selfcheck.CLASSES`, 19 classes); a moved one is found by name (`find_vtables()`), and `parse_addr()` then gives the found address (`rtti.FOUND`). Measured: a normal start 0.5 s (all 19 where they were); a simulated update (a constant moved by 0x10, and a constant that named another class) 6.8 s, both found again; `find_vtables()` alone 8.5 s for all 19. A class not found once by name stops the app.
  - **One code signature (the user's choice: the getter only):** `playervars.GETTER`, 1 hit at `gamedll+0x126fd40`, gives the PlayerState global (`+0x3921830`) and the array field (`0xbe8`). Not found: the old constant (the guard still checks each write). The session 7 note had the getter pattern with a 1-byte displacement; the real `cmp byte [rcx+0x3bf0], 0` has 4.
  - **Self-check per feature (1c; the user's choice: off while it fails, retried each second, the first pass is final):** `SelfCheck` mixin, `self_check()` in `slow()`, `passed()` before every write; the panel line under the status shows "Self-check: N of 10 passed", the failed ones with why, and the waiting ones. Checks: god (3 copies agree, 0 <= cur <= max), teleport (source within 0.5 m of the feet), waypoint (sane place), aim (`LookController` and `PlayerDI_PH +0xbb0` within 1° of the camera), health for nuke and one-hit (element copies agree, display copy equals the element), clock (3 copies agree), fury, reload, durability (weak: ranges only), search (kind 0..2 and time 0, 0.1 or 1 s on 90 %). Live: all passed (reload waits for a gun, waypoint for a waypoint). Each strong check failed with its field moved by a few bytes; the fury check passed with a moved field (zeros are in range): its worst case is a write of 100 into one float of its own module.
- **Loot after a long teleport (goal 2):** `long_jump()`: F8 or F10 over 200 m asks for a full scan 10 s later (`scan_all(full=True)`). Test: the rescan at once found 121 loot objects, the full scan at 10 s 337, a rescan at about 30 s 420, an independent full scan at about 50 s 417. So 10 s found 81 %; the rest streamed in later, and the rescan after the full scan found it (the full scan had put the new area's reservations into the memo). Change, not run yet: a rescan 30 s after the jump too (`jump_scans`); each scan line now has the time.
- **F8 falls through the map (the user):** see "End of session 8". The user also jumped many times in a row, so a timing measurement of the streaming (3 full scans in a row) was not valid.
- **False loot markers (the user: markers on bare ground and shelves), fixed in two parts:**
  - **Loot never placed in the world:** the loot object exists, but its model (`+0x8`) has no scene pointer (`+0x3a0` = 0; 257 other models share one pointer), `+0x390` = -1 and `+0x40` bit 3 clear. 16 of 270 search/pickup/collectable objects; 3 of the 16 were the user's 3 false markers (1.6 to 3.1 m away), the other 13 were 93 m or more away. 3 more objects had no model. `loot.spawned()`; the user: "those three false positives are gone".
  - **Taken pickups that the game set back to state 1:** in an ice cream truck, 5 pickups the user had taken showed again. A watcher (`takewatch.py`, scratch) showed: a take sets `+0x388` 1 -> 5 (6 of 6) and clears the model's `+0x318` (the item mesh); when the player comes back (about 9 m) the game sets the state 5 -> 1 (5 of 5) and spawns a new item only sometimes (then `+0x318` gets a pointer: 5 of 5 at one return, none at the next). `lootstate.no_item()`: an active pickup (state 1) with `+0x318` = 0 is hidden. Container ("search") models read 0 there always, so the rule is for pickups only; a dormant pickup (state 2) also reads 0 and stays shown until the game decides. Not confirmed by the user yet.
  - Dead end: the loot object's own position against its model position (0.00 m apart for every container; only bodies differ).
- **Nuke on bandits (goal 4): works (the user); one-hit melee killed `Human_1h` and `Baron_Rifleman` (the app log).** Dry run after the nuke: `Human_1h`, `Human_2h`, `Human_1h` (blue boxes) dead at 2 to 5 m; a survivor of a random encounter at 1 m (empty type name, `modules_human_survivor_encounter`, grey box) kept 1020 of 1020: the nuke, the aim and one-hit skip an unknown type; the green NPC `dlc_ft_sq_Old_Hunter` has no health module.
- `overlay.py` is at 500 lines (the limit): the next feature (flying) needs a split first.
- **Crash fixed at the end:** when the user closed the game, `player_pos()` gave None and `one_hit()` crashed in `flat(me, v)` (the `finally` turned the cheats off first). `one_hit()` and `track()` now return when the position is not sane. Not tested live (the game was closed).

## Session 7 (2026-11-04, from 1:45 AM)

- **Cheats off at the end** (`App.restore()`, in a `finally` around the main loop: F1, Quit, the window closed, an error; not taskkill). Each player-variable cheat that was written goes back to its default; each slider goes back to its base. Checked after F1: all 15 variables at the game values; `MoveSprintSpeed` back to 6 (a skill value; its game default is 5, so "the default" would have been wrong). The switches stay saved. If the game is gone (crash, restart), it prints "none were on": the values died with the process.
- **Sliders x1 to x4** (`playervars.SCALED`, `scale()`; x1 = off; the user's choice, start x2): write = base x factor once a second; base = the value before the first write, saved in `overlay_settings.json` ("base") so a killed app cannot compound x2 into x4; cleared at a clean end. Speed: `MoveForwardMaxSpeed` (3.5) and `MoveSprintSpeed` (6). **Jump: `NormalJumpHeight` alone did nothing** (x4 = 18.08, held by the game); with `HoldJumpHeight` (2.76) and `AdvancedParkourNormalJumpHeight` (1.64) added it works (which one does what was not split). The hold times of that group read 0.242 and 0.212 (defaults 0.1): a skill.
- **Always day / always night:** radio buttons; `set_time()` once a second at 12:00 or 00:00 (the same write as the buttons). Saved as `clock_hold`.
- **Immortality:** `ImmortalityBuff` (bool, `0x1588`), a switch.
- **StringPlayerVariable, researched:** a 0x18-byte record: class, value string, default string, in the `aikind.py` form (inline, or a pointer tagged `0x22`). The value names a buff target: `MeleeDamageMul` -> `Player_MeleeDamageMul`, `FallDamageReduction` -> `Player_FallDamageReduction`, `BlastDamageMul` -> `ExplosionDamagerBlast_PlayerBlastMul`. One `Buffs::StringProperty` points to `Player_MeleeDamageMul`; buff properties are 0x20 bytes (class, definition pointer, value at `+0x10`, an id), with `Buffs::FloatProperty` neighbours (one = 0.01). Guess: a buff changes a named parameter, and the game sums the buffs somewhere (not found; an exact-value search cannot see a multiplier). Three copies of the variable array: two on the heap, one in `gamedll +0x39ef4c8` (a template).
- **One-hit melee (the user's choice: by health, not by the buff):** each frame, an enemy (known type, not an NPC) within 5 m whose health dropped since the last frame, with no gun in hand, gets `nuke.fire()`. Log: "Viral 721 -> 575, set to 0" and more.
- **No fall damage:** `FallDamageResistance` (`0x9d08`, float, 0) = 1.0 (guess: a fraction like `OutfitHumanDamageResistanceFactor` = 0.15). The user: "looks good" (the health loss was not reported in numbers).
- **Rescans: 1 to 2.5 s instead of 12 to 17 s** (`findptr.scan(memo=...)`). Rule 1, "the regions that held a hit, plus new regions", **failed**: each check against a full scan missed 174 to 329 objects (up to 74 loot objects): new loot goes into old heap regions. Rule 2, "every region of a reservation (`AllocationBase`) that held a hit, plus new regions", simulated on full-scan snapshots: 0 loot missed in 3 checks; items (`ItemDescWithContext`) 18, 0, 123; reads 1.7 to 2.2 GB. So every 10th scan is a full one (`FULL_EVERY`: a new melee weapon may sit in a missed item). After a death the rescan misses the new player object, and the app falls back to a full scan (seen working).
- **Ambushers without a box (the user: 2 of 5 boxed): the AI heap grew from 64 to 80 MB** during a gunfire ambush. The app kept the old size and read only the first 64 MB each second, and `scan()` skipped regions over 64 MB, so a rescan could not fix it. The 3 Virals without a box sat past `heap + 64 MB`, the 2 with a box before it. Fix: `humans_in()` reads the size each time (`mem.region_size()`); `OBJECT_REGION_MAX` = 128 MB (+16 regions, +1.56 GB a full scan). The user: all ambushers boxed. After the game restart the heap was 80 MB from the start.
- With the 128 MB limit the first scan found 815 loot objects (348 before, same area): guess: some loot sits in regions of 64 to 128 MB. Not checked.
- **Restart test passed** (the user restarted the game: new PID, new module bases): all 16 stored vtables name their class; player position, teleport source, AI heap, health path, head bone, camera (eye 1.50 m), `LookController` = camera angles, game clock, player health, 15 player-variable offsets. `python restartcheck.py` (read-only; the base for the session 8 self-check).
- `mem.regions()` now yields a fifth value, the reservation (`AllocationBase`). `overlay.TYPE_COLOR` matches by prefix, so `Volatile_Permadeath` is orange too.
- **Volatile aim fixed.** The user's clue was right (orange box, no head dot), the guess was not: the Volatile mesh has a bone named `head` (#62), but `head.py` read no bone names at all on it. The bone records follow a header of 0xd8 + 8 x (u32 at `+0x5c`) bytes: 1 on all 7 human and zombie meshes (0xe0), 3 on the Volatile mesh `dlc_ft_zmb_volatile_skeleton.msh` (0xf0); the old fixed 0xe0 read 0x10 bytes early. Checked on 8 of 8 meshes (first and last bone names readable). `head.bone_name()`. The Volatile's head bone sat 1.15 m above the feet (bent over), so the old fallback (1.6 m) aimed 0.45 m too high. Head helpers: `helper_head_bottom` 1.14 m, `helper_head_top` 1.27 m: the head bone origin is the bottom of the head. Aim on Volatiles, measured: median 0.15° to 1.6° before each turn. Both Volatile types share one mesh. Record 0 holds a pointer to the skeleton file name, not the text.

- **Split:** `cheats.py` holds `Cheats` (a mixin for `App`): `cheats()`, `fury()`, `no_reload()`, `one_hit()`, `restore()`, and their constants. No change in behaviour.
- **Map waypoint (`waypoint.py`):** `LevelDI` (`gamedll+0x2a762e8`, 1 object) `+0x27c8` -> X; X `+0x8` -> `Locations::WaypointLocation` (`gamedll+0x28aace8`); `+0xa0` = (x, height, z). The cheat table's path said `+0x27d0` (game 1.2.2C). Found: a full scan for the class (the object exists only while a waypoint is set), then a pointer search back from it, then the path checked from the `LevelDI`. Note: a rescan cannot find a new object in a reservation that held no hit before (the first watch missed the waypoint for this reason). F8 teleports 1 m above the waypoint height (the table adds 1 m too). The user: works.
- **Fury / beast mode (`PlayerFuryModule`, `gamedll+0x2981ed0`):** watched through one beast mode: `+0x10` 0 -> 100 at the start; `+0x14` the points (100 -> 5.45, drain 2.94 a second = 100 / 34); `+0x18` the length (34 while it runs, else 0); `+0x1c` the time left while it runs, the 10 s "charged" time when the meter is full (`FuryChargedTime`), else -1 or 0; `+0x24` the drain. **Beast mode ended when the timer ran out, with 5.45 points left.** A write of 100 to `+0x14` held. The switch: points 100 each second, and while `+0x18` > 0 the timer back to `+0x18`.
- **Crash fixed:** after the first F8 teleport, `slow()` crashed in `health(None)`: a despawning AI had a health module but no element, and the table `self.hms` stored `None`. The table now skips such AI. The `finally` block turned the cheats off before the crash ended the app.
- **The app falls back to a full scan when a rescan misses any single object** (player, player health, `LookController`, `DayNightCycle`, `LevelDI`, fury module), not only the player.
- **Version safety (the user's question; the user chose to do it in session 8).** Heap addresses are found by each scan, so they survive anything. Module offsets of vtables and globals (`gamedll+0x...`) survive a restart (tested) but move with an update. Field offsets inside objects move when a class gains a field (`LevelDI +0x27d0` in 1.2.2C -> `+0x27c8` now). After an update today: wrong vtables -> the scan finds nothing -> no writes (safe); a wrong player-state global -> the guard refuses (safe); **unsafe: if only the player variable offsets move, the guard (class only) can pass on another variable of the same class.** Plan: (1) offsets by name from `playervars.names()`; (2) vtables by class name from `rtti.find_vtables()`; (3) a start-up self-check per feature; field offsets from code signatures where cheap.

## End of session 6 (2026-11-04): where to resume

- **Done and confirmed by the user, all in the app:** hold-to-track aim (F11) and "Smart aim" (fire button + gun); Day/Night buttons; ghost boxes fixed (`HumanAI +0x20` bit `0x400`); friendly NPCs green; nuke = zombies + hostile humans, never NPCs; scan 6 to 12 s (was 75 s); switches saved in `overlay_settings.json`.
- **Next session, the user's plan (all five, in this order):**
  1. Turn the player-variable cheats off when the app ends (F1 or Quit), on again at the next start (the switches are saved now).
  2. Super jump and speed: `NormalJumpHeight` (4.52), `MoveForwardMaxSpeed` (3.5). New kind of write: dry run first.
  3. Always day / always night: a switch that holds the clock (`daynight.py`).
  4. Near-instant rescans: rescan only the regions that held objects, plus new regions (`findptr.scan()`).
  5. `ImmortalityBuff` (bool); one-hit melee (`MeleeDamageMul`) and no fall damage (`FallDamageReduction`): both are `StringPlayerVariable` (a pointer, not a number), so research first.
- **Volatile aim, the user's clue:** Volatiles have an orange box but **no head dot**. So `head.head_pos()` finds no bone named `head` in their skeleton, and the aim falls back to feet + 1.6 m (`aim.HEAD`), which misses a big, bent-over Volatile. Next: at night, list the bone names of a Volatile mesh (`head.bone_index()` reads them) and add the right name. Also `Volatile_Permadeath` has no orange box (`TYPE_COLOR` matches `Volatile` exactly).
- **Untested:** the new nuke rule on real bandits (blue boxes; the nuke kills them; never green NPCs). The aim point (head bone vs head centre). The restart test (since session 2).

## Session 6 (2026-11-04, from midnight)

- **Aimbot done, in the app; the user: "zombies and humans it works great".** Hold F11 = track; panel switch "Smart aim" = the same lock while the fire button (left mouse) is held with a gun in hand (`items.held_gun()`). Only while the game is the active window. The user's choices: nearest in distance (in front, within 90° of yaw), zombies and humans (unknown types skipped), no angle limit, instant turn. One lock per hold; it moves to the next AI when the locked one dies or goes past 60 m (with no limit this can swing the view 57° to 84°).
- `aim.turn()` now writes absolute angles (`angles(eye, head)`), not yaw + error: the camera shows a write one frame later, so a per-frame "yaw + error" would add the old error twice.
- Measured (about 60 holds, 3 m to 58 m): the crosshair sat a median 0.2° to 0.4° from the head before each per-frame turn. `camlook.py` (scratch probe): camera angles − `LookController` angles = +0.02° yaw, +0.03° pitch median, so the camera adds no rotation of its own; the 0.3° is guess: the user's mouse and the recoil within one frame. A fast Banshee at 7 m: median 3.9°.
- **Later (the user: "a cherry on top"): it does not work well on Volatiles.** Not analysed. Clue: the type name read `Volatile_Permadeath`; `overlay.TYPE_COLOR` matches only `Volatile` exactly, so these boxes are magenta, not orange.
- Aim point (head bone origin vs head centre): not measured; no screenshot was taken during a hold.
- **Time of day (`daynight.py`, app: panel buttons Day 12:00 / Night 00:00 and the game clock).** Found by class name: the DLL files on disk hold every RTTI name as text (`.?AVDayNightCycle@@`); nothing in the cheat table. `DayNightCycle` (`gamedll_ph_x64_rwdi.dll+0x2a78608`, 1 object): `+0x10` = time of day as a fraction of a day (copies `+0x20`, `+0x5c`), `+0x24`/`+0x60` real seconds, `+0x28` = −1 (guess: a target time), `+0x7c` = 5538 (day length, s), `+0x80` = 1963 (night length, s). Day speed +0.00018 a second (92 min a day), night speed +0.0005 a second. The user confirmed "morning" at 09:30.
- Write test 00:00 (the user's OK): the three copies held and counted on at once at the night speed; the HUD showed the night XP x2 and Volatiles came, still in daylight. An engine copy in hours (inside one of 8 `TimeWeather` subsystem groups, `0x23abcf4cc98` this run) followed the game clock by itself.
- **In the app, confirmed by the user:** "Night" brings the night monsters, "Day" despawns them; "the environment lags behind, which I think is fine". Measured (`lightwatch.py`, scratch: mean brightness of the game picture every 5 s): after Night the light stayed day for about 70 s, then faded to night in about 20 s (brightness 85 → 5). After Day the light was day again within 40 s or less. Later, if wanted: find the light's own copy to remove the delay.
- Dead ends for the light copy: `CLightingWeatherSubsystem` (8; one holds the moving sun direction), `CHeightmapWeatherSubsystem`, the 4 KB around the `TimeWeather` groups (no owner class within 0x800 bytes).
- **Ghost boxes fixed (the user's report: boxes with no NPC, and the aim pulled onto them).** Cause: the game keeps a pool of dormant `HumanAI` slots near the player (vtable, position, frozen pose, full health), so `alive()` + health > 0 passed. The user's idea, confirmed: gunfire in a new area wakes some of them ("they spawn out of nowhere just out of view"). The 3 ghosts next to the player (screenshot: nothing there) were frozen for 20 s with full health; of 118 AI, 94 "living" ones were such ghosts.
- **The flag: `HumanAI +0x20` bit `0x400`** (`radar.in_world()`): `0x85` dormant, `0x487` spawned. A 60 s recording during gunfire (`slots.py`, scratch): 4 slots woke and went `0x85` → `0x487`; then of 121 AI, 96 of 97 frozen ones had `0x85` and 11 of 13 moving ones `0x487` (the exceptions: two that lay still, one that went dormant again; corpses keep `0x487`). `+0x1174` (0 → 3) and `+0x21c` (`0xc00` → 0 or 1) change too.
- **First fix, wrong:** `+0x208` (the `CoAIProxy` link) != 0. It removed the ghosts, but the user saw that AI woken by gunfire had no box: they have no proxy (11 of 15 spawned AI). Lesson: a sample without the event that matters (here gunfire) cannot test a rule.
- Fix: `radar.in_world()`; the app's AI list (boxes, aim, nuke, counts) keeps only spawned AI, `aim.living_head()` and `nuke.targets()` check it too; the corpse check still reads all slots. **The user confirmed: "working great now, no false positives so far"**, and the zombies woken by gunfire get boxes.
- **Friendly NPCs (grey boxes) found, in a safe zone.** All 20 spawned AI: type name empty (`+0x27c0` = `00…07`, a length-0 inline name, so `decode()` gave None), no health module, `+0x2278` → `modules_npc` (Biters: `modules_biter_anger`), `+0x1e30` → `default_npc` (Biters: `default_human`), `+0x2308` → the character (`dlc_ft_mq_Lydia`, `dlc_ft_mq_Shelby`), `+0x12f8` → spawn name (`dlc_ft_mq_Lydia;MainQuests`; zombies `ai_8380`). More text pointers in a `HumanAI`: `+0x230` animation preset, `+0x1c18` model preset, `+0x1c30` model file, `+0x2268` `infected` (zombies only). Now `aikind.kind()` = `NPC` for an empty name with `modules_npc`; `is_zombie(NPC)` is False; green box; the aim skips NPCs by name. The nuke and the aim never hit them before either (no health). Not checked on bandits (none loaded at the time).
- **The NPC colour is confirmed by the user** (green in the safe zone).
- **Nuke rule changed (the user's choice): zombies and hostile humans, never friendly NPCs or unknown types.** Before, `is_zombie()` counted any name not starting with `Human` as a zombie, so Baron's soldiers (`Baron_Rifleman`) got magenta boxes and the nuke hit them by mistake. Now `aikind.HUMANS = ("Human", "Baron")` (shortcut: only two human names seen) and `nuke.targets()` skips only `NPC` and None. Dry run in the safe zone: 0 targets among 20 NPCs. **Not tested on bandits** (none loaded): the boxes must be blue, and the nuke must kill them. If a bandit type has another prefix, test `+0x2268` (`infected` on zombies) as the zombie sign.
- **The object scan takes 12 s, not 75 to 87 s** (`findptr.scan()`; the user asked for 10 to 15 s). Profile of the old scan: 17.75 GB in 7000 regions, copies 57.7 s (0.31 GB/s cold), checks 28.6 s (`searchsorted` on every value). All 1663 objects of 15 classes sat in 213 regions of 9 MB or less plus the 64 MB AI heap (0.40 GB); none in the 8.5 GB of regions over 64 MB. Now: regions up to 64 MB only (9.3 GB; `chase()` still reads all), 4 threads with reused buffers (`mem.read_into()`; measured 4.1 to 9.9 GB/s against 1.0 to 2.0), and a range test before the exact test. Checked against the old scan on the live game: the same 1656 objects. Next step if wanted: rescan only the regions that held objects before, plus new regions (near instant).
- **Settings saved** (the user's idea): `overlay_settings.json` next to the app holds every switch and the loot distance, written at each change (a kill loses nothing), read at the start; a missing or broken file gives the defaults. "Armed" is never saved: the nuke starts disarmed. Live test: a file with Head dots off, 45 m and Armed on gave Head dots off, 45 m, Armed off.
- **Trainer ideas (session 6, not built):** player variables found with `playervars.py`: `NormalJumpHeight` 4.52 (super jump), `MoveForwardMaxSpeed` 3.5 (speed), `ImmortalityBuff` (bool: the game's own god mode), `MeleeDamageMul` and `FallDamageReduction` (StringPlayerVariable: hold a pointer, not a number; test first). Also: write the cheat defaults back when the app ends (F1 or Quit), an "always day / always night" lock, near-instant rescans, the aim on Volatiles.
- **Still open after session 6:** the aim point screenshot (scratch `aimshot.py` took none: the user held the fire button in short clicks); does the nuke kill a Volatile (`Volatile_Permadeath` too); the aim on Volatiles; the light delay (optional); the restart test (since session 2); `aikind.py` near a trader.

## End of session 5 (2026-11-04, about midnight): where to resume

- **Confirmed by the user, all in the app (`overlay.py`):** instant search (containers and corpses), corpse loot ESP, orange Volatiles, teleport (F9 mark, F10 go), god mode, infinite stamina, infinite ammo reserve and arrows, no durability loss (melee), no reload (gun in hand). Details in the Session 5 section below.
- **Aim (not in the app yet):** `aim.py --write`, F11 snaps the view onto the nearest head once. Every press holds since the third angle copy (`PlayerDI_PH +0xbb0..+0xbbc`) is written too. Misses come from target motion after the snap (1° to 8.5° on walking or close zombies; 0.03° to 0.31° on still ones).
- **Next session, the user's plan:** (1) hold a key to track (aim again on each frame), in the app; (2) a "smart" aimbot that locks on only while the user shoots (for example: fire button held and `items.held_gun()` not None). Ask the user about target choice (nearest to the crosshair or nearest in distance, zombies only or humans too, a maximum angle, smooth or instant) before building.
- **Open checks:** the aim point (the head bone origin may sit below the head centre: screenshot test); does the nuke kill a Volatile (colour confirmed, nuke not); the restart test (step 1, still open since session 2); `aikind.py` near a trader (human side untested); small stamina costs that `InfiniteStamina` does not cover (`KickStaminaUsage`, ...).
- **Known limits:** ~~the app starts with every switch off~~ (fixed in session 6: `overlay_settings.json`); killing the app with taskkill leaves the player-variable cheats on in the game until the game restarts; a melee weapon picked up after the last scan is protected only after the next scan (50 m walked).
- The quit key of every script is **F1** (was F8).

## Session 5 (2026-11-03, 8:15 PM, the user away): the three new writes are ready to test

- The game was in the pause menu. No game memory was written. Only read-only dry runs ran.
- **New scripts (dry run by default, `--write` writes):** `teleport.py` (F10: lift 0.5 m), `fastsearch.py` (search time 0 on the nearest container), `aim.py --write` (F11: turn the view onto the nearest head once). Each `--write` is a new kind of write: the user's OK first.
- **Dry runs passed on the live game:**
  - Teleport chain resolved: 4 `CBulletPhysicsCharacter` objects, the player's one through the chain; its `+0x158` is a `btRigidBody`. Rigid body height − 0.375 = the four feet copies = the model height (3.007), so the session 3 chain still holds. The rigid body `+0x10..+0x3c` is a 3x3 rotation (rows of 4 floats), `+0x40` the origin: the Bullet world transform. `+0x50` and on is not a second transform (it reads 1, 1, 1, then junk).
  - `LookController` read −89.375 / −50.5, the same as in session 3 (the view has not moved since). No pointer to it in `PlayerDI_PH` (first 0x4000 bytes) or in the writable globals of the game modules, so `aim.py` finds it by the scan.
  - The player stands 0.9 m from an unsearched `search` container (`kind 1`, 1.0 s, state 1, 1 item); three more are within 3 m. `fastsearch.py --write` would use the 0.9 m one.
- Stopped a second `overlay.py` (started 5:31 PM by the session 4 "full app run" check): two panels sat on top of each other, and F6 and F8 acted on both. Stopped `lootwatch.py` too (its test is covered by `fastsearch.py`).

**Session 5, the user back (9 PM): test results** (the user approved all three new kinds of write)
- **Instant search works.** `fastsearch.py --write`: 4 containers searched at once; each went state 1 → 5, items → 0, and the search time stayed 0 (the game never put 1.0 back, also not over 10 minutes). This also confirms `+0x388 = 5` live. Now a panel switch in the app ("Instant search", once a second, `search` and `body` loot).
- **God mode works** (the user, from the panel; it writes both health elements).
- **Teleport works** (the user: "works perfectly"). The source is `CBulletPhysicsCharacter +0xfd0` (x, feet, z): a probe lifted each copy alone; only `+0xfd0` held, and the game copied it to `+0xfb8`, `+0x1054`, `+0x10dc` within 4 ms. The `btRigidBody` origin did nothing (the game rewrites it). `teleport.py`: F9 marks, F10 returns; also in the app.
- **Aim works only sometimes.** Round 1 (`+0x6c/+0x70` only): the probe showed that each frame the game rebuilds `+0x6c` from `+0x74` and copies `+0x6c` to `+0x74` later; a write held only between the two. Round 2 (both pairs in one write): many presses held, but in some streaks every write went back to the exact old angle, also with the mouse still and at 15 m range. The yaw came back unwrapped (208.29), so the source is not `PlayerDI_PH +0xbb0` (wrapped). A third store, not found. Proposal: turn by mouse input (`SendInput`) instead.
- **New corpses (found statically, session 5):** `HumanAI +0x2558` → its `BodyContainer` once dead (3 of 3 dead AI, no living one). The body points back: `+0x70` → `HumanAI +0x2548`, `+0x5e8` → `HumanAI +0x40`, `+0x5f0` → `HumanAI +0x70`. 13 older bodies had no link (their AI slot reused). A fresh body is `kind 1`, 1.0 s at `+0x1f8` (older ones: 0.1 s). The app reads the link once a second. A body's state stays 1 after a search; the looted body read 0 items left (`+0x4d0`) of 2: candidate "looted" sign (`lootstate.emptied()`).
- **Body position: use the model, not `+0x14c`.** The game reuses `BodyContainer` objects (one body object served two different dead zombies within an hour), and the own matrix keeps an old place: 93 and 107 m off for 2 fresh corpses, while the model (`+0x8` → matrix `+0xf0`, `loot.model_pos()`) sat 0.1 m from the dead zombie. 14 of 16 bodies' models sat where the user had fought. The user: the box shows on a new kill and instant search works on it. Guess: a corpse turns into the "loot pack" (`kind 2`, 0.1 s, no AI link) when it despawns.
- **Volatiles were grey (type unknown), so the nuke skipped them.** A type name over 7 letters is a pointer with a tag in its top byte (`0x22`); mask it to 48 bits (`aikind.kind()`). 4 of 4 night AI with about 5,200 health read "Volatile". `+0x23b8` is not a type copy: it read "ChaseInfected".

## Session 4 (2026-11-03): GPU overlay

- **The overlay draws with raylib (GPU) now.** `python overlay.py` = raylib, `python overlay.py --tk` = the old tkinter canvas (the fallback). Same layers and colors. Panel, scan thread, slow update, god mode, nuke, aim readout and F6/F7/F8 unchanged.
- **Package, pinned: `raylib==5.5.0.4`** (the PyPI name of raylib-python-cffi; raylib C 5.5; wheel `cp314-win_amd64`). It brought `cffi 2.1.1` and `pycparser 3.12`. Install: `python -m pip install raylib==5.5.0.4`. Not 6.2.0.0 or 6.0.1.1: both were only 8 days old (2026-10-26). 5.5.0.4 is from 2025-12-11.
- `paint.py`: two painters with the same calls (`place`, `begin`, `end`, `rect`, `fill`, `circle`, `text`). `RlPaint`: transparent framebuffer, undecorated, topmost, mouse passthrough, vsync; created hidden and unfocused, then `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` (and no `WS_EX_APPWINDOW`), then shown with `SW_SHOWNOACTIVATE`. Each frame clears to (0, 0, 0, 0). Font: Segoe UI Bold at the tk size.
- One loop on the main thread: `paint.begin()`, `tick()`, `paint.end()` (raylib waits for vsync), `root.update()` (the panel). The tk mode sleeps 5 ms in place of the vsync wait.
- **Measured** (`overlaybench.py`, 3440×1440 on the 120 Hz main monitor). "Work" = main-thread time a frame outside `paint.end()`: the draw calls and `root.update()` (where tk redraws).

  | Boxes | tk, session 3 | tk, session 4 re-run | raylib, session 4 |
  |---|---|---|---|
  | 10 | 357/s, 1.4 ms | 324/s, 1.43 ms | 101/s, 0.11 ms |
  | 50 | 72/s, 12.7 ms | 73/s, 12.07 ms | 101/s, 0.25 ms |
  | 150 | 47/s, 19.8 ms | 46/s, 19.66 ms | 101/s, 0.61 ms |

  raylib worst gap 10.4 ms at all counts; tk worst 29.9 ms at 150 boxes.
- **A driver cap of 100 frames a second.** Every OpenGL present on this PC waits 10 ms, with or without vsync, also for a plain raylib window with no flags; the CPU sleeps meanwhile. Probe: draw 0.03 ms, batch flush 0.00 ms, `SwapScreenBuffer` 9.96 ms, `PollInputEvents` 0.02 ms. Window size and the layered style made no difference. Guess: the NVIDIA Control Panel "Max Frame Rate" or "Background Application Max Frame Rate" is 100 (RTX 3090, driver 610.88; not checked). No effect on the game monitor (60 Hz: vsync limits first). On the 120 Hz monitor the overlay would show 100 of 120 frames.
- **Checks (game paused, no game writes):** a screenshot over the game: 0.00 % of the pixels away from the shapes changed, and the shapes drew in their colors. `WindowFromPoint` on a box pixel and on an empty pixel both gave the game window. The active window did not change. Styles: LAYERED, TRANSPARENT, TOOLWINDOW, NOACTIVATE, TOPMOST, no APPWINDOW. `--tk` passed the same checks. Full app run: scan done (player, 47 AI, 6 cameras, 354 loot), the panel filled, `draw()` ran 60 times a second (the game monitor's refresh) with no error, and real loot markers showed. AI boxes were off the screen in the pause menu: not seen yet.
- Small difference: raylib labels are about 8 % narrower than the tk labels (raylib rounds each letter advance down to a whole pixel). The letters are the same size.
- The game window moved: it is on the second monitor now (60 Hz), client area 1920×1080 at (669, −1269). DPI 96 on both monitors.
- Pending: the user's check in the game, then "Tests that wait for the user (session 3)".

## Session 3 (2026-11-03): loot ESP

The user chose step 8 (loot ESP) first, then step 1 (restart test) and the rest in order.

- **Loot positions are done.** Four classes hold loot. Each object has its own 3x4 world matrix at `+0x140`, so the position is at `+0x14c`, `+0x15c`, `+0x16c` (x, height, z). Found with a probe: 72 of 93 `Container` and 109 of 136 `ComplexContainer` objects held a distinct position within 150 m of the player.
- Checked twice: a screenshot put the `ComplexContainer` markers next to the game's own white loot dots (offset about 30 px: the pivot, not the handle). The user checked the live overlay and named each class:
  - `Container` = loot you search (hold the key). Label `search`, yellow.
  - `ComplexContainer` = loot you take at once. Label `pickup`, cyan.
  - `CollectableObject` = rare quest items (a treasure map). Label `collectable`, green.
  - `BodyContainer` = dead zombies and NPCs. Label `body`, red.
- `overlay.py` now draws a circle and a label for each loot object within 30 m. The loot scan (75 s) runs in a background thread: at the start (at the same time as the main scan), after each 50 m walked, and after a death.
- **The "already looted" state (candidate, strong; found statically by lane C with the game paused).** `Container` and `ComplexContainer` share a base class with a state at `+0x388`: 1 = near the player, 2 = far (dormant), 5 = searched or taken. Evidence: the 4 `Container` objects with 5 had 0 items left (`+0x4d0`) of 1 or 3 (`+0x4d4`); all other 89 still had all their items. All 16 `ComplexContainer` objects with 5 were within 30 m, where the user had looted. The game's search-time function reads `+0x388` too. `lootstate.py`: `looted()`. The overlay now hides loot with state 5. Not yet checked live: search one container and watch its marker go.
- `BodyContainer` has state 1 on all 18 objects, and `CollectableObject` has another layout: no looted state for them yet.
- **Search time (from the cheat table's "Fast Search" lead, checked statically):** `+0x1f8` = search time in seconds: 1.0 on 79 normal containers (a copy of `+0x57c`), 0.1 on quick ones (a copy of `+0x580`), 0 on pickups. `+0x508` = kind: 1 = search (hold the key), 2 = quick (all bodies and 9 containers), 0 = pickup. The game function at `gamedll_ph_x64_rwdi.dll+0x10B3470` returns 0 when the kind is 2, or when the kind is 0 and the state is 1; else it returns `+0x1f8`. `+0x370` = 2.5 on both classes (probably the interaction range).
- `lootwatch.py` was started and waits for the F9 test (search two containers, take two pickups). It can now confirm `+0x388`.
- Dead end: `LootedObject` (707) and `LootingManager` hold names and `LootItemSet` pointers (loot tables). No loot object holds their IDs.
- Not loot: `ContainerItem` (90, parts of a `ComplexContainer`, same positions), `LootedObject` (707, no position field; maybe a record per looted object, not checked). The `Co...` components (`CoMultiloot`, `CoInteractable`, `CoCollectable`, `CoBackpackLoot`) had 0 objects.
- The loot objects sit in 6 to 18 small regions of the general heap (12 to 42 MB per class), not in one block like the AI. A quick search of known regions would miss new loot, so new loot needs the full scan.
- The game process started at 14:08, during session 2. It has not restarted since, so step 1 (restart test) is still open.
- While the user was away (game in the pause menu), three read-only agent lanes found: the looted state and the search time (lane C), the player health and the view angles (lane B), the AI type and the head bone (lane A). Details are under "Next steps" items 2 to 7. No game memory was written.
- **Humans vs zombies (lane A, candidate):** `HumanAI +0x27c0` holds the AI type as an 8-byte inline string (the name, zero bytes, last byte = 7 − length; copies at `+0x23b8`, `+0x2808`). The game's type list: Finisher, Elite, BigZombie, Human, Human2H, HumanRifle, HumanShotgun, Biter, Viral, Screamer, Spitter, Bolter, Suicider, Goon, Demolisher, Volatile, Corruptor, Skullface, Freak_*. Rule: a name that starts with `Human` is a human. All 47 live AI were `Biter`, so the human side is not tested. `nuke.py` now hits only zombie types.
- **Head position (lane A, static evidence on 47 of 47 AI):** `HumanAI +0x1d28` → X (inside the `CoSkeleton`). `X +0x58` = render world matrix (3x4, with the size scale 0.93 to 1.10). `X +0x290` = {bone array of 3x4 model-space matrices, bone count, `CCompactMesh`}. The mesh's `+0x68` → bone records of 0xe0 bytes; record i+1 is bone i, name pointer at `+0x28`. The bone named `head` has a different index per mesh (#106 to #137). Standing heads were 1.40 to 1.75 m above the feet. `head.py`: `head_pos()`; `aim.py` uses it.

- **The app (session 3, built while the user was away):** `overlay.py` now ties the tools together (see the Scripts table). Checked on the paused game with a screenshot of the panel: 22 living AI (22 zombies), 58 loot within 30 m, 20 looted hidden, health 164 of 475 in both elements, the aim readout. The overlay drawing was not checked (the game window was minimized). `nuke.py` (`fire()`) and `godmode.py` (`heal()`) share their write code with the app. Note: the standalone `nuke.py --write` also listens to F7 and does not know the panel's "Armed" switch.

- **Overlay speed, measured (session 3, `overlaybench.py`, no game needed):** the `tkinter` overlay window (3440×1440, layered, color key) redraws 10 boxes at 357/s (1.4 ms a frame), 50 boxes at 72/s (12.7 ms), 150 boxes at 47/s (19.8 ms). The cost follows the changed screen area, not the box count. So the 5 ms setting gives only 50 to 70 redraws a second with a normal scene, each frame 13 to 20 ms late; the loot markers add more than 100 items. **Decision (the user, session 3): build a GPU overlay with `raylib` (`raylib-python-cffi`) next session**, keep the `tkinter` panel and keep the `tkinter` overlay as a fallback. The other lag cause (two programs, up to about one frame) stays; only drawing inside the game (code injection) removes it, not recommended. **Done in session 4:** raylib holds the refresh rate with 0.61 ms of work at 150 boxes (see the session 4 section).

**Tests that wait for the user (session 3), in order**
0. The app: check the panel switches, and that the boxes, head dots and loot markers sit right during play.
1. Looted filter: search one `search` container and take one `pickup`. Both markers must go. Or push F9 for `lootwatch.py` after the same actions, which must list `+0x388`.
2. `godmode.py` dry run: take one zombie hit and see which health element drops. Then the user approves the first `--write`.
3. `aim.py`: put the crosshair on a zombie head; both errors must be near 0. Turn, and check that `LookController +0x6c` changes.
4. Head markers: a screenshot during play (not the pause menu) with `w2s(head_pos)` marked; each mark on a head, also for a crouched zombie.
5. `aikind.py` near a trader or a bandit: the type must start with `Human`.
6. Writes that need the user's OK first (new kinds). Scripts ready since session 5; the game must run, not the pause menu:
   - Instant search: `python fastsearch.py --write` next to a `search` container, then hold the search key. Expect: the search ends at once, state 1 → 5. If the time goes back to 1.0, write `+0x57c` too.
   - Teleport: `python teleport.py --write`, press F10 once. Expect "the model rose 0.5 m → it follows" (the player then falls 0.5 m). Stage 2 (the feet copies) runs only when stage 1 fails.
   - Aimbot turn: `python aim.py --write` with a zombie in front, press F11 once. Expect: the error after 0.3 s near 0. If the angles go back, try `+0x74/+0x78` or `PlayerDI_PH +0xbb0`. Then hold-to-track.
7. Restart test (step 1) after the next game restart.

## Rules (from the user — keep them)

- Education only. Single-player and offline.
- Writes are allowed (2026-11-03). The user did not recall setting the old "read only" rule and said "I'm fine with you writing". Edit files freely.
- **Game memory writes are allowed** (2026-11-03, session 2). The user asked for the nuke, was told the risks (crash, human/quest NPCs are `HumanAI` too), and chose "dry run, then write" with a 50 m radius. Keep that pattern for a new kind of write: a read-only dry run first, then the write. `mem.Process` stays read-only unless `write=True`.
- A public Cheat Engine table for game version 1.2.2C was read as plain text for leads (never loaded: tables can write memory). Much of it did not work on this version, so each entry was a lead to test, not a fact. It was deleted in session 9; the "cheat table" in older sections means that file.
- Walk the user through each step and explain it.
- The game runs as administrator. Run Python in an elevated terminal, or reads fail with "WinError 5 Access is denied".

## Where we left off (end of session 2, 2026-11-03)

- **Step 3 (entity list) is done.** `radar.py` shows live positions of the player and of every person and zombie (`HumanAI`) within 150 m.
  Final test: two zombies chased the player and walked 115 m and 101 m at up to 3.6 m/s, 2 to 11 m from the player. The AI count went 43 → 40 → 47 as zombies came and went.
- Two corrections to session 1:
  - The old player field `PlayerFallHelperModule` + `0x1b40` lags (still for 17 s while the player walked 10 m). Use the player model matrix.
  - Zombies **are** `HumanAI` objects. The live position is at `+0x1cc0`. The session 1 field `+0x254` is not it.
- How it was found: `heapwatch.py` read the whole 64 MB AI heap 7 times a second during a chase, and kept the float triples that walked on their own.
- Dead ends this session: `CoAIProxy` + `0x270` (a static spawn point), exact-class `CModelObject` (zombies are not in it), `CoSkinnedMesh` (no position near the player).
- A sleep (time skip) or a death makes a new player object at a new address. `radar.py` handles it (one 75 s scan).
- **Step 4 (camera, world to screen) is done.** `camera.py` finds the active `CBaseCamera` and projects positions with the view × projection matrix at `+0xc0`. Checked with screenshots during play: a box drawn from each projected zombie sat around that zombie, bottom at the feet.
- **Step 5 (overlay, the ESP) works.** `overlay.py`: a `tkinter` window, topmost, click-through, black = see-through, placed on the game client area. It draws a box (feet to feet + 1.75 m) and the distance for each `HumanAI` within 100 m, only while the game is the active window. Redraw every 5 ms (up to about 190 a second): at 15 ms (64 a second) the user saw a small lag when turning. The reads for one redraw take 0.6 ms for 67 AI. More speed would need a different drawing method (DirectX overlay), not worth it so far. Checked with screenshots during play: boxes sat on the near zombies, and far zombies behind trees and rocks had boxes too.
- The user said the boxes lag "a little but not too badly" at 15 ms. Changed to 5 ms; not yet rated by the user.
- **Health (zombies) is done.** `HumanHealthModule` + `0x28` = current health, `+0x2c` = maximum. Found with `healthwatch.py`: one zombie went 1033 → 827 → 661 → 523 → 385 → 247 → 0 in 6 hits. Link: `HumanAI` + `0x5e8` → object + `0x228` → `HumanHealthModule` (all 58 matched; copy at `+0x298`). The overlay draws a health bar left of each box and hides dead zombies. Checked with screenshots.
- **Nuke (step 7) works** (`nuke.py --write`, F7): first version wrote the display copy, boxes vanished but zombies lived. A watcher showed the copy came back (0 → 1018.5, then a hit took 138 from 880.5, not from 0). A two-level pointer search from the module for the exact value found the `lifecs` element. A one-zombie test write there killed it. The nuke now writes the element.
- **Not found:** the player's own health (no zombie hit the player during the recording). `PlayerHealthModule` exists (1 object, `gamedll_ph_x64_rwdi.dll+0x29a2418`); run `healthwatch.py` while a zombie hits the player.
- Session 2 ended here (2026-11-03): ESP overlay with health bars works, the nuke works. The user wants to continue with the wish list under "Next steps".

## Plan and status

| Step | State |
|---|---|
| 1. Attach and read bytes (`mem.py`) | done |
| 2. Player position | done: live field in the player model (session 2). The older field lags. |
| 2. Health | **zombies done** (session 2): `HumanHealthModule` + `0x28` / `+0x2c`. Player health not found yet. |
| 3. Entity list | **done** (session 2): `HumanAI` objects, position at `+0x1cc0`, found again every second. |
| 4. Camera matrix, world to screen | **done** (session 2): `camera.py`, checked with screenshots. |
| 5. Overlay (ESP) | **works** (session 2): `overlay.py`. Box height is fixed (a crouched zombie gets a full box). GPU drawing (raylib) since session 4. |
| 6. Aim angles | **found** (session 3, static): `LookController +0x6c/+0x70`; `aim.py` dry run with the head bone. The turn is not written yet. |
| 8. Loot ESP | **positions done** (session 3): `loot.py`, drawn by `overlay.py`. The "already looted" state is not found yet (`lootwatch.py`). |

## Environment

- Process name: `DyingLightGame_TheBeast_x64_rwdi.exe` (there is no `Dyi.exe` process). Folder: `C:\Games\Dying Light - The Beast\ph_ft\work\bin\x64`.
- Python 3.14.3, numpy 2.5.2, `raylib==5.5.0.4` (pinned, session 4), Windows 11. Work folder: `C:\dev\Github\Aimbot`, a git repository since session 9 (branch `main`). Game version 1.6.0.0 (session 9).
- Session 4: the game window is on the second monitor (60 Hz) with a 1920×1080 client area at (669, −1269). The main monitor runs at 120 Hz. The NVIDIA driver caps OpenGL presents at 100 a second (see the session 4 section).
- Game modules with class names (RTTI): `gamedll_ph_x64_rwdi.dll` (game logic, 66 MB), `engine_x64_rwdi.dll` (43 MB), `engine_core_x64_rwdi.dll`.
- Coordinates: Y is up. A position is 3 floats in a row: x, height, z. The unit is meters (a walk is about 1.4 to 3 per second).
- Readable memory is about 18.8 GB. One vtable scan of all of it takes about 75 s.
- Screens (session 2): main monitor 3440×1440 at (0, 0), a second monitor above it at (3, -1440). The game runs **windowed**, with a title bar, and its 3440×1440 client area starts at screen (347, 43). So the right 347 px and the bottom 43 px of the game are off the screen. An overlay must sit on the client area (`ClientToScreen`), not on the monitor. Call `SetProcessDpiAwareness(2)` first so that the numbers are physical pixels.

## Stable facts (valid after a game restart, for this game build)

Vtables, written as module + offset. One scan for the vtable address lists every object of the class.

| Class | Vtable | Objects seen |
|---|---|---|
| `PlayerFallHelperModule` | `gamedll_ph_x64_rwdi.dll+0x2996e10` | 1 (the local player) |
| `PlayerDI_PH` | `gamedll_ph_x64_rwdi.dll+0x257b1f0` | 1 |
| `GameDI_PH` | `gamedll_ph_x64_rwdi.dll+0x257eba8` | 1 |
| `HumanAI` | `gamedll_ph_x64_rwdi.dll+0x293e8e0` | 20 to 47. **Every live person and zombie.** 0x4000-byte slots in one heap block. |
| `CoAIProxy` | `gamedll_ph_x64_rwdi.dll+0x2cd6a28` | 589. One per AI spawn in the loaded world. 0x580 bytes each, in rows. |
| `CoAIObservableHumanAI` | `gamedll_ph_x64_rwdi.dll+0x2a4a060` | 22 |
| `CoAIObservablePlayerDI` | `gamedll_ph_x64_rwdi.dll+0x2a4a630` | 1 |
| `HumanWeaponModule` | `gamedll_ph_x64_rwdi.dll+0x2a36b38` | 22 |
| `HumanHealthModule` | `gamedll_ph_x64_rwdi.dll+0x2a34308` | 0 in the camp (session 1); 58 outside. One per zombie with health. |
| `PlayerHealthModule` | `gamedll_ph_x64_rwdi.dll+0x29a2418` | 1 |
| `CoHealth` | `gamedll_ph_x64_rwdi.dll+0x2d435a0` | 52. No float in its first 0x200 bytes dropped on hits. |
| `CoAIObservableObject` | `gamedll_ph_x64_rwdi.dll+0x2d32f58` | 0 |
| `cbs::CEntityMgr` | `engine_x64_rwdi.dll+0x178ea70` | 1 |
| `cbs::CEntity` | `engine_x64_rwdi.dll+0x178e070` | 16,477 (props, triggers, characters) |
| `cbs::CActor` | `engine_x64_rwdi.dll+0x1791d50` | 0 |
| `CLevel` | `engine_x64_rwdi.dll+0x1887398` | 8 |
| `CModelObject` | `engine_x64_rwdi.dll+0x18059e8` | 235 to 532. The player model is this class. Zombies are not. |
| `CoSkinnedMesh` | `engine_x64_rwdi.dll+0x179f290` | 585. No position near the player found. |
| `CoMeshRender` | `engine_x64_rwdi.dll+0x17a1230` | 7,825 |
| `CModelObjectPoseElement` | `engine_x64_rwdi.dll+0x1805790` | 532. Sits 0x520 bytes before its `CModelObject`. |
| `CoModelObjectProxy` | `gamedll_ph_x64_rwdi.dll+0x2d0eb38` | 528 |
| `CBaseCamera` | `engine_x64_rwdi.dll+0x177daf0` | 6, side by side in one block. The active one has its eye 1.5 m above the player model. |
| `CRendererCamera` | `engine_x64_rwdi.dll+0x177e120` | 91. Same layout as `CBaseCamera` (render copies, shadows and more). |
| `Container` | `gamedll_ph_x64_rwdi.dll+0x29c1910` | 93. Loot you search. Position at `+0x14c` (session 3). |
| `ComplexContainer` | `gamedll_ph_x64_rwdi.dll+0x29c7e98` | 136. Loot you take at once. Position at `+0x14c`. |
| `BodyContainer` | `gamedll_ph_x64_rwdi.dll+0x29c2e00` | 18. Dead zombies and NPCs. Position at `+0x14c`. |
| `CollectableObject` | `gamedll_ph_x64_rwdi.dll+0x29d5508` | 107. Rare quest items. Position at `+0x14c`. |
| `ContainerItem` | `gamedll_ph_x64_rwdi.dll+0x29c6b30` | 90. Points (`+0x8`) into a `ComplexContainer`. |
| `LootedObject` | `gamedll_ph_x64_rwdi.dll+0x2879470` | 707. No position field. |
| `LootingManager` | `gamedll_ph_x64_rwdi.dll+0x2879480` | 1 |
| `CoStash` | `gamedll_ph_x64_rwdi.dll+0x2922e58` | 1, in the AI heap |

Fields:

- **Player position, live:** `PlayerFallHelperModule` + `0x08` → `PlayerDI_PH` + `0x8` → `CModelObject`. That object has a 3x4 row-major world matrix at `+0xf0`. Position = floats at `+0xfc`, `+0x10c`, `+0x11c` (x, height, z). Checked session 2: smooth, 194 m walked, 0 jumps at 10 samples a second. A second model at the same place moves with it, and two more follow 1.3 m higher (hands or held items, freed later). `radar.py`: `player_pos()`.
- **Player position, lagged:** `PlayerFallHelperModule` + `0x1b40`. It updates in steps. Probably the last safe ground position for the fall helper. Do not use it for an ESP.
- **AI position, live:** `HumanAI` object + `0x1cc0` = (x, height, z). Checked session 2: chasing zombies walked 86 to 115 m with 0 jumps. Idle `HumanAI` objects also hold a position there. `+0x1cc0` is `+0xb0` from a second `HumanAI` vtable pointer at `+0x1c10` (a base class inside the object).
- **AI health, real:** `HumanHealthModule` + `0x18` → pointer table; its first entry → a `lifecs` health element (0x40 bytes, in a pool). Element `+0x1c`, `+0x20`, `+0x24` = current health (three copies), `+0x2c`, `+0x30`, `+0x34` = maximum. **Writing 0 to the three current copies kills the zombie** (session 2: it fell and died within a moment; the game kept the 0). `radar.py`: `health_element()`, `health()`.
- **AI health, display copy:** `HumanAI` + `0x5e8` → object (no vtable) + `0x228` → `HumanHealthModule`. In it: `+0x28` current health, `+0x2c` maximum (floats). Only a copy: a write of 0 there does not kill, and the game rewrites it from the element within seconds or at the next hit. Maximum seen: 376 to 1416 for most zombies, 5568 for one large special zombie. A killed zombie keeps its module, with health 0. `radar.py`: `health_module()`, `health()`. The module points to `lifecs` pools at `+0x20` and `+0x40`.
- **AI world matrix:** the same position is in `CoWorldXform::Matrices` objects (matrix at `+0x10`, translation column at `+0x1c`, `+0x2c`, `+0x3c`; guess for the last two, from the stride). It holds the rotation too, which an ESP box or the aim may need. The link from `HumanAI` to its matrix is not known.
- **The AI heap:** all `HumanAI` and `CoAIProxy` objects, and many components (`CoWorldXform`, `CoVisibility`, `CoMotionTrail`, `CoPlayerSensor`, `CoArea`), sat in one private 64 MB region (session 2: `0xcb500000000`). A search of it for the `HumanAI` vtable takes 0.04 s. `radar.py` finds it from the first `HumanAI` (`heap_of()`).
- **Loot position (session 3):** `Container`, `ComplexContainer`, `BodyContainer`, `CollectableObject` + `0x140` = 3x4 row-major world matrix. Position = floats at `+0x14c`, `+0x15c`, `+0x16c` (x, height, z). Their `+0x8`, `+0x18` and `+0x40` all point to one other object (a separate address, checked session 3) that holds the same matrix at its `+0xf0`, like a `CModelObject` (guess: the model of the loot; its class was not read). `loot.py`: `loot_pos()`.
- **AI spawn point (static):** `CoAIProxy` + `0x270` = (x, height, z), copy at `+0x548`. It does **not** follow movement.
- `HumanAI` + `0x208` points `0x58` bytes into a `CoAIProxy`. Idle slots hold null there, or all share one empty proxy.
- `HumanAI` + `0x254`: held positions in session 1 (camp), zero in session 2. Not the live position.
- **Camera layout** (`CBaseCamera`, also `CRendererCamera`), all row-major floats:
  - `+0x10` view matrix 3×4 (world → camera). `+0x40` camera world matrix 3×4; the eye position is its last column (`+0x4c`, `+0x5c`, `+0x6c`). The camera looks down its −z axis.
  - `+0x80` projection 4×4: `[0.5263 0 0 0; 0 1.2572 0 0; 0 0 −1 −0.05; 0 0 −1 0]` in session 2. 1.2572 / 0.5263 = 2.389 = 3440 / 1440. Vertical field of view 77°.
  - `+0xc0` **view × projection 4×4**: clip = M · (x, y, z, 1). Visible when clip.w > 0. Screen x = (clip.x / clip.w + 1) · W / 2, screen y = (1 − clip.y / clip.w) · H / 2.
  - `+0x100` and on: more matrices (probably the previous frame), not needed.
- `PlayerFallHelperModule` + `0x08` points to `PlayerDI_PH`. `PlayerDI_PH` + `0x190` points to `CoAIObservablePlayerDI`, and that + `0x80` points to `CoMotionTrail` (a trail of the player's recent positions, 12 bytes apart).
- `cbs::CEntity` is 0x140 bytes and holds no position. Slots: +0x10 another `CEntity`, +0x18 `PrefabEntityComponent`, +0x50 type object (`IAISpawnerEntity`, `IGSObjectEntity`, `IVehicleEntity`, ...), +0xb8 `cbs::Prefab`, +0xc0 `DynamicMessagePipeSet`, +0xc8 `LevelDI`. No direct link from an entity to a `HumanAI` was found.

## Run-specific (heap addresses: lost when the game restarts)

- Do not copy heap addresses from old notes. `radar.py` finds the objects by vtable at start, and again after the player object dies.
- `instances.json` is from the session 3 loot class count (heap addresses, stale after a restart). `track.py` still hard-codes session 1 addresses.

## Scripts

Session 9: the 13 research scripts that the app does not import are in `research/` (`fallrec`, `fastsearch`, `fields`, `graph`, `healthwatch`, `heapwatch`, `lootwatch`, `movers`, `overlaybench`, `restartcheck`, `valuefind`, `velfind`, `velprobe`). Run them from the root: `python -m research.<name>`. `track.py` keeps only `sane()`, `flat()`, `fastest()`.

| File | Use |
|---|---|
| `mem.py` | `Process` class: read, `u32`, `u64`, `f32`, `vec3`, `regions()` (base, size, protect, type, reservation), `region_size()`. `Process(name, pid=...)`. |
| `rtti.py` | `instances <class...>` finds vtables and counts objects (saves `instances.json`). `owners <vtable>`, or an address for the objects near it. `classes_near()` names the objects around an address. Session 8: `resolve_vtables()` checks vtable constants by class name and finds moved ones. |
| `graph.py` | `python graph.py <start object> <position address> [depth] [bytes]`: walks named objects, lists fields that hold a nearby position. |
| `fields.py` | `python fields.py <position address> <class> <size>`: finds the position offset of a class by testing all instances. |
| `radar.py` | **The radar.** Live player position and all `HumanAI` within 150 m. Searches the AI heap every second for new AI. Rescans all memory after a death or sleep. Hold F8 to end; prints each AI path and top speed. |
| `overlay.py` | **The app** (session 3): the ESP overlay plus a control panel, in one process. Since session 4 the overlay is a raylib (GPU) window; `--tk` = the old tkinter canvas. One loop on the main thread drives both windows. Overlay: box (magenta zombie, blue human, gray unknown), health bar, distance and head dot per AI; a labeled circle per loot object (looted loot hidden). Panel (left of the game window): a switch per layer and loot type, a loot distance slider, the player's health, god mode, the nuke (off until "Armed"), the aim readout, a status line. One background scan finds everything (player, AI, cameras, loot, player health module): at the start, after a death or a sleep, and after each 50 m walked. F6 overlay on/off, F7 nuke (only when armed), hold F8 to end. Writes game memory only for god mode and the nuke, and only while their switch is on. |
| `cheats.py` | Session 7: the app's cheats that write each second or frame (`Cheats` mixin): player variables, sliders, durability, fury, no reload, one-hit melee, and `restore()` at the end. |
| `waypoint.py` | Session 7: `waypoint()` = the map waypoint position, for the app's F8 teleport. |
| `selfcheck.py` | Session 8, version safety: `CLASSES` (the class of each vtable the app uses), `resolve()` at the start (vtables and player variables by name), the `SelfCheck` mixin (a read-only check per feature; `passed()` before each write). |
| `fallrec.py` | Session 8, read-only: the player's height for 20 s after a long teleport (session 9), against the waypoint and the last safe position. Runs 1 hour. For the F8 fall-through. |
| `movement.py` | Session 9: the app's teleports (F8, F9, F10) and flight (`Movement` mixin): F3 NoClip, F2 flying, `fly_step()`. |
| `velfind.py` | Session 9, read-only: records the `CBulletPhysicsCharacter` and its btRigidBody at each game frame while you walk and jump, then lists the floats that follow the real speed. `python velfind.py analyze` reads `velfind.npz` again. |
| `velprobe.py` | Session 9: `python velprobe.py [up|body] [--write]`: F12 writes 8 m/s into an up-speed field once (dry run without `--write`). Found the up-speed source. |
| `loot.py` | Loot classes (vtable, label, color), `find_loot()` (75 s scan), `loot_pos()`, `spawned()` (session 8: false for loot that the game never placed in the world). |
| `godmode.py` | Dry run: prints both player health elements twice a second (75 s scan first). `--write`: god mode (**writes game memory**, not run yet). Hold F8 to end. |
| `aim.py` | Read-only aimbot part: the yaw and pitch error from the crosshair to the nearest living AI's head. Hold F8 to end. `--write` (session 5, not run yet): each F11 press writes `LookController +0x6c/+0x70` once, then prints the error 0.3 s later. |
| `teleport.py` | Session 5, **works**. Dry run: the model and the source position. `--write`: F9 marks, F10 writes the mark into `CBulletPhysicsCharacter +0xfd0`. The app has the same keys. Hold F8 to end. |
| `playervars.py` | Session 5. The game's 3111 player variables. `python playervars.py <regex>` lists name, offset, value, default (read-only). `CHEATS` (ammo, stamina, immortal, fall) and `apply()` for the app; `SCALED` (jump, speed) and `scale()` for the sliders (session 7); the guard (`check()`) writes only into a record of the right class. Session 8: names only; `resolve_offsets()` finds the offsets by name and the path by the `GETTER` signature. |
| `items.py` | Session 5. `melee_durability()`: `ItemDescWithContext +0xb0` of a melee item (type at `+0x8` = `ItemDescMelee`). |
| `valuefind.py` | Session 5. Exact-value search in steps: `python valuefind.py scan <value>`, then `filter <new value>` after the value changes in the game; prints the survivors and their classes when 30 or fewer. Found the durability. |
| `daynight.py` | Session 6. `DayNightCycle` time of day. Dry run: the game clock every 2 s. `--write HH:MM [address]`: one jump of the clock (**writes game memory**), then 5 s of readings. `set_time()`, `hhmm()` for the app. |
| `fastsearch.py` | Session 5, **works**. Dry run: the `search` containers within 10 m. `--write`: 0.0 into `+0x1f8` of each unsearched one, then watches them for 10 minutes. The app has it as a switch. |
| `lootstate.py` | `looted(p, obj)`: `+0x388 == 5` (searched or taken; `Container` and `ComplexContainer` only). `no_item()` (session 8): an active pickup whose model holds no item. Run it for a list of the loot within 30 m with state, kind, search time and items. |
| `lootwatch.py` | Records the loot within 40 m (and one pointer level down) until **F9**, then lists the fields that changed next to the player, and the loot objects that the game freed. `python lootwatch.py analyze` reads the saved `lootwatch.pkl` again. For the "already looted" state. |
| `nuke.py` | Without options: dry run, lists the living zombies within 50 m. `--write`: each F7 press sets their health to 0 (**writes game memory**). Hold F8 to end. Since session 3 it skips humans and unknown types (`aikind.py`). |
| `aikind.py` | `kind(p, human)` = the AI type name, `is_zombie(name)`. Run it for a list of the AI within 60 m with type and health. |
| `head.py` | `head_pos(p, human)` = world position of the head bone. Run it for the head height of the AI within 40 m. `python head.py bones [type]` (session 7): every bone of the nearest AI of that type within 60 m, with its height. |
| `camera.py` | `active_camera()`, `view_proj()`, `w2s()` (world to screen), `game_window()`. Run it to print the screen position of the 3 nearest AI every half second. Has self-checks for `w2s`. |
| `heapwatch.py` | `python heapwatch.py <player CModelObject address>`: records every float triple within 40 m of the player in the AI heap until F8, then lists the ones that walked on their own, with the object that holds each. Found the AI position. The heap base is hard-coded (see the comment). |
| `healthwatch.py` | Scans `HumanHealthModule`, `CoHealth`, `PlayerHealthModule`, records their first 0x200 bytes until F8, then lists floats that went down in steps. `python healthwatch.py analyze` filters the saved file again. Found the zombie health. |
| `movers.py` | Records the world matrix position of every `CModelObject` until F8, saves `movers.npz`, lists the models that walked. Found the live player position. |
| `paint.py` | The overlay windows (session 4): `RlPaint` (raylib) and `TkPaint` (tkinter), with the same drawing calls. Window styles: click-through, topmost, never active, no taskbar button. |
| `overlaybench.py` | `python overlaybench.py [boxes] [--tk]`: redraw speed of the overlay window with N boxes (no game needed), through `paint.py`. Prints the rate, the work a frame and the time in `paint.end()`. |
| `track.py` | Live tracker of a few fixed addresses. Hold F8 to end. Old addresses. |
| `watch.py` | F8-driven capture and offline filters. Used to find the first position. |
| `findptr.py` | Pointer search over all memory. Dead end, see below. Its `scan()` is the vtable scan that the other scripts use; `scan(..., memo=d)` (session 7) rescans only the reservations that held hits plus new regions. `python findptr.py selftest`. |

**Aim, round 3 (session 5): every F11 press now holds.** An exact-value search (all writable memory, the view still, then two turns) kept only 3 yaw places: `LookController +0x6c`, `+0x74` and `PlayerDI_PH +0xbb8`. `PlayerDI_PH +0xbb0..+0xbbc` = wrapped yaw, pitch, yaw, pitch; `turn()` writes it too. The error 0.3 s after a press: 0.03° to 0.31° on a still zombie, 1° to 8.5° on a walking or close one (the target moves after the snap). Next: hold-to-track; maybe aim above the head bone origin (not measured).

**Player variables (session 5): infinite ammo, stamina, durability.** The game has 3111 named player variables in one array (`playervars.py`; `python playervars.py <regex>` lists them). Path: global `gamedll+0x3921830` → `PlayerState` `+0xbe8` → array; record = class pointer, value (+8), default. Offsets come from the game's registration code (`mov dword [rsp+X], offset; lea r9; lea r8, [name]; mov dl, type`), so `names()` follows a game update. Used: `Firearms*InfiniteAmmo` (6) and `InfiniteArrows`, `InfiniteStamina` (bools), and the candidate `EfficientFightingDurabilityLostMul` = 0 (no "infinite durability" variable exists). App switches write them each second; off writes the defaults back once. A guard writes only into a `…PlayerVariable` record (the first version followed one pointer too many; the dry run showed garbage, nothing was written). User test: **stamina works** (some small actions with their own cost variables still use a little, e.g. `KickStaminaUsage`). **Ammo: infinite reserve, not "no reload"**: each magazine still empties (the magazine count is another value, not found yet; `valuefind.py`-style search on the bullet count). **The durability multiplier failed** (a weapon went 75 → 67), so it was removed.

**Melee durability (session 5): `ItemDescWithContext +0xb0`** (`items.py`). Found with an exact-value search in steps (21 → 17 → 15 on screen; 12 places left, most of them GUI copies: `GuiInventoryItemData +0x1b8/+0x1c0`, `GuiWeaponSelectorItem +0x78`). A write of 50 held, every copy followed within 55 s, and the next hits counted down from 50. 860 `ItemDescWithContext` objects; `+0x8` → the item type (`ItemDescMelee`, `ItemDescFirearm`, …); only melee items hold a durability there. The app's switch saves each melee item's value and writes it back when it drops (a repair raises the saved value). The search script was a scratch file (`valuefind.py`: `scan <value>`, then `filter <value>`; floats within 1 and exact int32). Note: killing the app with taskkill leaves the player-variable cheats on in the game (no restore).

User test: **melee durability works** ("a massive fight and the durability is still the same").

**Gun magazine (session 5): `InventoryItem +0x18`** (int32, `items.py`). `valuefind.py` 24 → 22 left 13 int32 places. A write of 25 held, and the weapon selector (`GuiWeaponSelectorItem +0x88/+0x90`) and `WeaponFireRightController +0x14/+0x150` followed within 0.01 s. `InventoryItem` embeds an `ItemDescWithContext` at `+0x50` (so the type is at `+0x58`: `ItemDescFirearm`, …). 211 `InventoryItem` objects, 14 guns; the gun in hand was held by `PlayerDI_PH +0x2b58` (`[count, item]`, candidate "item in hand"); others by inventory screen entries or a world pickup. The app's "No reload" switch keeps only the gun in hand (each frame), so enemies cannot get it. User test: **works, also after a weapon switch**, so `PlayerDI_PH +0x2b58 +0x8` is confirmed as the item in hand.

**The quit key is F1 since session 5** (it was F8, next to the nuke key F7: the user hit F8 by mistake and ended the app). The older sections of this file still say F8. F1 is read with `GetAsyncKeyState`, so the game keeps focus. Hold it for half a second. F1 ends **every** running script that uses `watch.key_down()` (the overlay and the nuke too). Keys in use: F1 end, F6 overlay, F7 nuke, F9 teleport mark (also `lootwatch.py`), F10 teleport to the mark, F11 aim turn (`aim.py --write`) and the session 5 probe.
Box colours: magenta zombie, orange Volatile (`overlay.TYPE_COLOR`), blue human, grey unknown type.

## What worked and what failed

- **Failed:** Cheat Engine "unknown value" scans for a position. The count stuck near 9,700, then 900. Bones, camera, and buffers follow the player too.
- **Failed:** the pointer search over all memory (`findptr.py`). The result grows 10 times at each level. Do not use it for this.
- **Failed (session 2):** a guessed field per class, checked against "is it near the player". Three fields looked right and were static or wrong.
- **Worked:** class names (RTTI) → vtable → scan memory for objects of that class. Fast and stable.
- **Worked:** the object graph walk (`graph.py`). About 7,000 named objects (56 MB) instead of 10 GB.
- **Worked:** record raw readings to a file, then try filters offline.
- **Worked best (session 2):** watch one memory block during a chase, keep values that move smoothly and on their own, then name the object around each (`heapwatch.py`). It needs no guess about the class or offset.
- Memory at `0x33d3...` with steps of `0x10000` is a ring of per-frame graphics buffers. Ignore it.
- Pitfall: `Process("python.exe")` can attach to a launcher stub. Pass `pid=`.
- Pitfall: `np.isin(uint64 array, list of ints)` mixes types. Pass `np.array(list, dtype=np.uint64)`.
- Pitfall: `winsound.Beep` was silent on this PC. Use a key press for cues.
- Pitfall: a value near the player is not proof of a live field. Test it with something that moves.
- Pitfall: an old object address can read as valid floats after the game frees it. Check that the object still starts with its vtable (`alive()` in `radar.py`).
- Pitfall: a test needs the user at the game. Say "it runs now, start" only after the script prints that it records, and check the log for player movement before you trust a "nothing moved" result.
- One vtable scan takes about 12 s since session 6 (75 s before). Do not put it in a loop. Search the AI heap instead (0.04 s).
- **Worked (session 2):** to find where a value really lives, write the visible field, then watch it. If the game puts it back, search outward by pointers (two levels) from the object for the exact current value. Test a write on one target before all of them.
- **Worked (session 2):** check world to screen with a screenshot of the game window (Pillow `ImageGrab`), boxes drawn at the projected positions, then look at the image. Wait for the camera to move before the grab, so the game is not paused.
- Pitfall: a pointer filter "below the lowest module base" drops every heap pointer here, because one module loads at `0x180000000`. Filter "not inside any module" instead.
- Pitfall: the pause menu shows a dimmed 16:9 picture in the middle of the ultrawide window. Do not check the boxes against it.

## Next steps, in order

The user's wish list for session 3 (2026-11-03): **teleport, aimbot, instant loot search, god mode.** Claude added items 2, 3, 7, 8, 9. Suggested order:

1. **Restart test (short).** After a game restart, check that the vtable offsets still give the same classes, and that `HumanAI+0x1cc0`, the model matrix, the camera and the health path still work. Everything below builds on them.
2. **Humans vs zombies.** Session 3: candidate found (`HumanAI +0x27c0` type name, `aikind.py`), see the session 3 section; the human side is untested. Older plan: find a field or class that separates them (type, faction, max-health range, the `CoAIProxy` spawner type). Then the nuke and the aimbot skip traders and quest NPCs. Do this before the aimbot.
3. **Zombie head position.** Session 3: found (`head.py`), see the session 3 section; a live screenshot check is still open. Older plan: bones (skinned mesh) or `CoWorldXform` matrices. Needed for the aimbot; also lets ESP boxes fit a crouched zombie.
4. **God mode.** Session 3 (lane B, static, strong candidate): `PlayerHealthModule` holds its health elements **inside** the object at `+0x10` and `+0x80` (not behind a pointer as for the AI); a third one at `+0x48` is all zero. In each element: current `+0x1c/+0x20/+0x24`, maximum `+0x2c/+0x30/+0x34`. Both read 164.2 of 475, and the HUD bar was 34.3 % full (164.2 / 475 = 34.6 %). The cheat table's path is confirmed: `PlayerDI_PH +0x1c8` (mask 48 bits; the top 16 bits are the count, 104) → module list; entry `0x56` = `PlayerHealthModule`, `0x42` = `PlayerStaminaModule` (`+0x10` = 5.0, `+0x18` = 5.0, maybe the maximum), `0x67` = `PlayerFuryModule` (`+0x14` = 100.0). `godmode.py`: dry run by default; `--write` keeps all six current copies at the maximum (not run yet). Test: dry run, take one zombie hit, see which element drops; then the user approves the first `--write`.
   Older plan: find the player's real health: `PlayerHealthModule` (1 object) probably uses the same `lifecs` path as `HumanHealthModule` (`+0x18` → table → element `+0x1c/0x20/0x24`). Test: `healthwatch.py` while a zombie hits the player. Then keep the element at the maximum.
5. **Aimbot.** Session 3 (lane B, static match while paused): the game's view angles are in `LookController` (`gamedll_ph_x64_rwdi.dll+0x2995548`, 1 object): `+0x6c` yaw, `+0x70` pitch, in degrees (copy at `+0x74/+0x78`, and at `PlayerDI_PH +0xbb0/+0xbb4`). Yaw = `atan2(fwd.z, fwd.x)`, pitch = `asin(fwd.y)`, fwd = the camera's −z column; they matched to 0.0001°. Yaw grows when the view turns right. `aim.py`: read-only dry run, prints the yaw and pitch error to the nearest living AI's head (feet + 1.6 m) twice a second. Tests: put the crosshair on a zombie head (errors near 0); turn and check that `LookController +0x6c` changes (the live store, not a copy). Then the first write of a new kind (the view angles) needs the user's OK.
   Older plan: read-only first: the angle from the camera forward axis (−z column of the camera world matrix) to a zombie head. Then turn the view: either write the game's view angles (find them: they change when the mouse moves) or send mouse input (`SendInput`). Ask before the first write of a new kind.
6. **Teleport.** Session 3 candidates (lane C, static): `PlayerFallHelperModule+0x8` → `PlayerDI_PH+0xf0` → `+0x20` → `CBulletPhysicsCharacter` (`engine_x64_rwdi.dll+0x18ae850`). It holds the feet position at `+0xfb8`, `+0xfd0`, `+0x1054`, `+0x10dc`. Its `+0x158` → `btRigidBody`, whose `+0x40` = (x, feet + 0.375, z): the Bullet physics origin, the most likely source that the model follows. `+0x10b4` and `PlayerDI_PH+0x54c` hold a slightly different position (role unknown). Test (a write): raise `btRigidBody+0x40` height by 0.5 m and watch `player_pos()` for 1 s; if it snaps back, try `+0xfb8` and its copies. The cheat table's teleport AOB is a getter (`call [vtable+0x500]`); its global (`gamedll+0x254f848`) is only a zero-vector fallback, so the table must take the pointer from a hook at run time.
   Older note: the model matrix is a render copy; writing it will not move the player. Find the physics position: the value that the model follows (watch it during a jump or a fall; `PlayerFallHelperModule` and `CoMotionTrail` are leads). Dry run first.
7. **Instant loot search.** Session 3: the search time is `+0x1f8` in a `Container` (see the session 3 section). Test (a write, dry run first): write 0.0 to `+0x1f8` of one container within 3 m, search it, then read `+0x1f8` again (the game may copy 1.0 back from `+0x57c`; then write `+0x57c` too). Older plan: find the search timer: a float that rises (or falls) only while the search key is held at a container. Record with the `heapwatch.py` method, then write its end value.
8. **Loot ESP.** Positions done and drawn (session 3). Still open: hide loot that is already searched or taken (`lootwatch.py` test), maybe a separate key to hide the loot markers.
9. **Infinite stamina and weapon durability, time of day.** Same method as health.
- Clean up: `track.py` still hard-codes session 1 addresses. Delete it or point it at `radar.py` functions.

## Leftover data

`candidates.CT`, `candidates2.CT`, `run1.pkl`: deleted in session 9. The `*.npz` recordings, `instances.json` and `overlay_settings.json` are run data: kept out of git (`.gitignore`).

## Resume prompt

> Continue the learning project in C:\dev\Github\Aimbot (Dying Light: The Beast, single-player, offline). Read NOTES.md first, from the top: "End of session 9", then the "Session 9" section.
>
> Rules: education only, offline. File edits are allowed. Game memory writes are allowed, but each new kind of write gets a read-only dry run first. The game runs as administrator, so this terminal must be elevated. The quit key of every script is F1. Start a script, wait for its ready line, and only then tell me to act. Explain each step.
>
> Goal of this session, in this order:
> 1. Flying (F2): did the game crash right after "flying on" in session 9? Test flying again with a recorder: rise, hover, a wall, Shift.
> 2. The release on GitHub: the decisions and the clean-up listed under "End of session 9", then a local git repository. Do not push without my OK.
> 3. Hardening across game versions (field offsets inside objects).
