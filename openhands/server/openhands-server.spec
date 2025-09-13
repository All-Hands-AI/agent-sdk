# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for OpenHands Server.

This spec file configures PyInstaller to create a standalone executable
for the OpenHands Server application.
"""

from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    copy_metadata
)


# Get the project root directory (current working directory when running PyInstaller)
project_root = Path.cwd()

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Include any data files that might be needed
        # Add more data files here if needed in the future
        *collect_data_files('tiktoken'),
        *collect_data_files('tiktoken_ext'),
        *collect_data_files('litellm'),
        *collect_data_files('fastmcp'),
        *collect_data_files('mcp'),
        # Include Jinja prompt templates required by the agent SDK
        *collect_data_files('openhands.sdk.agent', includes=['prompts/*.j2']),
        # Include FastAPI static files and templates
        *collect_data_files('fastapi'),
        *collect_data_files('uvicorn'),
        # Include package metadata for importlib.metadata
        *copy_metadata('fastmcp'),
        *copy_metadata('fastapi'),
        *copy_metadata('uvicorn'),
        *copy_metadata('pydantic'),
    ],
    hiddenimports=[
        # Explicitly include modules that might not be detected automatically
        *collect_submodules('openhands.server'),
        # Include OpenHands SDK and tools submodules explicitly
        *collect_submodules('openhands.sdk'),
        *collect_submodules('openhands.tools'),
        
        # FastAPI and server dependencies
        *collect_submodules('fastapi'),
        *collect_submodules('uvicorn'),
        *collect_submodules('pydantic'),
        
        # LLM and tokenization dependencies
        *collect_submodules('tiktoken'),
        *collect_submodules('tiktoken_ext'),
        *collect_submodules('litellm'),
        *collect_submodules('fastmcp'),
        # Include mcp but exclude CLI parts that require typer
        'mcp.types',
        'mcp.client',
        'mcp.server',
        'mcp.shared',
        
        # Additional server-specific imports
        'multipart',
        'email_validator',
        'python_multipart',
        'starlette',
        'anyio',
        'sniffio',
        'h11',
        'httptools',
        'websockets',
        'watchfiles',
        'python_dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce binary size
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'IPython',
        'jupyter',
        'notebook',
        # Exclude mcp CLI parts that cause issues
        'mcp.cli',
        'mcp.cli.cli',
        # Exclude litellm proxy UI parts not needed for server
        'litellm.proxy.ui_crud_endpoints',
        # Exclude test modules
        'pytest',
        'unittest',
        'test',
        'tests',
    ],
    noarchive=False,
    # IMPORTANT: do not use optimize=2 (-OO) because it strips docstrings used by PLY/bashlex grammar
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='openhands-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
