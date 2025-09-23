import platform


def get_platform() -> str:
    system = platform.system().lower()  # e.g., "Linux" → "linux"
    machine = platform.machine().lower()  # e.g., "aarch64" → "arm64"

    # Normalize common architecture names
    arch_map = {
        "x86_64": "amd64",
        "aarch64": "arm64",
        "armv7l": "arm/v7",
        "armv6l": "arm/v6",
    }
    arch = arch_map.get(machine, machine)

    return f"{system}/{arch}"
