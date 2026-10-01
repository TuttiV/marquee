/* Syncplay Marquee.exe - self-contained launcher.
 *
 * This file is the front of the .exe; tools/make-exe.py appends two zip archives (a private Python runtime with all
 * libraries, and the app) plus a 64-byte trailer. On first run it unpacks them under %LOCALAPPDATA%\Syncplay Marquee
 * (showing a small progress window) and starts the app with pythonw.exe (no console). Later runs start straight away.
 * It contains its own small unzip (inflate) so it needs nothing from the system, not even Python.
 *
 * Test hooks: MARQUEE_HOME overrides the install folder; MARQUEE_NO_LAUNCH=1 unpacks and exits without starting.
 * Build: x86_64-w64-mingw32-gcc -O2 -mwindows -municode -static stub.c stub.res.o -lcomctl32 (see tools/make-exe.py). */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <stdbool.h>
#include <commctrl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#define TITLE L"Syncplay Marquee"
#define MAGIC "MARQSFX2"

#pragma pack(push, 1)
typedef struct {
    char magic[8];
    uint64_t rtOffset, rtSize, appOffset, appSize;
    uint32_t build, reserved;
    char rtStamp[16];
} Trailer;
#pragma pack(pop)

#include "decoders.h"

/* -------------------------------------------------------------------------------------- zip extraction ---- */
static uint32_t rd32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }
static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

static volatile LONG gProgress = 0;  /* 0..1000 */
static wchar_t gError[512];

static void makeDirs(wchar_t *path) {  /* Create every folder in path (a file path: the last part is not created) */
    for (wchar_t *p = path + 3; *p; p++) {
        if (*p == L'\\') { *p = 0; CreateDirectoryW(path, NULL); *p = L'\\'; }
    }
}

static int safeName(const char *name, size_t len) {
    if (len == 0 || name[0] == '/' || name[0] == '\\') return 0;
    for (size_t i = 0; i < len; i++) {
        if (name[i] == ':' || name[i] == '\\') return 0;
        if (name[i] == '.' && name[i + 1] == '.' && (i == 0 || name[i - 1] == '/') && (i + 2 >= len || name[i + 2] == '/')) return 0;
    }
    return 1;
}

/* Extract every entry of the zip held in memory into destDir. Returns 0 on success. */
static int extractZip(const uint8_t *zip, size_t size, const wchar_t *destDir, double base, double span) {
    if (size < 22) return -1;
    size_t eocd = size - 22;
    while (rd32(zip + eocd) != 0x06054b50) { if (eocd == 0) return -1; eocd--; }
    unsigned count = rd16(zip + eocd + 10);
    size_t central = rd32(zip + eocd + 16);
    for (unsigned i = 0; i < count; i++) {
        if (central + 46 > size || rd32(zip + central) != 0x02014b50) return -1;
        unsigned method = rd16(zip + central + 10);
        uint32_t crc = rd32(zip + central + 16), csize = rd32(zip + central + 20), usize = rd32(zip + central + 24);
        unsigned nameLen = rd16(zip + central + 28), extraLen = rd16(zip + central + 30), commentLen = rd16(zip + central + 32);
        size_t local = rd32(zip + central + 42);
        const char *name = (const char *)(zip + central + 46);
        central += 46 + nameLen + extraLen + commentLen;
        if (nameLen && name[nameLen - 1] == '/') continue;  /* Folder entries are created on demand */
        if (!safeName(name, nameLen)) continue;
        if (local + 30 > size || rd32(zip + local) != 0x04034b50) return -1;
        size_t dataStart = local + 30 + rd16(zip + local + 26) + rd16(zip + local + 28);
        if (dataStart + csize > size) return -1;
        uint8_t *buffer = (uint8_t *)VirtualAlloc(NULL, usize ? usize : 1, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!buffer) return -2;
        int bad = 0;
        if (method == 0) { if (csize != usize) bad = 1; else memcpy(buffer, zip + dataStart, usize); }
        else if (method == 8) bad = inflateRaw(zip + dataStart, csize, buffer, usize);
        else if (method == 14) bad = lzmaDecodeZipEntry(zip + dataStart, csize, buffer, usize);
        else bad = 1;
        if (!bad && crc32of(buffer, usize) != crc) bad = 1;
        if (bad) { VirtualFree(buffer, 0, MEM_RELEASE); return -3; }

        wchar_t wide[1024], full[2048];
        int n = MultiByteToWideChar(CP_UTF8, 0, name, (int)nameLen, wide, 1000);
        if (n <= 0) { VirtualFree(buffer, 0, MEM_RELEASE); return -4; }
        wide[n] = 0;
        for (int k = 0; k < n; k++) if (wide[k] == L'/') wide[k] = L'\\';
        _snwprintf(full, 2048, L"%ls\\%ls", destDir, wide);
        full[2047] = 0;
        makeDirs(full);
        HANDLE file = CreateFileW(full, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (file == INVALID_HANDLE_VALUE) { VirtualFree(buffer, 0, MEM_RELEASE); _snwprintf(gError, 512, L"Could not write %ls (error %lu)", full, GetLastError()); return -5; }
        DWORD written = 0;
        size_t done = 0;
        while (done < usize) {
            DWORD chunk = (DWORD)((usize - done) > (1u << 24) ? (1u << 24) : (usize - done));
            if (!WriteFile(file, buffer + done, chunk, &written, NULL) || written != chunk) { CloseHandle(file); VirtualFree(buffer, 0, MEM_RELEASE); return -6; }
            done += chunk;
        }
        CloseHandle(file);
        VirtualFree(buffer, 0, MEM_RELEASE);
        InterlockedExchange(&gProgress, (LONG)((base + span * (i + 1) / count) * 1000));
    }
    return 0;
}

/* ------------------------------------------------------------------------------------------------ files ---- */
static int exists(const wchar_t *path) { DWORD a = GetFileAttributesW(path); return a != INVALID_FILE_ATTRIBUTES; }

static uint8_t *readRange(HANDLE file, uint64_t offset, uint64_t size) {
    uint8_t *buffer = (uint8_t *)VirtualAlloc(NULL, size ? size : 1, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!buffer) return NULL;
    LARGE_INTEGER pos; pos.QuadPart = (LONGLONG)offset;
    if (!SetFilePointerEx(file, pos, NULL, FILE_BEGIN)) { VirtualFree(buffer, 0, MEM_RELEASE); return NULL; }
    uint64_t done = 0;
    while (done < size) {
        DWORD chunk = (DWORD)((size - done) > (1u << 26) ? (1u << 26) : (size - done)), got = 0;
        if (!ReadFile(file, buffer + done, chunk, &got, NULL) || got == 0) { VirtualFree(buffer, 0, MEM_RELEASE); return NULL; }
        done += got;
    }
    return buffer;
}

static void removeTree(const wchar_t *dir) {
    wchar_t pattern[2048];
    _snwprintf(pattern, 2048, L"%ls\\*", dir);
    WIN32_FIND_DATAW data;
    HANDLE find = FindFirstFileW(pattern, &data);
    if (find != INVALID_HANDLE_VALUE) {
        do {
            if (!wcscmp(data.cFileName, L".") || !wcscmp(data.cFileName, L"..")) continue;
            wchar_t child[2048];
            _snwprintf(child, 2048, L"%ls\\%ls", dir, data.cFileName);
            if (data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) removeTree(child);
            else { SetFileAttributesW(child, FILE_ATTRIBUTE_NORMAL); DeleteFileW(child); }
        } while (FindNextFileW(find, &data));
        FindClose(find);
    }
    RemoveDirectoryW(dir);
}

static void writeText(const wchar_t *path, const char *text) {
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) { DWORD w; WriteFile(file, text, (DWORD)strlen(text), &w, NULL); CloseHandle(file); }
}

static unsigned readNumber(const wchar_t *path) {
    char text[32] = {0};
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return 0;
    DWORD got = 0;
    ReadFile(file, text, 31, &got, NULL);
    CloseHandle(file);
    return (unsigned)strtoul(text, NULL, 10);
}

/* --------------------------------------------------------------------------------------- setup + window ---- */
typedef struct {
    wchar_t exePath[MAX_PATH * 2], root[2048], pyDir[2048], appDir[2048], pyMarker[2048], appMarker[2048];
    Trailer trailer;
    int needRuntime, needApp, ok;
} Setup;

static DWORD WINAPI setupThread(LPVOID param) {
    Setup *setup = (Setup *)param;
    HANDLE exe = CreateFileW(setup->exePath, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (exe == INVALID_HANDLE_VALUE) { _snwprintf(gError, 512, L"Could not read the installer file."); return 1; }
    crcInit();
    CreateDirectoryW(setup->root, NULL);
    double total = (setup->needRuntime ? 90.0 : 0.0) + (setup->needApp ? 10.0 : 0.0);
    double base = 0;
    if (setup->needRuntime) {
        uint8_t *zip = readRange(exe, setup->trailer.rtOffset, setup->trailer.rtSize);
        if (!zip) { _snwprintf(gError, 512, L"Not enough memory to unpack."); CloseHandle(exe); return 1; }
        removeTree(setup->pyDir);  /* A half-finished earlier attempt */
        CreateDirectoryW(setup->pyDir, NULL);
        int rc = extractZip(zip, (size_t)setup->trailer.rtSize, setup->pyDir, base / total, 90.0 / total);
        VirtualFree(zip, 0, MEM_RELEASE);
        if (rc != 0) { if (!gError[0]) _snwprintf(gError, 512, L"Unpacking failed (code %d). Is the disk full?", rc); CloseHandle(exe); return 1; }
        writeText(setup->pyMarker, "ok");
        base += 90.0;
    }
    if (setup->needApp) {
        uint8_t *zip = readRange(exe, setup->trailer.appOffset, setup->trailer.appSize);
        if (!zip) { _snwprintf(gError, 512, L"Not enough memory to unpack."); CloseHandle(exe); return 1; }
        CreateDirectoryW(setup->appDir, NULL);
        int rc = extractZip(zip, (size_t)setup->trailer.appSize, setup->appDir, base / total, 10.0 / total);
        VirtualFree(zip, 0, MEM_RELEASE);
        if (rc != 0) { if (!gError[0]) _snwprintf(gError, 512, L"Unpacking the app failed (code %d).", rc); CloseHandle(exe); return 1; }
        char number[16];
        _snprintf(number, 16, "%u", setup->trailer.build);
        writeText(setup->appMarker, number);
    }
    CloseHandle(exe);
    InterlockedExchange(&gProgress, 1000);
    setup->ok = 1;
    return 0;
}

/* ---------------------------------------------------------------------------------- splash window ----
 * A small borderless window drawn by hand to match the app: dark (or light, following Windows), the logo, a status
 * line and a smooth progress bar. Everything is painted off-screen first so it never flickers. */
typedef struct { COLORREF bg, border, text, muted, track, fill; } Palette;
static Palette gPal;
static double gShown = 0.0;   /* The bar eases towards gProgress instead of jumping */
static HICON gLogo;
static HFONT gTitleFont, gBodyFont, gSmallFont;
static int gDpi = 96;
static bool gFirstRun = true;
#define S(x) MulDiv((x), gDpi, 96)

static bool appsUseLightTheme(void) {
    DWORD value = 0, size = sizeof(value);
    if (RegGetValueW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize", L"AppsUseLightTheme",
                     RRF_RT_REG_DWORD, NULL, &value, &size) == ERROR_SUCCESS) return value != 0;
    return false;
}

static void fillRound(HDC dc, RECT r, int radius, COLORREF fill, COLORREF line) {
    HBRUSH brush = CreateSolidBrush(fill);
    HPEN pen = CreatePen(PS_SOLID, 1, line);
    HGDIOBJ oldBrush = SelectObject(dc, brush), oldPen = SelectObject(dc, pen);
    RoundRect(dc, r.left, r.top, r.right, r.bottom, radius, radius);
    SelectObject(dc, oldBrush); SelectObject(dc, oldPen);
    DeleteObject(brush); DeleteObject(pen);
}

static void drawText(HDC dc, const wchar_t *text, int x, int y, int w, int h, HFONT font, COLORREF color, UINT flags) {
    RECT r = { x, y, x + w, y + h };
    HGDIOBJ old = SelectObject(dc, font);
    SetTextColor(dc, color);
    DrawTextW(dc, text, -1, &r, flags | DT_NOPREFIX | DT_SINGLELINE);
    SelectObject(dc, old);
}

static void paintSplash(HWND hwnd, HDC target) {
    RECT client;
    GetClientRect(hwnd, &client);
    int w = client.right, h = client.bottom;
    HDC dc = CreateCompatibleDC(target);
    HBITMAP bitmap = CreateCompatibleBitmap(target, w, h);
    HGDIOBJ oldBitmap = SelectObject(dc, bitmap);
    SetBkMode(dc, TRANSPARENT);
    fillRound(dc, client, S(28), gPal.bg, gPal.border);
    if (gLogo) DrawIconEx(dc, S(30), S(28), gLogo, S(56), S(56), 0, NULL, DI_NORMAL);
    drawText(dc, L"Syncplay Marquee", S(102), S(26), w - S(130), S(30), gTitleFont, gPal.text, DT_LEFT | DT_VCENTER);
    drawText(dc, gFirstRun ? L"Setting up for the first time" : L"Installing the new version", S(102), S(58), w - S(130), S(22), gBodyFont, gPal.muted, DT_LEFT | DT_VCENTER);
    int percent = (int)(gShown / 10.0 + 0.5);
    wchar_t number[16];
    _snwprintf(number, 16, L"%d%%", percent);
    drawText(dc, gShown >= 950.0 ? L"Finishing up..." : L"Unpacking...", S(30), S(112), w / 2, S(20), gSmallFont, gPal.muted, DT_LEFT | DT_VCENTER);
    drawText(dc, number, w - S(30) - S(80), S(112), S(80), S(20), gSmallFont, gPal.text, DT_RIGHT | DT_VCENTER);
    RECT track = { S(30), S(138), w - S(30), S(138) + S(8) };
    fillRound(dc, track, S(8), gPal.track, gPal.track);
    int filled = (int)((track.right - track.left) * gShown / 1000.0);
    if (filled > 0) {
        RECT bar = { track.left, track.top, track.left + (filled < S(8) ? S(8) : filled), track.bottom };
        fillRound(dc, bar, S(8), gPal.fill, gPal.fill);
    }
    drawText(dc, gFirstRun ? L"This only happens once and takes a few seconds." : L"Just a moment.", S(30), h - S(38), w - S(60), S(20), gSmallFont, gPal.muted, DT_LEFT | DT_VCENTER);
    BitBlt(target, 0, 0, w, h, dc, 0, 0, SRCCOPY);
    SelectObject(dc, oldBitmap);
    DeleteObject(bitmap);
    DeleteDC(dc);
}

static LRESULT CALLBACK splashProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_TIMER: {
        double target = (double)gProgress;
        gShown += (target - gShown) * 0.22;
        if (target - gShown < 0.6) gShown = target;
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;
    }
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(hwnd, &ps);
        paintSplash(hwnd, dc);
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_NCHITTEST: return HTCAPTION;  /* Drag the window from anywhere */
    case WM_APP: DestroyWindow(hwnd); return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static HFONT makeFont(int pixels, int weight) {
    return CreateFontW(-S(pixels), 0, 0, 0, weight, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                       CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
}

static int runSetup(Setup *setup, HINSTANCE instance) {
    SetProcessDPIAware();
    HDC screen = GetDC(NULL);
    gDpi = GetDeviceCaps(screen, LOGPIXELSX);
    ReleaseDC(NULL, screen);
    gFirstRun = setup->needRuntime;
    if (appsUseLightTheme()) {
        Palette p = { RGB(0xff, 0xff, 0xff), RGB(0xd5, 0xd8, 0xde), RGB(0x24, 0x27, 0x2d), RGB(0x5d, 0x63, 0x6e), RGB(0xe6, 0xe8, 0xec), RGB(0x3f, 0x6f, 0xd4) };
        gPal = p;
    } else {
        Palette p = { RGB(0x1f, 0x20, 0x24), RGB(0x3b, 0x3e, 0x46), RGB(0xe3, 0xe5, 0xe9), RGB(0x9d, 0xa2, 0xac), RGB(0x34, 0x36, 0x3d), RGB(0x4c, 0x7f, 0xe6) };
        gPal = p;
    }
    gLogo = (HICON)LoadImageW(instance, MAKEINTRESOURCEW(1), IMAGE_ICON, S(56), S(56), LR_DEFAULTCOLOR);
    gTitleFont = makeFont(22, FW_SEMIBOLD);
    gBodyFont = makeFont(14, FW_NORMAL);
    gSmallFont = makeFont(12, FW_NORMAL);
    WNDCLASSW cls;
    ZeroMemory(&cls, sizeof(cls));
    cls.lpfnWndProc = splashProc;
    cls.hInstance = instance;
    cls.hCursor = LoadCursor(NULL, IDC_ARROW);
    cls.hIcon = LoadIconW(instance, MAKEINTRESOURCEW(1));
    cls.lpszClassName = L"MarqueeSetup";
    RegisterClassW(&cls);
    int w = S(460), h = S(200);
    HWND window = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW, L"MarqueeSetup", TITLE, WS_POPUP, (GetSystemMetrics(SM_CXSCREEN) - w) / 2,
                                  (GetSystemMetrics(SM_CYSCREEN) - h) / 2, w, h, NULL, NULL, instance, NULL);
    SetWindowRgn(window, CreateRoundRectRgn(0, 0, w + 1, h + 1, S(28), S(28)), TRUE);
    ShowWindow(window, SW_SHOW);
    SetTimer(window, 1, 33, NULL);
    HANDLE thread = CreateThread(NULL, 0, setupThread, setup, 0, NULL);
    MSG msg;
    while (true) {
        DWORD wait = MsgWaitForMultipleObjects(1, &thread, FALSE, INFINITE, QS_ALLINPUT);
        if (wait == WAIT_OBJECT_0) break;
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    }
    if (setup->ok) {  /* Let the bar reach 100% before the window goes away */
        for (int i = 0; i < 12 && gShown < 1000.0; i++) {
            gShown += (1000.0 - gShown) * 0.5 + 1.0;
            if (gShown > 1000.0) gShown = 1000.0;
            InvalidateRect(window, NULL, FALSE);
            UpdateWindow(window);
            Sleep(25);
        }
        Sleep(120);
    }
    KillTimer(window, 1);
    DestroyWindow(window);
    CloseHandle(thread);
    DeleteObject(gTitleFont); DeleteObject(gBodyFont); DeleteObject(gSmallFont);
    return setup->ok ? 0 : 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR arguments, int show) {
    static Setup setup;
    DWORD n = GetModuleFileNameW(NULL, setup.exePath, MAX_PATH * 2);
    if (n == 0 || n >= MAX_PATH * 2) { MessageBoxW(NULL, L"Could not find the program file.", TITLE, MB_ICONERROR); return 1; }

    HANDLE exe = CreateFileW(setup.exePath, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    LARGE_INTEGER end;
    DWORD got = 0;
    if (exe == INVALID_HANDLE_VALUE || !GetFileSizeEx(exe, &end) || end.QuadPart < (LONGLONG)sizeof(Trailer)) {
        MessageBoxW(NULL, L"Could not read the program file.", TITLE, MB_ICONERROR); return 1;
    }
    LARGE_INTEGER pos; pos.QuadPart = end.QuadPart - (LONGLONG)sizeof(Trailer);
    SetFilePointerEx(exe, pos, NULL, FILE_BEGIN);
    if (!ReadFile(exe, &setup.trailer, sizeof(Trailer), &got, NULL) || got != sizeof(Trailer) || memcmp(setup.trailer.magic, MAGIC, 8) != 0) {
        CloseHandle(exe);
        MessageBoxW(NULL, L"This file is damaged (the packed app is missing). Please download it again.", TITLE, MB_ICONERROR);
        return 1;
    }
    CloseHandle(exe);

    wchar_t base[2048];
    DWORD len = GetEnvironmentVariableW(L"MARQUEE_HOME", base, 2048);
    if (len == 0 || len >= 2048) {
        len = GetEnvironmentVariableW(L"LOCALAPPDATA", base, 2048);
        if (len == 0 || len >= 2048) { MessageBoxW(NULL, L"Could not find your local app data folder.", TITLE, MB_ICONERROR); return 1; }
        _snwprintf(setup.root, 2048, L"%ls\\Syncplay Marquee", base);
    } else {
        _snwprintf(setup.root, 2048, L"%ls", base);
    }
    wchar_t stamp[17] = {0};
    for (int i = 0; i < 16; i++) stamp[i] = (wchar_t)(unsigned char)setup.trailer.rtStamp[i];
    _snwprintf(setup.pyDir, 2048, L"%ls\\python-%ls", setup.root, stamp);
    _snwprintf(setup.appDir, 2048, L"%ls\\app", setup.root);
    _snwprintf(setup.pyMarker, 2048, L"%ls\\.unpacked", setup.pyDir);
    _snwprintf(setup.appMarker, 2048, L"%ls\\.marquee-build", setup.appDir);

    setup.needRuntime = !exists(setup.pyMarker);
    setup.needApp = !exists(setup.appDir) || readNumber(setup.appMarker) < setup.trailer.build;  /* An in-app update may be newer */
    if (setup.needRuntime || setup.needApp) {
        if (runSetup(&setup, instance) != 0) {
            wchar_t message[900];
            _snwprintf(message, 900, L"Setup could not finish.\n\n%ls", gError[0] ? gError : L"Unknown error.");
            MessageBoxW(NULL, message, TITLE, MB_ICONERROR);
            return 1;
        }
        if (setup.needRuntime) {  /* Drop runtimes left by older versions */
            wchar_t pattern[2048];
            _snwprintf(pattern, 2048, L"%ls\\python-*", setup.root);
            WIN32_FIND_DATAW data;
            HANDLE find = FindFirstFileW(pattern, &data);
            if (find != INVALID_HANDLE_VALUE) {
                do {
                    wchar_t old[2048];
                    _snwprintf(old, 2048, L"%ls\\%ls", setup.root, data.cFileName);
                    if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && wcscmp(old, setup.pyDir) != 0) removeTree(old);
                } while (FindNextFileW(find, &data));
                FindClose(find);
            }
        }
    }

    wchar_t noLaunch[8];
    if (GetEnvironmentVariableW(L"MARQUEE_NO_LAUNCH", noLaunch, 8) > 0) return 0;

    static wchar_t python[2048], script[2048], command[65536];
    _snwprintf(python, 2048, L"%ls\\pythonw.exe", setup.pyDir);
    _snwprintf(script, 2048, L"%ls\\program\\launch-syncplay.pyw", setup.appDir);
    _snwprintf(command, 65536, L"\"%ls\" \"%ls\" %ls", python, script, arguments ? arguments : L"");
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ZeroMemory(&startup, sizeof(startup));
    startup.cb = sizeof(startup);
    if (!CreateProcessW(NULL, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, setup.appDir, &startup, &process)) {
        MessageBoxW(NULL, L"Could not start Syncplay Marquee. Delete the folder %LOCALAPPDATA%\\Syncplay Marquee and open this file again.", TITLE, MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
