# Starts Syncplay without a console window (run with pythonw.exe). Anything Syncplay would print goes to syncplay.log.
import os
import runpy
import sys

here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # The Syncplay folder (this file lives in program/)
os.chdir(here)
sys.path.insert(0, here)

try:  # Give Syncplay its own Windows identity so the taskbar shows the Syncplay icon, not pythonw's Python logo
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Syncplay.Marquee.Client")
except Exception:
    pass

log = None
try:
    log = open(os.path.join(here, "syncplay.log"), "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stderr = log
except OSError:
    pass
updater = None
try:  # If the previous start after an update never got as far as a working window, put the old version back first
    from syncplay import updater
    if updater.recoverFromFailedUpdate(here):
        print("The last update didn't start properly, so the previous version was restored.")
        updater.forgetLoadedModules()
except Exception:
    import traceback
    traceback.print_exc()
try:  # A downloaded update is installed here, before any Syncplay module is loaded, so no file is in use
    import time
    from syncplay import updater
    if updater.hasStagedUpdate(here):
        for attempt in range(1, 7):  # A file can be briefly locked (virus scanner, the old copy still closing): try again
            try:
                print("Applying downloaded update (try {})".format(attempt))
                print("Applied downloaded update: {} files".format(updater.applyStaged(here, log=log)))
                break
            except OSError as e:
                print("Could not apply the update yet: {}".format(e))
                if attempt == 6:
                    raise
                time.sleep(1.5)
        updater.forgetLoadedModules()
except Exception:
    import traceback
    traceback.print_exc()
try:
    if updater is not None:
        updater.markStarted(here)  # From now on, a start that never shows a working window counts as a failed update
except Exception:
    pass
try:
    runpy.run_path(os.path.join(here, "syncplayClient.py"), run_name="__main__")
except SystemExit:
    raise
except BaseException:
    import traceback
    traceback.print_exc()
    try:  # A fresh update that crashes on start is undone right away and the previous version is started instead
        import subprocess
        from syncplay import updater as _updater
        if _updater.pendingUpdate(here) and _updater.rollBack(here, "The new version crashed while starting.", block=True):
            print("Rolled back the update; starting the previous version.")
            subprocess.Popen([sys.executable] + sys.argv, cwd=here, close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "Syncplay Marquee could not start. Details are in syncplay.log next to Syncplay Marquee.exe.", "Syncplay Marquee", 0x10)
    except Exception:
        pass
