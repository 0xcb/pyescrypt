# pyescrypt
Python bindings for [yescrypt](https://github.com/openwall/yescrypt), a memory-hard password hashing scheme that meets the requirements of NIST SP 800-63B. Yescrypt is the only scheme from the [Password Hashing Competition](https://www.password-hashing.net/) to receive recognition *and* meet these requirements (by being built on SHA-256, HMAC, and PBKDF2; see NIST SP 800-63B §5.1.1.2). Unfortunately Argon2, Catena, Lyra2, and Makwa use unapproved primitives and aren't suitable for NIST-compliant work.


## Usage
```python
import secrets
import time

# All default settings.
hasher = Yescrypt(n=2 ** 16, r=8, p=1, mode=Mode.JSON)
password = secrets.token_bytes(32)

start = time.time()
hashed = hasher.digest(
    password=password,
    salt=secrets.token_bytes(32))
stop = time.time() - start

try:
    hasher.compare(password, hashed)
except WrongPasswordConfiguration:
    print("Passwords have different configurations.")
except WrongPassword:
    print("Passwords don't match.")

print(
    f"Yescrypt took {stop:.2f} seconds to generate password hash {h.decode()} and "
    f"used {128 * 2**16 * 8 / 1024**2:.2f} MiB memory."
)
```
TODO: Explain.


## Installation
```shell
$ pip -m install pyescrypt
Collecting pyescrypt
  Downloading pyescrypt-0.1.0.tar.gz (73 kB)
     |████████████████████████████████| 73 kB 1.9 MB/s 
Requirement already satisfied: cffi>=1.0.0 in ./.local/lib/python3.8/site-packages (from pyescrypt) (1.14.6)
Requirement already satisfied: pycparser in ./.local/lib/python3.8/site-packages (from cffi>=1.0.0->pyescrypt) (2.20)
Building wheels for collected packages: pyescrypt
  Building wheel for pyescrypt (setup.py) ... done
  Created wheel for pyescrypt: filename=pyescrypt-0.1.0-py3-none-linux_x86_64.whl size=39771 sha256=db53f817c32b69f9c856eeb450cd1fb9a208e118d5ff467b0f740bc440def001
  Stored in directory: /home/0xcb/.cache/pip/wheels/ee/e3/9e/6f47431888cf3f05b020d4b6e2d50d0eafb834b290fc84558a
Successfully built pyescrypt
Installing collected packages: pyescrypt
Successfully installed pyescrypt-0.1.0
```
### Wheels
Wheels are available for Windows and macOS (x86-64 only). Other platforms build from source with Make and GCC.

Note: The macOS wheel is compiled without AVX support, since Big Sur's Python3 can't execute it. Given yescrypt is explicitly designed not to benefit from registers wider than 128 bits, AVX is no loss.

(Presumably Big Sur's Python3 troubles with AVX are related to Rosetta. See the ["What Can't Be Translated"](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment) section on the Rosetta page. The same binaries run without issue outside of Python.)

### Building from Source
Building pyescrypt from source requires GCC or a compatible compiler and (GNU) Make, regardless of platform. On Windows, the [Winlibs](https://github.com/brechtsanders/winlibs_mingw) distribution of MinGW is an excellent option. 

A GCC-like compiler is necessary because yescrypt makes liberal use of GCC preprocessor and C extensions that Microsoft's compiler doesn't support (#warning, restrict, etc.). Clang works, but not everywhere. The version that ships with macOS Big Sur for example is missing OpenMP support.

To build on macOS there are a few options, but the easiest is to `brew install gcc` and change the compiler to `gcc-11`, since GCC is otherwise just an alias for Clang. GCC gives you the option of static or dynamic builds.

You can also stick with Clang, `brew install libomp`, and change the makefile to use `libomp` instead of `libgomp`. Or you can `brew install llvm` for a more featureful Clang build, change the compiler, and also move to `libomp` (which comes packaged with LLVM).

By default, pyescrypt statically links GOMP (GNU OpenMP) and its dependencies on Windows and macOS, since GOMP isn't automatically available on non-Linux platforms. Sometimes (e.g. the AWS Lambda Python 3.8 runtime) GOMP even gets left out of Linux, but finding a copy of libgomp.so is easy (whereas an `-fPIC`-compiled libgomp.a has to be built, along with *GCC in its entirety*), so GOMP isn't statically linked on Linux.


## License
Scrypt, yescrypt, and pyescrypt are all released under the 2-clause BSD license.

A few parts of the yescrypt repository have an even more permissive license with no attribution requirement, but these are separate from the actual library (e.g. the Makefile, PHC interface, and ROM demo code).

Note that because pyescrypt links GOMP, GPL-licensed code is also included. Unless you're doing something unusual with compilation, though, there's nothing to worry about: GOMP falls under the [GCC Runtime Library Exception](https://www.gnu.org/licenses/gcc-exception-3.1-faq.en.html), and can be shared under other licenses or no license at all regardless of how it's linked.


## Useful Setuptools Commands
- `build`: build binaries and link them statically
- `build_dynamic`: build binaries and link them dynamically
- `bdist_wheel`: build binaries, link them statically, and package them in a wheel
- `bdist_wheel_dynamic`: build binaries, link them dynamically, and package them in a wheel


## Useful Make Targets
- `make static`: build binaries and link them statically
- `make dynamic`: build binaries and link them dynamically
- `make clean`: clear compiled object files
