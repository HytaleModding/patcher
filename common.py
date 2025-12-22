import subprocess
import sys
import tempfile
from pathlib import Path

import wget
from loguru import logger


class Constants:
    BASE_DIR = Path(__file__).resolve().parent
    TOOLS_DIR = BASE_DIR / "tools"
    WORK_DIR = BASE_DIR / "work"
    DOWNLOADS_DIR = WORK_DIR / "download"
    DECOMPILE_DIR = WORK_DIR / "decompile"
    PATCHES_DIR = BASE_DIR / "patches"

    @staticmethod
    def ensure_dirs():
        Constants.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        Constants.WORK_DIR.mkdir(parents=True, exist_ok=True)
        Constants.DECOMPILE_DIR.mkdir(parents=True, exist_ok=True)
        Constants.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        Constants.PATCHES_DIR.mkdir(parents=True, exist_ok=True)


def pre_init():
    # ensure running from venv
    if sys.prefix == sys.base_prefix:
        logger.error("Please run these scripts inside a virtual environment!")
        sys.exit(1)

    # ensure git
    try:
        _ = subprocess.run("git --version", capture_output=True, text=True, check=True)
        logger.info("Git check success: {}", _.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("Git not found! Please make sure Git is installed and available in your system PATH.")
        sys.exit(1)

    # get java version
    java_version = None
    try:
        fp = tempfile.TemporaryDirectory()
        fpath = Path(fp.name) / "A.java"
        fpath.write_bytes(
            b"public class A{ public static void main(String[] a) { System.out.println(System.getProperty(\"java.version\")); }}")
        result = subprocess.run(["java", str(fpath)], capture_output=True, text=True, check=True)  # java 11+
        java_version = result.stdout.strip()
        fp.cleanup()
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error(
            "Java not found or outdated! Please make sure JDK 25 is installed and available in your system PATH.")
        sys.exit(1)

    # check java version
    major = 0
    if java_version is not None:
        major = java_version.split(".")[0]
        major = int(major) if major.isdigit() else 0
    if major < 25:
        logger.error("JDK 25 or newer is required!", java_version)
        sys.exit(1)

    logger.info("Java check success: {}", java_version)

    # ensure jar utility
    try:
        _ = subprocess.run("jar --version", capture_output=True, text=True, check=True)
        logger.info("Jar utility check success: {}", _.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("Please make sure JDK is properly installed and the corresponding bin folder is on PATH.")
        sys.exit(1)

    Constants.ensure_dirs()


def download_server_jar(out_path: Path):
    # TODO: replace with actual Hytale server jar after release

    if not out_path.exists():
        logger.info("Downloading jar...")
        wget.download("https://cdn.ribica.dev/minigui.jar", out=str(out_path))


def decompile(jar_in: Path, out_dir: Path):
    if not jar_in.is_file():
        raise ValueError("Input jar does not exist")
    if not out_dir.is_dir():
        raise ValueError("Output directory does not exist")

    # Vineflower equivalent options:
    # --decompile-generics=true --hide-default-constructor=false --remove-bridge=false --ascii-strings=true --use-lvt-names=true
    subprocess.run([
        "java", "-jar", str(Constants.TOOLS_DIR / "fernflower.jar"),
        *"-dgs=1 -hdc=0 -rbr=0 -asc=1 -udv=1".split(),
        str(jar_in),
        str(out_dir)
    ], check=True, stdout=subprocess.DEVNULL)

    out_jar = out_dir / jar_in.name  # Fernflower outputs a jar with source files inside
    subprocess.run(["jar", "xf", str(out_jar)], cwd=str(out_dir), check=True)
    out_jar.unlink()


if __name__ == "__main__":
    pre_init()

    jar_path = Constants.DOWNLOADS_DIR / "minigui.jar"
    download_server_jar(jar_path)

    decompile(jar_path, Constants.DECOMPILE_DIR)
