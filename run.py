import os

from common import *
import sys
import shutil
import xml.etree.ElementTree as ET

from python_git_wrapper import Repository, GitError
from utils import ensure_maven

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
            # Run from project root with --directory to handle paths correctly
            relative_src_path = src_root.relative_to(Constants.PROJECT_DIR)
            # Use forward slashes for git directory argument
            directory_arg = str(relative_src_path).replace(os.sep, '/')

            out = subprocess.run(
                ["git", "apply", f"--directory={directory_arg}", "-p1", str(patch_file.absolute())],
                cwd=str(Constants.PROJECT_DIR),
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Applied patch {}, out={}", rel_path, out.stdout.strip())
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

            cmd = ["git", "diff", "--no-index", "--minimal", "--no-prefix",
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
    actions = ("setup", "makeFeaturePatches", "makeSourcePatches", "applySourcePatches")

    if len(sys.argv) <= 1 or sys.argv[1] not in actions:
        print("Usage: python run.py [{}]".format("|".join(actions)))
        sys.exit(1)

    logger.info('\n\n[ [ HytaleModding patcher by Neil, ribica & other contributors ] ]\n')


    action = sys.argv[1]
    pre_init()

    if action == "setup":
        if Constants.PROJECT_DIR.is_dir():
            logger.warning("Project directory already exists. Please delete the folder and run setup again.")
            sys.exit(1)

        decompile_dir = Constants.DECOMPILE_DIR
        skip_decompile = decompile_dir.exists() and any(decompile_dir.iterdir())

        # shutil.rmtree(Constants.WORK_DIR, ignore_errors=True)
        if not skip_decompile:
            Constants.ensure_dirs()

            # download and decompile
            jar_path = Constants.DOWNLOADS_DIR / "hytale-server.jar"
            download_server_jar(jar_path)

            decompile(jar_path, Constants.DECOMPILE_DIR, use_vineflower=True)
        else:
            logger.warning("Skipped decompilation because the work directory already exists!")

        # initialize project directory
        if not USE_MAVEN:
            # raw intellij build system:
            logger.error("Please use Maven")
            sys.exit(1)
            # Constants.PROJECT_DIR.mkdir(parents=True, exist_ok=True)
            # src = Constants.PROJECT_DIR / "src"
            # src.mkdir(parents=True, exist_ok=True)
        else:
            ensure_maven()
            # Maven initialization:
            # mvn archetype:generate -DgroupId=com.hypixel.hytale -DartifactId=hytale-server -DarchetypeArtifactId=maven‑archetype‑quickstart -DinteractiveMode=false
            logger.info("\n\nInitializing Maven project in:\n{}\n\n", Constants.PROJECT_DIR)

            subprocess.run([
                "mvn", "archetype:generate",
                # "-DgroupId=com.hypixel.hytale", "-DartifactId=hytale-server",
                "-DgroupId=com.hypixel.hytale", "-DartifactId=" + Constants.PROJECT_DIR.name,
                "-DarchetypeArtifactId=maven-archetype-quickstart", "-DinteractiveMode=false"
            ], check=True, shell=True)

            logger.info("Maven project initialized!")

            # Merge pom.xml with template
            pom_file = Constants.PROJECT_DIR / "pom.xml"
            template_file = Constants.BASE_DIR / "pom.xml.template"

            if template_file.exists():
                ET.register_namespace('', "http://maven.apache.org/POM/4.0.0")
                ns = {'mvn': 'http://maven.apache.org/POM/4.0.0'}

                target_tree = ET.parse(pom_file)
                target_root = target_tree.getroot()

                template_tree = ET.parse(template_file)
                template_root = template_tree.getroot()

                # Update dependencies
                tmpl_deps = template_root.find('mvn:dependencies', ns)
                if tmpl_deps is not None:
                    target_deps = target_root.find('mvn:dependencies', ns)
                    if target_deps is not None:
                        target_root.remove(target_deps)
                    target_root.append(tmpl_deps)

                # Update build
                tmpl_build = template_root.find('mvn:build', ns)
                if tmpl_build is not None:
                    target_build = target_root.find('mvn:build', ns)
                    if target_build is not None:
                        target_root.remove(target_build)
                    target_root.append(tmpl_build)

                target_tree.write(pom_file, encoding='UTF-8', xml_declaration=True)
                logger.info("Updated pom.xml with dependencies and build configuration from template")
            else:
                logger.warning("pom.xml.template not found, skipping pom update")

            src = Constants.PROJECT_DIR / "src" / "main" / "java"

        shutil.rmtree(src)
        src.mkdir(parents=True, exist_ok=True)

        # Copy only com.hypixel sources
        src_hypixel = Constants.DECOMPILE_DIR / "com" / "hypixel"
        dst_hypixel = src / "com" / "hypixel"

        if not src_hypixel.exists():
            logger.error("com.hypixel sources not found in decompiled output!")
            sys.exit(1)

        logger.info("Copying com.hypixel sources...")
        shutil.copytree(src_hypixel, dst_hypixel)
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

        logger.info('')
        logger.info('Setup finished!')
        logger.info('You can now open the "{}" folder in IntelliJ IDEA and follow further instructions in the README', Constants.PROJECT_DIR)
        logger.info('Please give us a star on GitHub if you find this project useful.')
        logger.info('Happy Modding!')
        logger.info('')

    elif action == "makeFeaturePatches":
        logger.warning("This is deprecated, please consider using makeSourcePatches instead.")

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

    elif action == "makeSourcePatches":
        make_source_patches()

    elif action == "applySourcePatches":
        apply_source_patches()
