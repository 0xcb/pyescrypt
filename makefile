# Yescrypt makes liberal use of GCC preprocessor and C extensions that break
# CL (#warning, restrict, etc.), and Clang can be quite brittle on Windows
# as well, so we simply require GCC everywhere.
CC = gcc
SRC_DIR = src/yescrypt
BUILD_DIR = build
TARGET_DIR = src/pyescrypt
OBJS = $(BUILD_DIR)/yescrypt-opt.o $(BUILD_DIR)/yescrypt-common.o $(BUILD_DIR)/sha256.o $(BUILD_DIR)/insecure_memzero.o
CLEANUP = 
ifeq ($(OS),Windows_NT)
	CLEANUP = del /f /Q "$(BUILD_DIR)\*"
else
	CLEANUP = rm -f $(OBJS)
endif
GOMP = 
ifeq ($(OS),Windows_NT)
	GOMP = -static -lgomp
else
	UNAME := $(shell uname)
	ifeq ($(UNAME),Darwin)
		GOMP = -static -lgomp
	else
		GOMP = -l:libgomp.a
	endif
endif

dynamic: $(OBJS)
	$(CC) -shared -fopenmp $(OBJS) -o $(TARGET_DIR)/yescrypt.bin

# Link GOMP statically since it's not distributed with Windows,
# sometimes gets left out of Linux distros or Docker containers, etc.
static: $(OBJS)
	$(CC) -shared -fopenmp $(GOMP) $(OBJS) -o $(TARGET_DIR)/yescrypt.bin

# Note: DSKIP_MEMZERO isn't actually used (the code only has a
# SKIP_MEMZERO guard), but we retain it in case it's used later.
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	$(CC) -Wall -O2 -fPIC -funroll-loops -fomit-frame-pointer -fopenmp -DSKIP_MEMZERO -mavx -c $< -o $@

yescrypt-opt.o: $(SRC_DIR)/yescrypt-platform.c

clean:
	$(CLEANUP)
