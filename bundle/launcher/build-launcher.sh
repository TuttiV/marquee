#!/usr/bin/env bash
# Rebuilds "../Syncplay Marquee.exe" (needs mingw-w64: apt install gcc-mingw-w64-x86-64)
set -e
cd "$(dirname "$0")"
x86_64-w64-mingw32-windres launcher.rc -O coff -o launcher.res.o
x86_64-w64-mingw32-gcc -O2 -Wall -mwindows -municode -static -o "../Syncplay Marquee.exe" launcher.c launcher.res.o
x86_64-w64-mingw32-strip "../Syncplay Marquee.exe"
echo "Built ../Syncplay Marquee.exe"
