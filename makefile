ifneq ($(MAKECMDGOALS),clean)
# Yescrypt makes liberal use of GCC preprocessor and C extensions that
# Microsoft's compiler doesn't support  (#warning, restrict, etc.). Clang
# supports them, but is generally brittle for the options we need across
# platforms, so we prefer GCC everywhere.

# Note: On macOS the GCC var is an alias to Clang and has to be changed
# to e.g. gcc-11 after `brew install gcc`, either at the command line
# with e.g. `make static GCC="gcc-11"` or by editing this file.
ifndef GCC
$(warning WARNING: GCC not set, Make may not be able to find the compiler)
GCC = gcc
endif

# LLVM's OMP has a simpler license (MIT) than GNU's GOMP (GPL), but as long as
# we're using GCC in the normal way linking GOMP falls under the GCC Runtime
# Library Exception. See:
#     https://www.gnu.org/licenses/gcc-exception-3.1-faq.en.html
# Static and dynamic linking are treated equally here.
ifndef OMP_PATH
$(warning WARNING: OMP_PATH not set, linker may not be able to find OpenMP)
else
OMP_PATH = -L"$(OMP_PATH)"
endif
endif

SRC_DIR = src/yescrypt
BUILD_DIR = build
TARGET_DIR = src/pyescrypt
OBJS = $(BUILD_DIR)/yescrypt-opt.o $(BUILD_DIR)/yescrypt-common.o \
       $(BUILD_DIR)/sha256.o $(BUILD_DIR)/insecure_memzero.o

PLATFORM =
ifeq ($(OS),Windows_NT)
	PLATFORM = Windows
else
	UNAME := $(shell uname)
	ifeq ($(UNAME),Darwin)
		PLATFORM = macOS
	else
		PLATFORM = Linux
	endif
endif

CLEANUP = 
ifeq ($(PLATFORM),Windows)
	CLEANUP = del /f /Q "$(BUILD_DIR)\*"
else
	CLEANUP = rm -f $(OBJS)
endif
    
SIMD =
ifeq ($(PLATFORM),macOS)
	SIMD = -msse2
else
	SIMD = -mavx
endif

OMP = 
ifeq ($(PLATFORM),Windows)
	OMP = -static -lgomp
else ifeq ($(PLATFORM),macOS)
	OMP = -static -lgomp
else
# Ubuntu ships with non-fPIC GOMP, so passing `-l:libgomp.a` fails. This is
# generally fine, since the only missing GOMP we've seen on Linux is Amazon's
# Python 3.8 Lambda runtime.
	OMP = -lgomp
endif

# Link GOMP statically when we can since it's not distributed with most systems.
static: $(OBJS)
	$(GCC) -shared -fPIC $(OBJS) $(OMP_PATH) -fopenmp $(OMP) -o $(TARGET_DIR)/yescrypt.bin

dynamic: $(OBJS)
	$(GCC) -shared -fPIC $(OBJS) $(OMP_PATH) -fopenmp -o $(TARGET_DIR)/yescrypt.bin

# Note: DSKIP_MEMZERO isn't actually used (the code only has a SKIP_MEMZERO
# guard), but we retain it in case it's used later.
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c | $(BUILD_DIR)
	$(GCC) -Wall -O2 -fPIC -funroll-loops -fomit-frame-pointer -fopenmp -DSKIP_MEMZERO $(SIMD) -c $< -o $@

$(BUILD_DIR):
	mkdir $@

yescrypt-opt.o: $(SRC_DIR)/yescrypt-platform.c

.PHONY: clean
clean:
	- $(CLEANUP)
