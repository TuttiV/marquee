## Build 32 - A Linux package for Mint and Ubuntu
- Linux: a proper package to install (marquee_32_amd64.deb). Open it, click Install and enter your password once. It adds mpv if you have no video player, puts the app in the applications menu with its icon, and invite links open it. Made for Linux Mint 21 and 22 and Ubuntu 22.04 or newer.
- Updates still install from inside the app, without a password: each person runs their own copy of the app files, which Help > Update keeps current. Installing a newer package brings that copy up to date too.
- Help > Uninstall removes the package (your system asks for your password). You can also remove it like any other package.
- Coming from the .tar.xz version: the first start from the package moves your desktop shortcut over and removes the old copy. Your settings stay.
- The Linux downloads are smaller: Qt's developer tools are no longer included.

## Build 31 - A real Windows Setup wizard
- New Windows Setup (Setup .exe): the usual wizard with Welcome, a page to pick the install folder (Browse...), a page with separate ticks for the Start menu and desktop shortcuts, and a Finish page that can start the app. No administrator rights needed; it installs to your user's Programs folder by default.
- Setup adds the app to Settings > Apps (Apps & features) with an Uninstall button, and Help > Uninstall hands over to it. Uninstalling asks whether to keep your settings.
- Running Setup again repairs or upgrades the app in place and keeps your shortcut choices. A copy unpacked by the single .exe is tidied away once Setup has installed it elsewhere.
- In-app updates keep working as before, and the version shown under Settings > Apps follows them.

## Build 30 - The server list is back, and the latest Syncplay
- Connection settings: the server box shows its drop-down arrow again, so you can pick one of the public Syncplay servers (the current list from syncplay.pl, or syncplay.pl:8995 to 8999 when update checks are off). You can still type any other server. Every other drop-down got the arrow back too.
- Includes the latest Syncplay changes (upstream 1.7.7 development, October 2026): a fix for a crash and endless reconnecting when a server refuses the connection (it only ever happened on macOS).

## Build 29 - A design pass: six new themes and a clearer people list
- Six new themes under Window > Theme, each following its own project's colour guide: Catppuccin Mocha and Latte, Rosé Pine and Rosé Pine Dawn, Nord, and Tokyo Night. The menu is grouped into standard, our own looks and community themes.
- People list: everyone has a round initial in their chat colour, "Not ready" is a calm grey (red now only means a problem, like a different file), and the column header row is gone.
- Easier reading: chat and the message box use Windows' 14px body size, nothing in the window is smaller than 12px, and the room name is no longer italic.

## Build 28 - Fixes, a proper installer and a softer light mode
- Fixed: a chat message could make the other person's app drop off the server and come straight back ("has left", then "has joined"). It happened when their video player wasn't connected yet. If the app can't handle a message from the server it now writes the error to its log and stays connected.
- Fixed: Restart after an update brought back the old version until you closed the app completely. It now restarts straight into the new one. (The update to this build still needs that one full close and reopen.)
- The install window works like a real installer: Cancel, or closing it, quits without installing and it asks again next time. On Windows the files it had unpacked are removed too.
- Light mode is calmer: built on a cool grey scale with nothing pure white, white-ish fields and buttons with clear borders, a soft blue resume bar, and the chat scrollbar only appears when there is something to scroll.
- Voice calls are gone (the Voice button and menu entry); nobody used them.

## Build 27 - Linux, and a real install window
- New install window on first start: pick the install folder (Browse...) and tick the shortcuts you want: Start menu (or the Linux applications menu) and desktop, each on its own. Help > Install and shortcuts changes them later or moves the app to another folder.
- Linux version (for Linux Mint, Ubuntu and similar 64-bit systems): a self-contained download with everything included; you only need mpv or VLC. Install it with the same window; invite links, updates and uninstall work as on Windows.
- Window > Theme > Same as system now also follows a dark desktop on Linux.
- Fixed: on Linux, if VLC closed before it was ready the app froze at full CPU.
- Dialog buttons no longer show old-style icons on Linux.

## Build 26 - Themes, shared subtitle delay, emoji and a smoother start
- Window > Theme: Same as Windows, Dark, Light and three new looks: Cinema (warm black and gold), Midnight (true black with cyan) and Sand (warm paper-like light). It switches instantly and is remembered.
- Subtitles > earlier / later (Ctrl+Shift+[ and ]) move the subtitle delay for everyone using this app at once, in 0.1 s steps; a new video starts at zero. Works with mpv (VLC can't change it from outside and says so).
- Help > Copy diagnostics copies the version, connection state and recent log to the clipboard to paste when asking for help. Passwords, keys, your name, room and file names are left out.
- File > Reopen player (Ctrl+Shift+R) restarts the app with the same video and room, for a player that froze.
- Chat: an emoji button next to Send, :shortcodes: like :fire: and :tada: turn into emoji, and a message that is only emoji shows large like a reaction.
- Opening an invite link now joins straight away when a player and name can be found (no start window), and the chat says who is already in the room.
- The Ready button glides between Not ready and Ready, with the tick drawing itself.
- Updates now download quietly in the background. A slim bar says the new build is ready with Restart now or Later; ignore it and it installs the next time the app starts.
- The people table redraws as soon as someone's subtitle changes.

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
