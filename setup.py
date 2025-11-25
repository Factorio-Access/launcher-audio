from setuptools import setup

setup(
    cffi_modules=["fa_launcher_audio/_internals/bindings/ffi_build.py:ffibuilder"],
)
