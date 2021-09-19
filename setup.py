#!/usr/bin/env python
import subprocess
import sys
from distutils.command.build import build  # type: ignore

from setuptools import find_packages, setup  # type: ignore
from setuptools.command.install import install  # type: ignore
from wheel.bdist_wheel import bdist_wheel as _bdist_wheel  # type: ignore

_MAKE_TYPE = ""


class BdistWheel(_bdist_wheel):
    """
    Yoink: https://github.com/Yelp/dumb-init/blob/
               48db0c0d0ecb4598d1a6400710445b85d67616bf/setup.py#L11-L27

    Even so setuptools is confused about yescrypt.bin being pure, presumably
    because it doesn't have a standard platform executable extension. But this
    at least gets it to name the wheels correctly, which is important since
    the names are stateful and will prevent pip installing when incorrect.
    """

    def finalize_options(self):
        _bdist_wheel.finalize_options(self)
        self.root_is_pure = False  # noqa

    def get_tag(self):
        python, abi, plat = _bdist_wheel.get_tag(self)
        python, abi = "py3", "none"
        return python, abi, plat


def _build_source() -> None:
    if subprocess.call(["make", "clean"]) != 0:
        sys.exit(-1)
    if subprocess.call(["make", _MAKE_TYPE]) != 0:
        sys.exit(-1)


class Build(build):
    """Clear any built binaries and rebuild with make."""

    def run(self):
        _build_source()
        build.run(self)


class BuildInstall(install):
    """Build yescrypt when installing from source."""

    def run(self):
        super().run()


if __name__ == "__main__":
    with open("REQUIREMENTS") as f:
        required = f.read().splitlines()

    with open("VERSION") as f:
        # Black automatically adds '\n'.
        version = f.readline().strip()

    if sys.argv[1] in ("build_dynamic", "bdist_wheel_dynamic"):
        _MAKE_TYPE = "dynamic"
    else:
        _MAKE_TYPE = "static"

    setup(
        name="pyescrypt",
        version=version,
        description=(
            "Python bindings for yescrypt: memory-hard, NIST-compliant password "
            "hashing."
        ),
        author="Colt Blackmore",
        author_email="coltblackmore+pyescrypt@gmail.com",
        install_requires=required,
        license="MIT",
        url="https://https://github.com/0xcb/pyescrypt",
        packages=find_packages("src"),
        package_dir={"": "src"},
        package_data={"": ["yescrypt.bin"]},
        cmdclass={
            "install": BuildInstall,
            "build": Build,
            "build_dynamic": Build,
            "bdist_wheel": BdistWheel,
            "bdist_wheel_dynamic": BdistWheel,
        },
        include_package_data=True,
        zip_safe=False,
    )
