import tempfile, sys, subprocess
from loguru import logger
from pathlib import Path


def ensure_java():
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


    major = 0
    if java_version is not None:
        major = java_version.split(".")[0]
        major = int(major) if major.isdigit() else 0
    if major < 25:
        logger.error("JDK 25 or newer is required!", java_version)
        sys.exit(1)

    logger.info("Java check success: {}", java_version)

    return java_version


def ensure_git():
    try:
        _ = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        logger.info("Git check success: {}", _.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("Git not found! Please make sure Git is installed and available in your system PATH.")
        sys.exit(1)


def ensure_jar():
    try:
        _ = subprocess.run(["jar", "--version"], capture_output=True, text=True, check=True)
        logger.info("Jar utility check success: {}", _.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("Please make sure JDK is properly installed and the corresponding bin folder is on PATH.")
        sys.exit(1)

def ensure_maven():
    try:
        _ = subprocess.run(["mvn", "--version"], capture_output=True, text=True, check=True)
        logger.info("Maven check success: {}", _.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("Please make sure Maven is properly installed and the corresponding bin folder is on PATH.")
        sys.exit(1)