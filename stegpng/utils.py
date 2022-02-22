import zlib
from typing import Union, get_args

#TODO If the data to be compressed contain 16384 bytes or fewer, the PNG encoder may set the window size by rounding up to a power of 2 (256 minimum). This decreases the memory required for both encoding and decoding, without adversely affecting the compression ratio.

Data = Union[bytes, bytearray]

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


def paeth(a, b, c):
    """Implements the basic PAETH algorithm used to encode scanlines.
    See the PNG documentation: https://www.w3.org/TR/PNG/#9Filter-type-4-Paeth"""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        Pr = a
    elif pb <= pc:
        Pr = b
    else:
        Pr = c
    return Pr


def as_data(data: Data):
    if not isinstance(data, get_args(Data)):
        types = " or ".join(get_args(Data))
        raise TypeError("Expected {}, not {}".format(types, type(data)))
    if not isinstance(data, bytes):
        data = bytes(data)
    return data
