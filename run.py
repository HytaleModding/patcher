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


if __name__ == "__main__":
    actions = ("setup", "makeFeaturePatches", "applyPatches")

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

        logger.info("Applying patches")
        apply_feature_patches(repo)


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

