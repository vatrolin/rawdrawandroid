import re
from sys import argv
from os.path import expanduser
from os import name as _OS_NAME
from glob import glob
from shlex import split as split_command
from subprocess import run as _run

# glue
def run(command: str, check = True, **kwargs):
    _run(split_command(command), check, **kwargs)
def sh(command: str, check = True, **kwargs):
    run(f"sh -c \"{command}\"")

def rimraf(*paths: str):
    for path in paths:
        sh(f"rm -rf \"{path}\"")

def path(format: str):
    return glob(expanduser(format))[0]

def _os_name():
    return { "posix": "linux", "nt": "windows" }[_OS_NAME]
OS_NAME = _os_name()

# android tools
ANDROID_VERSION = 30
APPNAME = "rawdrawandroidexample"
def _android_sdk_paths():
    ANDROID_SDK_PATH = path("~/Android/Sdk")
    ANDROID_NDK_PATH = path(f"{ANDROID_SDK_PATH}/ndk/23*")
    ANDROID_SDK_TOOLS_PATH = path(f"{ANDROID_SDK_PATH}/build-tools/*")
    ANDROID_NDK_TOOLS_PATH = path(f"{ANDROID_NDK_PATH}/toolchains/llvm/prebuilt/{OS_NAME}-x86_64")
    return [ANDROID_SDK_PATH, ANDROID_NDK_PATH, ANDROID_SDK_TOOLS_PATH, ANDROID_NDK_TOOLS_PATH]
[ANDROID_SDK_PATH, ANDROID_NDK_PATH, ANDROID_SDK_TOOLS_PATH, ANDROID_NDK_TOOLS_PATH] = _android_sdk_paths()

# clang
def clang_path(architecture: str):
    return path(f"{ANDROID_NDK_TOOLS_PATH}/bin/{architecture}-{OS_NAME}-android{ANDROID_VERSION}-clang")
_CLANG_ARGS = "-ffunction-sections -Os -fdata-sections -Wall -fvisibility=hidden -fPIC"
_CLANG_ARGS += f" -Os -DANDROID -DAPPNAME=\\\"{APPNAME}\\\" -DANDROID_FULLSCREEN -DANDROIDVERSION={ANDROID_VERSION}"
_CLANG_ARGS += f" -I./rawdraw -I{ANDROID_NDK_TOOLS_PATH}/sysroot/usr/include/android -I."
_LD_ARGS = "-Wl,--gc-sections -s"
_LD_ARGS += " -lm -lGLESv3 -lEGL -landroid -llog"
_LD_ARGS += " -shared -uANativeActivity_onCreate"
def clang_args(architecture: str):
    arch_args = {
        "arm64-v8a": "-m64",
        "armeabi-v7a": "-mfloat-abi=softfp -m32",
        "x86": "-march=i686 -mtune=intel -mssse3 -mfpmath=sse -m32",
        "x86_64": "-march=x86-64 -msse4.2 -mpopcnt -m64 -mtune=x86-64",
    }[architecture]
    architecture2 = {
        "arm64-v8a": "aarch64",
        "armeabi-v7a": "arm",
        "x86": "i686",
        "x86_64": "x86_64",
    }[architecture]
    arch_args += f" -L{ANDROID_NDK_PATH}/sysroot/usr/lib/{architecture2}-{OS_NAME}-android/{ANDROID_VERSION}"
    return f"{_CLANG_ARGS} {_LD_ARGS} {arch_args}"
def run_clang(architecture: str, input: str, output: str):
    print(f"{clang_path(architecture)} {clang_args(architecture)} {input} -o {output}")
    run(f"{clang_path(architecture)} {clang_args(architecture)} {input} -o {output}")

# app settings
TEMPLATE = {
    "APPNAME": APPNAME,
    "LABEL": "Rawdraw Android",
    "PACKAGENAME": f"org.vatrolin.{APPNAME}",
    "ANDROIDVERSION": ANDROID_VERSION,
    "ANDROIDTARGET": ANDROID_VERSION,
}
TARGETS = [
    #"arm64-v8a",
    #"armeabi-v7a",
    #"x86",
    "x86_64"
]

# make args
def format_template(filepath: str, values: dict):
    def _format_template(match):
        return str(values[match[1]])
    with open(f"{filepath}.template") as f:
        text = f.read()
    with open(f"{filepath}", "w+") as f:
        f.write(re.sub("\${([^}]+)}", _format_template, text))

def paths():
    print(f"ANDROID_SDK_PATH: {repr(ANDROID_SDK_PATH)}")
    print(f"ANDROID_SDK_TOOLS_PATH: {repr(ANDROID_SDK_TOOLS_PATH)}")
    print(f"ANDROID_NDK_PATH: {repr(ANDROID_NDK_PATH)}")
    print(f"ANDROID_NDK_TOOLS_PATH: {repr(ANDROID_NDK_TOOLS_PATH)}")

def clean():
    rimraf("bin/*")

def build():
    clean()
    format_template("AndroidManifest.xml", TEMPLATE)
    # make an .apk
    run(f"{ANDROID_SDK_TOOLS_PATH}/aapt package -f -F bin/temp1.apk -I {ANDROID_SDK_PATH}/platforms/android-{ANDROID_VERSION}/android.jar -M AndroidManifest.xml -S Sources/res -A Sources/assets -v --target-sdk-version {ANDROID_VERSION}")
    # add c++
    run("unzip -o bin/temp1.apk -d bin/temp1")
    for architecture in TARGETS:
        run(f"mkdir -p bin/temp1/lib/{architecture}")
        run_clang(architecture, f"test.c android_native_app_glue.c", f"bin/temp1/lib/{architecture}/lib{APPNAME}.so")
    sh("cd bin/temp1 && zip -D9r ../temp2.apk .")
    sh("cd bin/temp1 && zip -D0r ../temp2.apk ./resources.arsc ./AndroidManifest.xml")
    # sign the .apk
    KEYSTOREFILE = "my-release-key.keystore"
    STOREPASS = "password"
    ALIASNAME = "standkey"
    run(f"jarsigner -sigalg SHA1withRSA -digestalg SHA1 -verbose -keystore {KEYSTOREFILE} -storepass {STOREPASS} bin/temp2.apk {ALIASNAME}")
    # double sign the .apk (for version 30+)
    run(f"{ANDROID_SDK_TOOLS_PATH}/zipalign -v 4 bin/temp2.apk bin/{APPNAME}.apk")
    run(f"{ANDROID_SDK_TOOLS_PATH}/apksigner sign --key-pass pass:{STOREPASS} --ks-pass pass:{STOREPASS} --ks {KEYSTOREFILE} bin/{APPNAME}.apk")

def push():
    run("adb -e install bin/rawdrawandroidexample.apk")

if __name__ == "__main__":
    args = argv[1:]
    if len(args) == 0:
        args.append("build")
        args.append("push")
    for arg in args:
        if arg == "paths":
            paths()
        elif arg == "clean":
            clean()
        elif arg == "build":
            build()
        elif arg == "push":
            push()