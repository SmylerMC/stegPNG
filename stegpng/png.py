from struct import unpack, pack
from typing import Any, Optional, Union, Tuple, get_args
from zlib import crc32 as crc

import stegpng
from . import chunks
from .pngexceptions import *
from .utils import compress, decompress, paeth, as_data, Data as _Data
from math import ceil, floor
import requests


"""
This is the main StegPNG module, and contains the most basic structures that make up a PNG file.
"""

# Type aliases for annotations
_Png = "Png"
_Chunk = "PngChunk"
_ScanLine = "ScanLine"
_PixelPos = Union[tuple[int, int], list[int, int]]
_PixelContent = Union[list, tuple]
_ScanLineContent = Optional[tuple[int, _PixelContent]]

_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

# TODO stronger type checks everywhere in here
# TODO document everything that might raise a read only exception

class Png:

    """
    Represents a PNG file according to the PNG specification: https://www.w3.org/TR/PNG/.
    A PNG file starts with the PNG signature.
    It then contains a stream of PNG chunks, each starting with a four bytes length,
    followed by a four bytes ascii valid and then by a payload of the specified length, followed by a CRC checksum.
    It is mandatory that a PNG file starts with an IHDR chunk and ends with an IEND chunk.
    In between should be IDAT chunks, which contain the compressed image data.
    Additional chunks can appear between the IHDR and the IDATs, with additional metadata.
    If the image is palette index, one of those chunks has to be the PLTE chunk, which contains the palette.
    If data follows the IEND chunk, it shall be ignored by the decoder.
    """

    def __init__(self, filebytes: _Data, ignore_signature: bool = False, edit: bool = True) -> None:
        """
        Constructs a :class:`Png` object using the given bytes.
        To directly read a PNG file from disc or http, prefer the :func:`open` function.
        To create a new :class:`Png` object from scratch, prefer the :func:`create_empty_png` function.

        :param filebytes: the bytes that make up the PNG.
        :param ignore_signature: consider the PNG signature missing from the file's header.
        :param edit: whether to allow this Png object to be modified afterward.
        :raises TypeError: if one of the arguments is not of the right type.
        :raises InvalidPngStructureException: if ignore_signature is False and the PNG signature is missing.
        """
        filebytes = as_data(filebytes)
        if not isinstance(edit, bool):
            raise TypeError('Edit should be a boolean')
        if not ignore_signature and not read_png_signature(filebytes):
            raise InvalidPngStructureException("missing PNG signature")
        self.__filebytes = filebytes
        self.__chunks = None
        self.__file_end = None
        self.__scanlines = None
        self.edit = edit

        # True when the bytes changed but the pixels have not been updated yet
        self.__stream_has_changed = False

        # True when the scanlines have changed but the stream has not been updated yet
        self.__pixels_have_changed = False

    @property
    def chunks(self) -> list[_Chunk]:
        """
        :returns: the PNG chunks that make up this image.
        """
        if self.__chunks is None:
            self.__read_chunks()
        return self.__chunks

    def __read_chunks(self):
        # TODO Handle malformed files with a fancy exception
        decoded_chunks = []
        data = self.__filebytes
        start = 8
        end = len(data) - 1
        data = data[8:]
        no = -1
        while start <= end:
            no += 1
            length = unpack('>I', data[:4])[0]
            chunk = PngChunk(data[:length + 12])
            try:
                chunk_type = chunk.type
            except UnicodeDecodeError:
                raise InvalidPngStructureException(
                    "Failed to read chunk type at index {}".format(start)
                )
            decoded_chunks.append(chunk)
            start += length + 12
            data = data[length + 12:]
            if chunk_type == 'IEND':  # TODO Make this returns even if there is only garbage data after a non-iend chunk
                break
        self.__file_end = data
        self.__chunks = decoded_chunks

    @property
    def bytes(self) -> bytes:
        """
        :returns: the raw bytes that make up the PNG file.
        """
        global _PNG_SIGNATURE
        b = _PNG_SIGNATURE
        for chunk in self.chunks:
            b += chunk.bytes
        b += self.extra_data
        return b

    def save(self, file_name: str) -> None:
        """
        Save this PNG to a file on disc.
        :param file_name: name to save the file as. Will be overwritten if is already exists.
        """
        with _builtin_open(file_name, 'bw') as f:  # Workaround because we have our own open function
            f.write(self.bytes)

    def get_original(self) -> _Png:
        """
        :returns: a new Png object with exactly the same bytes as this one at the time it was created.
        """
        return Png(self.__filebytes)

    def copy(self) -> _Png:
        """
        :returns: a new Png object with the same bytes as this one.
        """
        return Png(self.bytes)

    def reset(self) -> None:
        """
        Resets any change done to the image and goes back to when it was created.
        """
        self.__read_chunks()

    def add_chunk(self, chunk: _Chunk, index: int = None) -> None:
        """
        Adds the chunk to the file, at the given index.
        If the index is omitted, the chunk is added just before the IEND last chunk.

        :param chunk: the chunk to add to the image.
        :param index: the index to add the chunk at.
            If this is None, the chunk will be placed according to the PNG specification
        """
        # TODO If chunk an an IDAT, add after all other IDATS
        # TODO If it is a IHDR, add at 0, if it is an IEND add at the tai
        # TODO Otherwise, add  before the first IDAT
        if index is None:
            if chunk.type == 'IHDR':
                index = 0
            elif chunk.type == 'IEND':
                index = len(self.chunks)
            else:
                index = len(self.chunks) - 1
        self.__chunks.insert(index, chunk)

    def remove_chunk(self, chunk: _Chunk) -> None:
        """
        Removes the given chunk from the image.

        :param chunk: a chunk to remove from the image.
        :raises ValueError: if this image does not contain the given chunk.
        """
        self.chunks.remove(chunk)

    def index_of_chunk(self, chunk: _Chunk) -> int:
        """
        :param chunk: a chunk to get the index of.
        :returns: the index of the given chunk in the image.
        :raises ValueError: if this image does not contain the given chunk.
        """
        return self.chunks.index(chunk)

    def address_of_chunk(self, chunk: _Chunk) -> int:
        """
        :param chunk: a chunk to get the address of.
        :returns: the byte address of the given chunk.
        :raises ValueError: if this image does not contain the given chunk.
        """
        add = len(_PNG_SIGNATURE)
        if chunk not in self.chunks:
            raise ValueError("chunk not in image")
        for c in self.chunks:
            if c is not chunk:
                add += len(c.bytes)
            else:
                break
        return add

    def get_chunks_by_type(self, name: str) -> tuple[_Chunk]:
        """
        :param name: the chunk type to look for (e.g. IHDR).
        :returns: all the chunks of the given type in this image.
        """
        return tuple(filter(lambda c: c.type == name, self.chunks))

    @property
    def extra_data(self) -> bytes:
        """
        :returns: any data found after the last valid chunk of this image.
            This is a good indication that someone is trying to hide somthing.
        """
        if self.__file_end is None:
            self.__read_chunks()
        return self.__file_end

    @extra_data.setter
    def extra_data(self, value: _Data) -> None:
        """
        Adds hidden data at the end of the image, after the IEND chunk.

        :param value: data to append to the end of the file.
        :raises TypeError: if value is not a valid type.
        """
        value = as_data(value)
        if self.__file_end is None:  # Ensure the file structure has been decoded
            self.__read_chunks()
        self.__file_end = value

    @property
    def width(self) -> int:
        """
        :returns: the width of this image.
        :raises InvalidPngStructureException: if this image is missing an IHDR chunk.
        """
        return self.__get_ihdr()['width']

    @width.setter
    def width(self, value: int) -> None:
        """
        Sets the width of this image.
        :param value: a new width for this image.
        :raises InvalidPngStructureException: if this image is missing an IHDR chunk.
        """
        self.__get_ihdr()['width'] = value

    @property
    def height(self) -> int:
        """
        :returns: the height of this image.
        :raises InvalidPngStructureException: if this image is missing an IHDR chunk.
        """
        return self.__get_ihdr()['height']

    @height.setter
    def height(self, value: int) -> None:
        """
        Sets the height of this image.
        :param value: a new height for this image.
        :raises InvalidPngStructureException: if this image is missing an IHDR chunk.
        """
        self.__get_ihdr()['height'] = value

    @property
    def size(self) -> tuple[int, int]:
        """
        :returns: the size of this image, as a (width, height) tuple.
        :raises InvalidPngStructureException: if this image is missing an IHDR chunk.
        """
        return self.__get_ihdr()['size']

    @size.setter
    def size(self, value: tuple[int, int]) -> None:
        """
        :param value: a new size for this image.
        :raises InvalidPngStructureException: if this image is missing an IHDR chunk.
        """
        self.__get_ihdr()['size'] = value

    @property
    def datastream(self) -> bytes:
        # TODO Setter
        # TODO have a cache for that
        """
        :returns: the compressed data stream inside the IDAT chunks.
        """
        stream = bytearray()
        for chunk in self.get_chunks_by_type('IDAT'):
            stream.extend(chunk.data)
        return bytes(stream)

    @property
    def imagedata(self) -> bytes:
        # TODO setter
        # TODO have a cache for that
        """
        :returns: the raw decompressed data from the IDAT chunks.
        """
        return decompress(self.datastream)

    @imagedata.setter
    def imagedata(self, data: _Data):
        data = compress(data)
        j = 0
        for i, chunk in enumerate(self.chunks):
            if chunk.type == "IDAT":
                j = i
                l = len(chunk.data)
                chunk.data = data[:l]
                data = data[l:]
        c = stegpng.create_empty_chunk("IDAT")
        c.data = data
        self.chunks.insert(j + 1, c)

    @property
    def scanlines(self) -> tuple[_ScanLine]:
        # TODO setter
        # TODO Interlace support
        """
        Decodes the scalines in this image.
        WARNING: Interlace is not currently supported.
        :returns: the scanlines of the image, as a tuple of scanlines, ordered from top to bottom order.
        :raises InvalidPngStructureException: if this image is missing an IHDR chunk,
            or if the interlace method is not supported.
        """
        ihdr = self.__get_ihdr()
        if ihdr['interlace'] != 0:
            # TODO More specific exception
            raise InvalidPngStructureException('Invalid interlace method: {}'.format(ihdr['interlace']))
        if not self.__scanlines:
            depth = ihdr['bit_depth']
            if depth not in ihdr['colortype_depth']:
                raise InvalidPngStructureException(
                    'Bit depth of {} is not allowed for color type {}'.format(
                        depth,
                        ihdr['colortype_name']
                    )
                )
            if ihdr['colortype_name'] == 'Indexed-colour':
                depth = 8
            width, height = self.size
            channel_count = ihdr['channel_count']
            data = self.imagedata
            linesize = width * ceil(depth / 8 * channel_count) + 1

            # The first scanline is the only one which can't have reference to its upper pixels,
            # so we compute it first
            lines = [ScanLine(channel_count,
                              depth,
                              None,
                              data=data[0:linesize],
                              edit=self.edit
                              ),
                     ]
            i = 1
            while (i + 1) * linesize <= len(data):
                s = ScanLine(
                    channel_count,
                    depth,
                    lines[i - 1],
                    data=data[i * linesize:(i + 1) * linesize]
                )
                lines.append(s)
                i += 1
            self.__scanlines = lines
        return tuple(self.__scanlines)

    def getpixel(self, position: tuple[int, int]) -> Tuple[int, ...]:
        """
        :param position: a valid position in the image.
        :returns: the pixel at the given position in the image,
            as tuple which length corresponds to the number of channels in the image.
        :raises InvalidPngStructureException: if this image is missing a critical chunk necessary for pixel decoding.
        :raises TypeError: if position is not of the right type.
        :raises ValueError: if position does not have exactly 2 elements.
        :raises IndexError: if position does not fit in the image dimensions.
        """
        x, y = self.__validate_pixel_pos(position)
        ihdr = self.__get_ihdr()
        scanline = self.scanlines[y]
        p = scanline.pixels[x]

        # Indexed color
        if ihdr['colortype_code'] == 3:
            plte = self.get_chunks_by_type('PLTE')
            if len(plte) == 0:
                raise InvalidPngStructureException('Missing a PLTE chunk')
            plte = plte[0]  # TODO Optimize this
            p = p[0]
            p = plte[p]

        if ihdr['channel_count'] == 1 and ihdr['colortype_code'] != 3:
            p = p[0]

        return p

    def __get_ihdr(self):
        if len(self.chunks) < 1 or self.chunks[0].type != 'IHDR':
            raise InvalidPngStructureException(
                'missing IHDR chunk at the beginning of the file'
            )
        return self.chunks[0]

    def __validate_pixel_pos(self, position):
        if not isinstance(position, get_args(_PixelPos)):
            raise TypeError('pixel position should be a tuple or a list: tuple(x, y)')
        if len(position) != 2:
            raise ValueError('pixel position should only contain 2 values: tuple(x, y)')
        x, y = position
        width, height = self.size
        if x >= width:
            raise IndexError(
                'the image has a width of {} but an x position of {} was given'.format(
                    width, x
                )
            )
        if y >= height:
            raise IndexError(
                'the image has an height of {} but an y position of {} was given'.format(
                    height, y
                )
            )
        return x, y

    def recalculate_image_data(self):
        b = bytearray()
        for scanline in self.scanlines:
            b += scanline.data
        self.imagedata = b

class PngChunk:

    """
    Represents a PNG chunk.
    The structure of a png chunk should be as follow:
            [   length (4 bytes, big-endian) |
                type (4 bytes, ascii)        |
                data (length bytes)          |
                crc (4 bytes)                ]

    The crc checksum is calculated with the chunk type and data, but does
    not include the length header.
    """

    def __init__(self, chunkbytes: _Data, edit: bool = True, auto_update: bool = True) -> None:
        """
        Creates a PngChunk from the bytes given in the chunkbytes parameter.
        To create a new, empty chunk, use the :func:`create_empty_chunk` function.

        :param chunkbytes: the raw bytes of the chunk.
            If to much data is given everything not in the range specified in the length header will be ignored.
        :param edit: whether to allow this chunk object to be modified afterward.
        :param auto_update: if this is true, the chunk's CRC is updated automatically when the chunk's content changes.
        :raises TypeError: if the data is not of a valid type.
        """
        # TODO raise exception if data len is invalid
        self.__bytes = as_data(chunkbytes)
        self.__bytes = self.__bytes[:self.length + 12]
        self.edit = edit
        self.auto_update = auto_update
        self.__dirty = False

    def __changing(self, update_crc: bool = True):
        """
        Should be called when ever a change that should change
        the bytes of the chunk occurs.
        """
        if not self.edit:
            raise Exception("Trying to edit read-only png!")
        else:
            if update_crc:
                self.update_crc()
            self.__dirty = True

    @property
    def bytes(self) -> bytes:
        """
        :returns: this chunk's raw content.
        """
        return self.__bytes

    @property
    def crc(self) -> int:
        """
        :returns: the chunk's CRC checksum, decoded.
        """
        return unpack('!I', self.__bytes[-4:])[0]

    @crc.setter
    def crc(self, value: int) -> None:
        """
        Changes this chunk's CRC. Does not disable automatic CRC update on change,
            if you want your change to persist after changing other aspects of the chunk,
            you need to disable auto update.

        :param value: a new value for the chunk's CRC.
        """
        if not isinstance(value, int):
            raise TypeError("The crc should be an integer.")
        self.__changing(update_crc=False)
        self.__bytes = self.bytes[:-4] + pack('!I', value)

    @property
    def type(self) -> str:
        """
        :returns: the type of this chunk (E.g. IHDR)
        """
        return self.__bytes[4:8].decode('ascii')

    @type.setter
    def type(self, value: str) -> None:
        """
        Changes the type of this chunk.

        :param value: the new chunk type.
        :raises TypeError: if value is not an str instance.
        :raises ValueError: if value is not of length 4.
        """
        self.__changing(update_crc=False)
        if not isinstance(value, str):
            raise TypeError("A chunk's type should be a string.")
        if len(value) != 4:
            raise ValueError("A chunk's type have to be 4 characters long.")
        self.__bytes = self.__bytes[0:4] + value.encode('ascii') + self.__bytes[8:]
        self.__changing(self.auto_update)

    def __len__(self) -> int:
        """
        :returns: the length of this chunk.
        """
        return self.length

    @property
    def length(self) -> bytes:
        """
        :returns: the length of this chunk.
        """
        return unpack('>I', self.__bytes[0:4])[0]

    @property
    def data(self) -> bytes:
        """
        :returns: this chunk's payload.
        """
        return self.bytes[8:-4]

    @data.setter
    def data(self, data: bytes) -> None:
        """
        Sets the chunk's raw payload.

        :param data: the new payload.
        :raises TypeError: if data is not of the correct type.
        """
        data = as_data(data)
        self.__changing(update_crc=False)
        self.__bytes = self.__bytes[0:8] + data + self.__bytes[-4:]
        self.__update_length()
        self.__changing(self.auto_update)

    def __update_length(self):
        length = len(self.__bytes) - 12
        if length < 0:
            raise Exception("Trying to update the length of a chunk, but it's smaller than 0!")
        self.__bytes = pack('>I', length) + self.__bytes[4:]

    def check_crc(self) -> bool:
        """
        :returns: True if the CRC checksum of this chunk is correct.
        """
        return self.compute_crc() == self.crc

    def compute_crc(self) -> int:
        """
        Compute the CRC checksum for this chunk.
        :returns: the correct CRC checksum for this chunk.
        """
        return crc(self.__bytes[4:-4])

    def update_crc(self) -> None:
        """
        Updates the CRC checksum of this chunk according to its content.
        """
        self.crc = self.compute_crc()

    def iscritical(self) -> bool:
        """
        :returns: whether this chunk's critical bit is set
            (which equals to the first character in the chunk's name being uppercase).
            A PNG decoder coming accros a critical chunk it doesn't know about should produce an error.
            The PNG specification includes 4 critical chunks: IHDR, PLTE, IDAT and IEND.
        """
        return (self.__bytes[4] & 0b000010000) >> 4 == 0

    def isancillary(self) -> bool:
        """
        :returns: whether this chunk is not a critical chunk.
        """
        return (self.__bytes[4] & 0b000010000) >> 4 == 1

    def is_supported(self) -> bool:
        """
        :returns: whether this chunk is supported by StegPNG.
        """
        global _supported_chunks
        return self.type in _supported_chunks

    def is_valid(self) -> bool:
        """
        :returns: whether this chunk's content is valid.
        """
        return self.__get_implementation().is_valid(self)

    def __get_implementation(self):
        if not self.is_supported():
            raise UnsupportedChunkException()
        global _supported_chunks
        return _supported_chunks[self.type]

    def getitem(self, key: str, ihdr: _Chunk = None, ihdrdata: dict[str, Any] = None) -> Any:
        """
        Accessor for chunk specific properties. Queries the underlying chunk implementation.

        :param key: property name.
        :param ihdr: Some chunk need additional information from the IHDR chunk of the image
            in order to interpret their content. This parameter is one way to provide that IHDR chunk.
        :param ihdrdata: Some chunk need additional information from the IHDR chunk of the image
            in order to interpret their content. This parameter is one way to provide that IHDR chunk.
        :returns: the value of the given key in the chunk by querying the correct implementation.
        """
        return self.__get_implementation().get(self, key, ihdr=ihdr, ihdr_data=ihdrdata)

    def __getitem__(self, key: str) -> Any:
        return self.getitem(key)

    def setitem(self, key: str, value: Any, ihdr: _Chunk = None, ihdrdata: dict[str, Any] = None) -> None:
        """
        Accessor for chunk specific properties. Calls the underlying chunk implementation.

        :param key: property name.
        :param value: the new value for the property.
        :param ihdr: Some chunk need additional information from the IHDR chunk of the image
            in order to interpret their content. This parameter is one way to provide that IHDR chunk.
        :param ihdrdata: Some chunk need additional information from the IHDR chunk of the image
            in order to interpret their content. This parameter is one way to provide that IHDR chunk.
        """
        self.__get_implementation().set(self, key, value, ihdr=ihdr, ihdr_data=ihdrdata)

    def __setitem__(self, key: str, value: Any) -> None:
        self.setitem(key, value)

    def __repr__(self) -> str:
        norm = super(PngChunk, self).__repr__()
        norm = norm.rsplit(' ')
        norm.insert(1, '[' + self.type + ']')
        return ' '.join(norm)

    def get_payload(self, ihdr: _Chunk = None, ihdr_data: dict[str, Any] = None) -> Any:
        """
        Allows to retrieve all properties stored in a chunk in one method call. Returns the entire content of the chunk.

        :param ihdr: Some chunk need additional information from the IHDR chunk of the image
            in order to interpret their content. This parameter is one way to provide that IHDR chunk.
        :param ihdr_data: Some chunk need additional information from the IHDR chunk of the image
            in order to interpret their content. This parameter is one way to provide that IHDR chunk.
        :returns: the content of the chunk, usually as a dictionary,
            but not always (E.g. PLTE chunks will return a tuple, and IDAT bytes).
        """
        return self.__get_implementation().get_all(self, ihdr=ihdr, ihdr_data=ihdr_data)

    def _set_empty_data(self) -> None:
        """
        Replaces the current data with some valid garbage, provided by the implementation.
        """
        self.data = self.__get_implementation().empty_data


class ScanLine:

    """
    Represents a scanline in a png data stream.
    This class is used internally for decoding,
    but exists because scanlines could be used for steganography because of the filter type.
    """

    def __init__(self, channelcount: int, bitdepth: int, previous: Optional[_ScanLine],
                 data: _Data = None, content: _ScanLineContent = None, edit: bool = True, png: Png = None) -> None:

        """
        :param channelcount: number of color channels in the image.
        :param bitdepth: number of bits per channel.
        :param previous: the previous scanline in the stream, or None if this is the first scanline of the stream.
        :param data: the raw bytes for this scanline. Either this or content has to not be None.
        :param content: the decoded content for this scanline, in the (int filter type, list/tuple pixels) format.
            Either this or data has to not be None.
        :param edit: whether to mark that scanline as read-only.
        """

        # Types and value checks
        if not isinstance(previous, ScanLine) and previous is not None:
            raise TypeError(
                'The previous argument should be a ScanLine or None, not {}'.format(
                    type(previous))
            )
        if (data, content) == (None, None):
            raise ValueError(
                "data and content can't be both None, please specify at least one")
        elif data is not None and content is not None:
            raise ValueError(
                'Cannot have a value for both pixels and data, please specify only one')
        if edit not in (True, False):
            raise TypeError('argument readonly must be a boolean value')
        if data is not None:
            data = as_data(data)
        elif content is not None and type(content) not in (list, tuple):
            raise TypeError('content must be a tuple or a list')
        if content is not None:
            if len(content) != 2 or type(content[0]) != int or type(content[1]) not in (tuple, list):
                raise ValueError(
                    "content should in the following format: (int filter, list/tuple pixels)")
            try:
                self.__checkpixels_args(content[1])
            except Exception as e:
                raise e

        # Variables assignments
        if content is not None:
            self.__filtertype, self.__pixels = content
            self.__pixels_dirty = False
            self.__filtertype_dirty = False
            self.__data_dirty = True
        elif data is not None:
            self.__data = data
            self.__filtertype_dirty = True
            self.__pixels_dirty = True
            self.__data_dirty = False
        self.edit = edit
        self.channelcount = channelcount
        self.bitdepth = bitdepth
        self.__unfiltered_dirty = True
        self._previous = previous

    @property
    def channelcount(self) -> int:
        """
        :returns: the number of channels in this scanline.
        """
        return self.__channelcount

    @channelcount.setter
    def channelcount(self, value: int) -> None:
        """
        :param value: a new number of channels for this scanline.
        """
        # TODO check valid values
        self.__channelcount = value

    @property
    def bitdepth(self) -> int:
        """
        :returns: the number of bit per channel in this scanline.
        """
        return self.__bitdepth

    @bitdepth.setter
    def bitdepth(self, value: int):
        """
        :param value: the new number of bit per channel for this scanline.
        """
        # TODO check valid values
        self.__bitdepth = value

    @property
    def filtertype(self) -> int:
        """
        :returns: the filter code for this scanline.
        """
        if self.__filtertype_dirty:
            self.__filtertype = self.data[0]
            self.__filtertype_dirty = False
        return self.__filtertype

    @filtertype.setter
    def filtertype(self, val: int):
        """
        :param val: new filter code value.
        """
        # TODO test this for errors and maybe use bytearrays
        # TODO check valid values and allow user to force using an invalid one
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        if type(val) != int:
            raise TypeError("Filter type should be an integer")
        b = self.unfiltered # Force decode the unfiltered data if needed
        self.__filtertype = val
        self.__data_dirty = True

    @property
    def unfiltered(self) -> bytes:
        """
        :returns: the unfiltered content of this scanline.
        """
        if self.__unfiltered_dirty:
            if not self.__data_dirty:
                workingsize = ceil(self.channelcount * self.bitdepth / 8)
                unfiltered = bytearray()

                if self.filtertype == 0:
                    unfiltered = self.data[1:]
                else:
                    for index, byte in enumerate(self.data[1:]):

                        # b or c will be set to 0 if not required by the filter type
                        # This is done to avoid unneeded computation,
                        # as they require the previous scanline to be also decoded
                        if index < workingsize:
                            a = 0
                        else:
                            a = unfiltered[index - workingsize]
                        if self._previous is None or self.filtertype not in (2, 3, 4):
                            b = 0
                        else:
                            b = self._previous.unfiltered[index]
                        if index < workingsize or self._previous is None or self.filtertype != 4:
                            c = 0
                        else:
                            c = self._previous.unfiltered[index - workingsize]

                        if self.filtertype == 1:
                            unfiltered.append((byte + a) % 256)
                        elif self.filtertype == 2:
                            unfiltered.append((byte + b) % 256)
                        elif self.filtertype == 3:
                            unfiltered.append((byte + floor((a + b) / 2)) % 256)
                        elif self.filtertype == 4:
                            unfiltered.append((byte + paeth(a, b, c)) % 256)
                        else:
                            raise UnsupportedFilterTypeException(code=self.filtertype)
                self.__unfiltered = bytes(unfiltered)
            elif not self.__pixels_dirty:
                unfiltered = bytearray()

                if self.bitdepth == 8:
                    for pixel in self.pixels:
                        for value in pixel:
                            unfiltered.append(value)
                    self.__unfiltered = bytes(unfiltered)
                else:
                    # TODO
                    raise NotImplementedError('Only a bit depth of 8 is supported yet')
            else:
                raise Exception('Unable to unfilter scanline. This is a bug, please report it')
            self.__unfiltered_dirty = False
        return self.__unfiltered

    @unfiltered.setter
    def unfiltered(self, value: _Data) -> None:
        """
        :param value: the unfiltered content of this scanline.
        """
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        value = as_data(value)
        if len(value) != len(self.unfiltered):
            raise ValueError(
                "Trying to set the unfiltered scanline with a length of the {} bytes, but the current one has a length of {}".format(
                    len(value), len(self.unfiltered))
            )
        self.__unfiltered = value
        self.__data_dirty = True
        self.__pixels_dirty = True

    @property
    def pixels(self) -> _PixelContent:
        """
        :returns: this scanline's pixel, decoded.
        """
        if self.__pixels_dirty:
            pixels = []
            pixel = []
            if self.bitdepth == 8:
                for byte in self.unfiltered:
                    pixel.append(byte)
                    if len(pixel) == self.channelcount:
                        pixels.append(tuple(pixel))
                        pixel = []
            else:
                raise NotImplementedError()
            # TODO ===================================================================
            self.__pixels = tuple(pixels)
            self.__pixels_dirty = False
        return self.__pixels

    @pixels.setter
    def pixels(self, value: _PixelContent):
        """
        :param value: new pixel values for this scanline.
        """
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        try:
            self.__checkpixels_args(value)
        except Exception as e:
            raise e
        self.__pixels = value
        self.__data_dirty = True
        self.__unfiltered_dirty = True

    def __checkpixels_args(self, pixels):
        """Used to verify that a pixels argument is valid"""
        l = None
        for pixel in pixels:
            if type(pixel) not in (list, tuple):
                raise TypeError('pixels should be tuples or lists, not {}'.format(type(pixel)))
            elif l == None:
                l = len(pixel)
            elif len(pixel) != l:
                raise ValueError('All pixels should have the same length')
            else:
                for channel in pixel:
                    if type(channel) != int:
                        raise TypeError(
                            'pixels should contain integers only, not {}'.format(type(channel)))
        return True

    @property
    def data(self) -> bytes:
        """
        :returns: this scanline's raw data
        """
        if self.__data_dirty:
            workingsize = ceil(self.channelcount * self.bitdepth / 8)
            filtered = bytearray()

            if self.__filtertype == 0:
                filtered = self.__unfiltered
            else:
                for index, byte in enumerate(self.unfiltered):

                    # b or c will be set to 0 if not required by the filtertype
                    # This is done to avoid unneded computation,
                    # as they require the previous scanline to be also decoded
                    if index < workingsize:
                        a = 0
                    else:
                        a = self.unfiltered[index - workingsize]
                    if self._previous is None or self.filtertype not in (2, 3, 4):
                        b = 0
                    else:
                        b = self._previous.unfiltered[index]
                    if index < workingsize or self._previous is None or self.filtertype != 4:
                        c = 0
                    else:
                        c = self._previous.unfiltered[index - workingsize]

                    if self.filtertype == 1:
                        filtered.append((byte - a) % 256)
                    elif self.filtertype == 2:
                        filtered.append((byte - b) % 256)
                    elif self.filtertype == 3:
                        filtered.append((byte - floor((a + b) / 2)) % 256)
                    elif self.filtertype == 4:
                        filtered.append((byte - paeth(a, b, c)) % 256)
                    else:
                        raise UnsupportedFilterTypeException(code=self.filtertype)
            self.__data = pack('B', self.filtertype) + bytes(filtered)
        return self.__data

    @data.setter
    def data(self, val: _Data):
        """
        :param val: set the raw data for this scanline.
        """
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        self.__data = as_data(val)
        self.__filtertype_dirty = True
        self.__pixels_dirty = True


_supported_chunks = chunks.implementations  # Just making a local reference for easier access


_builtin_open = open


def open(filename, ignore_signature=False):
    """
    :returns: a Png object, reading from the given file name. Http and Https links are supported as well.
    """
    data = None
    if filename.startswith('http://') or filename.startswith('https://'):
        data = requests.get(filename).content
    else:
        with __builtins__['open'](filename, 'rb') as f:
            data = f.read()
    if data is not None:
        return Png(data, ignore_signature=ignore_signature)
    else:
        raise Exception("Unknown error...")


def read_png_signature(data):
    return data[0:8] == _PNG_SIGNATURE


def create_empty_chunk(t, realy_empty=False):
    """
    :returns: an empty chunk with the necessary content to make it valid depending on , with the type given.
    If really_empty is not set, the chunk will be filled with default data
    to make it valid, if the type is supported
    """
    c = PngChunk(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    if not type(t) is type(''):
        raise TypeError("The type of a chunk should be a string.")
    c.type = t  # The crc is automatically updated when doing this.
    if not realy_empty:
        c._set_empty_data()
    return c


def create_empty_png():
    """
    Creates an empty Png object, with an IHDR chunk, an empty IDAT chunk, and an IEND chunk.
    """
    ihdr = create_empty_chunk('IHDR')
    iend = create_empty_chunk('IEND')
    idat = create_empty_chunk('IDAT')
    data = _PNG_SIGNATURE + ihdr.bytes + idat.bytes + iend.bytes
    return Png(data)
