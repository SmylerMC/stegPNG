from struct import unpack, pack
from zlib import crc32 as crc
from . import chunks
from . import pngexceptions #TODO remove
from .pngexceptions import *
from .utils import compress, decompress, paeth
from math import ceil, floor

_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

class Png:
    """Represents a PNG file to use for forensics analysis."""

    def __init__(self,  filebytes, ignore_signature=False, edit=True):
        """The argument should be the bytes of a PNG file.
        The PNG.open(str) methode should be used to read a local file.
        The bytes are read from the constructor, so it can take some time for large images."""
        if type(filebytes) not in (bytes, bytearray):
            raise TypeError()
        if edit not in (True, False):
            raise TypeError('Edit should be a boolean')
        if not ignore_signature and not read_png_signature(filebytes):
            raise pngexceptions.InvalidPngStructureException("missing PNG signature")
        self.__filebytes = filebytes
        self.__chunks = None
        self.__file_end = None
        self.__scanlines = None
        self.edit = edit

        #True when the bytes changed but the scanlines have not been updated yet
        self.__scanlines_dirty = True
        #True when the bytes changed but the pixels have not been updated yet
        self.__bytes_dirty = True

    @property
    def chunks(self):
        if self.__chunks == None:
            self.__read_chunks()
        return self.__chunks

    def __read_chunks(self):
        #TODO Handle malformed files with a fancy exception
        chunks = []
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
                    raise pngexceptions.InvalidPngStructureException("Failed to read chunk type at index {}".format(start))
                chunks.append(chunk)
                start += length + 12
                data = data[length + 12:]
                if chunk_type == 'IEND': #TODO Make this returns even if there is only garbage data after a non-iend chunk
                    break
        self.__file_end = data
        self.__chunks = chunks

    @property
    def bytes(self):
        global _PNG_SIGNATURE
        b = _PNG_SIGNATURE
        for chunk in self.chunks:
            b += chunk.bytes
        b += self.extra_data
        return b

    def save(self, fname):
        with __builtins__['open'](fname, 'bw') as f:
            f.write(self.bytes)

    def get_original(self):
        """Returns an original version of the object from when it was created."""
        return Png(self.__bytes)

    def copy(self):
        """Returns a copy of the object."""
        return Png(self.bytes)

    def reset(self):
        """Resets any change done to the image and goes back to when it was created."""
        self.__read_chunks()

    def add_chunk(self, chunk, index=None):
        """Adds the chunk to the file, at the given index.
        If the index is ommited, the chunk is added just before the IEND last chunk."""
        if index == None: #TODO There are other special cases, but the chunks are not supported yet
            if chunk.type == 'IHDR':
                index = 0
            elif chunk.type == 'IEND':
                index = len(self.chunks)
            else:
                index = len(self.chunks) - 1
        self.__chunks.insert(index, chunk)

    def remove_chunk(self, chunk):
        """Removes the given chunk from the image"""
        self.chunks.remove(chunk)

    def index_of_chunk(self, chunk):
        """Returns the index of the given chunk in the image"""
        return self.chunks.index(chunk)

    def address_of_chunk(self, chunk):
        """Returns the byte address of the given chunk.
        Quite resource intensif as it calways need to count each previous chunk."""
        add = len(_PNG_SIGNATURE)
        if not chunk in self.chunks:
            raise ValueError("chunk not in image")
        for c in self.chunks:
            if not c is chunk:
                add += len(c.bytes)
            else:
                break
        return add

    def get_chunks_by_type(self, ty):
        """Returns all the chunks of a given type"""
        return tuple(filter(lambda c:c.type == ty, self.chunks))

    @property
    def extra_data(self):
        """Returns any remainning data after the IEND chunk.
        If there is something, someone is probably trying to hide it"""
        if self.__file_end is None:
            self.__read_chunks()
        return self.__file_end

    @extra_data.setter
    def extra_data(self, value):
        if type(value) != type(b''):
            raise TypeError()
        if self.__file_end is None:
            self.__read_chunks()
        self.__file_end = value

    @property
    def width(self):
        if len(self.chunks) < 1 or self.chunks[0].type != 'IHDR':
            raise pngexceptions.InvalidPngStructureException('missing IHDR chunk at the beginning of the file')
        return self.chunks[0]['width']

    @width.setter
    def width(self, value):
        if len(self.chunks) < 1 or self.chunks[0].type != 'IHDR':
            raise pngexceptions.InvalidPngStructureException('missing IHDR chunk at the beginning of the file')
        self.chunks[0]['width'] = value

    @property
    def height(self):
        if len(self.chunks) < 1 or self.chunks[0].type != 'IHDR':
            raise pngexceptions.InvalidPngStructureException('missing IHDR chunk at the beginning of the file')
        return self.chunks[0]['height']

    @height.setter
    def height(self, value):
        if len(self.chunks) < 1 or self.chunks[0].type != 'IHDR':
            raise pngexceptions.InvalidPngStructureException('missing IHDR chunk at the beginning of the file')
        self.chunks[0]['height'] = value

    @property
    def size(self):
        if len(self.chunks) < 1 or self.chunks[0].type != 'IHDR':
            raise pngexceptions.InvalidPngStructureException('missing IHDR chunk at the beginning of the file')
        return self.chunks[0]['size']

    @size.setter
    def size(self, value):
        if len(self.chunks) < 1 or self.chunks[0].type != 'IHDR':
            raise pngexceptions.InvalidPngStructureException('missing IHDR chunk at the beginning of the file')
        self.chunks[0]['size'] = value
    
    @property
    def datastream(self):
        #TODO Setter
        #TODO have a cache for that
        """Returns the compressed data stream inside the IDAT chunks."""
        stream = bytearray()
        for chunk in self.get_chunks_by_type('IDAT'):
            stream.extend(chunk.data)
        return stream

    @property
    def imagedata(self):
        #TODO setter
        #TODO have a cache for that
        """Returns the raw decompressed data from the IDAT chunks"""
        return decompress(self.datastream) 

    @property
    def scanlines(self):
        #TODO setter
        #TODO Interlace support
        """Returns the scanlines of the image, as a tuple of scanlines.
        The scanline are sorted from top to bottom order."""
        ihdr = self.get_chunks_by_type('IHDR')
        if len(ihdr) != 1:
            raise InvalidPngStructureException('There should be one and only one IHDR chunk!')
        ihdr = ihdr[0]
        if ihdr['interlace'] != 0:
            raise Exception('Invalid interlace method: {}'.format(ihdr['interlace']))
        if self.__scanlines_dirty:
            depth = ihdr['bit_depth']
            if not depth in ihdr['colortype_depth']:
                raise pngexception.MalformedChunkException(
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
            linesize = width * ceil(depth/8 * channel_count) + 1

            # The first scanline is the only one which can't have reference to its upper pixels,
            # so we compute it first
            lines = [ ScanLine( channel_count,
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
                        lines[i-1],
                        data=data[i*linesize:(i+1)*linesize]
                    )
                lines.append(s)
                i += 1
            self.__scanlines = lines
            self.__scanlines_dirty = False
        return self.__scanlines


    def getpixel(self, position):
        if type(position) not in (list, tuple):
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

        if len(self.chunks) == 0:
            raise InvalidPngStructureException('This png has no chunks')
        ihdr = self.chunks[0]
        if ihdr.type != 'IHDR':
            raise InvalidPngStructureException('The first chunk of a png file should be an IHDR chunk')
        scanline = self.scanlines[y]
        p = scanline.pixels[x]

        # Indexed color
        if ihdr['colortype_code'] == 3:
            plte = self.get_chunks_by_type('PLTE')
            if len(plte) == 0:
                raise InvalidPngStructureException('Missing a PLTE chunk')
            plte = plte[0] #TODO Optimize this
            p = p[0]
            p = plte[p]

        if ihdr['channel_count'] == 1 and ihdr['colortype_code'] != 3:
            p = p[0]

        return p


class PngChunk:

    def __init__(self, chunkbytes, edit=True, auto_update=True):
        """Creates a PngChunk from the bytes given in the chunkbytes parameter.
        It should include the chunk's size, type and crc checksum.
        If to much data is given, it ignores everything after the encoded length

        If edit is set to False, doing anything that would change the bytes of the chunk throws an exception.
        If auto_update is True, the crc of the chunk will be updated when the data is changed.

        The structure of a png chunk should be as follow:
            [length (4 bytes, big-endian) | type (4 bytes, ascii) | data (length bytes) | crc (4 bytes)]

        The crc checksum is calculated with the chunk type and data, but does not include the length header.
        """

        if not type(chunkbytes) in (type(b''), bytearray):
            raise TypeError("A PNG chunk should be created from bytes, not from {}".format(type(chunkbytes).__name__  ))

        self.__bytes = chunkbytes
        self.__bytes = self.__bytes[:self.length + 12]
        self.edit = edit
        self.auto_update = auto_update
        self.__dirty = False

    def __changing(self, update_crc=True):
        """Should be called when ever a change that should change
        the bytes of the chunk occures."""
        if not self.edit:
            raise Exception("Trying to edit read-only png!")
        else:
            if update_crc:
                self.update_crc()
            self.__dirty = True

    @property
    def bytes(self):
        """Returns the raw chunk as bytes"""
        return self.__bytes

    @property
    def crc(self):
        """Returns the CRC checksum included in the chunk"""
        return unpack('!I', self.__bytes[-4:])[0]

    @crc.setter
    def crc(self, value):
        if type(value) != type(1):
            raise TypeError("The crc should be an integer.")
        self.__changing(update_crc=False)
        self.__bytes= self.bytes[:-4] + pack('!I', value)

    @property
    def type(self):
        return self.__bytes[4:8].decode('ascii')

    @type.setter
    def type(self, value):
        self.__changing(update_crc=False)
        if type(value) != type(''):
            raise TypeError("A chunk's type should be a string.")
        if len(value) != 4:
            raise ValueError("A chunk's type have to be 4 characters long.")
        self.__bytes = self.__bytes[0:4] + value.encode('ascii') + self.__bytes[8:]
        self.__changing(self.auto_update)

    def __len__(self):
        return self.length

    @property
    def length(self):
        return unpack('>I', self.__bytes[0:4])[0]

    @property
    def data(self):
        return self.bytes[8:-4]

    @data.setter
    def data(self, data):
        if not type(data) == type(b''):
            raise TypeError("A PNG chunk can only carry data as bytes, not as {}".format(type(data).__name__  ))
        self.__changing(update_crc=False)
        self.__bytes = self.__bytes[0:8] + data + self.__bytes[-4:]
        self.__update_length()
        self.__changing(self.auto_update)

    def __update_length(self):
        length = len(self.__bytes) - 12
        if length < 0:
            raise Exception("Trying to update the length of a chunk, but it's smaller than 0!")
        self.__bytes = pack('>I', length) + self.__bytes[4:]

    def check_crc(self):
        return self.compute_crc() == self.crc

    def compute_crc(self):
        comp_crc = crc(self.__bytes[4:-4])
        return comp_crc

    def update_crc(self):
        self.crc = self.compute_crc()

    def iscritical(self):
        return (self.__bytes[4] & 0b000010000) >> 4 == 0

    def isancillary(self):
        return (self.__bytes[4] & 0b000010000) >> 4 == 1

    def is_supported(self):
        global _supported_chunks
        return self.type in _supported_chunks

    def is_valid(self):
        return self.__get_implementation().is_valid(self)

    def __get_implementation(self):
        if not self.is_supported():
            raise pngexceptions.UnsupportedChunkException()
        global _supported_chunks
        return _supported_chunks[self.type]

    def __getitem__(self, index):
        return self.__get_implementation().get(self, index)

    def __setitem__(self, index, value):
        self.__get_implementation().set(self, index, value)

    def __repr__(self):
        norm = super(PngChunk, self).__repr__()
        norm = norm.rsplit(' ')
        norm.insert(1, '[' + self.type +']')
        return ' '.join(norm)

    def get_payload(self):
        return self.__get_implementation().get_all(self)

    def _set_empty_data(self):
        """Replaces the current data with some valid garbage, provided by the implementation"""
        self.data = self.__get_implementation().empty_data


class ScanLine:
    """Represents a scanline in a png datastream.
    This class is used internaly for decoding,
    but exists because scanlines could be used for steganography because of the filter type"""

    def __init__(self, channelcount, bitdepth, previous, data=None, content=None, edit=True):

        #TODO Docstring

        # Types and value checks
        if type(previous) != ScanLine and previous != None:
            raise TypeError(
                'The previous argument should be a ScanLine or None, not {}'.format(
                    type(previous))
                )
        if (data, content) == (None, None) :
            raise ValueError(
                "data and content can't be both None, please specify at least one")
        elif data != None and content != None:
            raise ValueError(
                'Cannot have a value for both pixels and data, please specify only one')
        if edit not in (True, False):
            raise TypeError('argument readonly must be a boolean value')
        if data != None and type(data) not in (bytearray, bytes):
            raise TypeError('Scanline data must be byte or bytearray')
        elif content != None and type(content) not in (list, tuple):
            raise TypeError('content must be a tuple or a list')
        if content != None:
            if len(content) != 2 or type(content[0]) != int or type(content[1]) not in (tuple, list):
                raise ValueError(
                    "content should in the following format: (int filter, list/tuple pixels)")
            try:
                self.__checkpixels_args(content[1])
            except Exception as e:
                raise e

        # Variables assignments
        if content != None:
            self.__filtertype, self.__pixels = content
            self.__pixels_dirty = False
            self.__filtertype_dirty = False
            self.__data_dirty = True
        elif data != None:
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
    def channelcount(self):
        return self.__channelcount

    @channelcount.setter
    def channelcount(self, value):
        #TODO check valid values
        self.__channelcount = value
    
    @property
    def bitdepth(self):
        return self.__bitdepth

    @bitdepth.setter
    def bitdepth(self, value):
        #TODO check valid values
        self.__bitdepth = value
    
    @property
    def filtertype(self):
        if self.__filtertype_dirty:
            self.__filtertype = self.data[0]
            self.filertype_dirty = False
        return self.__filtertype

    @filtertype.setter
    def filtertype(self, val):
        #TODO test this for errors and maybe use bytearrays
        #TODO check valid values and allow user to force using an invalid one
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        if type(val) != int:
            raise TypeError("Filter type should be an integer")
        self.__filtertype = val
        self.__data_dirty = True

    @property
    def unfiltered(self):
        if self.__unfiltered_dirty:
            if not self.__data_dirty:
                workingsize = ceil(self.channelcount * self.bitdepth / 8)
                unfiltered = bytearray()
        
                
                if self.filtertype == 0:
                    unfiltered = self.data[1:]
                else:
                    for indice, byte in enumerate(self.data[1:]):


                        # b or c will be set to 0 if not required by the filtertype
                        # This is done to avoid uneeded computation,
                        # as they require the previous scanline to be also decoded
                        if indice < workingsize:
                            a = 0
                        else:
                            a = unfiltered[indice-workingsize]
                        if self._previous == None or self.filtertype not in (2, 3, 4):
                            b = 0
                        else:
                            b = self._previous.unfiltered[indice]
                        if indice < workingsize or self._previous == None or self.filtertype != 4:
                            c = 0
                        else:
                            c = self._previous.unfiltered[indice - workingsize]

                        if self.filtertype == 1:
                            unfiltered.append((byte + a) % 256)
                        elif self.filtertype == 2:
                            unfiltered.append((byte + b) % 256)
                        elif self.filtertype == 3:
                            unfiltered.append( (byte + floor((a+b) / 2)) % 256 )
                        elif self.filtertype == 4:
                            unfiltered.append( (byte + paeth(a, b, c)) % 256)
                        else:
                            raise InvalidPNGException('Invalid filter type')
                self.__unfiltered = bytes(unfiltered)
            elif not self.__pixels_dirty:
                unfiltered = bytearray()

                if self.bitdepth == 8:
                    for pixel in self.pixels:
                        for value in pixel:
                            unfiltered.append(value)
                    self.__unfiltered = bytes(unfiltered)
                else:
                    #TODO
                    raise NotImplementedError('Only a bit depth of 8 is supported yet')
            else:
                raise Exception('Unnable to unfilter scanline. This is a bug, please report it')
            self.__unfiltered_dirty = False
        return self.__unfiltered


    @unfiltered.setter
    def unfilterred(self, value):
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        if type(value) not in (bytes, bytearray):
            raise TypeError("An unfiltered scanline should be bytes or a bytearray")
        if len(value) != len(self.unfiltered):
            raise ValueError(
                "Trying to set the unfiltered scanline with a length of the {} bytes, but the current one has a length of {}".format(len(value), len(unfiltered))
            )
        self.__unfiltered = value
        self.__data_dirty = True
        self.__pixels_dirty = True


    @property
    def pixels(self):
        if self.__pixels_dirty:
            pixels = []
            pixel = []
            indice = 0
            if self.bitdepth == 8:
                for byte in self.unfiltered:
                    pixel.append(byte)
                    if len(pixel) == self.channelcount:
                        pixels.append(tuple(pixel))
                        pixel = []
            else:
                raise NotImplementedError()
            #TODO ===================================================================
            self.__pixels = tuple(pixels)
            self.__pixels_dirty = False
        return self.__pixels

    @pixels.setter
    def pixels(self, value):
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        try:
            self.__checkpixels_arg(pixels)
        except Exception as e:
            raise e
        self.__pixels = pixels
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
    def data(self):
        if self.__data_dirty:
            workingsize = ceil(self.channelcount * self.bitdepth / 8)
            filtered = bytearray()

            if self.filtertype == 0:
                filtered = self.unfiltered
            else:
                for indice, byte in enumerate(self.unfiltered):

                    # b or c will be set to 0 if not required by the filtertype
                    # This is done to avoid uneeded computation,
                    # as they require the previous scanline to be also decoded
                    if indice < workingsize:
                        a = 0
                    else:
                        a = self.unfiltered[indice-workingsize]
                    if self._previous == None or self.filtertype not in (2, 3, 4):
                        b = 0
                    else:
                        b = self._previous.unfiltered[indice]
                    if indice < workingsize or self._previous == None or self.filtertype != 4:
                        c = 0
                    else:
                        c = self._previous.unfiltered[indice - workingsize]

                    if self.filtertype == 1:
                        unfiltered.append((byte - a) % 256)
                    elif self.filtertype == 2:
                        unfiltered.append((byte - b) % 256)
                    elif self.filtertype == 3:
                        unfiltered.append( (byte - floor((a+b) / 2)) % 256 )
                    elif self.filtertype == 4:
                        unfiltered.append( (byte - paeth(a, b, c)) % 256)
                    else:
                        raise InvalidPNGException('Invalid filter type')
            self.__data = pack('B', self.filtertype) + bytes(filtered)
        return self.__data

    @data.setter
    def data(self, val):
        if not self.edit:
            raise Exception("Trying to edit readonly scanline!")
        if type(val) not in (bytes, bytearray):
            raise TypeError("Data should be bytes or bytearray")
        self.__data = data
        self.__filtertype_dirty = True
        self.__pixels_dirty = True



_supported_chunks = chunks.implementations #Just making a local reference for easier access

def open(filename, ignore_signature=False):
    """Returns a Png object from the given file name."""
    data = None
    if filename.startswith('http://') or filename.startswith('https://'):
        from requests import Session
        data = requests.get(filename).content
    else:
        with __builtins__['open'](filename, 'rb') as f:
            data=f.read()
    if data != None:
        return Png(data, ignore_signature=ignore_signature)
    else:
        raise Exception("Unknown error...")

def read_png_signature(data):
    return data[0:8] == _PNG_SIGNATURE

def create_empty_chunk(t, realy_empty=False):
    """Creates and return an empty chunk of length of 0, with the type given.
    If realy_empty is not set, the chunk will be filled with default data
    to make it valid, if the type is suported"""
    c = PngChunk(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    if not type(t) is type(''):
        raise TypeError("The type of a chunk should be a string.")
    c.type = t #The crc is automaticaly updated when doing this.
    if not realy_empty:
        c._set_empty_data()
    return c

def create_empty_png():
    ihdr = create_empty_chunk('IHDR')
    iend = create_empty_chunk('IEND')
    idat = create_empty_chunk('IDAT')
    data = _PNG_SIGNATURE + ihdr.bytes + idat.bytes + iend.bytes
    return Png(data)
