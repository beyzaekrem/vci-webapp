## FFMPEG

git clone https://github.com/FFmpeg/nv-codec-headers.git
cd nv-codec-headers/
make install
cd ..

apt-get install -y nasm build-essential yasm cmake libtool libc6 libc6-dev unzip wget libnuma1 libnuma-dev
git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg/
cd ffmpeg
./configure --enable-nonfree --enable-cuda-nvcc --enable-libnpp --extra-cflags=-I/usr/local/cuda/include --extra-ldflags=-L/usr/local/cuda/lib64 --disable-static --enable-shared
make -j 8
make install

export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/lib"

/usr/local/bin/ffmpeg

export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/srv/vci-capture/external/Video_Codec_SDK_13.0.19/Lib/linux/stubs/x86_64"

Copy the .so files to .so.1 of nvenc
