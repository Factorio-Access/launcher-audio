/*
 * audio_defs.h - CFFI declarations for miniaudio
 *
 * This file contains the minimal subset of miniaudio declarations needed
 * for our CFFI bindings. Types use ... for opaque structs.
 */

/* Basic types - must match miniaudio exactly */
typedef unsigned char      ma_uint8;
typedef unsigned int       ma_uint32;
typedef unsigned long long ma_uint64;
typedef int                ma_int32;
typedef int                ma_result;
typedef int                ma_bool32;

/* Format enum */
typedef enum {
    ma_format_unknown = 0,
    ma_format_u8      = 1,
    ma_format_s16     = 2,
    ma_format_s24     = 3,
    ma_format_s32     = 4,
    ma_format_f32     = 5
} ma_format;

/* Waveform type enum */
typedef enum {
    ma_waveform_type_sine     = 0,
    ma_waveform_type_square   = 1,
    ma_waveform_type_triangle = 2,
    ma_waveform_type_sawtooth = 3
} ma_waveform_type;

/* Opaque types - CFFI will let C determine sizes */
typedef struct ma_engine { ...; } ma_engine;
typedef struct ma_sound { ...; } ma_sound;
typedef struct ma_decoder { ...; } ma_decoder;
typedef struct ma_waveform { ...; } ma_waveform;
typedef struct ma_gainer { ...; } ma_gainer;
typedef struct ma_audio_buffer { ...; } ma_audio_buffer;
typedef struct ma_audio_buffer_ref { ...; } ma_audio_buffer_ref;

/* Config structures - also opaque */
typedef struct ma_engine_config { ...; } ma_engine_config;
typedef struct ma_sound_config { ...; } ma_sound_config;
typedef struct ma_decoder_config { ...; } ma_decoder_config;
typedef struct ma_waveform_config { ...; } ma_waveform_config;
typedef struct ma_gainer_config { ...; } ma_gainer_config;
typedef struct ma_audio_buffer_config { ...; } ma_audio_buffer_config;

/* Engine functions */
ma_engine_config ma_engine_config_init(void);
ma_result ma_engine_init(const ma_engine_config* pConfig, ma_engine* pEngine);
void ma_engine_uninit(ma_engine* pEngine);
ma_result ma_engine_start(ma_engine* pEngine);
ma_result ma_engine_stop(ma_engine* pEngine);
ma_uint64 ma_engine_get_time_in_pcm_frames(const ma_engine* pEngine);
ma_uint32 ma_engine_get_sample_rate(const ma_engine* pEngine);
ma_result ma_engine_read_pcm_frames(ma_engine* pEngine, void* pFramesOut,
                                     ma_uint64 frameCount, ma_uint64* pFramesRead);
ma_result ma_engine_set_volume(ma_engine* pEngine, float volume);

/* Sound functions */
ma_result ma_sound_init_from_file(ma_engine* pEngine, const char* pFilePath,
                                   ma_uint32 flags, void* pGroup,
                                   void* pDoneFence, ma_sound* pSound);
ma_result ma_sound_init_from_data_source(ma_engine* pEngine, void* pDataSource,
                                          ma_uint32 flags, void* pGroup, ma_sound* pSound);
void ma_sound_uninit(ma_sound* pSound);
ma_result ma_sound_start(ma_sound* pSound);
ma_result ma_sound_stop(ma_sound* pSound);
void ma_sound_set_volume(ma_sound* pSound, float volume);
float ma_sound_get_volume(const ma_sound* pSound);
void ma_sound_set_pitch(ma_sound* pSound, float pitch);
float ma_sound_get_pitch(const ma_sound* pSound);
void ma_sound_set_pan(ma_sound* pSound, float pan);
float ma_sound_get_pan(const ma_sound* pSound);
void ma_sound_set_looping(ma_sound* pSound, ma_bool32 isLooping);
ma_bool32 ma_sound_is_looping(const ma_sound* pSound);
ma_bool32 ma_sound_is_playing(const ma_sound* pSound);
ma_bool32 ma_sound_at_end(const ma_sound* pSound);
void ma_sound_set_start_time_in_pcm_frames(ma_sound* pSound, ma_uint64 absoluteGlobalTimeInFrames);
void ma_sound_set_stop_time_in_pcm_frames(ma_sound* pSound, ma_uint64 absoluteGlobalTimeInFrames);
void ma_sound_set_fade_in_pcm_frames(ma_sound* pSound, float volumeBeg, float volumeEnd, ma_uint64 fadeLengthInFrames);
ma_result ma_sound_seek_to_pcm_frame(ma_sound* pSound, ma_uint64 frameIndex);

/* Decoder functions */
ma_decoder_config ma_decoder_config_init(ma_format outputFormat, ma_uint32 outputChannels, ma_uint32 outputSampleRate);
ma_decoder_config ma_decoder_config_init_default(void);
ma_result ma_decoder_init_memory(const void* pData, size_t dataSize,
                                  const ma_decoder_config* pConfig, ma_decoder* pDecoder);
void ma_decoder_uninit(ma_decoder* pDecoder);
ma_result ma_decoder_get_length_in_pcm_frames(ma_decoder* pDecoder, ma_uint64* pLength);
ma_result ma_decoder_read_pcm_frames(ma_decoder* pDecoder, void* pFramesOut,
                                      ma_uint64 frameCount, ma_uint64* pFramesRead);
ma_result ma_decoder_seek_to_pcm_frame(ma_decoder* pDecoder, ma_uint64 frameIndex);

/* Waveform functions */
ma_waveform_config ma_waveform_config_init(ma_format format, ma_uint32 channels,
                                            ma_uint32 sampleRate, ma_waveform_type type,
                                            double amplitude, double frequency);
ma_result ma_waveform_init(const ma_waveform_config* pConfig, ma_waveform* pWaveform);
void ma_waveform_uninit(ma_waveform* pWaveform);
ma_result ma_waveform_read_pcm_frames(ma_waveform* pWaveform, void* pFramesOut,
                                       ma_uint64 frameCount, ma_uint64* pFramesRead);
ma_result ma_waveform_set_frequency(ma_waveform* pWaveform, double frequency);
ma_result ma_waveform_set_amplitude(ma_waveform* pWaveform, double amplitude);
ma_result ma_waveform_seek_to_pcm_frame(ma_waveform* pWaveform, ma_uint64 frameIndex);

/* Gainer functions (for per-channel volume control) */
ma_gainer_config ma_gainer_config_init(ma_uint32 channels, ma_uint32 smoothTimeInFrames);
ma_result ma_gainer_init(const ma_gainer_config* pConfig, void* pAllocationCallbacks, ma_gainer* pGainer);
void ma_gainer_uninit(ma_gainer* pGainer, void* pAllocationCallbacks);
ma_result ma_gainer_process_pcm_frames(ma_gainer* pGainer, void* pFramesOut,
                                        const void* pFramesIn, ma_uint64 frameCount);
ma_result ma_gainer_set_gain(ma_gainer* pGainer, float newGain);
ma_result ma_gainer_set_gains(ma_gainer* pGainer, float* pNewGains);

/* Audio buffer functions (for pre-decoded audio) */
ma_audio_buffer_config ma_audio_buffer_config_init(ma_format format, ma_uint32 channels,
                                                    ma_uint64 sizeInFrames, const void* pData,
                                                    void* pAllocationCallbacks);
ma_result ma_audio_buffer_init(const ma_audio_buffer_config* pConfig, ma_audio_buffer* pAudioBuffer);
ma_result ma_audio_buffer_init_copy(const ma_audio_buffer_config* pConfig, ma_audio_buffer* pAudioBuffer);
void ma_audio_buffer_uninit(ma_audio_buffer* pAudioBuffer);
ma_result ma_audio_buffer_read_pcm_frames(ma_audio_buffer* pAudioBuffer, void* pFramesOut,
                                           ma_uint64 frameCount, ma_bool32 loop);
ma_result ma_audio_buffer_seek_to_pcm_frame(ma_audio_buffer* pAudioBuffer, ma_uint64 frameIndex);
ma_result ma_audio_buffer_get_length_in_pcm_frames(const ma_audio_buffer* pAudioBuffer, ma_uint64* pLength);
ma_bool32 ma_audio_buffer_at_end(const ma_audio_buffer* pAudioBuffer);

/* Audio buffer ref (references external data without copying) */
ma_result ma_audio_buffer_ref_init(ma_format format, ma_uint32 channels, const void* pData,
                                    ma_uint64 sizeInFrames, ma_audio_buffer_ref* pAudioBufferRef);
void ma_audio_buffer_ref_uninit(ma_audio_buffer_ref* pAudioBufferRef);
ma_result ma_audio_buffer_ref_set_data(ma_audio_buffer_ref* pAudioBufferRef,
                                        const void* pData, ma_uint64 sizeInFrames);
ma_result ma_audio_buffer_ref_read_pcm_frames(ma_audio_buffer_ref* pAudioBufferRef,
                                               void* pFramesOut, ma_uint64 frameCount, ma_bool32 loop);
ma_result ma_audio_buffer_ref_seek_to_pcm_frame(ma_audio_buffer_ref* pAudioBufferRef, ma_uint64 frameIndex);
