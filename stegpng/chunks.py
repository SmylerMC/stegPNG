from struct import pack, unpack
from .pngexceptions import InvalidChunkStructureException, UnsupportedCompressionMethodException
import zlib

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
            empty_data=b'\x00\x00\x00\x01\x00\x00\x00\x01\x01\x00\x00\x00\x00',
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
            self.set(chunk, 'width', value[0])
            self.set(chunk, 'height', value[1])
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
        return self.get(chunk, 'bit_depth') in self.get(chunk, 'colortype_depth')

class ChunkIDAT(ChunkImplementation):

    """Not ready at all""" #TODO
    def __init__(self):
        super(ChunkIDAT, self).__init__('IDAT')

    def get_all(self, chunk):
        return {'data': 'lots of data'}

    def get(self, chunk, field):
        pass

class ChunktEXt(ChunkImplementation):

    def __init__(self):
        super(ChunktEXt, self).__init__('tEXt',
            empty_data=b'A\x00',
            minlength=2,
        )

    def get_all(self, chunk):
        return {'text': self.get(chunk, 'text'),
                'keyword': self.get(chunk, 'keyword')}

    def get(self, chunk, field):
        if field not in ('text', 'keyword', 'content'):
            raise KeyError()
        if chunk.data.count(0x00) != 1 or chunk.data.find(0x00) > 78:
            raise InvalidChunkStructureException("invalid number of null byte separator in tEXt chunk")
        sep = chunk.data.find(0x00)
        keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0].decode('ascii')
        text = unpack('{}s'.format(len(chunk.data) - sep - 1), chunk.data[sep + 1: len(chunk.data)])[0].decode('latin1')
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
        return chunk.data.count(0x00) == 1 and chunk.data.find(0x00) <= 78

class ChunksRGB(ChunkImplementation):

    """""" #TODO Needs to be tested

    def __init__(self):
        super(ChunksRGB, self).__init__('sRGB',
            empty_data=b'\x00',
            length=1,
        )
        self.rederingtypes = (
            "Perceptual",
            "Relative colorimetric",
            "Saturation",
            "Absolute colorimetric"
        )

    def get_all(self, chunk):
        return {
                'rendering_code': self.get(chunk, 'rendering_code'),
                'rendering_name': self.get(chunk, 'rendering_name'),
            }

    def get(self, chunk, field):
        if field == 'rendering_code':
            return chunk.data[0]
        elif field == 'rendering_name':
            try:
                return self.rederingtypes[self.get(chunk, 'rendering_code')]
            except KeyError:
                raise InvalidChunkStructureException('invalid sRGB value')
        else:
            raise KeyError()

    def set(self, chunk, field, value):
        if field == 'rendering_code':
            chunk.data[0] = b'' + value + chunk.data[1:]
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk):
        return self.get(chunk, 'rendering_code') in range(4)

class ChunktIME(ChunkImplementation):

    #TODO Test all of this

    def __init__(self):
        super(ChunktIME, self).__init__(
            'tIME',
            length=7,
            empty_data=b'\x00\x00\x01\x01\x00\x00\x00',
        )

    def get_all(self, chunk):
        return {
            'year': self.get(chunk, 'year'),
            'month': self.get(chunk, 'month'),
            'day': self.get(chunk, 'day'),
            'hour': self.get(chunk, 'hour'),
            'minute': self.get(chunk, 'minute'),
            'second': self.get(chunk, 'second'),
        }

    def get(self, chunk, field):
        if field == 'year':
            return unpack('>h', chunk.data[0:2])[0]
        elif field == 'month':
            return chunk.data[2]
        elif field == 'day':
            return chunk.data[3]
        elif field == 'hour':
            return chunk.data[4]
        elif field == 'minute':
            return chunk.data[5]
        elif field == 'second':
            return chunk.data[6]
        else:
            raise KeyError()

    def set(self, chunk, field, value):
        if field == 'year':
            chunk.data = pack('>h', value) + chunk.data[2:]
        elif field == 'month':
            chunk.data = chunk.data[:2] + pack('B', value) + chunks.data[3:]
        elif field == 'day':
            chunk.data = chunk.data[:3] + pack('B', value) + chunks.data[4:]
        elif field == 'hour':
            chunk.data = chunk.data[:4] + pack('B', value) + chunks.data[5:]
        elif field == 'minute':
            chunk.data = chunk.data[:5] + pack('B', value) + chunks.data[6:]
        elif field == 'second':
            chunk.data = chunk.data[:6] + pack('B', value)
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk):
        year = self.get(chunk, 'year')
        month = self.get(chunk, 'month')
        day = self.get(chunk, 'day')
        hour = self.get(chunk, 'hour')
        minute = self.get(chunk, 'minute')
        second = self.get(chunk, 'second')
        month_ok = month >= 1 and month <= 12
        if month in (1, 3, 5, 7, 8, 10, 12):
            max_day = 31
        elif month == 2:
            if year % 4 == 0 and (year % 400 == 0 or year % 100 != 0):
                max_day = 29
            else:
                max_day = 28
        else:
            max_day = 30
        day_ok = day >= 1 and day <= max_day
        hour_ok = hour >= 0 and hour <= 23
        minute_ok = minute >= 0 and minute <= 59
        second_ok = second >= 0 and second <= 60
        return day_ok and month_ok and hour_ok and minute_ok and second_ok


class ChunkgAMA(ChunkImplementation):

    """""" #TODO Needs to be tested

    def __init__(self):
        super(ChunkgAMA, self).__init__('gAMA',
            empty_data=b'\x00\x00\x00\x00',
            length=4,
        )

    def get_all(self, chunk):
        return {
                'gama': self.get(chunk, 'gama'),
            }

    def get(self, chunk, field):
        if field == 'gama':
            return unpack('>I', chunk.data[0:4])[0] / 100000
        else:
            raise KeyError()

    def set(self, chunk, field, value):
        if field == 'gama':
            chunk.data = pack('>I', int(value * 100000))
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk):
        return True


class ChunkzTXt(ChunkImplementation):  #TODO Not fully tested

    def __init__(self):
        super(ChunkzTXt, self).__init__('zTXt',
            empty_data=b'A\x00\x00',
            minlength=3,
        )

    def get_all(self, chunk):
        return {'text': self.get(chunk, 'text'),
                'keyword': self.get(chunk, 'keyword'),
                'compression': self.get(chunk, 'compression')}

    def get(self, chunk, field):
        if field not in ('text', 'keyword', 'content', 'compression'):
            raise KeyError()
        if chunk.data.count(0x00) < 1:
            raise InvalidChunkStructureException("invalid number of null byte separator in zTXt chunk")
        sep = chunk.data.find(0x00)
        keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0].decode('ascii')
        compression_code = chunk.data[sep + 1]
        if compression_code == 0:
            text = zlib.decompress(chunk.data[sep + 2:])
            text = unpack('{}s'.format(len(text)), text)[0].decode('latin1')
        else:
            raise UnsupportedCompressionMethodException()
        if field == 'text':
            return text
        elif field == 'keyword':
            return keyword
        elif field == 'compression':
            return compression_code
        elif field == 'content':
            return keyword, text

    def set(self, chunk, field, value): #TODO
        if field not in ('text', 'keyword'):
            raise KeyError()
        if chunk.data.count(0x00) < 1:
            raise InvalidChunkStructureException("invalid number of null byte separator in zTXt chunk")
        sep = chunk.data.find(0x00)
        compression_code = chunk.data[sep + 1]
        if field == 'text':
            if compression_code == 0:
                text = value.encode('ascii')
                text = zlib.compress(text)
                chunk.data = chunk.data[:sep + 2] + text
            else:
                raise UnsupportedCompressionMethodException()
        elif field == 'keyword':
            chunk.data = value.encode('ascii') + chunk.data[sep:]

    def _is_payload_valid(self, chunk):
        return chunk.data.count(0x00) >= 1 and chunk.data.find(0x00) <= 78


implementations = {
    'IHDR': ChunkIHDR(),
    'IDAT': ChunkIDAT(),
    'IEND': ChunkImplementation('IEND', length=0),
    'tEXt': ChunktEXt(),
    'sRGB': ChunksRGB(),
    'tIME': ChunktIME(),
    'gAMA': ChunkgAMA(),
    'zTXt': ChunkzTXt(),
    #https://www.hackthis.co.uk/forum/programming-technology/27373-png-idot-chunk
}

#TODO Update to new system... ============================================================================
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
