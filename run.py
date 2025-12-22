import os

from common import *
import sys
import shutil

from python_git_wrapper import Repository, GitError

USE_MAVEN = True


def ensure_repo() -> Repository:
    if not Constants.PROJECT_DIR.is_dir() or not (Constants.PROJECT_DIR / ".git").is_dir():
        logger.error("Project directory does not exist or is not a git repository. Please run setup first.")
        sys.exit(1)

    repo = Repository(str(Constants.DECOMPILE_DIR))
    # repo.current_branch  # will raise if empty
    return repo

def apply_feature_patches(repo: Repository):
    try:
        repo.execute("am --abort")
    except GitError as e:
        if "Resolve operation not in progress, we are not resuming." not in e.args[0]:
            logger.error("Failed to abort previous patch application: {}", e)
            sys.exit(1)

    for patch_file in sorted(Constants.PATCHES_DIR.glob("*.patch")):
        try:
            repo.execute("am --3way", str(patch_file))
        except GitError as e:
            logger.warning("Failed to apply patch {}: {}", patch_file.name, e)
            logger.warning("Please resolve the conflict manually and then run makeFeaturePatches")
            sys.exit(1)


def apply_source_patches():
    logger.info("Applying source patches...")
    src_root = Constants.PROJECT_DIR / "src" / "main" / "java"
    decompile_root = Constants.DECOMPILE_DIR
    patches_root = Constants.SRC_PATCHES_DIR

    if not patches_root.exists():
        logger.info("No source patches directory found.")
        return

    patches = list(patches_root.rglob("*.patch"))
    if not patches:
        logger.info("No source patches found.")
        return

    logger.info("Found {} source patches.", len(patches))

    for patch_file in patches:
        rel_path = patch_file.relative_to(patches_root)
        java_rel_path = rel_path.with_suffix(".java")
        target_file = src_root / java_rel_path
        original_file = decompile_root / java_rel_path

        if not original_file.exists():
            logger.warning("Original file for patch {} not found at {}", rel_path, original_file)
            continue

        # Copy original to target, stripping CR
        target_file.parent.mkdir(parents=True, exist_ok=True)

        content = original_file.read_bytes().replace(b'\r', b'')
        target_file.write_bytes(content)

        # Apply patch
        try:
            subprocess.run(
                ["git", "apply", "-p1", str(patch_file.absolute())],
                cwd=str(src_root),
                check=True,
                capture_output=True
            )
            logger.info("Applied patch {}", rel_path)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to apply patch {}: {}", rel_path, e.stderr.decode().strip())


def make_source_patches():
    logger.info("Making source patches...")
    src_root = Constants.PROJECT_DIR / "src" / "main" / "java"
    decompile_root = Constants.DECOMPILE_DIR
    patches_root = Constants.SRC_PATCHES_DIR

    patches_root.mkdir(parents=True, exist_ok=True)

    count = 0

    for file_path in src_root.rglob("*.java"):
        rel_path = file_path.relative_to(src_root)
        original_file = decompile_root / rel_path

        if not original_file.exists():
            continue

        # Prepare temp files with stripped CR
        with tempfile.TemporaryDirectory() as tmpdir:
            t_orig_dir = Path(tmpdir) / "a"
            t_mod_dir = Path(tmpdir) / "b"

            t_orig = t_orig_dir / rel_path
            t_mod = t_mod_dir / rel_path

            t_orig.parent.mkdir(parents=True, exist_ok=True)
            t_mod.parent.mkdir(parents=True, exist_ok=True)

            t_orig.write_bytes(original_file.read_bytes().replace(b'\r', b''))
            t_mod.write_bytes(file_path.read_bytes().replace(b'\r', b''))

            cmd = ["git", "diff", "--no-index", "--minimal",
                   f"a/{rel_path.as_posix()}",
                   f"b/{rel_path.as_posix()}"]

            result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)

            patch_content = result.stdout
            patch_file = patches_root / rel_path.with_suffix(".patch")

            if patch_content:
                patch_file.parent.mkdir(parents=True, exist_ok=True)
                if patch_file.exists() and patch_file.read_text() == patch_content:
                    pass
                else:
                    patch_file.write_text(patch_content)
                    logger.info("Created/Updated patch: {}", patch_file.name)
                    count += 1
            else:
                if patch_file.exists():
                    patch_file.unlink()
                    logger.info("Removed patch: {}", patch_file.name)

    logger.info("Processed source patches. Created/Updated: {}", count)


if __name__ == "__main__":
    actions = ("setup", "makeFeaturePatches", "applyPatches", "makeSourcePatches", "applySourcePatches")

    if len(sys.argv) <= 1 or sys.argv[1] not in actions:
        print("Usage: python run.py [{}]".format("|".join(actions)))
        sys.exit(1)

    action = sys.argv[1]
    pre_init()

    if action == "setup":
        if Constants.PROJECT_DIR.is_dir():
            print("Project directory already exists. Please delete the folder and run setup again.")
            sys.exit(1)

        # remove previous work dir
        shutil.rmtree(Constants.WORK_DIR, ignore_errors=True)
        Constants.ensure_dirs()

        # download and decompile
        jar_path = Constants.DOWNLOADS_DIR / "minigui.jar"
        download_server_jar(jar_path)

        decompile(jar_path, Constants.DECOMPILE_DIR)

        # TODO: apply patches after setup

        # initialize project directory
        if not USE_MAVEN:
            # raw intellij build system:
            Constants.PROJECT_DIR.mkdir(parents=True, exist_ok=True)
            src = Constants.PROJECT_DIR / "src"
            src.mkdir(parents=True, exist_ok=True)
        else:
            # Maven initialization:
            # mvn archetype:generate -DgroupId=com.hypixel.hytale -DartifactId=hytale-server -DarchetypeArtifactId=maven‑archetype‑quickstart -DinteractiveMode=false
            logger.info("\n\nInitializing Maven project in:\n{}\n\n", Constants.PROJECT_DIR)

            subprocess.run([
                "mvn", "archetype:generate",
                # "-DgroupId=com.hypixel.hytale", "-DartifactId=hytale-server",
                "-DgroupId=dev.ribica.hytalemodding", "-DartifactId=" + Constants.PROJECT_DIR.name,
                "-DarchetypeArtifactId=maven-archetype-quickstart", "-DinteractiveMode=false"
            ], check=True, shell=True)

            logger.info("Maven project initialized!")

            src = Constants.PROJECT_DIR / "src" / "main" / "java"

        shutil.rmtree(src)
        shutil.copytree(Constants.DECOMPILE_DIR, src)

        repo_gitignore = Constants.PROJECT_DIR / ".gitignore"
        repo_gitignore.write_text("\n".join(("target/", ".idea/", "out/", "*.iml", "*.class")))

        repo = Repository(str(Constants.PROJECT_DIR))
        repo.execute("init")
        repo.add_files(['.gitignore'])
        repo.add_files(all_files=True)
        repo.commit("Initial decompilation")
        repo.execute("tag baseline")

        # logger.info("Applying patches")
        # apply_feature_patches(repo)


    elif action == "makeFeaturePatches":
        repo = ensure_repo()
        tmp = tempfile.TemporaryDirectory()

        # git format-patch --no-stat --minimal -N -o ../patches [range]
        # range can be abc1234..HEAD or similar

        # for some reason this does not work, like python subprocess changes how baseline..HEAD is passed as argument?
        # out = repo.execute(
        #     "format-patch --no-stat --minimal -N",
        #     "-o", tmp.name,
        #     "baseline..HEAD"
        # )
        out = subprocess.run(
            f'git format-patch --no-stat --minimal -N -o "{tmp.name}" baseline..HEAD',
            cwd=str(Constants.PROJECT_DIR), shell=True, capture_output=True, text=True, check=True
        )

        logger.info("git format-patch output:\n{}", out.stdout.strip())
        num_patches = len(list(Constants.PATCHES_DIR.glob("*.patch")))
        copies = 0
        for new_patch_file in os.listdir(tmp.name):
            index = int(new_patch_file.split("-")[0])  # 0001-...
            if index <= num_patches:
                continue  # skip existing patches
            shutil.move(
                os.path.join(tmp.name, new_patch_file),
                Constants.PATCHES_DIR / new_patch_file
            )
            copies += 1

        logger.info("Patches created, files copied: {}", copies)

    elif action == "applyPatches":
        logger.warning("no-op")
        # repo = ensure_repo()
        # apply_feature_patches(repo)

    elif action == "makeSourcePatches":
        make_source_patches()

    elif action == "applySourcePatches":
        apply_source_patches()
