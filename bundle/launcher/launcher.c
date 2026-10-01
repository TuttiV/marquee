/* Syncplay Marquee.exe - a tiny Windows launcher (GUI subsystem, so no console window ever opens).
 *
 * First run: opens the one-time setup (creates a private Python environment, visible so you can see progress).
 * Every run after: starts Syncplay through pythonw.exe (no console) and exits immediately.
 * Build: see build-launcher.sh (needs mingw-w64). Arguments are passed straight through to Syncplay. */
#include <windows.h>
#include <wchar.h>

static int fileExists(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

static void fail(const wchar_t *message) {
    MessageBoxW(NULL, message, L"Syncplay Marquee", MB_ICONERROR | MB_OK);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR arguments, int show) {
    static wchar_t dir[32768], pythonw[32768], script[32768], setup[32768], command[65536];
    DWORD length = GetModuleFileNameW(NULL, dir, 32768);
    if (length == 0 || length >= 32768) { fail(L"Could not work out where Syncplay is installed."); return 1; }
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) *slash = 0;
    SetCurrentDirectoryW(dir);

    _snwprintf(pythonw, 32768, L"%ls\\.venv\\Scripts\\pythonw.exe", dir);
    _snwprintf(script, 32768, L"%ls\\program\\launch-syncplay.pyw", dir);
    if (!fileExists(script)) { fail(L"program\\launch-syncplay.pyw is missing. Keep Syncplay Marquee.exe in the folder you extracted, with the program folder next to it."); return 1; }

    if (!fileExists(pythonw)) {  /* First run: one-time setup in a visible window, then continue */
        _snwprintf(setup, 32768, L"cmd.exe /c \"\"%ls\\Setup Syncplay.bat\"\"", dir);
        STARTUPINFOW startup;
        PROCESS_INFORMATION process;
        ZeroMemory(&startup, sizeof(startup));
        startup.cb = sizeof(startup);
        if (!CreateProcessW(NULL, setup, NULL, NULL, FALSE, CREATE_NEW_CONSOLE, NULL, dir, &startup, &process)) {
            fail(L"Could not start the first-time setup (Setup Syncplay.bat).");
            return 1;
        }
        WaitForSingleObject(process.hProcess, INFINITE);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        if (!fileExists(pythonw)) return 1;  /* The setup window already explained what went wrong */
    }

    _snwprintf(command, 65536, L"\"%ls\" \"%ls\" %ls", pythonw, script, arguments ? arguments : L"");
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ZeroMemory(&startup, sizeof(startup));
    startup.cb = sizeof(startup);
    if (!CreateProcessW(NULL, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, dir, &startup, &process)) {
        fail(L"Could not start Syncplay Marquee. Delete the .venv folder next to Syncplay Marquee.exe and run it again to redo the setup.");
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
