# pyescrypt
Python bindings for [yescrypt](https://github.com/openwall/yescrypt), a memory-hard password hashing scheme that meets the requirements of NIST SP 800-63B. Yescrypt is the only recognized scheme from the [Password Hashing Competition](https://www.password-hashing.net/) to meet these requirements (by being built on SHA-256, HMAC, and PBKDF2; see NIST SP 800-63B §5.1.1.2). Unfortunately Argon2, Catena, Lyra2, and Makwa use unapproved primitives and aren't suitable for NIST-compliant work.

## Usage
TODO

## Requirements
Building pyescrypt from source requires GCC or a compatible compiler and (GNU) Make, regardless of platform. On Windows, the [Winlibs](https://github.com/brechtsanders/winlibs_mingw) distribution of MinGW is an excellent option. A GCC-like compiler is necessary because yescrypt makes liberal use of GCC preprocessor and C extensions that Microsoft's compiler doesn't support (#warning, restrict, etc.). Clang may work, but not on all platforms.

## License
Note that by default pyescrypt statically links GOMP (GNU OpenMP), since it's not automatically available on non-Linux platforms and sometimes (e.g. the AWS Lambda Python 3.8 container) even gets left out of Linux. This means that by default, you're statically linking GPL-licensed code (the version depends on your toolchain), with everything that entails. Dynamically linked versions can be generated with the `dynamic` command versions below.

Only GOMP (`libgomp.a`) is statically linked on Linux. On other platforms, its dependencies are also pulled in.

Of course, to link statically the libraries must be available and must have been compiled with `-fPIC`, otherwise you'll see an error like `relocation R_X86_64_32 against hidden symbol can not be used when making a shared object`. The build process is tested with GCC using MinGW on Windows and the default toolchain on Ubuntu. macOS should build like Windows, but is untried.


## Useful Setuptools Commands
- `build`: build binaries and link them statically
- `build_dynamic`: build binaries and link them dynamically
- `bdist_wheel`: build binaries, link them statically, and package them in a wheel
- `bdist_wheel_dynamic`: build binaries , link them dynamically, and package them in a wheel


## Useful Make Targets
- `make static`: build binaries and link them statically
- `make dynamic`: build binaries and link them dynamically
- `make clean`: clear compiled object files
