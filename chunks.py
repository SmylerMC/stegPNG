from struct import pack, unpack
from pngexceptions import InvalidChunkStructureException

class ChunkImplementation:

    def __init__(self, chtype, length=None, maxlength=1<<31-1, minlength=0):
        self.type = chtype
        if length != None:
            self.maxlength = length
            self.minlength = length
        else:
            self.maxlength = maxlength
            self.minlength = minlength

    def _is_length_valid(self, chunk):
        return chunk.type == self.type and len(chunk) <= self.maxlength and len(chunk) >= self.minlength

    def is_valid(self, chunk):
        return self._is_length_valid(chunk) and self._is_payload_valid(chunk)

    def _is_payload_valid(self, chunk):
        """This is to be overriden for most chunks."""
        return True

    def get_all(self, chunk):
        """This is to be overriden for most chunks."""
        return {}

    def get(self, chunk, attribute):
        """This is to be overriden for most chunks."""
        raise KeyError()

    def set(self, chunk, attribute, value):
        """This is to be overriden for most chunks."""
        raise KeyError()

class ChunkIHDR(ChunkImplementation):

    """This still needs to support setting attributes""" #TODO

    def __init__(self):
        super(ChunkIHDR, self).__init__('IHDR', length=13)
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

class ChunkIDAT(ChunkImplementation):

    def __init__(self):
        super(ChunkIDAT, self).__init__('IDAT')

    def get_all(self, chunk):
        return {'data': 'lots of data'}

    def get(self, chunk, field):
        pass

class ChunktEXt(ChunkImplementation):

    def __init__(self):
        super(ChunktEXt, self).__init__('IDAT')

    def get_all(self, chunk):
        return {'text': self.get(chunk, 'text'),
                'keyword': self.get(chunk, 'keyword')}

    def get(self, chunk, field):
        if field not in ('text', 'keyword'):
            raise KeyError()
        sep = -1
        for i in range(len(chunk.data)):
            if chunk.data[i] == 0x00:
                sep = i
                break
        if sep != -1:
            keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0].decode('ascii')
            text = unpack('{}s'.format(len(chunk.data) - sep - 1), chunk.data[sep + 1: len(chunk.data)])[0].decode('ascii')
        else:
            raise InvalidChunkStructureException()
        if field == 'text':
            return text
        elif field == 'keyword':
            return keyword
        else:
            raise KeyError()

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
