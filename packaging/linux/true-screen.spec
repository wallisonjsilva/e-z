"""Candidato Linux onedir; build local não representa homologação/release."""

from pathlib import Path

root = Path(SPECPATH).resolve().parents[1]
unused_qt = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.QtHttpServer", "PySide6.QtWebSockets",
    "PySide6.Qt5Compat", "PySide6.QtNetwork", "pytest", "PyInstaller",
]

a = Analysis(
    [str(root / "src/true_screen/__main__.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["PySide6.QtDBus"],
    hookspath=[],
    runtime_hooks=[],
    excludes=unused_qt,
    noarchive=False,
)
# PNG é integrado ao QtGui; JPEG é o único plugin de imagem requerido.
unused_libraries = ("libQt6Network.so", "libQt6Pdf.so", "libQt6Qml", "libQt6Quick",
                    "libQt6VirtualKeyboard", "libQt6EglFS", "libQt6EglFs")
desktop_platforms = {"libqxcb.so", "libqwayland-egl.so", "libqwayland-generic.so", "libqoffscreen.so", "libqminimal.so"}

def required_binary(entry):
    target = entry[0]
    name = Path(target).name
    if name.startswith(unused_libraries):
        return False
    if "/imageformats/" in target:
        return name == "libqjpeg.so"
    if "/platforms/" in target:
        return name in desktop_platforms
    if "/egldeviceintegrations/" in target or name == "libqtuiotouchplugin.so":
        return False
    if "/tls/" in target or "/networkinformation/" in target or "virtualkeyboard" in target.lower():
        return False
    return True

a.binaries = [entry for entry in a.binaries if required_binary(entry)]
a.datas = [entry for entry in a.datas if required_binary(entry)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="true-screen",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="true-screen")
