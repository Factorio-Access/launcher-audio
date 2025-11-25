"""
CFFI build script for miniaudio bindings.

Run with: uv run python fa_launcher_audio/_internals/bindings/ffi_build.py
"""

from cffi import FFI
from pathlib import Path

ffibuilder = FFI()

# Get paths
this_dir = Path(__file__).parent.resolve()
pkg_dir = this_dir.parent.parent.resolve()  # fa_launcher_audio/

defs_path = this_dir / "audio_defs.h"

# Read our curated header declarations
cdef_content = defs_path.read_text()
ffibuilder.cdef(cdef_content)

# The source that CFFI will compile
# We include the headers with their implementation defines
source_code = '''
/* dr_libs decoders */
#define DR_WAV_IMPLEMENTATION
#include "dr_wav.h"

#define DR_FLAC_IMPLEMENTATION
#include "dr_flac.h"

#define DR_MP3_IMPLEMENTATION
#include "dr_mp3.h"

/* stb_vorbis for OGG support */
#define STB_VORBIS_HEADER_ONLY
#include "stb_vorbis.c"

/* miniaudio - the main audio engine */
#define MINIAUDIO_IMPLEMENTATION
#include "miniaudio.h"

/* Now include stb_vorbis implementation */
#undef STB_VORBIS_HEADER_ONLY
#include "stb_vorbis.c"
'''

ffibuilder.set_source(
    "fa_launcher_audio._audio_cffi",
    source_code,
    include_dirs=[str(pkg_dir)],
    libraries=[],
    extra_compile_args=[],
)

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
