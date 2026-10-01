# coding:utf8

"""English dictionary"""

# Filename, dictionary name and LANGUAGE-TAG value based on ISO country code. Language tag listed at https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-lcid/a9eac961-e77d-41a6-90a5-ce1a8b0cdb9c?redirectedfrom=MSDN

en = {
    "LANGUAGE": "English",
    "LANGUAGE-TAG": "en",

    # Strings for Windows NSIS installer
    "installer-language-file": "English.nlf", # Relevant .nlf file at https://github.com/kichik/nsis/tree/master/Contrib/Language%20files
    "installer-associate": "Associate Syncplay with multimedia files.",
    "installer-shortcut": "Create Shortcuts in following locations:",
    "installer-start-menu": "Start Menu",
    "installer-desktop": "Desktop",
    "installer-quick-launch-bar": "Quick Launch Bar",
    "installer-automatic-updates": "Check for updates automatically",
    "installer-uninstall-configuration": "Delete configuration file.",

    # Client notifications
    "config-cleared-notification": "Settings cleared. Changes will be saved when you store a valid configuration.",

    "relative-config-notification": "Loaded relative configuration file(s): {}",

    "connection-attempt-notification": "Attempting to connect to {}:{}",  # Port, IP
    "reconnection-attempt-notification": "Connection with server lost, attempting to reconnect",
    "reconnect-menu-triggered-notification": "Manual reconnect initiated - will attempt fresh connection to {}:{} in 2 seconds...",
    "reconnect-failed-no-host-error": "Cannot reconnect: no server information available",
    "reconnect-failed-no-port-error": "Cannot reconnect: invalid server configuration",
    "reconnect-failed-error": "Reconnection failed: {}",
    "disconnection-notification": "Disconnected from server",
    "connection-failed-notification": "Connection with server failed",
    "connected-successful-notification": "Successfully connected to server",
    "retrying-notification": "%s, Retrying in %d seconds...",  # Seconds
    "reachout-successful-notification": "Successfully reached {} ({})",

    "rewind-notification": "Rewinded due to time difference with {}",  # User
    "fastforward-notification": "Fast-forwarded due to time difference with {}",  # User
    "slowdown-notification": "Slowing down due to time difference with {}",  # User
    "revert-notification": "Reverting speed back to normal",

    "pause-notification": "{} paused at {}",  # User, Time
    "unpause-notification": "{} unpaused",  # User
    "seek-notification": "{} jumped from {} to {}",  # User, from time, to time

    "current-offset-notification": "Current offset: {} seconds",  # Offset

    "media-directory-list-updated-notification": "Syncplay media directories have been updated.",

    "room-join-notification": "{} has joined the room: '{}'",  # User
    "left-notification": "{} has left",  # User
    "left-paused-notification": "{} left, {} paused",  # User who left, User who paused
    "playing-notification": "{} is playing '{}' ({})",  # User, file, duration
    "playing-notification/room-addendum": " in room: '{}'",  # Room

    "not-all-ready": "Not ready: {}",  # Usernames
    "all-users-ready": "Everyone is ready ({} users)",  # Number of ready users
    "ready-to-unpause-notification": "You are now set as ready - unpause again to unpause",
    "set-as-ready-notification": "You are now set as ready",
    "set-as-not-ready-notification": "You are now set as not ready",
    "autoplaying-notification": "Auto-playing in {}...",  # Number of seconds until playback will start

    "identifying-as-controller-notification": "Identifying as room operator with password '{}'...",
    "failed-to-identify-as-controller-notification": "{} failed to identify as a room operator.",
    "authenticated-as-controller-notification": "{} authenticated as a room operator",
    "created-controlled-room-notification": "Created managed room '{}' with password '{}'. Please save this information for future reference!\n\nIn managed rooms everyone is kept in sync with the room operator(s) who are the only ones who can pause, unpause, seek, and change the playlist.\n\nYou should ask regular viewers to join the room '{}' but the room operators can join the room '{}' to automatically authenticate themselves.",  # RoomName, operatorPassword, roomName, roomName:operatorPassword

    "other-set-as-ready-notification": "{} was set as ready by {}", # User set as ready, user who set them as ready
    "other-set-as-not-ready-notification": "{} was set as not ready by {}", # User set as not ready, user who set them as not ready

    "file-different-notification": "File you are playing appears to be different from {}'s",  # User
    "file-differences-notification": "Your file differs in the following way(s): {}",  # Differences
    "room-file-differences": "File differences: {}",  # File differences (filename, size, and/or duration)
    "file-difference-filename": "name",
    "file-difference-filesize": "size",
    "file-difference-duration": "duration",
    "alone-in-the-room": "You're alone in the room",

    "different-filesize-notification": " (their file size is different from yours!)",
    "userlist-playing-notification": "{} is playing:",  # Username
    "file-played-by-notification": "File: {} is being played by:",  # File
    "no-file-played-notification": "{} is not playing a file",  # Username
    "notplaying-notification": "People who are not playing any file:",
    "userlist-room-notification":  "In room '{}':",  # Room
    "userlist-file-notification": "File",
    "controller-userlist-userflag": "Operator",
    "ready-userlist-userflag": "Ready",

    "update-check-failed-notification": "Could not automatically check whether Syncplay {} is up to date. Want to visit https://syncplay.pl/ to manually check for updates?",  # Syncplay version
    "syncplay-uptodate-notification": "Syncplay is up to date",
    "syncplay-updateavailable-notification": "A new version of Syncplay is available. Do you want to visit the release page?",

    "mplayer-file-required-notification": "Syncplay using mplayer requires you to provide file when starting",
    "mplayer-file-required-notification/example": "Usage example: syncplay [options] [url|path/]filename",
    "mplayer2-required": "Syncplay is incompatible with MPlayer 1.x, please use mplayer2 or mpv",

    "shared-subtitle-picked-notification": "{} picked the subtitle '{}' - loading it",
    "subtitle-search-started-notification": "Searching OpenSubtitles...",
    "subtitle-search-none-notification": "No subtitles found on OpenSubtitles for this file",
    "subtitle-search-pick-notification": "Type /pick [number] to use one of these subtitles for everyone in the room",
    "subtitle-download-started-notification": "Downloading subtitle '{}'...",
    "subtitle-not-shared-notification": "Loaded for you only - the server doesn't support subtitle sharing",
    "subtitle-search-no-file-error": "Open a file first so Syncplay knows what to search for",
    "opensubtitles-not-configured-error": "Set openSubtitlesApiKey (and optionally openSubtitlesUsername/openSubtitlesPassword) in your Syncplay config file - get a free key at opensubtitles.com/consumers",
    "subtitle-search-failed-error": "Could not get subtitles from OpenSubtitles",
    "subtitle-pick-invalid-error": "Invalid choice - run /subs first and pick a number from the list",
    "subtitles-menu-label": "&Subtitles",
    "findsubtitles-menu-label": "&Find subtitles...",
    "sharesubtitlefile-menu-label": "&Share subtitle file...",
    "loadsharedsubtitle-menu-label": "&Load last shared subtitle",
    "sharesubtitlefile-dialog-title": "Choose a subtitle file to share",
    "sharesubtitlefile-dialog-filter": "Subtitles (*.srt *.ass *.ssa *.vtt)",
    "subtitle-dialog-title": "Find subtitles",
    "subtitle-dialog-no-file": "No file open - open a video to search for subtitles",
    "subtitle-dialog-pill-room": "Loads for everyone in the room",
    "subtitle-dialog-pill-solo": "Only for you (server can't share subtitles)",
    "subtitle-dialog-setup-title": "Your OpenSubtitles account (optional)",
    "subtitle-dialog-setup-explanation": "Subtitle search works without an account, using a free public catalogue. Adding your own free OpenSubtitles API key gives exact file-hash matches and more results. Your account name and password are optional and raise the daily download limit.",
    "subtitle-dialog-back-button": "Back",
    "subtitle-dialog-forget-button": "Forget my key",
    "opensubtitles-key-saved": "Key saved - it will be remembered next time",
    "opensubtitles-save-failed-error": "Could not save your OpenSubtitles key: {}",
    "opensubtitles-source-own": "Using your own OpenSubtitles key (ending {}). It is saved for next time.",
    "opensubtitles-source-builtin": "Using the key built into this app. Enter your own below to use that instead.",
    "opensubtitles-source-none": "No key set - using the free public catalogue.",
    "subtitle-dialog-settings-button": "Account...",
    "subtitle-dialog-settings-tooltip": "Use your own OpenSubtitles API key for better matches",
    "subtitle-dialog-public-hint": "Using the free public catalogue. Add your own OpenSubtitles API key under Account for exact matches.",
    "subtitle-dialog-get-key-button": "Get a free API key",
    "subtitle-dialog-api-key-placeholder": "API key",
    "subtitle-dialog-username-placeholder": "OpenSubtitles username (optional)",
    "subtitle-dialog-password-placeholder": "OpenSubtitles password (optional)",
    "subtitle-dialog-save-button": "Save and search",
    "subtitle-dialog-key-required": "Enter your API key to continue",
    "subtitle-dialog-language-label": "Languages",
    "subtitle-dialog-language-placeholder": "en, sv",
    "subtitle-dialog-language-tooltip": "Comma-separated language codes, e.g. en, sv, pt-BR",
    "subtitle-dialog-search-button": "Search",
    "subtitle-dialog-column-release": "Release",
    "subtitle-dialog-column-language": "Language",
    "subtitle-dialog-column-downloads": "Downloads",
    "subtitle-dialog-empty": "No results yet.\nPress Search to look for subtitles that match the file you're watching.",
    "subtitle-dialog-found": "{} subtitles found - double-click one to use it",
    "subtitle-dialog-exact-tooltip": "Exact match for this video file",
    "subtitle-dialog-hi-tooltip": "Includes hearing-impaired annotations",
    "subtitle-dialog-share-checkbox": "Load for everyone in the room",
    "subtitle-dialog-use-button": "Use subtitle",
    "subtitle-dialog-close-button": "Close",
    "subtitle-dialog-loaded-room": "Loaded '{}' for everyone in the room",
    "subtitle-dialog-loaded-solo": "Loaded '{}' for you",
    "always-ready-on-notification": "Always ready is on - you'll stay ready when you pause or change file",
    "always-ready-off-notification": "Always ready is off",
    "always-ready-label": "Always ready",
    "always-ready-status": "You're always ready",
    "always-ready-tooltip": "Stay marked as ready automatically, so pausing or changing file never un-readies you",
    "always-ready-menu-label": "&Always ready",
    "commandlist-notification/alwaysready": "\tar [on|off] - toggle always ready (stay ready when pausing or changing file)",
    "chip-subtitles-label": "Subtitles",
    "chip-invite-label": "Copy invite",
    "chip-invite-tooltip": "Copy the server and room details to share with friends (your password is never copied)",
    "invite-heading": "Join me on Syncplay Marquee!",
    "invite-link-note": "(The link opens the app; if it doesn't, use the details below.)",
    "chip-private-label": "Private room",
    "chip-private-tooltip": "Start a new room with a random name that strangers can't guess, and copy the invite",
    "private-room-created-notification": "Private room created - invite copied to the clipboard",
    "invite-other-server-notification": "That invite is for another server ({}:{}). Close this window and open the link again.",
    "invite-invalid-notification": "That invite link isn't valid.",
    "invite-joined-notification": "Joined room {} from an invite link.",
    "invite-links-menu-label": "Open invite links with this app",
    "invite-server": "Server: {}   Port: {}",
    "invite-room": "Room: {}",
    "invite-password-note": "The server needs a password - ask me for it",
    "invite-copied-notification": "Invite copied to the clipboard",
    "status-connecting": "Connecting...",
    "status-connected": "Connected",
    "status-room": "Room: {}",
    "status-users": "{} watching \u00b7 {} ready",
    "subtitle-reference-needs-key-notification": "{} picked the subtitle '{}' from OpenSubtitles.com - add your own API key (Find subtitles > Account) to load it",
    "torbox-menu-label": "My &TorBox library...",
    "torbox-dialog-title": "My TorBox library",
    "torbox-save-failed-error": "Could not save your TorBox API key: {}",
    "torbox-forget-button": "Forget key",
    "torbox-key-saved": "API key saved - it will be remembered next time",
    "torbox-no-key-error": "Add your TorBox API key first (torbox.app > Settings)",
    "torbox-setup-title": "Connect your TorBox account",
    "torbox-setup-explanation": "Syncplay lists what's already in your own TorBox account so you can play it. Your API key is only used to talk to TorBox and is never shared with other users. Find it on torbox.app under Settings.",
    "torbox-key-placeholder": "TorBox API key",
    "torbox-get-key-button": "Open TorBox settings",
    "torbox-save-button": "Save and load library",
    "torbox-back-button": "Back",
    "torbox-search-placeholder": "Search your library by title or file name...",
    "torbox-refresh-button": "Refresh",
    "torbox-key-button": "API key...",
    "torbox-filter-resolution": "Resolution",
    "torbox-filter-codec": "Codec",
    "torbox-filter-hdr": "HDR",
    "torbox-filter-language": "Language",
    "torbox-filter-minsize": "Min size",
    "torbox-filter-maxsize": "Max size",
    "torbox-filter-any": "Any",
    "torbox-play-button": "Play for me",
    "torbox-room-button": "Play for the room",
    "torbox-share-tooltip": "Adds the stream link to the shared playlist. Anyone in the room can open that link, which uses your TorBox account.",
    "torbox-loading": "Loading your library...",
    "torbox-found": "{} files match - double-click one to play it",
    "torbox-no-match": "No files match your search and filters",
    "torbox-empty": "Nothing streamable in your account yet.\nItems show up here once they're ready in TorBox.",
    "torbox-fetching-link": "Getting a stream link for '{}'...",
    "torbox-playing": "Opened '{}'",
    "torbox-playing-room": "Added '{}' to the room playlist",
    "torbox-playlist-disabled-notification": "Shared playlists are off, so this is playing for you only",
    "chat-placeholder": "Message the room...",
    "now-no-room": "Not in a room",
    "now-no-file": "No file open",
    "now-people": "{} watching",
    "now-ready": "{}/{} ready",
    "welcome-chat-line": "Welcome! Say hi to the room below.",
    "contact-short": "Tip: press Ctrl+Shift+S to find subtitles for the video you are watching.",
    "people-different-file": "Different file",
    "people-different-name": "different file name",
    "people-different-size": "different size",
    "people-different-duration": "different length",
    "people-no-file": "No file open",
    "update-source-prompt": "Enter the GitHub repository that publishes updates for this app (for example yourname/yourrepo):",
    "update-repo-invalid": "That doesn't look like a GitHub repository. Use the form owner/name, for example yourname/yourrepo.",
    "update-source-menu-label": "Update &source...",
    "update-source-saved": "Updates will now come from github.com/{}",
    "private-update-uptodate": "You're up to date (build {}).",
    "private-update-failed": "Couldn't update: {}",
    "update-installed-notification": "Updated to build {}.",
    "update-not-installed-notification": "The update was downloaded but couldn't be installed yet. Close and reopen the app to try again (details are in syncplay.log).",
    "update-rolled-back-notification": "Build {0} didn't start properly, so the app went back to build {1}. It won't try build {0} again.",
    "update-log-menu-label": "Update &log...",
    "update-log-title": "Update log",
    "update-log-close": "Close",
    "subtitle-dialog-auto-label": "Load subtitles automatically in my language when a video opens",
    "subtitle-dialog-auto-tooltip": "Only you get them - nothing is shared with the room. Uses the languages in the box above.",
    "auto-subtitles-loaded-notification": "Loaded {} subtitles for you: {}",
    "auto-subtitles-guess-notification": "Loaded {} subtitles for you: {} (matched by name - open Find subtitles to pick another)",
    "stage-idle": "HOUSE LIGHTS UP",
    "stage-waiting": "WAITING ON THE AUDIENCE",
    "stage-paused": "INTERMISSION",
    "stage-playing": "NOW SHOWING",
    "seat-different-file": "Different file",
    "subtitle-dialog-api-key-saved-placeholder": "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022 {} (saved - type a new key to replace it)",
    "chat-heading-label": "CHAT",
    "watching-heading-label": "WHO'S WATCHING",
    "chip-library-label": "Library",
    "alone-hint": "Just you here so far. Send your friends an invite:",
    "shortcuts-menu-label": "Add &shortcuts (Start menu and desktop)",
    "uninstall-menu-label": "&Uninstall Syncplay Marquee...",
    "shortcuts-offer": "Add Syncplay Marquee to your Start menu and desktop?",
    "shortcuts-added-notification": "Shortcuts added to your Start menu and desktop.",
    "uninstall-confirm": "Remove Syncplay Marquee from this PC? Its files, shortcuts and invite-link setup will be deleted after the app closes. You can then delete the downloaded .exe yourself.",
    "uninstall-settings-checkbox": "Also delete my settings and saved keys",
    "uninstall-done": "Syncplay Marquee will now close and remove itself. You can delete the .exe file you downloaded.",
    "status-lost": "Reconnecting...",
    "banner-lost": "Connection lost - trying to reconnect...",
    "banner-reconnect-button": "Reconnect now",
    "status-subtitles-loaded": "Subtitles: {}",
    "status-subtitles-auto": "Subtitles: automatic",
    "openplaylistfile-menu-label": "Open &playlist file...",
    "reloadplaylistfile-menu-label": "&Reload playlist file",
    "playlist-reload-none-notification": "There's no playlist file to reload yet. Use File > Open playlist file first.",
    "playlist-reload-missing-notification": "Couldn't read the playlist file {}.",
    "playlist-reload-empty-notification": "{} has no entries, so the playlist was left as it is.",
    "playlist-reloaded-notification": "Reloaded the playlist: {} entries from {}.",
    "dropout-switch-label": "Pause if someone drops out",
    "dropout-switch-tooltip": "Pause for everyone when someone leaves or loses connection, and resume by itself once they are back and ready.",
    "dropout-paused-notification": "{} dropped out, so playback is paused. It resumes when they're back and ready (or press play).",
    "dropout-waiting-ready-notification": "{} is back. Waiting for them to be ready...",
    "dropout-resumed-notification": "{} is back and ready. Resuming.",
    "sync-check-started-notification": "Checking who's behind...",
    "sync-check-no-chat-error": "This server doesn't support chat, so the sync check can't ask the room.",
    "notify-joined": "{} joined the room",
    "notify-left": "{} left the room",
    "chip-more-tooltip": "More: subtitles, library, voice, private room",
    "chip-tune-tooltip": "Room options",
    "chip-room-change-tooltip": "Switch to another room",
    "chip-room-link": "Room: {}  \u00b7  change",
    "ready-state-on": "Ready",
    "ready-state-off": "Not ready",
    "subtitles-heading-label": "Subtitles",
    "loadshuffleplaylistfromfile-menu-label": "Load and shuffle playlist from file",
    "theme-menu-label": "Theme",
    "theme-system-label": "Same as Windows",
    "theme-dark-label": "Dark",
    "theme-light-label": "Light",
    "theme-cinema-label": "Cinema (warm dark, gold)",
    "theme-midnight-label": "Midnight (black, cyan)",
    "theme-sand-label": "Sand (warm light)",
    "update-bar-ready": "{} is downloaded and ready.",
    "update-bar-restart-button": "Restart now",
    "update-bar-later-button": "Later",
    "subdelay-earlier-menu-label": "Subtitles earlier (-0.1 s, everyone)",
    "subdelay-later-menu-label": "Subtitles later (+0.1 s, everyone)",
    "subdelay-reset-menu-label": "Reset subtitle delay",
    "subdelay-now": "Subtitle delay is now {} for everyone using this app.",
    "subdelay-changed-by": "{} set the subtitle delay to {}.",
    "subdelay-unsupported": "Your player can't change the subtitle delay, so only the others will see it.",
    "reopenplayer-menu-label": "Reopen player (same video and room)",
    "reopenplayer-failed": "The player couldn't be reopened.",
    "diagnostics-menu-label": "Copy diagnostics",
    "diagnostics-copied": "Copied {} lines of diagnostics (no passwords or keys). Paste them wherever you're asking for help.",
    "emoji-button-tooltip": "Emoji",
    "welcome-others-here": "In the room: {}.",
    "welcome-first-here": "You're the first one here. Use Copy invite to bring someone in.",
    "chip-voice-label": "Voice",
    "chip-voice-join-label": "Join voice",
    "chip-voice-tooltip": "Start a voice call for the room (a private Jitsi Meet link, no account needed) or join the one in progress",
    "voice-chat-line": "Voice call: {}",
    "voice-started-notification": "Voice call started. The link is in the chat and opened in your browser.",
    "tray-show-label": "Show Syncplay Marquee",
    "notifications-menu-label": "Desktop &notifications",
    "resume-offer": "Continue from {}?",
    "resume-continue-button": "Continue",
    "resume-start-over-button": "Start over",
    "sync-in-sync-ping": "In sync \u00b7 {} ms",
    "sync-in-sync": "In sync",
    "sync-ahead": "{:.1f} s ahead",
    "sync-behind": "{:.1f} s behind",
    "sync-label-tooltip": "How far you are from the room. Click to check who else is behind.",
    "synccheck-menu-label": "Who's &behind? (sync check)",
    "connectionsettings-menu-label": "&Connection settings (server, name, player)...",
    "skipstart-menu-label": "Open &straight into my last room",
    "startwindow-skipped-notification": "From now on the app opens straight into this room. To change the server, name or player, use File > Connection settings (or hold Shift while opening).",
    "private-update-checking": "Checking for updates...",
    "private-update-installing": "Downloading {}...",
    "private-update-restarting": "Restarting to finish the update...",
    "private-update-restart-manually": "The update is installed. Please close and reopen the app to finish.",
    "private-update-available-chat": "A new build is available: {}. Choose Help > Update to install it.",
    "shared-subtitle-received-notification": "{} shared the subtitle '{}' - type /loadsub to load it",
    "shared-subtitle-sent-notification": "Shared subtitle '{}' with the room",
    "shared-subtitle-loaded-notification": "Loaded shared subtitle '{}'",
    "shared-subtitle-saved-notification": "This player can't load subtitles automatically - the shared subtitle was saved to: {}",
    "shared-subtitle-none-error": "No shared subtitle has been received yet",
    "subtitle-invalid-name-error": "Subtitle must be a .srt, .ass, .ssa or .vtt file",
    "subtitle-invalid-data-error": "Subtitle file contents are invalid",
    "subtitle-too-large-error": "Subtitle file is too large to share",
    "subtitle-file-not-found-error": "Subtitle file could not be read",
    "subtitle-no-file-error": "No subtitle path given and none found next to the current file",
    "unrecognized-command-notification": "Unrecognized command",
    "commandlist-notification": "Available commands:",
    "commandlist-notification/room": "\tr [name] - change room",
    "commandlist-notification/list": "\tl - show user list",
    "commandlist-notification/undo": "\tu - undo last seek",
    "commandlist-notification/pause": "\tp - toggle pause",
    "commandlist-notification/seek": "\t[s][+-]time - seek to the given value of time, if + or - is not specified it's absolute time in seconds or min:sec",
    "commandlist-notification/offset": "\to[+-]duration - offset local playback by the given duration (in seconds or min:sec) from the server seek position - this is a deprecated feature",
    "commandlist-notification/help": "\th - this help",
    "commandlist-notification/toggle": "\tt - toggles whether you are ready to watch or not",
    "commandlist-notification/setready": "\tsr [name] - sets user as ready",
    "commandlist-notification/setnotready": "\tsn [name] - sets user as not ready",
    "commandlist-notification/create": "\tc [name] - create managed room using name of current room",
    "commandlist-notification/auth": "\ta [password] - authenticate as room operator with operator password",
    "commandlist-notification/findsub": "\tsubs [languages] - search OpenSubtitles for the current file (e.g. subs en,sv)",
    "commandlist-notification/picksub": "\tpick [number] - download a subtitle from the last search, load it and load it for everyone in the room",
    "commandlist-notification/sharesub": "\tss [path] - share a subtitle file (.srt/.ass/.ssa/.vtt) with the room; without a path, shares the one next to your current file",
    "commandlist-notification/loadsub": "\tls - load the most recently shared subtitle into your player",
    "commandlist-notification/chat": "\tch [message] - send a chat message in a room",
    "commandList-notification/queue": "\tqa [file/url] - add file or url to bottom of playlist",
    "commandList-notification/queueandselect": "\tqas [file/url] - add file or url to bottom of playlist and select it",
    "commandList-notification/playlist": "\tql - show the current playlist",
    "commandList-notification/select": "\tqs [index] - select given entry in the playlist",
    "commandList-notification/next": "\tqn - select next entry in the playlist",
    "commandList-notification/delete": "\tqd [index] - delete the given entry from the playlist",
    "syncplay-version-notification": "Syncplay version: {}",  # syncplay.version
    "more-info-notification": "More info available at: {}",  # projectURL

    "gui-data-cleared-notification": "Syncplay has cleared the path and window state data used by the GUI.",
    "language-changed-msgbox-label": "Language will be changed when you run Syncplay.",
    "promptforupdate-label": "Is it okay for Syncplay to automatically check for updates from time to time?",

    "media-player-latency-warning": "Warning: The media player took {} seconds to respond. If you experience syncing issues then close applications to free up system resources, and if that doesn't work then try a different media player.",  # Seconds to respond
    "mpv-unresponsive-error": "mpv has not responded for {} seconds so appears to have malfunctioned. Please restart Syncplay.",  # Seconds to respond


    # Client prompts
    "enter-to-exit-prompt": "Press enter to exit\n",

    # Client errors
    "missing-arguments-error": "Some necessary arguments are missing, refer to --help",
    "server-timeout-error": "Connection with server timed out",
    "mpc-slave-error": "Unable to start MPC in slave mode!",
    "mpc-version-insufficient-error": "MPC version not sufficient, please use `mpc-hc` >= `{}`",
    "mpc-be-version-insufficient-error": "MPC version not sufficient, please use `mpc-be` >= `{}`",
    "mpv-version-error": "Syncplay is not compatible with this version of mpv. Please use a different version of mpv (e.g. Git HEAD).",
    "mpv-failed-advice": "The reason mpv cannot start may be due to the use of unsupported command line arguments or an unsupported version of mpv.",
    "player-file-open-error": "Player failed opening file",
    "player-path-error": "Player path is not set properly. Supported players are: mpv, mpv.net, VLC, MPC-HC, MPC-BE, mplayer2, and IINA",
    "hostname-empty-error": "Hostname can't be empty",
    "empty-error": "{} can't be empty",  # Configuration
    "media-player-error": "Media player error: \"{}\"",  # Error line
    "unable-import-gui-error": "Could not import GUI libraries. You need to have the correct version of PySide installed for the GUI to work. If you want to run Syncplay in console mode then run it with the --no-gui command line switch. See https://syncplay.pl/guide/ for more details.",
    "unable-import-twisted-error": "Could not import Twisted. Please install Twisted v16.4.0 or later.",

    "arguments-missing-error": "Some necessary arguments are missing, refer to --help",

    "unable-to-start-client-error": "Unable to start client",

    "player-path-config-error": "Player path is not set properly. Supported players are: mpv, mpv.net, VLC, MPC-HC, MPC-BE, mplayer2, and IINA.",
    "no-file-path-config-error": "File must be selected before starting your player",
    "no-hostname-config-error": "Hostname can't be empty",
    "invalid-port-config-error": "Port must be valid",
    "empty-value-config-error": "{} can't be empty",  # Config option

    "not-json-error": "Not a json encoded string\n",
    "hello-arguments-error": "Not enough Hello arguments\n",  # DO NOT TRANSLATE
    "version-mismatch-error": "Mismatch between versions of client and server\n",
    "vlc-failed-connection": "Failed to connect to VLC. If you have not installed syncplay.lua and are using the latest verion of VLC then please refer to https://syncplay.pl/LUA/ for instructions. Syncplay and VLC 4 are not currently compatible, so either use VLC 3 or an alternative such as mpv.",
    "vlc-failed-noscript": "VLC has reported that the syncplay.lua interface script has not been installed. Please refer to https://syncplay.pl/LUA/ for instructions.",
    "vlc-failed-versioncheck": "This version of VLC is not supported by Syncplay.",
    "vlc-initial-warning": 'VLC does not always provide accurate position information to Syncplay, especially for .mp4 and .avi files. If you experience problems with erroneous seeking then please try an alternative media player such as <a href="https://mpv.io/">mpv</a> (or <a href="https://github.com/stax76/mpv.net/">mpv.net</a> for Windows users).',

    "feature-sharedPlaylists": "shared playlists",  # used for not-supported-by-server-error
    "feature-chat": "chat",  # used for not-supported-by-server-error
    "feature-readiness": "readiness",  # used for not-supported-by-server-error"
    "feature-managedRooms": "managed rooms",  # used for not-supported-by-server-error
    "feature-subtitleSharing": "subtitle sharing",  # used for not-supported-by-server-error
    "feature-setOthersReadiness": "readiness override",  # used for not-supported-by-server-error

    "not-supported-by-server-error": "The {} feature is not supported by this server..",  # feature
    "shared-playlists-not-supported-by-server-error": "The shared playlists feature may not be supported by the server. To ensure that it works correctly requires a server running Syncplay  {}+, but the server is running Syncplay {}.",  # minVersion, serverVersion
    "shared-playlists-disabled-by-server-error": "The shared playlist feature has been disabled in the server configuration. To use this feature you will need to connect to a different server.",

    "invalid-seek-value": "Invalid seek value",
    "invalid-offset-value": "Invalid offset value",

    "switch-file-not-found-error": "Could not switch to file '{0}'. Syncplay looks in specified media directories.",  # File not found
    "folder-search-timeout-error": "The search for media in media directories was aborted as it took too long to search through '{}' after having processed the first {:,} files. This will occur if you select a folder with too many subfolders in your list of media folders to search through or if there are too many files to process. For automatic file switching to work again please select File->Set Media Directories in the menu bar and remove this directory or replace it with an appropriate subfolder. If the folder is actually fine then you can re-enable it by selecting File->Set Media Directories and pressing 'OK'.",  # Folder, Files processed. Note: {:,} is {} but with added commas seprators.
    "folder-search-timeout-warning": "Warning: It has taken {} seconds to scan {:,} files in the folder '{}'. This will occur if you select a folder with too many subfolders in your list of media folders to search through or if there are too many files to process.",  # Folder, Files processed. Note: {:,} is {} but with added commas seprators.
    "folder-search-first-file-timeout-error": "The search for media in '{}' was aborted as it took too long to access the directory. This could happen if it is a network drive or if you configure your drive to spin down after a period of inactivity. For automatic file switching to work again please go to File->Set Media Directories and either remove the directory or resolve the issue (e.g. by changing power saving settings).",  # Folder
    "added-file-not-in-media-directory-error": "You loaded a file in '{}' which is not a known media directory. You can add this as a media directory by selecting File->Set Media Directories in the menu bar.",  # Folder
    "no-media-directories-error": "No media directories have been set. For shared playlist and file switching features to work properly please select File->Set Media Directories and specify where Syncplay should look to find media files.",
    "cannot-find-directory-error": "Could not find media directory '{}'. To update your list of media directories please select File->Set Media Directories from the menu bar and specify where Syncplay should look to find media files.",

    "failed-to-load-server-list-error": "Failed to load public server list. Please visit https://www.syncplay.pl/ in your browser.",


    # Client arguments
    "argument-description": 'Solution to synchronize playback of multiple media player instances over the network.',
    "argument-epilog": 'If no options supplied _config values will be used',
    "nogui-argument": 'show no GUI',
    "host-argument": "server's address",
    "name-argument": 'desired username',
    "debug-argument": 'debug mode',
    "force-gui-prompt-argument": 'make configuration prompt appear',
    "no-store-argument": "don't store values in .syncplay",
    "room-argument": 'default room',
    "password-argument": 'server password',
    "player-path-argument": 'path to your player executable',
    "file-argument": 'file to play',
    "args-argument": 'player options, if you need to pass options starting with - prepend them with single \'--\' argument',
    "clear-gui-data-argument": 'resets path and window state GUI data stored as QSettings',
    "language-argument": 'language for Syncplay messages ({})', # Languages

    "version-argument": 'prints your version',
    "version-message": "You're using Syncplay version {} ({})",

    "load-playlist-from-file-argument": "loads playlist from text file (one entry per line)",


    # Client labels
    "config-window-title": "Syncplay Marquee",

    "connection-group-title": "Connection settings",
    "host-label": "Server address: ",
    "name-label":  "Username (optional):",
    "password-label":  "Server password (if any):",
    "room-label": "Default room: ",
    "roomlist-msgbox-label": "Edit room list (one per line)",

    "media-setting-title": "Media player settings",
    "executable-path-label": "Path to media player:",
    "media-path-label": "Path to video (optional):",
    "player-arguments-label": "Player arguments (if any):",
    "browse-label": "Browse",
    "update-server-list-label": "Update list",

    "more-title": "Show more settings",
    "never-rewind-value": "Never",
    "seconds-suffix": " secs",
    "privacy-sendraw-option": "Send raw",
    "privacy-sendhashed-option": "Send hashed",
    "privacy-dontsend-option": "Don't send",
    "filename-privacy-label": "Filename information:",
    "filesize-privacy-label": "File size information:",
    "checkforupdatesautomatically-label": "Check for Syncplay updates automatically",
    "autosavejoinstolist-label": "Add rooms you join to the room list",
    "slowondesync-label": "Slow down on minor desync (not supported on MPC-HC/BE)",
    "rewindondesync-label": "Rewind on major desync (recommended)",
    "fastforwardondesync-label": "Fast-forward if lagging behind (recommended)",
    "dontslowdownwithme-label": "Never slow down or rewind others (experimental)",
    "pausing-title": "Pausing",
    "pauseonleave-label": "Pause when user leaves (e.g. if they are disconnected)",
    "readiness-title": "Initial readiness state",
    "readyatstart-label": "Set me as 'ready to watch' by default",
    "forceguiprompt-label": "Don't always show the Syncplay configuration window",  # (Inverted)
    "showosd-label": "Enable OSD Messages",

    "showosdwarnings-label": "Include warnings (e.g. when files are different, users not ready)",
    "showsameroomosd-label": "Include events in your room",
    "shownoncontrollerosd-label": "Include events from non-operators in managed rooms",
    "showdifferentroomosd-label": "Include events in other rooms",
    "showslowdownosd-label": "Include slowing down / reverting notifications",
    "language-label": "Language:",
    "automatic-language": "Default ({})",  # Default language
    "showdurationnotification-label": "Warn about media duration mismatches",
    "showplaylistskipwarnings-label": "Warn when playlist may skip unwatched files",
    "showplaylistskipwarnings-tooltip": "Show warnings when Syncplay thinks the playlist skips files that have not been watched.",
    "showplaylistorderwarnings-label": "Warn when playlist files appear out of order",
    "showplaylistorderwarnings-tooltip": "Show warnings when Syncplay thinks playlist files may be in the wrong order.",
    "basics-label": "Basics",
    "files-label": "Files",  # Media folders and watched-file settings
    "readiness-label": "Play/Pause",
    "misc-label": "Privacy/Misc",
    "core-behaviour-title": "Core room behaviour",
    "syncplay-internals-title": "Syncplay internals",
    "syncplay-mediasearchdirectories-title": "Directories to search for media",
    "syncplay-mediasearchdirectories-label": "Directories to search for media (one path per line)",
    "syncplay-watchedfiles-title": "Watched files",
    "syncplay-watchedautomove-label": "Automatically move watched files to subfolder (if subfolder exists)",
    "syncplay-watchedmovesubfolder-label": "Subfolder for watched files",
    "syncplay-watchedsubfolderautocreate-label": "Automatically create watched subfolder when needed",
    "mark-as-watched-menu-label": "Mark as watched",
    "mark-as-unwatched-menu-label": "Mark as unwatched",
    "previous-file-menu-section-label": "Previous file: '{}'",  # filename
    "mark-previous-file-as-watched-menu-label": "Mark as watched",
    "add-previous-file-to-playlist-menu-label": "Add to playlist",
    "sync-label": "Sync",
    "sync-otherslagging-title": "If others are lagging behind...",
    "sync-youlaggging-title": "If you are lagging behind...",
    "messages-label": "Messages",
    "messages-osd-title": "On-screen Display settings",
    "messages-other-title": "Other display settings",
    "chat-label": "Chat",
    "privacy-label": "Privacy",  # Currently unused, but will be brought back if more space is needed in Misc tab
    "privacy-title": "Privacy settings",
    "unpause-title": "If you press play, set as ready and:",
    "unpause-ifalreadyready-option": "Unpause if already set as ready",
    "unpause-ifothersready-option": "Unpause if already ready or others in room are ready (default)",
    "unpause-ifminusersready-option": "Unpause if already ready or if all others ready and min users ready",
    "unpause-always": "Always unpause",
    "syncplay-trusteddomains-title": "Trusted domains (for streaming services and hosted content)",

    "chat-title": "Chat message input",
    "chatinputenabled-label": "Enable chat input via mpv",
    "chatdirectinput-label": "Allow instant chat input (bypass having to press enter key to chat)",
    "chatinputfont-label": "Chat input font",
    "chatfont-label": "Set font",
    "chatcolour-label": "Set colour",
    "chatinputposition-label": "Position of message input area in mpv",
    "chat-top-option": "Top",
    "chat-middle-option": "Middle",
    "chat-bottom-option": "Bottom",
    "chatoutputheader-label": "Chat message output",
    "chatoutputfont-label": "Chat output font",
    "chatoutputenabled-label": "Enable chat output in media player (mpv only for now)",
    "chatoutputposition-label": "Output mode",
    "chat-chatroom-option": "Chatroom style",
    "chat-scrolling-option": "Scrolling style",

    "mpv-key-tab-hint": "[TAB] to toggle access to alphabet row key shortcuts.",
    "mpv-key-hint": "[ENTER] to send message. [ESC] to escape chat mode.",
    "alphakey-mode-warning-first-line": "You can temporarily use old mpv bindings with a-z keys.",
    "alphakey-mode-warning-second-line": "Press [TAB] to return to Syncplay chat mode.",

    "help-label": "Help",
    "reset-label": "Restore defaults",
    "run-label": "Run Syncplay",
    "storeandrun-label": "Store configuration and run Syncplay",

    "contact-label": "Feel free to e-mail <a href=\"mailto:dev@syncplay.pl\"><nobr>dev@syncplay.pl</nobr></a>, <a href=\"https://github.com/Syncplay/syncplay/issues\"><nobr>create an issue</nobr></a> to report a bug/problem via GitHub, <a href=\"https://github.com/Syncplay/syncplay/discussions\"><nobr>start a discussion</nobr></a> to make a suggestion or ask a question via GitHub, <a href=\"https://www.facebook.com/SyncplaySoftware\"><nobr>like us on Facebook</nobr></a>, <a href=\"https://twitter.com/Syncplay/\"><nobr>follow us on Twitter</nobr></a>, or visit <a href=\"https://syncplay.pl/\"><nobr>https://syncplay.pl/</nobr></a>. Do not use Syncplay to send sensitive information.",

    "joinroom-label": "Join room",
    "joinroom-menu-label": "Join room {}",
    "seektime-menu-label": "Seek to time",
    "undoseek-menu-label": "Undo seek",
    "play-menu-label": "Play",
    "pause-menu-label": "Pause",
    "playbackbuttons-menu-label": "Show playback buttons",
    "autoplay-menu-label": "Show auto-play button",
    "autoplay-guipushbuttonlabel": "Play when all ready",
    "autoplay-minimum-label": "Min users:",
    "hideemptyrooms-menu-label": "Hide empty persistent rooms",

    "sendmessage-label": "Send",

    "ready-guipushbuttonlabel": "I'm ready to watch!",

    "roomuser-heading-label": "Room / User",
    "size-heading-label": "Size",
    "duration-heading-label": "Length",
    "filename-heading-label": "Filename",
    "notifications-heading-label": "Room chat",
    "userlist-heading-label": "People",

    "browseformedia-label": "Browse for media files",

    "file-menu-label": "&File",  # & precedes shortcut key
    "openmedia-menu-label": "&Open media file",
    "openstreamurl-menu-label": "Open &media stream URL",
    "setmediadirectories-menu-label": "Set media &directories",
    "loadplaylistfromfile-menu-label": "&Load playlist from file",
    "saveplaylisttofile-menu-label": "&Save playlist to file",
    "reconnect-menu-label": "&Reconnect to server",
    "exit-menu-label": "E&xit",
    "advanced-menu-label": "&Advanced",
    "window-menu-label": "&Window",
    "setoffset-menu-label": "Set &offset",
    "createcontrolledroom-menu-label": "&Create managed room",
    "identifyascontroller-menu-label": "&Identify as room operator",
    "settrusteddomains-menu-label": "Set &trusted domains",
    "addtrusteddomain-menu-label": "Add {} as trusted domain",  # Domain

    "edit-menu-label": "&Edit",
    "cut-menu-label": "Cu&t",
    "copy-menu-label": "&Copy",
    "paste-menu-label": "&Paste",
    "selectall-menu-label": "&Select All",

    "playback-menu-label": "&Playback",

    "help-menu-label": "&Help",
    "userguide-menu-label": "Open user &guide",
    "update-menu-label": "Check for &update",

    "startTLS-initiated": "Attempting secure connection",
    "startTLS-secure-connection-ok": "Secure connection established ({})",
    "startTLS-server-certificate-invalid": 'Secure connection failed because Syncplay could not verify the server security certificate. The certificate may be expired, incomplete, or signed by a certificate authority that this client does not trust. The server may need to be updated, or its administrator may need to configure a more widely compatible certificate chain. For further details and troubleshooting see <a href="https://syncplay.pl/trouble">here</a>.',
    "startTLS-server-certificate-invalid-DNS-ID": "Syncplay does not trust this server because it uses a certificate that is not valid for its hostname.",
    "startTLS-not-supported-client": "This client does not support TLS",
    "startTLS-not-supported-server": "This server does not support TLS",

    # TLS certificate dialog
    "tls-information-title": "Certificate Details",
    "tls-dialog-status-label": "<strong>Syncplay is using an encrypted connection to {}.</strong>",
    "tls-dialog-desc-label": "Encryption with a digital certificate keeps information private as it is sent to or from the<br/>server {}.",
    "tls-dialog-connection-label": "Information encrypted using Transport Layer Security (TLS), version {} with the cipher<br/>suite: {}.",
    "tls-dialog-certificate-label": "Certificate issued by {} valid until {}.",

    # About dialog
    "about-menu-label": "&About Syncplay",
    "about-dialog-title": "About Syncplay",
    "about-dialog-release": "Version {} release {}",
    "about-dialog-license-text": "Licensed under the Apache&nbsp;License,&nbsp;Version 2.0",
    "about-dialog-license-button": "License",
    "about-dialog-dependencies": "Dependencies",

    "setoffset-msgbox-label": "Set offset",
    "offsetinfo-msgbox-label": "Offset (see https://syncplay.pl/guide/ for usage instructions):",

    "promptforstreamurl-msgbox-label": "Open media stream URL",
    "promptforstreamurlinfo-msgbox-label": "Stream URL",

    "addfolder-label": "Add folder",

    "adduris-msgbox-label": "Add URLs to playlist (one per line)",
    "editplaylist-msgbox-label": "Set playlist (one per line)",
    "trusteddomains-msgbox-label": "Domains it is okay to automatically switch to (one per line)",

    "createcontrolledroom-msgbox-label": "Create managed room",
    "controlledroominfo-msgbox-label": "Enter name of managed room\r\n(see https://syncplay.pl/guide/ for usage instructions):",

    "identifyascontroller-msgbox-label": "Identify as room operator",
    "identifyinfo-msgbox-label": "Enter operator password for this room\r\n(see https://syncplay.pl/guide/ for usage instructions):",

    "public-server-msgbox-label": "Select the public server for this viewing session",

    "megabyte-suffix": " MB",

    # Tooltips

    "host-tooltip": "Hostname or IP to connect to, optionally including port (e.g. syncplay.pl:8999). Only synchronised with people on same server/port.",
    "name-tooltip": "Nickname you will be known by. No registration, so can easily change later. Random name generated if none specified.",
    "password-tooltip": "Passwords are only needed for connecting to private servers.",
    "room-tooltip": "Room to join upon connection can be almost anything, but you will only be synchronised with people in the same room.",

    "edit-rooms-tooltip": "Edit room list.",

    "executable-path-tooltip": "Location of your chosen supported media player (mpv, mpv.net, VLC, MPC-HC/BE, mplayer2 or IINA).",
    "media-path-tooltip": "Location of video or stream to be opened. Necessary for mplayer2.",
    "player-arguments-tooltip": "Additional command line arguments / switches to pass on to this media player.",
    "mediasearcdirectories-arguments-tooltip": "Directories where Syncplay will search for media files, e.g. when you are using the click to switch feature. Syncplay will look recursively through subfolders.",

    "more-tooltip": "Display less frequently used settings.",
    "filename-privacy-tooltip": "Privacy mode for sending currently playing filename to server.",
    "filesize-privacy-tooltip": "Privacy mode for sending size of currently playing file to server.",
    "privacy-sendraw-tooltip": "Send this information without obfuscation. This is the default option with most functionality.",
    "privacy-sendhashed-tooltip": "Send a hashed version of the information, making it less visible to other clients.",
    "privacy-dontsend-tooltip": "Do not send this information to the server. This provides for maximum privacy.",
    "checkforupdatesautomatically-tooltip": "Regularly check with the Syncplay website to see whether a new version of Syncplay is available.",
    "autosavejoinstolist-tooltip": "When you join a room in a server, automatically remember the room name in the list of rooms to join.",
    "slowondesync-tooltip": "Reduce playback rate temporarily when needed to bring you back in sync with other viewers. Not supported on MPC-HC/BE.",
    "dontslowdownwithme-tooltip": "Means others do not get slowed down or rewinded if your playback is lagging. Useful for room operators.",
    "pauseonleave-tooltip": "Pause playback if you get disconnected or someone leaves from your room.",
    "readyatstart-tooltip": "Set yourself as 'ready' at start (otherwise you are set as 'not ready' until you change your readiness state)",
    "forceguiprompt-tooltip": "Configuration dialogue is not shown when opening a file with Syncplay.",  # (Inverted)
    "nostore-tooltip": "Run Syncplay with the given configuration, but do not permanently store the changes.",  # (Inverted)
    "rewindondesync-tooltip": "Jump back when needed to get back in sync. Disabling this option can result in major desyncs!",
    "fastforwardondesync-tooltip": "Jump forward when out of sync with room operator (or your pretend position if 'Never slow down or rewind others' enabled).",
    "showosd-tooltip": "Sends Syncplay messages to media player OSD.",
    "showosdwarnings-tooltip": "Show warnings if playing different file, alone in room, users not ready, etc.",
    "showsameroomosd-tooltip": "Show OSD notifications for events relating to room user is in.",
    "shownoncontrollerosd-tooltip": "Show OSD notifications for events relating to non-operators who are in managed rooms.",
    "showdifferentroomosd-tooltip": "Show OSD notifications for events relating to room user is not in.",
    "showslowdownosd-tooltip": "Show notifications of slowing down / reverting on time difference.",
    "showdurationnotification-tooltip": "Useful for when a segment in a multi-part file is missing, but can result in false positives.",
    "language-tooltip": "Language to be used by Syncplay.",
    "unpause-always-tooltip": "If you press unpause it always sets you as ready and unpause, rather than just setting you as ready.",
    "unpause-ifalreadyready-tooltip": "If you press unpause when not ready it will set you as ready - press unpause again to unpause.",
    "unpause-ifothersready-tooltip": "If you press unpause when not ready, it will only unpause if others are ready.",
    "unpause-ifminusersready-tooltip": "If you press unpause when not ready, it will only unpause if others are ready and minimum users threshold is met.",
    "trusteddomains-arguments-tooltip": "Domains that it is okay for Syncplay to automatically switch to when shared playlists is enabled.",

    "chatinputenabled-tooltip": "Enable chat input in mpv (press enter to chat, enter to send, escape to cancel)",
    "chatdirectinput-tooltip": "Skip having to press 'enter' to go into chat input mode in mpv. Press TAB in mpv to temporarily disable this feature.",
    "font-label-tooltip": "Font used for when entering chat messages in mpv. Client-side only, so doesn't affect what other see.",
    "set-input-font-tooltip": "Font family used for when entering chat messages in mpv. Client-side only, so doesn't affect what other see.",
    "set-input-colour-tooltip": "Font colour used for when entering chat messages in mpv. Client-side only, so doesn't affect what other see.",
    "chatinputposition-tooltip": "Location in mpv where chat input text will appear when you press enter and type.",
    "chatinputposition-top-tooltip": "Place chat input at top of mpv window.",
    "chatinputposition-middle-tooltip": "Place chat input in dead centre of mpv window.",
    "chatinputposition-bottom-tooltip": "Place chat input at bottom of mpv window.",
    "chatoutputenabled-tooltip": "Show chat messages in OSD (if supported by media player).",
    "font-output-label-tooltip": "Chat output font.",
    "set-output-font-tooltip": "Font used for when displaying chat messages.",
    "chatoutputmode-tooltip": "How chat messages are displayed.",
    "chatoutputmode-chatroom-tooltip": "Display new lines of chat directly below previous line.",
    "chatoutputmode-scrolling-tooltip": "Scroll chat text from right to left.",

    "help-tooltip": "Opens the Syncplay.pl user guide.",
    "reset-tooltip": "Reset all settings to the default configuration.",
    "update-server-list-tooltip": "Connect to syncplay.pl to update list of public servers.",

    "sslconnection-tooltip": "Securely connected to server. Click for certificate details.",

    "joinroom-tooltip": "Leave current room and joins specified room.",
    "seektime-msgbox-label": "Jump to specified time (in seconds / min:sec). Use +/- for relative seek.",
    "ready-tooltip": "Indicates whether you are ready to watch.",
    "autoplay-tooltip": "Auto-play when all users who have readiness indicator are ready and minimum user threshold met.",
    "switch-to-file-tooltip": "Double click to switch to {}",  # Filename
    "sendmessage-tooltip": "Send message to room",

    "watchedautomove-tooltip": "Automatically move file into watched subfolder when end of file is reached. This only works if the parent directory is a media directory.",
    "watchedsubfolder-tooltip": "Subfolder for watched files to be moved into relative to file directory (subfolder needs to exist for file to be moved). This only works if the parent directory is a media directory.",
    "watchedsubfolderautocreate-tooltip": "Automatically create watched subfolder when moving file to subfolder if it does not already exist. This only works if the parent directory is a media directory.",

    # In-userlist notes (GUI)
    "differentsize-note": "Different size!",
    "differentsizeandduration-note": "Different size and duration!",
    "differentduration-note": "Different duration!",
    "nofile-note": "(No file being played)",

    # Server messages to client
    "new-syncplay-available-motd-message": "You are using Syncplay {} but a newer version is available from https://syncplay.pl",  # ClientVersion
    "persistent-rooms-notice": "NOTICE: This server uses persistent rooms, which means that the playlist information is stored between playback sessions. If you want to create a room where information is not saved then put -temp at the end of the room name.", # NOTE: Do not translate the word -temp
    "ready-chat-message": "I have set {} as ready.", # User
    "not-ready-chat-message": "I have set {} as not ready.", # User

    # Server notifications
    "welcome-server-notification": "Welcome to Syncplay server, ver. {0}",  # version
    "client-connected-room-server-notification": "{0}({2}) connected to room '{1}'",  # username, host, room
    "client-left-server-notification": "{0} left server",  # name
    "no-salt-notification": "PLEASE NOTE: To allow room operator passwords generated by this server instance to still work when the server is restarted, please add the following command line argument when running the Syncplay server in the future: --salt {}",  # Salt


    # Server arguments
    "server-argument-description": 'Solution to synchronize playback of multiple media player instances over the network. Server instance',
    "server-argument-epilog": 'If no options supplied _config values will be used',
    "server-port-argument": 'server TCP port',
    "server-password-argument": 'server password',
    "server-isolate-room-argument": 'should rooms be isolated?',
    "server-salt-argument": "random string used to generate managed room passwords",
    "server-disable-ready-argument": "disable readiness feature",
    "server-motd-argument": "path to file from which motd will be fetched",
    "server-rooms-argument": "path to database file to use and/or create to store persistent room data. Enables rooms to persist without watchers and through restarts",
    "server-permanent-rooms-argument": "path to file which lists permanent rooms that will be listed even if the room is empty (in the form of a text file which lists one room per line) - requires persistent rooms to be enabled",
    "server-disable-subtitle-sharing-argument": "disable subtitle sharing between users",
    "server-chat-argument": "Should chat be disabled?",
    "server-chat-maxchars-argument": "Maximum number of characters in a chat message (default is {})", # Default number of characters
    "server-maxusernamelength-argument": "Maximum number of characters in a username (default is {})",
    "server-stats-db-file-argument": "Enable server stats using the SQLite db file provided",
    "server-startTLS-argument": "Enable TLS connections using the certificate files in the path provided",
    "server-messed-up-motd-unescaped-placeholders": "Message of the Day has unescaped placeholders. All $ signs should be doubled ($$).",
    "server-messed-up-motd-too-long": "Message of the Day is too long - maximum of {} chars, {} given.",
    "server-listen-only-on-ipv4": "Listen only on IPv4 when starting the server.",
    "server-listen-only-on-ipv6": "Listen only on IPv6 when starting the server.",
    "server-interface-ipv4": "The IP address to bind to for IPv4. Leaving it empty defaults to using all.",
    "server-interface-ipv6": "The IP address to bind to for IPv6. Leaving it empty defaults to using all.",

    # Server errors
    "unknown-command-server-error": "Unknown command {}",  # message
    "not-json-server-error": "Not a json encoded string {}",  # message
    "line-decode-server-error": "Not a utf-8 string",
    "not-known-server-error": "You must be known to server before sending this command",
    "client-drop-server-error": "Client drop: {} -- {}",  # host, error
    "password-required-server-error": "Password required",
    "wrong-password-server-error": "Wrong password supplied",
    "hello-server-error": "Not enough Hello arguments",  # DO NOT TRANSLATE

    # Playlists
    "playlist-selection-changed-notification":  "{} changed the playlist selection",  # Username
    "playlist-contents-changed-notification": "{} updated the playlist",  # Username
    "cannot-find-file-for-playlist-switch-error": "Could not find file {} in media directories for playlist switch!",  # Filename
    "cannot-add-duplicate-error": "Could not add second entry for '{}' to the playlist as no duplicates are allowed.",  # Filename
    "cannot-add-unsafe-path-error": "Could not automatically load {} because it is not on a trusted domain. You can switch to the URL manually by double clicking it in the playlist, and add trusted domains via File->Advanced->Set Trusted Domains. If you right click on a URL then you can add its domain as a trusted domain via the context menu.",  # Filename
    "sharedplaylistenabled-label": "Enable shared playlists",
    "removefromplaylist-menu-label": "Remove from playlist",
    "shuffleremainingplaylist-menu-label": "Shuffle remaining playlist",
    "shuffleentireplaylist-menu-label": "Shuffle entire playlist",
    "undoplaylist-menu-label": "Undo last change to playlist",
    "addfilestoplaylist-menu-label": "Add file(s) to bottom of playlist",
    "addurlstoplaylist-menu-label": "Add URL(s) to bottom of playlist",
    "editplaylist-menu-label": "Edit playlist",

    "open-containing-folder": "Open folder containing this file",
    "addyourfiletoplaylist-menu-label": "Add your file to playlist",
    "addotherusersfiletoplaylist-menu-label": "Add {}'s file to playlist",  # [Username]
    "addyourstreamstoplaylist-menu-label": "Add your stream to playlist",
    "addotherusersstreamstoplaylist-menu-label": "Add {}' stream to playlist",  # [Username]
    "openusersstream-menu-label": "Open {}'s stream",  # [username]'s
    "openusersfile-menu-label": "Open {}'s file",  # [username]'s

    "setasready-menu-label": "Set {} as ready", # [Username]
    "setasnotready-menu-label": "Set {} as not ready", # [Username]

    "playlist-instruction-item-message": "Drag file here to add it to the shared playlist.",
    "sharedplaylistenabled-tooltip": "Room operators can add files to a synced playlist to make it easy for everyone to watching the same thing. Configure media directories under 'Misc'.",

    "playlist-empty-error": "Playlist is currently empty.",
    "playlist-invalid-index-error": "Invalid playlist index",
    "cannot-move-file-due-to-name-conflict-error": "Could not move '{}' to '{}' subfolder because a file with that name already exists.",  # Path, subfolder
    "cannot-move-file-due-to-parent-name-conflict-error": "Could not move '{}' back to '{}' because a file with that name already exists in that folder.",  # Path, parent folder
    "file-not-in-watched-subfolder-error": "'{}' is not in the watched files subfolder.",  # path
    "watched-file-tracking-disabled-error": "Watched file tracking is disabled.",
    "watched-subfolder-unavailable-error": "Could not move '{}' to '{}' subfolder because the subfolder could not be found or created.",  # path, subfolder
    "watched-parent-folder-unavailable-error": "Could not move '{}' out of the watched files subfolder because the parent folder could not be found.",  # path
    "moved-file-to-subfolder-notification": "Moved '{}' to '{}' subfolder.",
    "moved-file-from-watched-subfolder-notification": "Moved '{}' back to '{}'.",  # path, parent folder

    # Watched file functionality
    "syncplay-watchedhistory-title": "Watched history",
    "syncplay-watchedhistoryenabled-label": "Enable watched history (JSON index)",
    "syncplay-watchedhistory-export-label": "Export watched history",
    "syncplay-watchedhistory-import-label": "Import and merge watched history",
    "syncplay-autoremovefromplaylist-label": "Automatically remove watched files from playlist",
    "watchedhistoryenabled-tooltip": "Record watched files alongside the Syncplay config file as '.syncplay-watched.json'. Watched state is preserved even if files are moved or deleted.",
    "autoremovewatchedfromplaylist-tooltip": "Remove a playlist item from the shared playlist when Syncplay marks it as watched after playback reaches the end.",
    "watched-json-read-error": "Could not read watched history file '{}': {}",  # path, error
    "watched-json-invalid-data-error": "Watched history file contains invalid data.",
    "watched-json-write-error": "Could not write watched history file '{}': {}",  # path, error
    "watched-json-concurrent-update-error": "Could not update watched history file due to concurrent changes: {}",  # path
    "watched-history-export-title": "Export watched history",
    "watched-history-import-title": "Import watched history",
    "watched-history-json-filter": "JSON files (*.json);;All files (*)",
    "watched-history-reconcile-prompt": "{} file(s) are in watched subfolders but are not recorded in watched history. Add them before exporting?\n\nExamples:\n{}",
    "watched-history-add-and-export": "Add and export",
    "watched-history-export-without-adding": "Export without adding",
    "watched-history-export-success": "Watched history exported to '{}'.",  # path
    "watched-history-export-added": "Added {} file(s) from watched subfolders before exporting.",  # count
    "watched-history-import-success": "Watched history imported. Added: {}; updated: {}; unchanged: {}; skipped: {}.",  # counts
    "watched-history-no-import-changes": "The selected watched history file did not contain any new or newer entries.",
    "watched-history-backup-created": "Backup created at '{}'.",  # path
    "watched-history-invalid-error": "The selected file is not a valid Syncplay watched history file.",
    "watched-history-operation-error": "Watched history operation failed: {}",  # error
    "watched-move-permission-error": "Could not move '{}' to watched subfolder due to a permissions error.",  # filename
    "watched-move-failed-error": "Could not move '{}' to watched subfolder: {}",  # filename, error
    "watched-move-too-many-retries-error": "Giving up on moving '{}' to watched subfolder after too many retries.",  # filename
    "watched-mark-watched-error": "Could not mark '{}' as watched: {}",  # filename, error
    "watched-mark-unwatched-error": "Could not mark '{}' as unwatched: {}",  # filename, error
    "watched-record-history-error": "Could not record watched history for '{}': {}",  # filename, error
    "marked-file-as-watched-notification": "Marked '{}' as watched.",  # filename
    "marked-file-as-unwatched-notification": "Marked '{}' as unwatched.",  # filename
    "watched-last-watched-tooltip": "Last watched {} in room '{}' ({})",  # how long, room, date and time
    "watched-datetime-format": "%d %B %Y %H:%M",
    "watched-ago-minutes": "{} minute(s) ago", # minutes
    "watched-ago-hours": "{} hour(s) ago", # hours
    "watched-ago-days": "{} day(s) ago", # dates
    "playlist-skip-warning-tooltip": "Warning: This appears to skip unwatched file {}.", # missing file number
    "playlist-out-of-order-warning-tooltip": "Warning: File {} appears out of order after file {}. File {} was expected instead." # actual file number, previous file number, expected file number
}
