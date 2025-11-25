/*
 * audio_impl.c - Implementation file for miniaudio and dr_libs
 *
 * This file defines the implementations for all the single-header libraries
 * we use. It should be compiled once and linked with the CFFI extension.
 */

/* dr_libs decoders */
#define DR_WAV_IMPLEMENTATION
#include "dr_wav.h"

#define DR_FLAC_IMPLEMENTATION
#include "dr_flac.h"

#define DR_MP3_IMPLEMENTATION
#include "dr_mp3.h"

/* stb_vorbis for OGG support - included in header-only mode first */
#define STB_VORBIS_HEADER_ONLY
#include "stb_vorbis.c"

/* miniaudio - the main audio engine */
#define MINIAUDIO_IMPLEMENTATION
#include "miniaudio.h"

/* Now include stb_vorbis implementation */
#undef STB_VORBIS_HEADER_ONLY
#include "stb_vorbis.c"
