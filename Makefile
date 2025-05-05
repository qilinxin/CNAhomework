# Compiler and flags
CC      := gcc
CFLAGS  := -Wall -ansi -pedantic

# Source lists
GBN_SRCS := emulator.c gbn.c
SR_SRCS  := emulator.c sr.c

# Default target: build both
all: gbn sr

# Build Go‐Back‐N simulator
gbn: $(GBN_SRCS)
	$(CC) $(CFLAGS) -o $@ $(GBN_SRCS)

# Build Selective‐Repeat simulator
sr: $(SR_SRCS)
	$(CC) $(CFLAGS) -o $@ $(SR_SRCS)

# Remove built executables
.PHONY: clean
clean:
	rm -f gbn sr
