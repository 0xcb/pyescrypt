# Yescrypt makes liberal use of GCC preprocessor and C extensions that break
# CL (#warning, restrict, etc.) and Clang. Realistically, it's not worth the
# headache of compiling with anything other than GCC. Unfortunately, distutils
# (and CFFI, which uses distutils for compilation under the hood) is unutterably
# bad at using GCC on Windows, forces specific file prefixes and extensions on
# compilation and linking, and just generally Does Not Work. This makes
# supporting Yescrypt on multiple compilers and multiple platforms for CFFI's
# API mode a non-starter. Instead we use a simple makefile and load the
# generated binary in ABI mode.
import json
import secrets
from base64 import b64decode, b64encode
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Any, cast, Optional

from cffi import FFI  # type: ignore

ffi = FFI()

# Refer to yescrypt.h for details and private defines.
# TODO: PARAMETERS are a compile-time decision. Using values other than those in
#  YESCRYPT_DEFAULTS below will error out in yescrypt_kdf(), unless the C source
#  values for Swidth, PWXsimple, and PWXgather are modified -- but the latter two
#  aren't currently set up to be editable, and thus even the S-box size (Sbytes)
#  is pinned.
#  Explicit values:
#   https://github.com/openwall/yescrypt/blob/03d4b65753e2b5568c93eec4fbf6f52b4ceefc40/yescrypt-opt.c#L403
#  Derived S-box value:
#   https://github.com/openwall/yescrypt/blob/03d4b65753e2b5568c93eec4fbf6f52b4ceefc40/yescrypt-opt.c#L412
YESCRYPT_WORM = 1
YESCRYPT_RW = 0x002
YESCRYPT_ROUNDS_3 = 0x000
YESCRYPT_ROUNDS_6 = 0x004
YESCRYPT_GATHER_1 = 0x000
YESCRYPT_GATHER_2 = 0x008
YESCRYPT_GATHER_4 = 0x010
YESCRYPT_GATHER_8 = 0x018
YESCRYPT_SIMPLE_1 = 0x000
YESCRYPT_SIMPLE_2 = 0x020
YESCRYPT_SIMPLE_4 = 0x040
YESCRYPT_SIMPLE_8 = 0x060
YESCRYPT_SBOX_6K = 0x000
YESCRYPT_SBOX_12K = 0x080
YESCRYPT_SBOX_24K = 0x100
YESCRYPT_SBOX_48K = 0x180
YESCRYPT_SBOX_96K = 0x200
YESCRYPT_SBOX_192K = 0x280
YESCRYPT_SBOX_384K = 0x300
YESCRYPT_SBOX_768K = 0x380
# Only valid for yescrypt_init_shared()
YESCRYPT_SHARED_PREALLOCATED = 0x10000

YESCRYPT_RW_DEFAULTS = (
    YESCRYPT_RW
    | YESCRYPT_ROUNDS_6
    | YESCRYPT_GATHER_4
    | YESCRYPT_SIMPLE_2
    | YESCRYPT_SBOX_12K
)

YESCRYPT_DEFAULTS = YESCRYPT_RW_DEFAULTS

ffi.cdef(
    """
    typedef uint32_t yescrypt_flags_t;

    typedef struct {
        void *base, *aligned;
        size_t base_size, aligned_size;
    } yescrypt_region_t;

    typedef yescrypt_region_t yescrypt_shared_t;
    typedef yescrypt_region_t yescrypt_local_t;

    /**
     * yescrypt parameters combined into one struct. N, r, p are the same as in
     * classic scrypt, except that the meaning of p changes when YESCRYPT_RW is
     * set. flags, t, g, NROM are special to yescrypt.
     */
    typedef struct {
        yescrypt_flags_t flags;
        uint64_t N;
        uint32_t r, p, t, g;
        uint64_t NROM;
    } yescrypt_params_t;

    typedef union {
        unsigned char uc[32];
        uint64_t u64[4];
    } yescrypt_binary_t;

    int yescrypt_init_local(yescrypt_local_t *local);
    int yescrypt_free_local(yescrypt_local_t *local);
    int yescrypt_init_shared(yescrypt_shared_t *shared,
        const uint8_t *seed, size_t seedlen, const yescrypt_params_t *params);
    int yescrypt_free_shared(yescrypt_shared_t *shared);

    uint8_t *yescrypt_encode_params(const yescrypt_params_t *params,
        const uint8_t *src, size_t srclen);

    int yescrypt_kdf(const yescrypt_shared_t *shared,
        yescrypt_local_t *local,
        const uint8_t *passwd, size_t passwdlen,
        const uint8_t *salt, size_t saltlen,
        const yescrypt_params_t *params,
        uint8_t *buf, size_t buflen);

    uint8_t *yescrypt_r(const yescrypt_shared_t *shared, yescrypt_local_t *local,
        const uint8_t *passwd, size_t passwdlen,
        const uint8_t *setting,
        const yescrypt_binary_t *key,
        uint8_t *buf, size_t buflen);
"""
)

_LIB = ffi.dlopen(f"{Path(__file__).parent.resolve()}/yescrypt.bin")


class Mode(Enum):
    MCF = 1
    JSON = 2
    RAW = 3


class WrongPassword(Exception):
    pass


class WrongPasswordConfiguration(Exception):
    pass


class Yescrypt:
    _mode: Mode

    # Reuse across calls.
    _params: Any
    _local_region: Any
    # Not implemented yet.
    _shared_region: Any

    def __init__(
        self,
        n: int = 2 ** 16,
        r: int = 8,
        t: int = 0,
        p: int = 1,
        mode: Mode = Mode.JSON,
    ):
        """
        Creates a Yescrypt hasher with settings preconfigured and memory
        preallocated.

        The hasher should be considered immutable. This allows its parameters and
        the local memory used for hashing to be allocated once and reused, which is
        important as the amount of memory used grows (allocation is slow and
        dominates hashing time when using GiBs of memory).

        Note that instances of Yescrypt aren't thread-safe externally. They're of
        course thread-safe internally for their own `p` value, but you can't hash
        with the same Yescrypt instance across multiple threads simultaneously.

        :param n: Block count (capital 'N' in yescrypt proper).
        :param r: Block size, in 128-byte units.
        :param t: An additional time factor. Useful for making hashing more
         expensive when more memory is not available.
        :param p: Parallelism. Unlike scrypt, threads in yescrypt don't increase
         memory usage.
        :param mode: The encoding to expect for inputs and to generate for outputs.
         `Mode.JSON` encodes all relevant data and is the default. `Mode.MCF` is
         similar but uses the Modular Crypt Format, forces hashes to be 32 bytes
         (length is implicit, not encoded), and limits salts to 64 bytes. `Mode.RAW`
         applies no special encoding and leaves everything in the user's hands.
        """
        self._mode = mode

        # Yescrypt doesn't use g (hash upgrade) currently.
        g = 0
        nrom = 0
        self._params = ffi.new(
            "yescrypt_params_t*", (YESCRYPT_RW_DEFAULTS, n, r, p, t, g, nrom)
        )
        self._local_region = ffi.new("yescrypt_local_t*")
        if _LIB.yescrypt_init_local(self._local_region):
            raise Exception("Initialization Error: yescrypt_init_local failed.")
        # Force OS to allocate the memory for these parameters. New parameters
        # should get a new Yescrypt instance.
        # NB: We use YESCRYPT_RW exclusively, so unlike in scrypt p doesn't
        # contribute to the size.
        # TODO: The first execution of digest() isn't any faster when we pre-init
        #  memory like this. Need to investigate. For now we'll simply call
        #  digest() on load (cold start, not warm-up).
        # from ctypes import memset
        # ptr = int(ffi.cast('uint64_t', self._local_region.aligned))
        # memset(ptr, 0, self._local_region.aligned_size)

    def digest(
        self,
        password: bytes,
        salt: Optional[bytes] = None,
        settings: Optional[bytes] = None,
        hash_length: int = 32,
    ) -> bytes:
        """
        Generates a yescrypt hash for `password` in the mode this Yescrypt instance
        is configured to use.

        Note that in `Mode.MCF` the Modular Crypt Format string contains a salt,
         found in `settings`, and `hash_length` is fixed at 32.

        :param password: A password to hash.
        :param salt: A salt for the hash. Required unless using `settings` with
         `Mode.MCF`.
        :param settings: An MCF-encoded paraneter string. Only used with `Mode.MCF`.
        :param hash_length: The desired hash length. Must be 32 when using `Mode.MCF`.
        :return: JSON-, MCF-, or raw-encoded hash bytes.
        """
        if self._mode is Mode.MCF:
            if hash_length != 32:
                raise ValueError(
                    "Argument Error: Yescrypt assumes 256-bit hashes for MCF and "
                    "does not store length in the crypt string. The hash_length "
                    "argument must be 32 in MCF mode."
                )
            if not settings:
                if not salt:
                    raise ValueError(
                        "Argument Error: A salt is required if not using MCF-encoded "
                        "settings."
                    )
                settings = _LIB.yescrypt_encode_params(self._params, salt, len(salt))
            if not settings:
                raise Exception("Hashing Error: yescrypt_encode_params failed.")
            # Buffer for encoded 32-byte password and max 64-byte salt (128 bytes),
            # with a 'y' for yescrypt, 4 $ delimeters, up to 8 6-byte parameters,
            # and a null terminator.
            buf_length = 181
            with ffi.new(f"uint8_t[{buf_length}]") as hash_buffer:
                if not _LIB.yescrypt_r(
                    ffi.NULL,
                    self._local_region,
                    password,
                    len(password),
                    settings,
                    ffi.NULL,
                    hash_buffer,
                    buf_length,
                ):
                    raise Exception("Hashing Error: yescrypt_r failed.")
                digest = ffi.string(hash_buffer, 10000)
        else:
            with ffi.new(f"uint8_t[{hash_length}]") as hash_buffer:
                if _LIB.yescrypt_kdf(
                    ffi.NULL,
                    self._local_region,
                    password,
                    len(password),
                    salt,
                    len(cast(bytes, salt)),
                    self._params,
                    hash_buffer,
                    hash_length,
                ):
                    raise Exception("Hashing Error: yescrypt_kdf failed.")
                digest = bytes(hash_buffer)
            if self._mode is Mode.JSON:
                digest = json.dumps(
                    {
                        "alg": "yescrypt",
                        "ver": "1.1",
                        "cfg": {k: getattr(self._params, k) for k in dir(self._params)},
                        "key": b64encode(digest).decode(),
                        "slt": b64encode(cast(bytes, salt)).decode(),
                    },
                    separators=(",", ":"),
                ).encode()

        return digest

    def compare(
        self, password: bytes, hashed_password: bytes, salt: Optional[bytes] = None
    ) -> None:
        """
        Generates a yescrypt hash for `password`, securely compares it to an
        existing `hashed_password`, and raises an exception if they don't match.
        Mismatches between the Yescrypt instance Mode and the `hashed_password`
        format raise a ValueError, except in Mode.RAW, where all bets are off.

        In Mode.JSON the encoded arguments are checked against this Yescrypt
        instance and a special exception is raised if they don't match. This
        shortcircuits hasing of `password` of entirely.

        In Mode.MCF, the internal yescrypt library decodes the arguments from the
        MCF string and the comparison simply fails if they don't match, since a
        different hash will be produced. In the future this may be enhanced with
        a more specific exception like Mode.JSON.

        In Mode.RAW, all responsibility is left in the hands of the caller,
        including supplying the salt (the parameters are already present in the
        Yescrypt instance, but may not match those used for hashed_password).

        :param password: A password to check.
        :param hashed_password: A password hash to check against.
        :param salt: The salt used for `hashed_password`. Only required when using
         Mode.RAW.
        :raises: WrongPassword, WrongPasswordConfiguration, ValueError
        """
        if self._mode == Mode.JSON:
            try:
                data = json.loads(hashed_password)
            except JSONDecodeError:
                if hashed_password.startswith(b"$y$"):
                    raise ValueError(
                        "Argument Error: MCF string passed to a JSON instance of "
                        "Yescrypt."
                    )
                else:
                    raise ValueError(
                        "Argument Error: Raw (probably) data passed to a JSON "
                        "instance of Yescrypt."
                    )
            # Make sure the parameters of this instance of Yescrypt are compatible
            # with those of the hashed password.
            cfg = data["cfg"]
            for k in cfg.keys():
                if cfg[k] != getattr(self._params, k):
                    raise WrongPasswordConfiguration(
                        "Error: Password configurations are incompatible."
                    )
            salt = b64decode(data["slt"])
            password_hash = self.digest(
                password, salt=salt, hash_length=len(b64decode(data["key"]))
            )
        elif self._mode == Mode.MCF:
            if not hashed_password.startswith(b"$y$"):
                try:
                    _ = json.loads(hashed_password)
                    raise ValueError(
                        "Argument Error: JSON passed to an MCF instance of Yescrypt."
                    )
                except ValueError:
                    raise
                except Exception:
                    raise ValueError(
                        "Argument Error: Raw (probably) data passed to an MCF "
                        "instance of Yescrypt."
                    )
            settings = hashed_password[: hashed_password.rfind(b"$")]

            # Length is always 32 in MCF mode.
            password_hash = self.digest(password, settings=settings, hash_length=32)
        else:
            if not salt:
                raise ValueError("Argument Error: A salt is required in RAW mode.")
            password_hash = self.digest(
                password, salt=salt, hash_length=len(hashed_password)
            )
        if not secrets.compare_digest(password_hash, hashed_password):
            raise WrongPassword("Error: Password does not match stored hash.")

    def __del__(self) -> None:
        if hasattr(self, "_local_region"):
            _LIB.yescrypt_free_local(self._local_region)


def main() -> None:
    # Example usage.
    import time

    # All default settings.
    hasher = Yescrypt(n=2 ** 16, r=8, p=1, mode=Mode.JSON)
    for i in range(5):
        password = secrets.token_bytes(32)
        salt = secrets.token_bytes(32)
        start = time.time()
        h = hasher.digest(password, salt)
        stop = time.time() - start
        try:
            hasher.compare(password, h)
        except WrongPasswordConfiguration:
            print("Passwords have different configurations.")
        except WrongPassword:
            print("Passwords don't match.")
        print(
            f"Yescrypt took {stop:.2f} seconds to generate main hash {h.decode()} and "
            f"used {128 * 2**16 * 8 / 1024**2:.2f} MiB memory."
        )


if __name__ == "__main__":
    main()
