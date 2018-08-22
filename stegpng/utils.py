import zlib

#TODO If the data to be compressed contain 16384 bytes or fewer, the PNG encoder may set the window size by rounding up to a power of 2 (256 minimum). This decreases the memory required for both encoding and decoding, without adversely affecting the compression ratio.

def compress(data):
    if len(data) <= 16384:
        window_size = 8
        p = 256
        while len(data) > p:
            window_size += 1
            p <<= 1
        compressor = zlib.compressobj(level=8, wbits=window_size)
        b = bytearray(compressor.compress(data))
        b.extend(compressor.flush())
        return b
    else:
        return zlib.compress(data)

def decompress(data):
    return zlib.decompress(data)
