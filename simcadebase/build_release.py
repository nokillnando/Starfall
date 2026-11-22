"""Build the next Simcade core release. Upload its numbered folder before latest.txt."""

import argparse
import hashlib
import re
import shutil
import stat
import sys
import uuid
from pathlib import Path


def retry_read_only_removal(remove, path, error):
    if sys.platform != "win32" or not isinstance(error, PermissionError):
        raise error
    target = Path(path)
    mode = target.stat().st_mode
    if mode & stat.S_IWRITE:
        raise error
    target.chmod(mode | stat.S_IWRITE)
    remove(path)


def export_share(root, config_path, loader, modules, offline, parser):
    addon_table = loader.split("local bundledAddons = {", 1)[1].split("}", 1)[0]
    addons = re.findall(r'^    "(simcadebase/addons/\w+\.txt)",$', addon_table, re.M)
    config = config_path.read_text(encoding="utf-8")
    loader_call = 'require("simcadebase/simcade_loader.txt")(CONFIG)'
    if config.count(loader_call) != 1:
        parser.error("--share requires a vehicle config that calls the Simcade loader")

    # Starfall scans included data for directives too. Neutralize its source comments.
    package = bytearray()
    for path in modules + addons:
        source = (root.parent / path).read_bytes().replace(b"\r\n", b"\n")
        source = re.sub(rb"(?m)^([ \t]*)--@", rb"\1-- ", source)
        package.extend(f"{len(source)}\n".encode("ascii"))
        package.extend(source)
    if len(package) > 4 * 1024 * 1024:
        parser.error("offline bundle exceeds the loader's 4 MiB limit")

    bundle_name = "simcade_core_bundle.bin" if offline else "simcade_core_bundle.txt"
    bundle_path = f"simcadebase/{bundle_name}"
    loader_include = "--@include simcadebase/simcade_loader.txt"
    if loader_include not in config:
        parser.error("--share requires the Simcade loader include in the vehicle config")
    stripped = {f"--@include {path}" for path in modules + addons}
    config = "\n".join(line for line in config.split("\n") if line.strip() not in stripped)
    config = config.replace(loader_include, f"{loader_include}\n--@includedata {bundle_path}", 1)
    if offline:
        config, changed = re.subn(
            r"(CONFIG\.CORE_UPDATE\s*=\s*\{\s*enabled\s*=\s*)(?:true|false)\b",
            r"\g<1>false", config, count=1,
        )
        if not changed:
            config = config.replace(loader_call, f"CONFIG.CORE_UPDATE = {{ enabled = false }}\n{loader_call}")
    config = config.replace(loader_call, f'{loader_call[:-1]}, "{bundle_path}")')
    loader = re.sub(r"^--@include \S+\n", "", loader, flags=re.M)

    share = root / "share"
    if offline:
        share /= "offline"
    share /= "simcadebase"
    share.mkdir(parents=True, exist_ok=True)
    (share / bundle_name).write_bytes(package)
    (share / "simcade_loader.txt").write_bytes(loader.encode("utf-8"))
    (share / "simcade_vehicle_config.txt").write_bytes(config.encode("utf-8"))
    print(f"Share the three files inside {share}. Copy them into data/starfall/simcadebase on the recipient's PC.")
    custom_includes = re.findall(r"^--@(?:include|includedir|includedata) (.+)$", config, re.M)
    for include in custom_includes:
        if include not in ("simcadebase/simcade_loader.txt", bundle_path):
            print(f"Also share the custom include: {include}")


def main():
    root = Path(__file__).resolve().parent
    default_output = root / "releases"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", nargs="?", type=int, help="override the next release number or start a fresh release folder")
    parser.add_argument("output", nargs="?", type=Path, default=default_output,
                        help="release hosting directory ('release' and 'releases' use simcadebase/releases)")
    parser.add_argument("--keep-local", action="store_true",
                        help="leave the bundled revision as it is")
    parser.add_argument("--include-source", action="store_true",
                        help="also publish individual core files for source updates")
    parser.add_argument("--source-only", action="store_true",
                        help="publish individual core files without a core.bin")
    parser.add_argument("--overwrite", action="store_true",
                        help="rebuild the latest unpublished release in place")
    parser.add_argument("--share", nargs="?", type=Path, const=root / "simcade_vehicle_config.txt",
                        metavar="CONFIG", help="export a shareable config, loader and offline bundle")
    parser.add_argument("--offline", action="store_true",
                        help="with --share, export a .bin bundle with updates disabled")
    args = parser.parse_args()
    if args.offline and not args.share:
        parser.error("--offline requires --share")
    loader_path = root / "simcade_loader.txt"
    loader_bytes = loader_path.read_bytes()
    loader = loader_bytes.decode("utf-8")
    local_revision_pattern = rb"(?m)^local LOCAL_REVISION = ([1-9][0-9]{0,8})(?=\r?$)"
    local_revision = re.search(local_revision_pattern, loader_bytes)
    if not local_revision:
        parser.error("loader must declare the bundled core revision")
    loader = loader.replace("\r\n", "\n")
    schema = re.search(r"^local LOCAL_CONFIG_SCHEMA = ([1-9][0-9]{0,8})$", loader, re.M)
    if not schema:
        parser.error("loader must declare the config schema required by these cores")
    modules = re.findall(r'^    "(simcadebase/simcade_\w+\.txt)",$', loader, re.M)
    includes = re.findall(r"^--@include (\S+)$", loader, re.M)
    if not modules or modules != includes or len(set(modules)) != len(modules):
        parser.error("loader module list and fallback includes must agree")
    if args.share:
        if args.revision is not None or args.output != default_output or args.overwrite or args.include_source or args.source_only or args.keep_local:
            parser.error("--share exports the current sources without building a release")
        export_share(root, args.share, loader, modules, args.offline, parser)
        return
    output = default_output if args.output in (Path("release"), Path("releases")) else args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    latest = output / "latest.txt"
    previous = int(latest.read_text().split()[0]) if latest.exists() else 0
    numbered_folders = [int(path.name) for path in output.iterdir()
                        if path.is_dir() and re.fullmatch(r"[1-9][0-9]{0,8}", path.name)]
    newest_release = max(previous, max(numbered_folders, default=0))
    newest = max(newest_release, int(local_revision[1]))
    default_revision = previous if args.overwrite else newest + 1
    revision = default_revision if args.revision is None else args.revision
    destination = output / str(revision)
    existing_bundle = (destination / "core.bin").is_file()
    existing_index = (destination / "sources.txt").is_file()
    if args.overwrite and (revision != previous or revision != newest_release or not (existing_bundle or existing_index)):
        parser.error("--overwrite requires the latest existing release in this folder")
    if not 1 <= revision <= 999999999:
        parser.error("revision must be a positive integer of at most nine digits")
    if not args.overwrite and (revision <= newest_release or destination.exists()):
        parser.error("choose a revision newer than the published release")
    stamp_local = not args.keep_local and output == default_output
    local_floor = int(local_revision[1]) + (0 if args.overwrite else 1)
    if stamp_local and newest_release and revision < local_floor:
        parser.error("choose a revision newer than the bundled core")
    include_source = args.include_source or args.source_only or (
        args.overwrite and (existing_index or (destination / "simcadebase").is_dir())
    )
    include_bundle = not args.source_only and (not args.overwrite or existing_bundle or args.include_source)
    # Published files must inherit the release directory's Windows permissions.
    staging = output / f".build-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        release = staging / str(revision)
        release.mkdir()
        package = bytearray()
        source_index = []
        blobs = staging / "source"
        if include_source:
            blobs.mkdir()
        for path in modules:
            source = (root.parent / path).read_bytes()
            if include_source:
                source = source.replace(b"\r\n", b"\n")
                digest = hashlib.sha256(source).hexdigest()
                source_index.append(f"{path} {digest}\n")
                name = f"{digest}.txt"
                previous_blob = output / "source" / name
                if previous_blob.is_file():
                    if previous_blob.read_bytes() != source:
                        parser.error(f"source file has changed on disk: {previous_blob}")
                else:
                    (blobs / name).write_bytes(source)
            package.extend(f"{len(source)}\n".encode("ascii"))
            package.extend(source)
        if len(package) > 4 * 1024 * 1024:
            parser.error("core exceeds the loader's 4 MiB limit")
        if include_bundle:
            (release / "core.bin").write_bytes(package)
        if include_source:
            (release / "sources.txt").write_bytes("".join(source_index).encode("ascii"))
            source_directory = output / "source"
            source_directory.mkdir(exist_ok=True)
            for blob in blobs.iterdir():
                blob.replace(source_directory / blob.name)
        manifest = staging / "latest.txt"
        manifest.write_bytes(f"{revision} {hashlib.sha256(package).hexdigest()} {schema[1]}\n".encode())
        if args.overwrite:
            backup = destination.rename(output / f".backup-{uuid.uuid4().hex}")
            try:
                release.rename(destination)
                try:
                    manifest.replace(latest)
                except OSError:
                    destination.rename(release)
                    raise
            except OSError:
                backup.rename(destination)
                raise
            try:
                shutil.rmtree(backup, onexc=retry_read_only_removal)
            except OSError as error:
                print(f"Release rebuilt. Could not remove backup {backup}: {error}", file=sys.stderr)
        else:
            release.rename(destination)
            manifest.replace(latest)
        if stamp_local:
            updated_loader = re.sub(local_revision_pattern, f"local LOCAL_REVISION = {revision}".encode(), loader_bytes)
            staged_loader = loader_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            try:
                staged_loader.write_bytes(updated_loader)
                staged_loader.replace(loader_path)
            finally:
                staged_loader.unlink(missing_ok=True)
    finally:
        shutil.rmtree(staging)
    if include_source:
        print(f"Upload the files under {output / 'source'} first. Unchanged files share the same URL across releases.")
    print(f"Upload {destination} before {latest}. Preserve the exact file bytes.")
    if stamp_local:
        print(f"Bundled core is now r{revision}. Existing chips keep their uploaded fallback.")


if __name__ == "__main__":
    main()
