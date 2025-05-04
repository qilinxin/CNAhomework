# Compiler and flags
CC = gcc
CFLAGS = -Wall -ansi -pedantic -Iinclude -Isrc

# Source and target files
SRC_DIR = src
INC_DIR = include

GBN_SRC = $(INC_DIR)/emulator.c $(SRC_DIR)/gbn.c
SR_SRC  = $(INC_DIR)/emulator.c $(SRC_DIR)/sr.c

all: gbn sr

gbn: $(GBN_SRC)
	$(CC) $(CFLAGS) -o gbn $(GBN_SRC)

sr: $(SR_SRC)
	$(CC) $(CFLAGS) -o sr $(SR_SRC)

clean:
	rm -f gbn sr
