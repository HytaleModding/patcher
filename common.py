import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import os
import wget
from loguru import logger
from tqdm import tqdm

from utils import ensure_java, ensure_git, ensure_jar


SERVER_JAR_ENV = "HYTALESERVER_JAR_PATH"

class Constants:
    BASE_DIR = Path(__file__).resolve().parent
    TOOLS_DIR = BASE_DIR / "tools"
    WORK_DIR = BASE_DIR / "work"
    DOWNLOADS_DIR = WORK_DIR / "download"
    DECOMPILE_DIR = WORK_DIR / "decompile"
    PATCHES_DIR = BASE_DIR / "patches"
    SRC_PATCHES_DIR = BASE_DIR / "src-patches"
    PROJECT_DIR = BASE_DIR / "hytale-server"


    @staticmethod
    def ensure_dirs():
        Constants.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        Constants.WORK_DIR.mkdir(parents=True, exist_ok=True)
        Constants.DECOMPILE_DIR.mkdir(parents=True, exist_ok=True)
        Constants.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        Constants.PATCHES_DIR.mkdir(parents=True, exist_ok=True)
        Constants.SRC_PATCHES_DIR.mkdir(parents=True, exist_ok=True)
        # do not create PROJECT_DIR here


def pre_init():
    # ensure running from venv
    if sys.prefix == sys.base_prefix:
        logger.error("Please run these scripts inside a virtual environment!")
        sys.exit(1)

    # ensure git
    ensure_git()

    # get and check java version
    java_version = ensure_java()

    # ensure jar utility
    ensure_jar()

    Constants.ensure_dirs()


def download_server_jar(out_path: Path):
    logger.info("Server Jar Environment Path: " + os.getenv(SERVER_JAR_ENV) + "\\HytaleServer.jar")
    if os.path.isfile('HytaleServer.jar'):
        logger.info("Using local HytaleServer.jar, copying to {}", out_path)
        shutil.copyfile('HytaleServer.jar', out_path)
    elif (p := os.getenv(SERVER_JAR_ENV)) and os.path.isfile(p):
        logger.info("Using {}, copying to {}", SERVER_JAR_ENV, out_path)
        shutil.copyfile(p, out_path)
    elif (p := os.getenv(SERVER_JAR_ENV) + "\\HytaleServer.jar") and os.path.isfile(p):
        logger.info("Using {}, copying to {} using only directory", SERVER_JAR_ENV, out_path)
        shutil.copyfile(p, out_path)
    else:
        logger.error("HytaleServer.jar not found, please download it and put it in this directory: {}", os.getcwd())
        sys.exit(1)


def run_fernflower(classes_dir: Path, out_dir: Path):
    # Vineflower equivalent options:
    #
    source = classes_dir / "com" / "hypixel"
    if source.exists():
        out_dir = out_dir / "com" / "hypixel"
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        source = classes_dir

    subprocess.run([
        "java", "-jar", str(Constants.TOOLS_DIR / "fernflower.jar"),
        *"-dgs=1 -hdc=0 -rbr=0 -asc=1 -udv=1 -log=WARN".split(),
        "-e=.",
        str(source),
        str(out_dir)
    ], cwd=str(classes_dir), check=True)


def run_vineflower(classes_dir: Path, out_dir: Path):
    source = classes_dir / "com" / "hypixel"
    if source.exists():
        out_dir = out_dir / "com" / "hypixel"
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        source = classes_dir

    subprocess.run([
        "java", "-jar", str(Constants.TOOLS_DIR / "vineflower.jar"),
        *"--decompile-generics=true --hide-default-constructor=false --remove-bridge=false --ascii-strings=true --use-lvt-names=true --log-level=warn".split(),
        "-e=.",
        str(source),
        str(out_dir)
    ], cwd=str(classes_dir), check=True)


def decompile(jar_in: Path, out_dir: Path, use_vineflower: bool = False):
    if not jar_in.is_file():
        raise ValueError("Input jar does not exist")
    if not out_dir.is_dir():
        raise ValueError("Output directory does not exist")

    logger.info("Extracting {}...", jar_in)
    classes_dir = out_dir / "classes_temp"
    if classes_dir.exists():
        shutil.rmtree(classes_dir)
    classes_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(jar_in, 'r') as zf:
        for member in tqdm(zf.infolist()):
            if member.filename.startswith('darwin') \
                or member.filename.startswith('linux') \
                or member.filename.startswith('freebsd') \
                or member.filename.startswith('win') \
                :  # zstd native libs, skip
                continue
            if member.filename == "META-INF/LICENSE":
                member.filename = "META-INF/LICENSE.renamed"
            zf.extract(member, classes_dir)

    logger.info("Decompiling extracted classes in {} to {}...", classes_dir, out_dir)

    if use_vineflower:
        run_vineflower(classes_dir, out_dir)
    else:
        run_fernflower(classes_dir, out_dir)

    shutil.rmtree(classes_dir)


if __name__ == "__main__":
    pre_init()
