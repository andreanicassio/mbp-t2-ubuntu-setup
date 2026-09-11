obj-m += t2bce_audio.o
t2bce_audio-y := audio.o protocol.o protocol_bce.o pcm.o
ccflags-y += -DWITHOUT_NVME_PATCH -I$(src) -I$(src)/t2bce_core/include
