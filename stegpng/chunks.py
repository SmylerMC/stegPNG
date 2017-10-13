from struct import pack, unpack
from .pngexceptions import InvalidChunkStructureException

class ChunkImplementation:

    def __init__(self, chtype, empty_data=b'', length=None, maxlength=1<<31-1, minlength=0):
        """Arguments:
            chtype: The chunk type (IHDR, IDAT, IEND etc...
            empty_data: the data an empty chunk of this type should have, to makeit valid
            length: The fixed length of the chunk. Overrides minlength and maxlength if set.
            minlength: The minimum length of the chunk.
            maxlength: The minimum length of the chunk."""
        self.type = chtype
        self.empty_data = empty_data
        if length != None:
            self.maxlength = length
            self.minlength = length
        else:
            self.maxlength = maxlength
            self.minlength = minlength

    def _is_length_valid(self, chunk):
        """Returns True if the chunk's length is valid for that chunk.
        This not to be overriden in most case, the length, maxlength and minlength arguments
        of __init__ should be used."""
        return chunk.type == self.type and len(chunk) <= self.maxlength and len(chunk) >= self.minlength

    def is_valid(self, chunk):
        """Returns True if the chunk is valid.
        It ignores the crc signature, use PngChunk#check_crc() for that.
        This method should normaly not be overriden as it checks the chunk's header
        and calls _is_payload_valid() to check the payload. This is what is to be overiden."""
        return self._is_length_valid(chunk) and self._is_payload_valid(chunk)

    def _is_payload_valid(self, chunk):
        """This is to be overriden for most chunks."""
        return chunk.data == b''

    def get_all(self, chunk):
        """This is to be overriden for most chunks."""
        return {}

    def get(self, chunk, field):
        """This is to be overriden for most chunks."""
        raise KeyError()

    def set(self, chunk, field, value):
        """This is to be overriden for most chunks."""
        raise KeyError()

class ChunkIHDR(ChunkImplementation):

    def __init__(self):
        super(ChunkIHDR, self).__init__(
            'IHDR',
            length=13,
            empty_data=b'\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00',
        )
        self.__color_types = (
        ("Greyscale", (1,2, 4, 8, 16)),
        ("Wrong!!", None),
        ("Truecolour", (8, 16)),
        ("Indexed-colour", (1, 2, 4, 8)),
        ("Greyscale with alpha", (8, 16)),
        ("Wrong!!", None),
        ("Truecolour with alpha", (8, 16))
        )

    def get_all(self, chunk):
        return {
            'size': self.get(chunk, 'size'),
            'colortype_name': self.get(chunk, 'colortype_name'),
            'colortype_code': self.get(chunk, 'colortype_code'),
            'colortype_depth': self.get(chunk, 'colortype_depth'),
            'bit_depth': self.get(chunk, 'bit_depth'),
            'compression': self.get(chunk, 'compression'),
            'filter_method': self.get(chunk, 'filter_method'),
            'interlace': self.get(chunk, 'interlace')
        }

    def get(self, chunk, field):
        if field == 'size':
            width = unpack('>I', chunk.data[0:4])[0]
            height = unpack('>I', chunk.data[4:8])[0]
            return (width, height)
        elif field == 'width':
            return unpack('>I', chunk.data[0:4])[0]
        elif field == 'height':
            return unpack('>I', chunk.data[4:8])[0]
        elif field == 'colortype_name':
            code = self.get(chunk, 'colortype_code')
            return self.__color_types[code][0]
        elif field == 'colortype_code':
            return unpack('B', chunk.data[9:10])[0]
        elif field == 'colortype_depth':
            code = self.get(chunk, 'colortype_code')
            return self.__color_types[code][1]
        elif field == 'bit_depth':
            return unpack('B', chunk.data[8:9])[0]
        elif field == 'compression':
            return unpack('B', chunk.data[10:11])[0]
        elif field == 'filter_method':
            return unpack('B', chunk.data[11:12])[0]
        elif field == 'interlace':
            return unpack('B', chunk.data[12:13])[0]
        else:
            raise KeyError()

    def set(self, chunk, field, value):
        if field == 'size':
            width = pack('>I', value[0])
            height = pack('>I', value[1])
            chunk.data = width + height + chunk.data[8:]
        elif field == 'width':
            width = pack('>I', value)
            chunk.data = width + chunk.data[4:]
        elif field == 'height':
            height = pack('>I', value)
            chunk.data = chunk.data[:4] + height + chunk.data[8:]
        elif field == 'colortype_code':
            code = pack('B', value)
            chunk.data = chunk.data[:9] + code + chunk.data[10:]
        elif field == 'bit_depth':
            code = pack('B', value)
            chunk.data = chunk.data[:8] + code + chunk.data[9:]
        elif field == 'compression':
            code = pack('B', value)
            chunk.data = chunk.data[:10] + code + chunk.data[11:]
        elif field == 'filter_method':
            code = pack('B', value)
            chunk.data = chunk.data[:11] + code + chunk.data[12:]
        elif field == 'interlace':
            code = pack('B', value)
            chunk.data = chunk.data[:12] + code + chunk.data[13:]
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk):
        return self.get(chunk, 'bit_depth') in self.get(chunk, colortype_depth)

class ChunkIDAT(ChunkImplementation):

    """Not ready at all""" #TODO
    def __init__(self):
        super(ChunkIDAT, self).__init__('IDAT')

    def get_all(self, chunk):
        return {'data': 'lots of data'}

    def get(self, chunk, field):
        pass

class ChunktEXt(ChunkImplementation):

    """This still needs to support setting attributes""" #TODO

    def __init__(self):
        super(ChunktEXt, self).__init__('IDAT',
            empty_data=b'\x00',
        )

    def get_all(self, chunk):
        return {'text': self.get(chunk, 'text'),
                'keyword': self.get(chunk, 'keyword')}

    def get(self, chunk, field):
        if field not in ('text', 'keyword', 'content'):
            raise KeyError()
        if chunk.data.count(0x00) != 1:
            raise InvalidChunkStructureException("invalid number of null byte separator in tEXt chunk")
        sep = chunk.data.find(0x00)
        keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0].decode('ascii')
        text = unpack('{}s'.format(len(chunk.data) - sep - 1), chunk.data[sep + 1: len(chunk.data)])[0].decode('ascii')
        if field == 'text':
            return text
        elif field == 'keyword':
            return keyword
        elif field == 'content':
            return keyword, text

    def set(self, chunk, field, value):
        if field not in ('text', 'keyword'):
            raise KeyError()
        if chunk.data.count(0x00) != 1:
            raise InvalidChunkStructureException("invalid number of null byte separator in tEXt chunk")
        sep = chunk.data.find(0x00)
        value = value.encode('ascii')
        if field == 'text':
            chunk.data = chunk.data[:sep + 1] + value
        elif field == 'keyword':
            chunk.data = value + chunk.data[sep:]

    def _is_payload_valid(self, chunk):
        return chunk.data.count(0x00) == 1

implementations = {
    'IHDR': ChunkIHDR(),
    'IDAT': ChunkIDAT(),
    'IEND': ChunkImplementation('IEND', length=0),
    'tEXt': ChunktEXt()
}

#TODO Update to new system... ============================================================================
class InfosRGB:

    def __init__(self, chunk):
        try:
            super(InfosRGB, self).__init__(chunk)
            self.rederingtypes = (
                "Perceptual",
                "Relative colorimetric",
                "Saturation",
                "Absolute colorimetric"
            )
            self.rendering = chunk.data[0]
            self.isvalid = self.rendering in range(4)
            if self.isvalid:
                self.rendering = self.rederingtypes[self.rendering]
        except Exception as e:
            print(e)
            self.isvalid = False


class InfogAMA:

    def __init__(self, chunk):
        try:
            super(InfogAMA, self).__init__(chunk)
            self.gama = unpack('>I', chunk.data[0:4])[0] / 100000
            self.isvalid = True
        except Exception as e:
            print(e)
            self.isvalid = False

class InfopHYs:

    def __init__(self, chunk):
        try:
            super(InfopHYs, self).__init__(chunk)
            self.ppuX = unpack('>I', chunk.data[0:4])[0] #FIXME
            self.ppuY = unpack('>I', chunk.data[4:8])[0]
            self.unit = chunk.data[8]
            self.isvalid = True
        except Exception as e:
            print(e)
            self.isvalid = False


class InfotIME:

    def __init__(self, chunk):
        try:
            super(InfotIME, self).__init__(chunk)
            self.year = unpack('>h', chunk.data[0:2])[0]
            self.month = chunk.data[2]
            self.day = chunk.data[3]
            self.hour = chunk.data[4]
            self.minute = chunk.data[5]
            self.second = chunk.data[6]
            if 1 <= self.month <= 12 and 1 <= self.day <= 31 and 0 <= self.hour <= 23 and 0 <= self.minute <= 59 and 0 <= self.second <= 60:
                self.isvalid = True
            else:
                self.isvalid = False
        except Exception as e:
            print(e)
            self.isvalid = False

class InfotEXt:

    def __init__(self, chunk):
        super(InfotEXt, self).__init__(chunk)
        try:
            sep = -1
            for i in range(len(chunk.data)):
                if chunk.data[i] == 0x00:
                    sep = i
                    break
            if sep != -1:
                self.keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0].decode('ascii')
                self.text = unpack('{}s'.format(len(chunk.data) - sep - 1), chunk.data[sep + 1: len(chunk.data)])[0].decode('ascii')
                self.isvalid = True
            else:
                self.isvalid = False
        except Exception as e:
            print(e)
            self.isvalid = False


class InfotiTXt:

    def __init__(self, chunk):
        super(InfotiTXt, self).__init__(chunk)
        try:
            sep = -1
            for i in range(len(chunk.data)):
                if chunk.data[i] == 0x00:
                    sep = i
                    break
            if sep != -1:
                self.keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0].decode('ascii')
                self.text = unpack('{}s'.format(len(chunk.data) - sep - 1), chunk.data[sep + 1: len(chunk.data)])[0].decode('UTF-8')
                self.isvalid = True
            else:
                self.isvalid = False
        except Exception as e:
            print(e)
            self.isvalid = False

class InfoIDAT:

    def __init__(self, chunk):
        super(InfoIDAT, self).__init__(chunk)

    def decompress(self):
        return decomp().decompress(self.chunk.data)






#TODO Remove that after making sure it's not used
types ={'IHDR': 13, 'PLTE': -2, 'IDAT':-1, 'IEND': 0, 'tRNS': -2, 'cHRM': -2, 'gAMA': 4, 'iCCP': -2, 'sBIT': -2, 'sRGB': 1, 'tEXt': -1, 'zTXt': -1, 'iTXt': -1, 'bKGD': -2, 'hIST': -2, 'pHYs':9, 'sPLT': -2, 'tIME': 7}
