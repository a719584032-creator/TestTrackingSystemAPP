"""Helper utilities for packaging the client with PyInstaller."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build_executable(output_dir: str = "dist") -> None:
    spec_file = ROOT / "patvs_client.spec"
    if not spec_file.exists():
        spec_file.write_text(
            """
# -*- mode: python -*-
block_cipher = None

a = Analysis(['main.py'],
             pathex=['.'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='patvs-client',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          argv_emulation=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='patvs-client')
""",
            encoding="utf-8",
        )
    subprocess.run(
        ["pyinstaller", "--noconfirm", "--clean", "--distpath", output_dir, str(spec_file)],
        check=True,
    )


if __name__ == "__main__":
    build_executable()
