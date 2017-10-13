from struct import unpack, pack
from zlib import crc32 as crc, decompressobj as decomp
from . import chunks
from . import pngexceptions

_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

class Png:
    """Represents a PNG file to use for forensics analysis."""

    def __init__(self,  filebytes, ignore_signature=False):
        """The argument should be the bytes of a PNG file.
        The PNG.open(str) methode should be used to read a local file.
        The bytes are read from the constructor, so it can take some time for large images."""
        if not ignore_signature and not read_png_signature(filebytes):
            raise pngexceptions.InvalidPngStructureException("missing PNG signature")
        self.__filebytes = filebytes
        self.__chunks = None
        self.__file_end = None

    @property
    def chunks(self):
        if self.__chunks == None:
            self.__read_chunks()
        return self.__chunks

    @property
    def file_end(self): #TODO
        if self.__file_end is None:
            self.__read_chunks()
        return self.__file_end

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
            chunks.append(chunk)
            start += length + 12
            data = data[length + 12:]
            if chunk.type == 'IEND':
                self.__file_end = data
                break
        self.__chunks = chunks

    @property
    def bytes(self):
        global _PNG_SIGNATURE
        b = _PNG_SIGNATURE
        for chunk in self.chunks:
            b += chunk.bytes
        b += self.file_end
        return b

    def save(self, fname):
        with opn(fname, 'bw') as f: #This is not a type, open() is being ovewriten
            f.write(self.bytes)

    def get_original(self):
        """Returns an original version of the object from when it was created."""
        return PNG(self.__bytes)

    def copy(self):
        """Returns a copy of the object."""
        return PNG(self.bytes)

    def reset(self):
        """Resets any change done to the image and goes back to when it was created."""
        self.__read_chunks()

    def add_chunk(self, chunk, index=None):
        """Adds the chunk to the file, at the given index.
        If the index is ommited, the chunk is added just before the IEND last chunk."""
        if index == None:
            index = len(self.chunks - 2)
        self.__chunks.insert(index, chunk)

class PngChunk:

    def __init__(self, chunkbytes, edit=True, auto_update=True):
        """Creates a PngChunk from the bytes given in the chunkbytes parameter.
        It should include the chunk's size, type and crc checksum.

        If edit is set to False, doing anything that would change the bytes of the chunk throws an exception.
        If auto_update is True, the crc of the chunk will be updated when the data is changed.

        The structure of a png chunk should be as follow:
            [length (4 bytes, big-endian) | type (4 bytes, ascii) | data (length bytes) | crc (4 bytes)]

        The crc checksum is calculated with the chunk type and data, but does not include the length header.
        """

        if not type(chunkbytes) == type(b''):
            raise TypeError("A PNG chunk should be created from bytes, not from {}".format(type(data).__name__  ))

        self.__bytes = chunkbytes
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
        return self.__bytes

    @property
    def crc(self):
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

    def get_payload(self):
        return self.__get_implementation().get_all(self)

    def _set_empty_data(self):
        """Replaces the current data with a garbage, but valid one provided by the implementation"""
        self.data = self.__get_implementation().empty_data

_supported_chunks = chunks.implementations #Just making a local reference for easier access

__opn = open
def open(filename, ignore_signature=False):
    """Returns a PNG object from the given file name."""
    with __opn(filename, 'rb') as f:
        return PNG(f.read(), ignore_signature=ignore_signature)

def read_png_signature(data):
    return data[0:8] == _PNG_SIGNATURE

def get_empty_chunk(t, realy_empty=False):
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
