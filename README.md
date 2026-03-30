# JSaB Save Decoder/Encoder/Editor

A save file editor for Just Shapes & Beats that lets you decode the game's binary save format into readable JSON, edit it, and re-encode it back into a valid save file.

## Save File:

`C:\Program Files (x86)\Steam\userdata`
Replace {YOUR SteamID} with your actual Steam ID (a numeric folder name).
If there are more Steam users and you do not know which one is yours use:
[steamid.io](steamid.io) - steamID3 without [U:1:

## What's editable, and what isn't

You can safely edit many fields in the save file, such as:
Story progress flags (hasCompletedStoryMode, hasCompletedLostChapter, etc.)
Settings (musicVolume, sfxVolume, colorBlind, kbLayout, etc.)
Arcade completion ranks (modelCompletion values per level)

Beat Points cannot be edited
If you're here hoping to give yourself a ton of Beat Points — unfortunately that's not possible through save file editing. 
During my research into the game's code (GameAssembly.dll), I discovered that the bp field is stored internally as a SecureNumber — an encrypted value with a randomly generated key and an integrity check. This means:
The value stored in the save file is not the raw BP number you see in-game
Manually changing it will either display 0 BP, corrupt your save, or reset your entire progress
The game includes a built-in cheat detection system (UI_CheatDetected) that triggers when the value doesn't match its internal checksum

This tool is intended for legitimate save management.. things like backing up your progress, restoring a broken save.

## Notes:

- ALWAYS back up your save file before making any changes, i don't care if you're "experienced" the game just loves to work in unexpected ways.
- The game must be closed when replacing the save file.
- This tool was tested on version 108052 / v.16.50.
- Feel free to update this code, in-fact i encourage it. There has to be a way to edit BP somehow, i just was not able to do it myself.