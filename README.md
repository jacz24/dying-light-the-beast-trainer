# Dying Light: The Beast Trainer

An open-source trainer for the single-player game, and a study of how game memory works. It gives an ESP overlay, aim
assist, teleports, NoClip and flying, and the usual player cheats. All of it is Python that you can read before you run it.

Unofficial. Not affiliated with or endorsed by Techland. "Dying Light" is a trademark of its owner.

> **Single-player only.** The game has online co-op for up to 4 players (you and 3 friends). This trainer is not made or supported for co-op
> sessions, and we do not endorse its use there.

## What it does

| Feature | Key or panel | What it changes |
|---|---|---|
| ESP: a box, health bar, distance and head dot per enemy (magenta zombie, orange Volatile, blue human, green friendly NPC) | F6 shows or hides | nothing (read-only) |
| Loot markers: containers, pickups, bodies, collectables, within a distance you set; looted ones hidden | panel | nothing (read-only) |
| Aim: track the nearest head while F11 is held; "smart aim" while you fire a gun | F11, panel | the view angles |
| Teleport: mark a place, go back to it, or go to the map waypoint | F9 mark, F10 go, F8 waypoint | the player position |
| NoClip: fly through walls | F3 | the player position and speed |
| Flying: fly, walls stop you | F2 | the player speed |
| God mode, immortality, no fall damage, infinite stamina, ammo and arrows, no reload, no durability loss, infinite fury | panel switches | the game's own player variables and health |
| One-hit melee, the nuke (kills hostile enemies within 50 m; it must be armed first) | panel, F7 | enemy health |
| Super jump and speed (x1 to x4), instant loot search, time of day (hold day or night) | panel | player variables, loot search time, the game clock |

Flight keys: W and S along the view, A and D sideways, Space up, Ctrl down, Shift for x4 speed (10 m/s, 40 m/s with Shift).
Hold F1 for half a second to quit. The app then sets each player variable back to the game's value.

## Requirements

- Windows 10 or 11, and the game in **windowed** mode (the overlay sits on the game's window).
- For the source only: Python 3.14 (tested with 3.14.3), then `pip install -r requirements.txt`.
- An **elevated** (administrator) terminal: the game runs as administrator, so a normal process cannot read its memory.
- Tested on game version 1.6.0.0. After a game update, a feature whose fields moved stays off (see "Safety").

## Download

`BeastTrainer.exe` is on the Releases page. GitHub Actions builds it from the tagged source (`.github/workflows/release.yml`)
and puts its SHA-256 next to it; check it with `Get-FileHash BeastTrainer.exe`. Windows asks for admin rights when it
starts. The exe is not signed, and antivirus software may flag it, because it reads and writes another program's memory.
If you do not trust a binary, run the source (below): it is the same code.

## Run

1. Start the game and load a save.
2. Start `BeastTrainer.exe`, or, in an elevated terminal in this folder: `python overlay.py`
3. The control panel opens at once. The overlay starts after the first memory scan (about 15 s). The settings are saved
   in `overlay_settings.json` next to the exe or the script.

Options: `--dry-fly` (NoClip and flying only print what they would write), `--tk` (the older tkinter overlay).

## Safety

- **Read-only unless a switch is on.** The memory handle can write only after the first write that you ask for.
- **A self-check before every write.** Each feature reads its fields first and checks that they make sense (for example:
  the teleport field is at the player's feet; the three copies of a health value agree). A feature whose check fails
  stays off. So after a game update the app turns a feature off, and it does not write into the wrong place.
- **Found by name, not by address.** Classes are found by their RTTI names, and the game's 3111 player variables by their
  registered names, so these survive most updates.
- **Each kind of write was tested read-only first** (a "dry run"), then once in the game, before it went into the app.
- Writes to game memory can crash the game. Back up your saves.
- Antivirus software can warn about a program that reads and writes another program's memory. Read the source.

## How it works

1. **Find objects by class.** The game is C++ with RTTI. Each class has a vtable, and every object of the class starts
   with a pointer to it. One scan of memory for a vtable address lists every object of that class: the player, each AI,
   the cameras, each loot container. (`rtti.py`, `findptr.py`)
2. **Find fields by behaviour.** A field is the one that changes when the thing it stands for changes: record an object
   while zombies walk, while the player jumps, while a zombie takes hits, then keep the values that follow. (`research/`)
3. **World to screen.** The active camera holds a view-projection matrix; each world position goes through it to a
   pixel. (`camera.py`)
4. **A GPU overlay.** A transparent, click-through raylib window on top of the game draws the boxes. (`paint.py`)
5. **Writes.** The trainer writes the game's own values: the player variables (`playervars.py`), the physics position
   and speed of the player (`teleport.py`, `movement.py`), the health elements of enemies (`nuke.py`).

`NOTES.md` is the full research log: what was measured, what worked, and the dead ends.

## Layout

- `overlay.py`: the app (overlay, control panel, main loop). Mixins: `cheats.py`, `movement.py`, `selfcheck.py`.
- Game knowledge, one module per topic: `radar.py` (player and AI), `aim.py`, `head.py`, `camera.py`, `loot.py`,
  `lootstate.py`, `godmode.py`, `nuke.py`, `playervars.py`, `items.py`, `daynight.py`, `teleport.py`, `waypoint.py`,
  `aikind.py`. Low level: `mem.py`, `rtti.py`, `findptr.py`, `paint.py`, `watch.py`, `track.py`.
- `research/`: the tools that found the fields. Run them from this folder: `python -m research.<name>`.

## Takedown

If you hold the rights to the game and want this repository removed, open an issue, and it will be taken down.

## Licence

MIT. See `LICENSE`.
