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

/* Sound config - for advanced sound initialization */
typedef struct ma_sound_config {
    void* pFilePath;
    void* pFilePathW;
    void* pDataSource;
    void* pInitialAttachment;
    ma_uint32 initialAttachmentInputBusIndex;
    ma_uint32 channelsIn;
    ma_uint32 channelsOut;
    ma_uint32 monoExpansionMode;
    ma_uint32 flags;
    ma_uint32 volumeSmoothTimeInPCMFrames;
    ma_uint64 initialSeekPointInPCMFrames;
    ma_uint64 rangeBegInPCMFrames;
    ma_uint64 rangeEndInPCMFrames;
    ma_uint64 loopPointBegInPCMFrames;
    ma_uint64 loopPointEndInPCMFrames;
    ma_bool32 isLooping;
    void* endCallback;
    void* pEndCallbackUserData;
    ...;
} ma_sound_config;

ma_sound_config ma_sound_config_init_2(ma_engine* pEngine);

/* Sound functions */
ma_result ma_sound_init_ex(ma_engine* pEngine, const ma_sound_config* pConfig, ma_sound* pSound);
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
void ma_sound_set_fade_start_in_pcm_frames(ma_sound* pSound, float volumeBeg, float volumeEnd, ma_uint64 fadeLengthInFrames, ma_uint64 absoluteGlobalTimeInFrames);
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

/* Sound flags */
#define MA_SOUND_FLAG_NO_DEFAULT_ATTACHMENT 0x00001000
#define MA_SOUND_FLAG_NO_PITCH              0x00002000
#define MA_SOUND_FLAG_NO_SPATIALIZATION     0x00004000

/* Special value for channelsOut to use data source's channel count */
#define MA_SOUND_SOURCE_CHANNEL_COUNT       0xFFFFFFFF

/* Node graph types */
typedef enum {
    ma_node_state_started = 0,
    ma_node_state_stopped = 1
} ma_node_state;

/* Node graph opaque types */
typedef struct ma_node_graph { ...; } ma_node_graph;
typedef struct ma_node_base { ...; } ma_node_base;
typedef struct ma_node_config { ...; } ma_node_config;
typedef struct ma_splitter_node { ...; } ma_splitter_node;
typedef struct ma_splitter_node_config { ...; } ma_splitter_node_config;
typedef struct ma_data_source_node { ...; } ma_data_source_node;
typedef struct ma_data_source_node_config { ...; } ma_data_source_node_config;

/* Generic node type - nodes are passed as void* in many APIs */
typedef void ma_node;

/* Node functions */
ma_result ma_node_attach_output_bus(ma_node* pNode, ma_uint32 outputBusIndex, ma_node* pOtherNode, ma_uint32 otherNodeInputBusIndex);
ma_result ma_node_detach_output_bus(ma_node* pNode, ma_uint32 outputBusIndex);
ma_result ma_node_detach_all_output_buses(ma_node* pNode);
ma_result ma_node_set_output_bus_volume(ma_node* pNode, ma_uint32 outputBusIndex, float volume);
float ma_node_get_output_bus_volume(const ma_node* pNode, ma_uint32 outputBusIndex);
ma_result ma_node_set_state(ma_node* pNode, ma_node_state state);
ma_node_state ma_node_get_state(const ma_node* pNode);
void ma_node_uninit(ma_node* pNode, void* pAllocationCallbacks);

/* Node graph functions */
ma_node* ma_node_graph_get_endpoint(ma_node_graph* pNodeGraph);

/* Engine node graph access */
ma_node* ma_engine_get_endpoint(ma_engine* pEngine);
ma_node_graph* ma_engine_get_node_graph(ma_engine* pEngine);

/* Splitter node functions */
ma_splitter_node_config ma_splitter_node_config_init(ma_uint32 channels);
ma_result ma_splitter_node_init(ma_node_graph* pNodeGraph, const ma_splitter_node_config* pConfig, void* pAllocationCallbacks, ma_splitter_node* pSplitterNode);
void ma_splitter_node_uninit(ma_splitter_node* pSplitterNode, void* pAllocationCallbacks);

/* Data source node functions */
ma_data_source_node_config ma_data_source_node_config_init(void* pDataSource);
ma_result ma_data_source_node_init(ma_node_graph* pNodeGraph, const ma_data_source_node_config* pConfig, void* pAllocationCallbacks, ma_data_source_node* pDataSourceNode);
void ma_data_source_node_uninit(ma_data_source_node* pDataSourceNode, void* pAllocationCallbacks);
ma_result ma_data_source_node_set_looping(ma_data_source_node* pDataSourceNode, ma_bool32 isLooping);
ma_bool32 ma_data_source_node_is_looping(ma_data_source_node* pDataSourceNode);

/* Custom panner node - equal power mono-to-stereo panning */
typedef struct panner_node { ...; } panner_node;

ma_result panner_node_init(ma_node_graph* pNodeGraph, float initial_pan, void* pAllocationCallbacks, panner_node* pPanner);
void panner_node_uninit(panner_node* pPanner, void* pAllocationCallbacks);
void panner_node_set_pan(panner_node* pPanner, float pan);
float panner_node_get_pan(const panner_node* pPanner);

