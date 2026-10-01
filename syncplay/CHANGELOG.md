## Build 25 - A cleaner look
- The window is calmer: the header keeps just Copy invite and a "..." menu (subtitles, library, voice, private room), room options live behind the sliders icon, the room shows as "Room: name - change", and an empty shared playlist folds down to one line.
- The people list shows everyone's ready state in words (Ready / Not ready), the file each person has open (amber if it differs from yours, reason in the tooltip) and the subtitle they have on when they use Marquee.
- The Ready button is slimmer and says where you stand: "Not ready" or "Ready". The status bar says just "Connected" (address on hover), with your sync note beside it.
- Menus, the settings window, dialogs, the tray menu and message boxes all use the same line icons, dark/light colours and one blue primary button. Radio buttons, table headers and the settings sidebar are fixed for dark mode.

## Build 24 - Straight into the room, resume, notifications, voice
- The app now opens straight into your last room once your first setup is done. File > Connection settings brings the start window back (Shift at launch or --force-gui-prompt also work), and File > Skip start window turns it off again.
- Resume where you left off: open the same video again and a bar offers to continue from the saved position (or start over).
- Your own sync indicator in the status bar shows how far you are from the room; click it, or use Playback > Who's behind? (Ctrl+Shift+Y), to ask everyone where they are and get a one-line summary in chat.
- Desktop notifications when someone joins, leaves or mentions you, from a tray icon (toggle in the tray menu).
- A Voice button starts a private Jitsi call for the room and shows Join voice for everyone else; links in chat are now clickable.

## Build 22 - Playlist files and pause on drop-out
- File > Open playlist file... (Ctrl+Shift+O) loads a text or .m3u8 playlist, and File > Reload playlist file (Ctrl+Shift+L) reads the same file again, for when another program rewrites it. A file passed with --load-playlist-from-file is remembered too.
- New switch "Pause if someone drops out": when someone leaves or loses connection everyone pauses, and playback resumes by itself once they are back and ready. Pressing play yourself cancels the wait.

## Build 19 - Narrow windows, subtitle note, nicer ready button
- The window can now be as narrow as a phone-sized column beside your video: below about 860 px the chat stacks above the people table, the header buttons shrink to icons and the size/length columns hide.
- The status bar says which subtitle is on for the current video, or that automatic subtitles are on.
- The Ready bar is redrawn: taller, softly shaded, with a round tick when you're ready.

## Build 17 - Everything ties together
- Menus, the people table and the playlist use the same clean line icons as the buttons; the accent blue now comes from the logo.
- Buttons follow one language: green means go (Ready, Start, Use subtitle), blue is secondary. About is redrawn, and progress bars (including the update download) match.
- The app offers Start menu and desktop shortcuts once (Help > Add shortcuts any time), and Help > Uninstall removes it cleanly.
- If the connection drops, a banner appears with a Reconnect now button and the status dot pulses; the title bar shows your room and how many are ready.

## Build 15 - A nicer first start
- The window shown while the app unpacks itself for the first time (and after a new .exe) is redrawn to match the app: dark or light like Windows, the logo, a smooth progress bar and a plain status line. It's sharp on high-DPI screens and you can drag it.

## Build 13 - Start window to match
- The start (configuration) window now matches the main window: the same panels, and one green "Store configuration and run" button. Errors and confirmations show as soft notices.

## Build 11 - A modern Syncplay
- The window keeps Syncplay's familiar two panes, restyled: flat dark (or light) surfaces, rounded panels, roomier rows, muted timestamps and coloured names in chat.
- The people table has round ready / not-ready badges, and Size, Length and File columns that turn red when they differ from yours.
- A slim progress bar shows where the room is in the video.
- Subtitles, Library, Copy invite and Private room are small buttons above the table.
- When you're alone in a room it offers to copy an invite; the shared playlist is a slim strip until something is queued.
- The secure-connection padlock moved to the status bar.
- If OpenSubtitles rejects a saved username/password, downloads still work with the API key alone; the key box shows dots when a key is saved.

## Build 9 - Invite links, private rooms and safer updates
- Copy invite now gives a link that opens the app straight in your room (Windows uses this app for it; switch it off in Help > Open invite links with this app).
- New "Private room" button: a room with a random name strangers can't guess, with its invite copied for you. New installs start in a random room instead of a guessable one.
- Updating restarts straight back into your room and tells you which build you're on.
- If a new version ever fails to start, the app puts the previous version back by itself.
- New Update log (Help > Update log) shows what changed in every build.
- Subtitles: your language is remembered, and "Load subtitles automatically in my language" fetches them for you when a video opens (nothing is shared with the room).
- VLC is found automatically and preferred; the "No media directories" warning no longer greets new users.
- The updater always picks the highest-numbered release and refuses releases with broken files.

## Build 7 - Reliable update check
- The update check looks at every release and takes the highest build number.

## Build 3 - One-click updates
- Help > Update downloads, installs and restarts with no questions.
- Your OpenSubtitles key is remembered between sessions.
- The VLC position-accuracy warning no longer appears in the chat.

## Build 1 - First version
- Find and share subtitles for the whole room (OpenSubtitles, or straight from a file).
- Browse your own TorBox library and play from it.
- A redesigned window with an "always ready" switch, dark and light themes and a new logo.
- One file to open: no Python or extra setup needed.
