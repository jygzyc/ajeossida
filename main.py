import gzip
import os
import shutil
import subprocess
import sys

CUSTOM_NAME = "ajeossida"


def run_command(command, cwd=None):
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, check=True, text=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error while running command: {command}\nError: {e}")
        sys.exit(1)


def git_clone_repo():
    repo_url = "https://github.com/frida/frida.git"
    destination_dir = os.path.join(os.getcwd(), CUSTOM_NAME)

    print(f"\n[*] Cloning repository {repo_url} to {destination_dir}...")
    run_command(f"git clone --recurse-submodules {repo_url} {destination_dir}")


def check_ndk_version():
    home_path = os.path.expanduser("~")
    ndk_base = os.path.join(home_path, "Library/Android/sdk/ndk")

    ndk_versions = []

    for ndk_version in os.listdir(ndk_base):
        dir_path = os.path.join(ndk_base, ndk_version)

        if os.path.isdir(dir_path) and ndk_version.startswith("25."):
            ndk_versions.append(ndk_version)

    if not ndk_versions:
        print("\n[!] Android NDK r25 is needed")
        sys.exit(1)

    # Sort versions and pick the largest
    biggest_version = max(ndk_versions, key=lambda v: list(map(int, v.split('.'))))

    biggest_version_path = os.path.join(ndk_base, biggest_version)
    print(f"[*] NDK version: {biggest_version}")
    return biggest_version_path


def setup_android_build(ndk_path, arch):
    build_dir = os.path.join(os.getcwd(), CUSTOM_NAME, arch)
    os.makedirs(build_dir, exist_ok=True)

    os.environ['ANDROID_NDK_ROOT'] = ndk_path
    print(f"\n[*] Configuring the build for {arch}...")
    result = run_command(f"{os.path.join('..', 'configure')} --host={arch}", cwd=build_dir)
    if result == 0:
        return build_dir
    else:
        print("\n[!] Failed to configure")
        sys.exit(1)


def build(build_dir):
    run_command("make", cwd=build_dir)


def replace_strings_in_files(directory, search_string, replace_string):
    if os.path.isfile(directory):
        file_path = directory
        with open(file_path, 'r+', encoding='utf-8') as file:
            content = file.read()
            if search_string in content:
                print(f"Patch {file.name}")
                patched_content = content.replace(search_string, replace_string)
                file.seek(0)
                file.write(patched_content)
                file.truncate()
    else:
        for root, dirs, files in os.walk(directory):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'r+', encoding='utf-8') as file:
                        content = file.read()
                        if search_string in content:
                            print(f"Patch {file.name}")
                            patched_content = content.replace(search_string, replace_string)
                            file.seek(0)
                            file.write(patched_content)
                            file.truncate()
                except Exception as e:
                    pass


def compress_file(file_path):
    try:
        # Create a .gz file from the original file
        with open(file_path, 'rb') as f_in:
            with gzip.open(file_path + '.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"[*] Compressed {file_path} to {file_path}.gz")
    except Exception as e:
        print(f"[!] Error compressing {file_path}: {e}")


def main():
    custom_dir = os.path.join(os.getcwd(), CUSTOM_NAME)
    if os.path.exists(custom_dir):
        print(f"\n[*] Cleaning {custom_dir}...")
        shutil.rmtree(custom_dir)

    assets_dir = os.path.join(os.getcwd(), "assets")
    if os.path.exists(assets_dir):
        print(f"\n[*] Cleaning {assets_dir}...")
        shutil.rmtree(assets_dir)
    os.mkdir(assets_dir)

    git_clone_repo()

    ndk_version_path = check_ndk_version()

    architectures = ["android-arm64", "android-arm", "android-x86_64", "android-x86"]
    build_dirs = [setup_android_build(ndk_version_path, arch) for arch in architectures]

    # libfrida-agent-raw.so patch
    print(f"\n[*] Patch 'libfrida-agent-raw.so' with 'lib{CUSTOM_NAME}-agent-raw.so' recursively...")
    replace_strings_in_files(custom_dir, "libfrida-agent-raw.so", f"lib{CUSTOM_NAME}-agent-raw.so")

    # re.frida.server patch
    print(f"\n[*] Patch 're.frida.server' with 're.{CUSTOM_NAME}.server' recursively...")
    replace_strings_in_files(custom_dir, "re.frida.server", f"re.{CUSTOM_NAME}.server")

    # frida-helper patch
    print(f"\n[*] Patch 'frida-helper' with '{CUSTOM_NAME}-helper' recursively...")
    patch_strings = ["frida-helper-32", "frida-helper-64", "get_frida_helper_", "\"/frida-\""]
    for patch_string in patch_strings:
        replace_strings_in_files(custom_dir, patch_string, patch_string.replace("frida", f"{CUSTOM_NAME}"))

    # frida-agent patch
    print(f"\n[*] Patch 'frida-agent' with '{CUSTOM_NAME}-agent' recursively...")
    patch_strings = ["frida-agent-", "\"agent\" / \"frida-agent.", "\'frida-agent\'", "\"frida-agent\"", "get_frida_agent_"]
    for patch_string in patch_strings:
        replace_strings_in_files(custom_dir, patch_string, patch_string.replace("frida", f"{CUSTOM_NAME}"))

    # frida-server patch
    print(f"\n[*] Patch 'frida-server' with '{CUSTOM_NAME}-server' recursively...")
    frida_server_meson_path = os.path.join(custom_dir, "subprojects/frida-core/server/meson.build")
    patch_strings = ["frida-server-raw", "\'frida-server\'", "\"frida-server\"", "frida-server-universal"]
    for patch_string in patch_strings:
        replace_strings_in_files(frida_server_meson_path, patch_string, patch_string.replace("frida", f"{CUSTOM_NAME}"))

    # frida-gadget patch
    print(f"\n[*] Patch 'frida-gadget' with '{CUSTOM_NAME}-gadget' recursively...")
    patch_strings = ["\"frida-gadget\"", "\"frida-gadget-tcp", "\"frida-gadget-unix"]
    for patch_string in patch_strings:
        replace_strings_in_files(custom_dir, patch_string, patch_string.replace("frida", f"{CUSTOM_NAME}"))
    frida_core_meson_path = os.path.join(custom_dir, "subprojects/frida-core/meson.build")
    replace_strings_in_files(frida_core_meson_path, "gadget_name = 'frida-gadget' + shlib_suffix",
                             f"gadget_name = '{CUSTOM_NAME}-gadget' + shlib_suffix")
    frida_core_compat_build_py_path = os.path.join(custom_dir, "subprojects/frida-core/compat/build.py")
    replace_strings_in_files(frida_core_compat_build_py_path, "frida-gadget",
                             f"{CUSTOM_NAME}-gadget")
    frida_gadget_meson_path = os.path.join(custom_dir, "subprojects/frida-core/lib/gadget/meson.build")
    patch_strings = ["frida-gadget-modulated", "libfrida-gadget-modulated", "frida-gadget-raw", "\'frida-gadget\'", "frida-gadget-universal"]
    for patch_string in patch_strings:
        replace_strings_in_files(frida_gadget_meson_path, patch_string, patch_string.replace("frida", f"{CUSTOM_NAME}"))

    # gum-js-loop patch
    print(f"\n[*] Patch 'gum-js-loop' with '{CUSTOM_NAME}-js-loop' recursively...")
    replace_strings_in_files(custom_dir, "\"gum-js-loop\"", f"\"{CUSTOM_NAME}-js-loop\"")

    # No libc hooking
    print(f"\n[*] Patch not to hook libc function")
    # frida/subprojects/frida-core/lib/payload/exit-monitor.vala
    exit_monitor_path = os.path.join(custom_dir, "subprojects/frida-core/lib/payload/exit-monitor.vala")
    replace_strings_in_files(exit_monitor_path, "interceptor.attach", "// interceptor.attach")
    # frida/subprojects/frida-gum/gum/backend-posix/gumexceptor-posix.c
    gumexceptor_posix_path = os.path.join(custom_dir, "subprojects/frida-gum/gum/backend-posix/gumexceptor-posix.c")
    patch_strings = ["gum_interceptor_replace", "gum_exceptor_backend_replacement_signal, self, NULL);",
                     "gum_exceptor_backend_replacement_sigaction, self, NULL);"]
    for patch_string in patch_strings:
        replace_strings_in_files(gumexceptor_posix_path, patch_string, "// " + patch_string)

    # Perform the first build
    for build_dir in build_dirs:
        print(f"\n[*] First build for {build_dir.rsplit('/')[-1]}")
        build(build_dir)

    # frida_agent_main patch
    print(f"\n[*] Patch 'frida_agent_main' with '{CUSTOM_NAME}_agent_main' recursively...")
    replace_strings_in_files(custom_dir, "frida_agent_main", f"{CUSTOM_NAME}_agent_main")

    # Second build after patching
    for build_dir in build_dirs:
        print(f"\n[*] Second build for {build_dir.rsplit('/')[-1]}")
        build(build_dir)

    # Patch gmain, gdbus
    gmain = bytes.fromhex('67 6d 61 69 6e 00')
    amain = bytes.fromhex('61 6d 61 69 6e 00')

    gdbus = bytes.fromhex('67 64 62 75 73 00')
    gdbug = bytes.fromhex('67 64 62 75 67 00')

    patch_list = [os.path.join(build_dir, f"subprojects/frida-core/server/{CUSTOM_NAME}-server") for build_dir in build_dirs] + \
                 [os.path.join(build_dir, f"subprojects/frida-core/lib/gadget/{CUSTOM_NAME}-gadget.so") for build_dir in build_dirs]

    for file_path in patch_list:
        # Open the binary file for reading and writing
        with open(file_path, 'rb+') as f:
            print(f"\n[*] gmain, gdbus patch for {file_path}")
            # Read the entire file content
            content = f.read()
            patched_content = content.replace(gmain, amain)
            patched_content = patched_content.replace(gdbus, gdbug)

            f.seek(0)
            f.write(patched_content)
            f.truncate()

    # Get frida version
    frida_version_py = os.path.join(custom_dir, "releng/frida_version.py")
    result = subprocess.run(['python3', frida_version_py], capture_output=True, text=True)
    frida_version = result.stdout.strip()

    # Rename
    for file_path in patch_list:
        arch = [i for i in file_path.split(os.sep) if i.startswith('android-')]
        arch = arch[0] if arch else ''

        if file_path.endswith('.so'):
            new_file_path = f"{file_path.rsplit('.so', 1)[0]}-{frida_version}-{arch}.so"
        else:
            new_file_path = f"{file_path}-{frida_version}-{arch}"

        try:
            os.rename(file_path, new_file_path)
            print(f"\n[*] Renamed {file_path} to {new_file_path}")
            compress_file(new_file_path)

            shutil.move(f"{new_file_path}.gz", f"{assets_dir}")
        except Exception as e:
            print(f"[!] Error renaming {file_path}: {e}")

    print(f"\n[*] Building of {CUSTOM_NAME} completed. The output is in the assets directory")


if __name__ == "__main__":
    main()
