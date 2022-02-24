from struct import pack, unpack
from .pngexceptions import InvalidChunkStructureException, UnsupportedCompressionMethodException
from .utils import compress, decompress


"""
This module contains the core classes that represent the various components of a PNG file.
"""

class ChunkImplementation:

    """
    A superclass for various chunk implementations.
    All chunk implementations should extend from this class and
    override the following methods:
        get
        get_all
        set
        is_payload_valid

    The following method may also be overriten in special cases:
        _is_length_valid
    """
        

    def __init__(self, chunk_type: str, empty_data: bytes = b'',
                 length: (int, list) = None, max_length: int = 1 << 31 - 1, min_length: int = 0):

        """
        :param chunk_type:  The chunk type (IHDR, IDAT, IEND etc...)
        :param empty_data:  The minimum bytes for a chunk of this type
        :param length:      The fixed length of the chunk
        :param length:      A list of valid lengths for the chunk
                            Overrides min_length and max_length if set
        :param min_length:  The minimum length of the chunk.
        :param max_length:  The maximum length of the chunk.

        :raises             TypeError on invalid argument type:
        :raises             ValueError on invalid argument value:
        """

        if type(chunk_type) != str:
            raise TypeError("Invalid type for a chunk type. It should be str")
        if len(chunk_type) != 4:
            raise ValueError("Chunk types must be strings of length 4")
        self.type = chunk_type

        if type(empty_data) != bytes:
            raise TypeError("Invalid type for empty data. It should be bytes")
        self.empty_data = empty_data

        if length:
            if type(length) == tuple:
                for i in length:
                    if not type(i) is int:
                        raise TypeError("Possible lengths should be integers.")
                self.lengths = length
            elif type(length) is int:
                self.max_length = length
                self.min_length = length

            else:
                raise TypeError(
                    "length should be an integer or a tuple of integers"
                )
        else:
            if not (type(max_length) == type(min_length) == int):
                raise TypeError("min_length and max_length should be integers")
            if not (max_length >= min_length >= 0):
                raise ValueError("Invalid values for max_length and min_length")
            self.max_length = max_length
            self.min_length = min_length

    def _is_length_valid(self, chunk) -> bool:

        """
        Returns True if the chunk's length is valid for that chunk.
        This method is not to be overriden in most case
        the length, max_length and min_length arguments of __init__
        should be used instead
        
        :param PngChunk chunk:      The chunk to read
        
        :return:                    True if the length is valid, False otherwise
        """
        try:
            return self.min_length <= len(chunk) <= self.max_length
        except AttributeError:
            return len(chunk) in self.lengths

    def is_valid(self, chunk, ihdr=None, ihdr_data=None):
        
        """
        Returns True if the chunk is valid.
        Ignores the crc signature, use PngChunk#check_crc() for that.
        This method should normally not be overridden
        _is_payload_valid() is what is to be overridden in most cases

        :param PngChunk chunk:  The chunk to test
        :param PngChunk ihdr:   The IHDR chunk of the image
        :param bytes ihdr_data:  The decided IDHR chunk

        :return:                True if the length of the chunk is valid, False otherwise
        """

        return self._is_length_valid(chunk) and self._is_payload_valid(chunk)

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):

        """
        This is to be overridden for most chunks

        The ihdr and ihdr_data arguments may be used when addition
        information fom the ihdr chunk is required to read the chunk.
        If ihdr is supplied, ihdr_data should be ignored

        :param PngChunk chunk:  The chunk to test
        :param PngChunk ihdr:   The IHDR chunk of the image, if available
        :param dict ihdr_data:   A dictionary representing the IHDR Chunk

        :return:                True if the payload of the chunk is valid, False otherwise
        """

        return chunk.data == b''

    def get_all(self, chunk, ihdr=None, ihdr_data=None):

        """
        This is to be overriden for most chunks

        The ihdr and ihdr_data arguments may be used when addition
        information fom the ihdr chunk is required to read the chunk.
        If ihdr is supplied, ihdr_data should be ignored

        :param PngChunk chunk:  The chunk to read
        :param PngChunk ihdr:   The IHDR chunk of the image, if available
        :param dict ihdr_data:   A dictionnary representing the IHDR Chunk

        :return:                a dictionnary representing the chunk's payload
        """

        return {}

    def get(self, chunk, key, ihdr=None, ihdr_data=None):

        """
        This is to be overriden for most chunks

        The ihdr and ihdr_data arguments may be used when addition
        information fom the ihdr chunk is required to read the chunk.
        If ihdr is supplied, ihdr_data should be ignored

        :param PngChunk chunk: The chunk to read
        :param str key: The key to read
        :param PngChunk ihdr: The IHDR chunk of the image, if available
        :param dict ihdr_data: A dictionnary representing the IHDR Chunk
        
        :return: A value stored in the chunk's payload
        """

        raise KeyError()

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):

        """
        This is to be overriden for most chunks

        The ihdr and ihdr_data arguments may be used when addition
        information fom the ihdr chunk is required to read the chunk.
        If ihdr is supplied, ihdr_data should be ignored

        :param PngChunk chunk: The chunk to write
        :param str field: The field to write
        :param value: The value to write
        :param PngChunk ihdr: The IHDR chunk of the image, if available
        :param dict ihdr_data: A dictionnary representing the IHDR Chunk
        """

        raise KeyError()

class ChunkIHDR(ChunkImplementation):
    
    """The IHDR chunk is the file header. It MUST be present at the begining of the file,
    following directly after the PNG file signature. Some implementations may ignore any
    chunk preceding it, allowing for some sort of steganography. The presence of any other
    chunk at the begining of a file is therefore very likely to indicate hidden content
    and must be checked.
    The IHDR chunk contains critical information to decode the image.

    Keys:
        size: a tuple (width, height)
        width: The width of the image
        height: The height of the image
        colortype_name: A fancy name for the color type (read only)
        colortype_code: The integer encoding the colortype
        colortype_depth: A tuple with the allowed depth for this colortype
        bit_depth: The bit depth used for encoding
        compression: An integer encoding the compression method
        filter_method: An integer encoding the filtering method
        interlace: An integer encoding the interlace method
        channel_count The number of color channel in the image (read only)"""

    def __init__(self):
        super(ChunkIHDR, self).__init__(
            'IHDR',
            length=13,
            empty_data=b'\x00\x00\x00\x01\x00\x00\x00\x01\x01\x00\x00\x00\x00',
        )
        # Name, bit depths, channel count
        self.__color_types = (
            ("Greyscale", (1, 2, 4, 8, 16), 1),
            ("Wrong!!", None, None),
            ("Truecolour", (8, 16), 3),
            ("Indexed-colour", (1, 2, 4, 8), 1),
            ("Greyscale with alpha", (8, 16), 2),
            ("Wrong!!", None, None),
            ("Truecolour with alpha", (8, 16), 4)
        )
        self.__key_size = "size"
        self.__key_width = "width"
        self.__key_height = "height"
        self.__key_colortype_name = "colortype_name"
        self.__key_colortype_code = "colortype_code"
        self.__key_colortype_depth = "colortype_depth"
        self.__key_bit_depth = "bit_depth"
        self.__key_compression = "compression"
        self.__key_filter_method = "filter_method"
        self.__key_interlace = "interlace"
        self.__key_channel_count = "channel_count"

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            self.__key_size: self.get(chunk, self.__key_size),
            self.__key_colortype_name: self.get(chunk, self.__key_colortype_name),
            self.__key_colortype_code: self.get(chunk, self.__key_colortype_code),
            self.__key_colortype_depth: self.get(chunk, self.__key_colortype_depth),
            self.__key_bit_depth: self.get(chunk, self.__key_bit_depth),
            self.__key_compression: self.get(chunk, self.__key_compression),
            self.__key_filter_method: self.get(chunk, self.__key_filter_method),
            self.__key_interlace: self.get(chunk, self.__key_interlace),
            self.__key_channel_count: self.get(chunk, self.__key_channel_count)
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field == self.__key_size:
            width = unpack('>I', chunk.data[0:4])[0]
            height = unpack('>I', chunk.data[4:8])[0]
            return width, height
        elif field == self.__key_width:
            return unpack('>I', chunk.data[0:4])[0]
        elif field == self.__key_height:
            return unpack('>I', chunk.data[4:8])[0]
        elif field == self.__key_colortype_name:
            code = self.get(chunk, self.__key_colortype_code)
            return self.__color_types[code][0]
        elif field == self.__key_colortype_code:
            return unpack('B', chunk.data[9:10])[0]
        elif field == self.__key_colortype_depth:
            code = self.get(chunk, self.__key_colortype_code)
            return self.__color_types[code][1]
        elif field == self.__key_bit_depth:
            return unpack('B', chunk.data[8:9])[0]
        elif field == self.__key_compression:
            return unpack('B', chunk.data[10:11])[0]
        elif field == self.__key_filter_method:
            return unpack('B', chunk.data[11:12])[0]
        elif field == self.__key_interlace:
            return unpack('B', chunk.data[12:13])[0]
        elif field == self.__key_channel_count:
            code = self.get(chunk, self.__key_colortype_code)
            return self.__color_types[code][2]
        else:
            raise KeyError()

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field == self.__key_size:
            self.set(chunk, self.__key_width, value[0])
            self.set(chunk, self.__key_height, value[1])
        elif field == self.__key_width:
            width = pack('>I', value)
            chunk.data = width + chunk.data[4:]
        elif field == self.__key_height:
            height = pack('>I', value)
            chunk.data = chunk.data[:4] + height + chunk.data[8:]
        elif field == self.__key_colortype_code:
            code = pack('B', value)
            chunk.data = chunk.data[:9] + code + chunk.data[10:]
        elif field == self.__key_bit_depth:
            code = pack('B', value)
            chunk.data = chunk.data[:8] + code + chunk.data[9:]
        elif field == self.__key_compression:
            code = pack('B', value)
            chunk.data = chunk.data[:10] + code + chunk.data[11:]
        elif field == self.__key_filter_method:
            code = pack('B', value)
            chunk.data = chunk.data[:11] + code + chunk.data[12:]
        elif field == self.__key_interlace:
            code = pack('B', value)
            chunk.data = chunk.data[:12] + code + chunk.data[13:]
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        depth = self.get(chunk, self.__key_bit_depth)
        return depth in self.get(chunk, self.__key_colortype_depth)


class ChunkIDAT(ChunkImplementation):
    """IDAT chunks contain the compressed image datastream, eventualy splited
    over multiple IDAT chunks.
    This chunk is critical, a valid image MUST contain at least one IDAT chunk,
    which has to be placed between the IHDR and IEND chunk.
    Key:
        data: simply returns the raw chunk data
              has to be processed with other IDAT chunks"""

    def __init__(self):
        super(ChunkIDAT, self).__init__('IDAT', min_length=1)
        self.__key_data = 'data'

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {self.__key_data: self.get(chunk, self.__key_data)}

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field == self.__key_data:
            return chunk.data
        else:
            raise KeyError(
                f"Only '{self.__key_data}' key is valid for IHDR chunks"
            )

class ChunktEXt(ChunkImplementation):
    """tEXt chunks contain text information.
    They are made a a keyword (max 78 bytes),
    and the text itself, separated by a null byte.
    The texts must be valid latin-1.
    Keywords may follow common practices to encode specific information,
    but this is not decoded here.
    Keys:
        keyword: The keyword
        text: The actual text
        content: not available from get_all, returns a (keyword, text) tuple"""

    def __init__(self):
        super(ChunktEXt, self).__init__('tEXt',
                                        empty_data=b'A\x00',
                                        min_length=2,
                                        )
        self.__key_keyword = 'keyword'
        self.__key_text = 'text'

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {self.__key_keyword: self.get(chunk, self.__key_keyword),
                self.__key_text: self.get(chunk, self.__key_text)}

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field not in (self.__key_text, self.__key_keyword):
            raise KeyError()
        if chunk.data.count(0x00) != 1 or chunk.data.find(0x00) > 78:
            raise InvalidChunkStructureException(
                "Invalid number of null byte separator in tEXt chunk"
            )
        sep = chunk.data.find(0x00)
        keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0]
        keyword = keyword.decode('latin1')
        textlen = len(chunk.data) - sep - 1
        text = chunk.data[sep + 1: len(chunk.data)]
        text = unpack('{}s'.format(textlen), text)[0]
        text = text.decode('latin1')
        if field == self.__key_keyword:
            return text
        elif field == self.__key_text:
            return keyword
        raise KeyError(f"Invalid key for tEXt chunk")

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field not in (self.__key_text, self.__key_keyword):
            raise KeyError()
        if chunk.data.count(0x00) != 1:
            raise InvalidChunkStructureException(
                "invalid number of null byte separator in tEXt chunk"
            )
        sep = chunk.data.find(0x00)
        value = value.encode('latin1')
        if field == self.__key_text:
            chunk.data = chunk.data[:sep + 1] + value
        elif field == self.__key_keyword:
            chunk.data = value + chunk.data[sep:]

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return chunk.data.count(0x00) == 1 and chunk.data.find(0x00) <= 78


class ChunksRGB(ChunkImplementation):

    # TODO Docstring

    def __init__(self):
        super(ChunksRGB, self).__init__('sRGB',
                                        empty_data=b'\x00',
                                        length=1,
                                        )
        self.renderingtypes = (
            "Perceptual",
            "Relative colorimetric",
            "Saturation",
            "Absolute colorimetric"
        )
        self.__key_rendering_code = "rendering_code"
        self.__key_rendering_name = "rendering_name"

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            self.__key_rendering_code: self.get(
                chunk,
                self.__key_rendering_code
            ),
            self.__key_rendering_name: self.get(
                chunk,
                self.__key_rendering_name
            ),
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field == self.__key_rendering_code:
            return chunk.data[0]
        elif field == self.__key_rendering_name:
            try:
                return self.renderingtypes[
                    self.get(chunk, self.__key_rendering_code)
                ]
            except KeyError:
                raise InvalidChunkStructureException('invalid sRGB value')
        else:
            raise KeyError()

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field == self.__key_rendering_code:
            chunk.data = pack('B', value)
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return self.get(chunk, self.__key_rendering_code) in range(4)

class ChunktIME(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunktIME, self).__init__(
            'tIME',
            length=7,
            empty_data=b'\x00\x00\x01\x01\x00\x00\x00',
        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            'year': self.get(chunk, 'year'),
            'month': self.get(chunk, 'month'),
            'day': self.get(chunk, 'day'),
            'hour': self.get(chunk, 'hour'),
            'minute': self.get(chunk, 'minute'),
            'second': self.get(chunk, 'second'),
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
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

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field == 'year':
            chunk.data = pack('>h', value) + chunk.data[2:]
        elif field == 'month':
            chunk.data = chunk.data[:2] + pack('B', value) + chunk.data[3:]
        elif field == 'day':
            chunk.data = chunk.data[:3] + pack('B', value) + chunk.data[4:]
        elif field == 'hour':
            chunk.data = chunk.data[:4] + pack('B', value) + chunk.data[5:]
        elif field == 'minute':
            chunk.data = chunk.data[:5] + pack('B', value) + chunk.data[6:]
        elif field == 'second':
            chunk.data = chunk.data[:6] + pack('B', value)
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        year = self.get(chunk, 'year')
        month = self.get(chunk, 'month')
        day = self.get(chunk, 'day')
        hour = self.get(chunk, 'hour')
        minute = self.get(chunk, 'minute')
        second = self.get(chunk, 'second')
        month_ok = 1 <= month <= 12
        if month in (1, 3, 5, 7, 8, 10, 12):
            max_day = 31
        elif month == 2:
            if year % 4 == 0 and (year % 400 == 0 or year % 100 != 0):
                max_day = 29
            else:
                max_day = 28
        else:
            max_day = 30
        day_ok = 1 <= day <= max_day
        hour_ok = 0 <= hour <= 23
        minute_ok = 0 <= minute <= 59
        second_ok = 0 <= second <= 60
        return day_ok and month_ok and hour_ok and minute_ok and second_ok


class ChunkgAMA(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunkgAMA, self).__init__('gAMA',
                                        empty_data=b'\x00\x00\x00\x00',
                                        length=4,
                                        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            'gama': self.get(chunk, 'gama'),
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field == 'gama':
            return unpack('>I', chunk.data[0:4])[0] / 100000
        else:
            raise KeyError()

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field == 'gama':
            chunk.data = pack('>I', int(value * 100000))
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return True


class ChunkzTXt(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunkzTXt, self).__init__('zTXt',
                                        empty_data=b'A\x00x\x9c\x03\x00\x00\x00\x00\x01',
                                        min_length=3,
                                        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {'text': self.get(chunk, 'text'),
                'keyword': self.get(chunk, 'keyword'),
                'compression': self.get(chunk, 'compression')}

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field not in ('text', 'keyword', 'content', 'compression'):
            raise KeyError()
        if chunk.data.count(0x00) < 1:
            raise InvalidChunkStructureException("invalid number of null byte separator in zTXt chunk")
        sep = chunk.data.find(0x00)
        keyword = unpack('{}s'.format(sep), chunk.data[0: sep])[0].decode('latin1')
        compression_code = chunk.data[sep + 1]
        if compression_code == 0:
            text = decompress(chunk.data[sep + 2:])
            text = unpack('{}s'.format(len(text)), text)[0].decode('latin1')
        else:
            raise UnsupportedCompressionMethodException(code=compression_code)
        if field == 'text':
            return text
        elif field == 'keyword':
            return keyword
        elif field == 'compression':
            return compression_code
        elif field == 'content':
            return keyword, text

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field not in ('text', 'keyword'):
            raise KeyError()
        if chunk.data.count(0x00) < 1:
            raise InvalidChunkStructureException("invalid number of null byte separator in zTXt chunk")
        sep = chunk.data.find(0x00)
        compression_code = chunk.data[sep + 1]
        if field == 'text':
            if compression_code == 0:
                text = value.encode('latin1')
                text = compress(text)
                chunk.data = chunk.data[:sep + 2] + text
            else:
                raise UnsupportedCompressionMethodException()
        elif field == 'keyword':
            chunk.data = value.encode('latin1') + chunk.data[sep:]

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return chunk.data.count(0x00) >= 1 and chunk.data.find(0x00) <= 78

class ChunkcHRM(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunkcHRM, self).__init__(
            'cHRM',
            length=32,
            empty_data=b'\x00' * 32,
        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            'white_x': self.get(chunk, 'white_x'),
            'white_y': self.get(chunk, 'white_y'),
            'red_x': self.get(chunk, 'red_x'),
            'red_y': self.get(chunk, 'red_y'),
            'green_x': self.get(chunk, 'green_x'),
            'green_y': self.get(chunk, 'green_y'),
            'blue_x': self.get(chunk, 'blue_x'),
            'blue_y': self.get(chunk, 'blue_y'),
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field == 'white_x':
            return unpack('>I', chunk.data[0:4])[0] / 100000
        elif field == 'white_y':
            return unpack('>I', chunk.data[4:8])[0] / 100000
        elif field == 'red_x':
            return unpack('>I', chunk.data[8:12])[0] / 100000
        elif field == 'red_y':
            return unpack('>I', chunk.data[12:16])[0] / 100000
        elif field == 'green_x':
            return unpack('>I', chunk.data[16:20])[0] / 100000
        elif field == 'green_y':
            return unpack('>I', chunk.data[20:24])[0] / 100000
        elif field == 'blue_x':
            return unpack('>I', chunk.data[24:28])[0] / 100000
        elif field == 'blue_y':
            return unpack('>I', chunk.data[28:32])[0] / 100000
        else:
            raise KeyError()

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field == 'white_x':
            value = pack('>I', round(value * 100000))
            chunk.data = value + chunk.data[4:]
        elif field == 'white_y':
            value = pack('>I', round(value * 100000))
            chunk.data = chunk.data[:4] + value + chunk.data[8:]
        elif field == 'red_x':
            value = pack('>I', round(value * 100000))
            chunk.data = chunk.data[:8] + value + chunk.data[12:]
        elif field == 'red_y':
            value = pack('>I', round(value * 100000))
            chunk.data = chunk.data[:12] + value + chunk.data[16:]
        elif field == 'green_x':
            value = pack('>I', round(value * 100000))
            chunk.data = chunk.data[:16] + value + chunk.data[20:]
        elif field == 'green_y':
            value = pack('>I', round(value * 100000))
            chunk.data = chunk.data[:20] + value + chunk.data[24:]
        elif field == 'blue_x':
            value = pack('>I', round(value * 100000))
            chunk.data = chunk.data[:24] + value + chunk.data[28:]
        elif field == 'blue_y':
            value = pack('>I', round(value * 100000))
            chunk.data = chunk.data[:28] + value
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return True

class ChunkpHYs(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunkpHYs, self).__init__(
            'pHYs',
            length=9,
            empty_data=b'\x00',
        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            'ppu_x': self.get(chunk, 'ppu_x'),
            'ppu_y': self.get(chunk, 'ppu_y'),
            'unit_code': self.get(chunk, 'unit_code'),
            'unit_name': self.get(chunk, 'unit_name'),
            'dpi': self.get(chunk, 'dpi'),
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field == 'ppu_x':
            return unpack('>I', chunk.data[0:4])[0]
        elif field == 'ppu_y':
            return unpack('>I', chunk.data[4:8])[0]
        elif field == 'unit_code':
            return chunk.data[8]
        elif field == 'unit_name':
            code = self.get(chunk, 'unit_code')
            if code == 0:
                return 'unknown'
            elif code == 1:
                return 'meter'
            else:
                raise InvalidChunkStructureException("invalid unit code, only 1 or 0 allowed, found {}".format(code))
        elif field == 'dpi':
            return round(self.get(chunk, 'ppu_x') / 39.3701), round(self.get(chunk, 'ppu_y') / 39.3701)
        else:
            raise KeyError()

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field == 'ppu_x':
            chunk.data = pack('>I', value) + chunk.data[4:]
        elif field == 'ppu_y':
            chunk.data = chunk.data[:4] + pack('>I', value) + chunk.data[8:]
        elif field == 'unit_code':
            chunk.data = chunk.data[:8] + pack('B', value)
        elif field == 'dpi':
            self.set(chunk, 'ppu_x', round(value[0] * 39.3701))
            self.set(chunk, 'ppu_y', round(value[1] * 39.3701))
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return self.get(chunk, 'unit_code') in range(2)

class ChunkiTXt(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunkiTXt, self).__init__('iTXt',
                                        empty_data=b'A\x00\x00\x00\x00A\x00',
                                        min_length=12,
                                        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {'keyword': self.get(chunk, 'keyword'),
                'compressed': self.get(chunk, 'compressed'),
                'compression_code': self.get(chunk, 'compression_code'),
                'language': self.get(chunk, 'language'),
                'translated_keyword': self.get(chunk, 'translated_keyword'),
                'text': self.get(chunk, 'text'),
                }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field not in ('text', 'keyword', 'compression_code',
                         'compressed', 'language', 'translated_keyword',):
            raise KeyError()
        if chunk.data.count(b'\x00') < 3:
            raise InvalidChunkStructureException("invalid number of null byte separator in iTXt chunk")
        sep1 = chunk.data.find(0x00)
        if sep1 > 79:
            raise InvalidChunkStructureException(
                "iTXt keyword is too long, it should be at most 79 bytes and is {}".format(sep1)
            )
        sep2 = chunk.data.find(0x00, sep1 + 3)
        sep3 = chunk.data.find(0x00, sep2 + 1)
        if field == 'keyword':
            return chunk.data[:sep1].decode('latin1')
        elif field == 'language':
            return chunk.data[sep1 + 3:sep2].decode('latin1')
        elif field == 'translated_keyword':
            return chunk.data[sep2 + 1:sep3].decode('utf-8')
        compression_flag = chunk.data[sep1 + 1]
        if field == 'compressed':
            if compression_flag == 0:
                return False
            elif compression_flag == 1:
                return True
            else:
                raise InvalidChunkStructureException(
                    'invalid compression flag, it sould be 0 or 1 and is {}'.format(compression_flag))
        compression_code = chunk.data[sep1 + 2]
        if field == 'compression_code':
            return compression_code
        if field == 'text':
            data = chunk.data[sep3 + 1:]
            if compression_flag == 0:
                return data.decode('utf-8')
            elif compression_flag == 1:
                if compression_code == 0:
                    return decompress(data).decode('utf-8')
                else:
                    raise UnsupportedCompressionMethodException()
            else:
                raise InvalidChunkStructureException(
                    'invalid compression flag, it sould be 0 or 1 and is {}'.format(compression_flag))
        else:
            raise KeyError()

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        sep1 = chunk.data.find(0x00)
        sep2 = chunk.data.find(0x00, sep1 + 3)
        sep3 = chunk.data.find(0x00, sep2 + 1)
        if field == 'keyword':
            chunk.data = value.encode('latin1') + chunk.data[sep1:]
        elif field == 'compressed':
            if value:
                chunk.data = chunk.data[:sep1 + 1] + b'\x01' + chunk.data[sep1 + 2:]
            else:
                chunk.data = chunk.data[:sep1 + 1] + b'\x00' + chunk.data[sep1 + 2:]
        elif field == 'compression_code':
            chunk.data = chunk.data[:sep1 + 2] + pack('B', value) + chunk.data[sep1 + 3:]
        elif field == 'language':
            chunk.data = chunk.data[:sep1 + 3] + value.encode('latin1') + chunk.data[sep2:]
        elif field == 'translated_keyword':
            chunk.data = chunk.data[:sep2 + 1] + value.encode('utf-8') + chunk.data[sep3:]
        elif field == 'text':
            value = value.encode('utf-8')
            if self.get(chunk, 'compressed'):
                if self.get(chunk, 'compression_code') == 0:
                    chunk.data = chunk.data[:sep3 + 1] + compress(value)
                else:
                    raise UnsupportedCompressionMethodException()
            else:
                chunk.data = chunk.data[:sep3 + 1] + value
        else:
            raise KeyError()

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return chunk.data.count(0x00) >= 3 and chunk.data.find(0x00) <= 78


class ChunkbKGD(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunkbKGD, self).__init__('bKGD',
                                        empty_data=b'\x00',
                                        length=(1, 2, 6),
                                        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {'color_types': self.get(chunk, 'color_types'),
                'color': self.get(chunk, 'color')}

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field == 'color_types':
            if len(chunk) == 1:
                return (3,)
            elif len(chunk) == 2:
                return (0, 4)
            elif len(chunk) == 6:
                return (2, 6)
            else:
                raise InvalidChunkStructureException("Invalid length for a bKGD chunk")
        elif field == 'color':
            if len(chunk) == 1:
                return chunk.data[0]
            elif len(chunk) == 2:
                return unpack('>H', chunk.data)[0]
            elif len(chunk) == 6:
                return unpack('>H', chunk.data[:2])[0], unpack('>H', chunk.data[2:4])[0], unpack('>H', chunk.data[4:6])[
                    0]
            else:
                raise InvalidChunkStructureException("Invalid length for a bKGD chunk")

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        if field == 'color_type':
            if value == 3:
                if not len(chunk) == 1:
                    chunk.data = b'\x00'
            elif value in (0, 4) or value == (0, 4):
                if not len(chunk) == 2:
                    chunk.data = b'\x00\x00'
            elif value in (2, 6) or value == (2, 6):
                if not len(chunk) == 2:
                    chunk.data = b'\x00\x00\x00\x00\x00\x00'
            else:
                raise ValueError("Invalid value for color_type in bKGD chunk")
        elif field == 'color':
            if len(chunk) == 1:
                if not (value >= 0 and value <= 255):
                    raise ValueError("Palette index should be between 0 and 255")
                chunk.data = pack('B', value)
            elif len(chunk) == 2:
                chunk.data = pack('>H', value)
            elif len(chunk) == 6:
                if len(value) != 3:
                    raise ValueError("Backgroud color value should have 3 channels")
                for x in value:
                    if not type(x) is int:
                        raise ValueError("Backgroud color value should only be integers")
                    elif not (x >= 0 and x <= (1 << 16) - 1):
                        raise ValueError("Palette index should be between 0 and 65535")
                # Some unsigned shorts were used here, make sure it was a unique mistake
                chunk.data = pack('>H', value[0]) + pack('>H', value[1]) + pack('>H', value[2])
            else:
                raise InvalidChunkStructureException("Invalid length for a bKGD chunk")

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return len(chunk) in (1, 2, 6)

class ChunksBIT(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunksBIT, self).__init__('sBIT',
                                        min_length=1,
                                        max_length=4,
                                        empty_data=b'\x00',
                                        )

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {'color_type': self.get(chunk, 'color_type'),
                'significant_bits': self.get(chunk, 'significant_bits')}

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if len(chunk) == 1:
            color_type = 0
            val = chunk.data[0]
        elif len(chunk) == 2:
            color_type = 4
            val = chunk.data[0], chunk.data[1]
        elif len(chunk) == 3:
            color_type = (2, 3)
            val = chunk.data[0], chunk.data[1], chunk.data[2]
        elif len(chunk) == 4:
            color_type = 6
            val = chunk.data[0], chunk.data[1], chunk.data[2], chunk.data[3]
        else:
            raise InvalidChunkStructureException("sBIT chunk is to large")
        if field == 'color_type':
            return color_type
        elif field == 'significant_bits':
            return val
        else:
            raise KeyError()

    def set(self, chunk, field, val, ihdr=None, ihdr_data=None):
        if field == 'color_type':
            if val == 0:
                if not len(chunk) == 1:
                    chunk.data == b'\x00'
            elif val == 4:
                if not len(chunk) == 2:
                    chunk.data == b'\x00\x00'
            elif val in (2, 3) or val == (2, 3):
                if not len(chunk) == 3:
                    chunk.data == b'\x00\x00\x00'
            elif val == 6:
                if not len(chunk) == 4:
                    chunk.data == b'\x00\x00\x00\x00'
            else:
                print(val)
                raise ValueError("invalid color type")
        elif field == 'significant_bits':
            t = self.get(chunk, 'color_type')
            if t == 0:
                if not type(val) is int or not (0 < val < 255):
                    raise TypeError("Expecting an integer between 0 and 255")
                chunk.data = pack('B', val)
            else:
                if not type(val) is tuple:
                    raise ValueError('Excpecting a tuple')
                v = b''
                for x in val:
                    if not type(x) is int or not (0 < x < 255):
                        raise ValueError('Expecting a tuple of integers between 0 and 255')
                    v += pack('B', x)
                if (t, len(v)) not in ((4, 2), ((2, 3), 3), (6, 4)):
                    raise ValueError('Invalid length for this specific color type')
                chunk.data = v

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        return True


class ChunkPLTE(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunkPLTE, self).__init__('PLTE',
                                        empty_data=b'\x00' * 3,
                                        min_length=3,
                                        max_length=768, )

    def _is_length_valid(self, chunk, ihdr=None, ihdr_data=None):
        """Overrides from superclass, it should only be valid if it is a multiple of 3"""
        return len(chunk) % 3 == 0 and super(ChunkPLTE, self)._is_length_valid(chunk)

    def get(self, chunk, index, ihdr=None, ihdr_data=None):
        if not isinstance(index, int) or index < 0 or index > 256:
            raise IndexError('Palette index should be an integer')
        p = chunk.data[index * 3: index * 3 + 3]
        return p[0], p[1], p[2]

    def set(self, chunk, index, val, ihdr=None, ihdr_data=None):
        if not isinstance(index, int) or index < 0 or index > 256:
            raise ValueError('Palette index should be an integer')
        if not isinstance(val, tuple) or len(val) != 3:
            raise ValueError('Palette value should be a tuple of 3 integers')
        for p in val:
            if p > 255 or p < 0:
                raise ValueError('Color values should be integers between 0 and 255')
        v = pack('B', val[0]) + pack('B', val[1]) + pack('B', val[2])
        chunk.data = chunk.data[:index * 3] + v + chunk.data[index * 3 + 3:]

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        if not self.is_valid(chunk):
            raise InvalidChunkStructureException('Invalid PLTE chunk')
        return tuple([self.get(chunk, i) for i in range(len(chunk) // 3)])

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        raise Exception('Not implemented') # TODO


class ChunksPLT(ChunkImplementation):

    # TODO Docstring
    # TODO Do not hardcode keys

    def __init__(self):
        # TODO I have a doubt about wether or not the length is correct here, check it.
        super(ChunksPLT, self).__init__('sPLT',
                                        empty_data=b'\x00\x00',
                                        min_length=2, )

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        try:
            chunk.get_payload(ihdr=ihdr, ihdr_data=ihdr_data)
        except:
            return False
        else:
            return True

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            'palette_name': self.get(chunk, 'palette_name'),
            'sample_depth': self.get(chunk, 'sample_depth'),
            'palette': self.get(chunk, 'palette')
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        sep = chunk.data.find(b'\x00')
        if field == 'palette_name':
            return chunk.data[:sep].decode('latin1')
        sample_depth = chunk.data[sep + 1]
        if field == 'sample_depth':
            return sample_depth
        elif field == 'palette':
            l = len(chunk.data[sep + 2:])
            if (sample_depth == 8 and l % 6 != 0) or (sample_depth == 16 and l % 8 != 0):
                raise InvalidChunkStructureException(
                    "The sample depth of the sPLT chunk does not match the number of entries.")
            if sample_depth not in (8, 16):
                raise InvalidChunkStructureException("Wrong sample depth in sPLT chunk: {}".format(sample_depth))
            clen = 1 if sample_depth == 8 else 2
            plt = []
            for i in range(0, l, clen * 4 + 2):
                entry = []
                if clen == 1:
                    for j in range(i, i + 4):
                        entry.append(chunk.data[j])
                else:
                    for j in range(i, i + 8, 2):
                        entry.append(unpack('>H', chunk.data[j:j + 2])[0])
                entry.append(unpack('>H', chunk.data[-2:])[0])
                plt.append(tuple(entry))
            return tuple(plt)

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        sep = chunk.data.find(0x00)
        if field == 'palette_name':
            if type(value) == str:
                value_bytes = value.encode('latin-1')
            else:
                raise TypeError(
                    "Invalid palette type for a palette name, found type {} instead of str.".format(type(value)))
            chunk.data = value_bytes + chunk.data[sep:]

        elif field == 'sample_depth':
            if len(chunk['palette']) != 0:
                raise ValueError("You can't modify a sPLT chunk sample depth if the chunk's palette is not empty.")
            chunk.data = chunk.data[:sep + 1] + pack('B', value) + chunk.data[sep + 2:]

        elif field == 'palette':
            if type(value) not in (tuple, list):
                raise TypeError("Excepting palette to be a tuple or a list")
            depth = chunk['sample_depth']
            max_val = (1 << (depth + 1)) - 1
            buff = bytearray()
            for color in value:
                if type(color) not in (tuple, list) or len(color) != 3:
                    raise TypeError("A palette should contain tuples or lists of length 3")
                for channel in color:
                    if not type(channel) == int or not (0 <= channel <= max_val):
                        raise TypeError(
                            'Palette channel values should be integers between 0 and {} (for this specific sample depth)'.format(
                                max_val))
                    if depth == 8:
                        mode = 'B'
                    elif depth == 16:
                        mode == '>H'
                    else:
                        raise InvalidChunkStructureException('Invalid bit depth: {}'.format(depth))
                    buff.extend(pack(color))
            chunk.data = chunk.data[:sep + 3] + buff
        else:
            raise KeyError()


class ChunktRNS(ChunkImplementation):
    """tRNS Chunk encode information about the transparency of the image.
    - For indexed color images, one single byte transparency value is given
    for each palette entry
    - For greyscale and truecolor images, a single two bytes value is given
    for the entire image."""

    # TODO Do not hardcode keys

    def __init__(self):
        super(ChunktRNS, self).__init__('tRNS',
                                        empty_data=b'\x00\x00',
                                        min_length=2, )

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        if ihdr:
            ihdr_data = ihdr.get_payload()
        if type(ihdr_data) != dict:
            raise TypeError()
        colortype = ihdr_data.get('colortype_code')
        if not colortype:
            raise ValueError("Missing key: colortype_code")

        # TODO
        raise Exception("Not implemented")

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return self.get(chunk, 'palette', ihdr=ihdr, ihdr_data=ihdr_data)

    def get(self, chunk, field, ihdr=None, ihdr_data=None):
        if field != "palette":
            raise KeyError("Unvalid key: {}".format(field))

        if ihdr and ihdr.type == 'IHDR':
            colortype = ihdr['colortype_code']
        elif ihdr_data and type(ihdr_data) == dict:
            colortype = ihdr.getitem('colortype_code')
        else:
            raise ValueError("Either valid ihdr or ihdr_data argument required.")

        unvalid_0 = colortype == 0 and len(chunk.data) % 2 != 0
        unvalid_2 = colortype == 2 and len(chunk.data) % 6 != 0

        if unvalid_0 or unvalid_2:
            raise InvalidChunkStructureException(
                'Invalid length for color type {}'.format(colortype)
            )
        l = []
        if colortype == 0:
            for i in range(0, len(chunk.data), 2):
                l.append(unpack('H', chunk.data[i: i + 2])[0])

        if colortype == 2:
            for i in range(0, len(chunk.data), 6):
                p = []
                for j in range(i, i + 6, 2):
                    p.append(unpack('H', chunk.data[i + j: i + j + 2])[0])
                l.append(tuple(p))
        elif colortype == 3:
            l = [i for i in chunk.data]

        else:
            raise ValueError(
                'Invalid colortype: {}, only 0, 2 and 3 accepted'.format(
                    colortype
                )
            )
        return tuple(l)

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):
        sep = chunk.data.find(0x00)
        if field == 'palette_name':
            if type(value) == str:
                value_bytes = value.encode('latin-1')
            else:
                raise TypeError(
                    "Invalid palette type for a palette name, found type {} instead of str.".format(type(value)))
            chunk.data = value_bytes + chunk.data[sep:]

        elif field == 'sample_depth':
            if len(chunk['palette']) != 0:
                raise ValueError("You can't modify a sPLT chunk sample depth if the chunk's palette is not empty.")
            chunk.data = chunk.data[:sep + 1] + pack('B', value) + chunk.data[sep + 2:]

        elif field == 'palette':
            if type(value) not in (tuple, list):
                raise TypeError("Excepting palette to be a tuple or a list")
            depth = chunk['sample_depth']
            max_val = (1 << (depth + 1)) - 1
            buff = bytearray()
            for color in value:
                if type(color) not in (tuple, list) or len(color) != 3:
                    raise TypeError("A palette should contain tuples or lists of length 3")
                for channel in color:
                    if not type(channel) == int or not (channel >= 0 and channel <= max_val):
                        raise TypeError(
                            'Palette channel values should be integers between 0 and {} (for this specific sample depth)'.format(
                                max_val))
                    if depth == 8:
                        mode = 'B'
                    elif depth == 16:
                        mode == '>H'
                    else:
                        raise InvalidChunkStructureException('Invalid bit depth: {}'.format(depth))
                    buff.extend(pack(color))
            chunk.data = chunk.data[:sep + 3] + buff
        else:
            raise KeyError()


class ChunkiCCP(ChunkImplementation):
    """iCCP chunks contain a compressed CCP profile, along with a name for it
    keys:
        profile_name:   The name of the profile                 (str)
        compression:    The compression method used, usally 0   (int)
        profile:        The decompressed profile                (bytes)
    """

    def __init__(self):
        super(ChunkiCCP, self).__init__('iCCP',
                                        empty_data=b'0\x00\x00',  # TODO Default profile
                                        min_length=3, )
        self.__key_profile_name = 'profile_name'
        self.__key_compression = 'compression'
        self.__key_profile = 'profile'

        self.__keys = (
            self.__key_profile_name,
            self.__key_compression,
            self.__key_profile,
        )

    def _is_payload_valid(self, chunk, ihdr=None, ihdr_data=None):
        sep = chunk.data.find(0)
        return 0 < sep <= 79 and sep < len(chunk.data) - 1

    def get_all(self, chunk, ihdr=None, ihdr_data=None):
        return {
            self.__key_profile_name: self.get(
                chunk,
                self.__key_profile_name,
                ihdr=ihdr,
                ihdr_data=ihdr_data
            ),
            self.__key_compression: self.get(
                chunk,
                self.__key_compression,
                ihdr=ihdr,
                ihdr_data=ihdr_data
            ),
            self.__key_profile: self.get(
                chunk,
                self.__key_profile,
                ihdr=ihdr,
                ihdr_data=ihdr_data
            ),
        }

    def get(self, chunk, field, ihdr=None, ihdr_data=None):

        # We are doing this here to raise the Exception before checking
        # the chunks structure
        if not field in self.__keys:
            raise KeyError()

        if not self._is_payload_valid(chunk):
            raise InvalidChunkStructureException("chunk is not valid")

        sep = chunk.data.find(0)
        compression_method = chunk.data[sep + 1]

        if field == self.__key_profile_name:
            return chunk.data[:sep].decode('latin-1')

        if field == self.__key_compression:
            return compression_method

        elif field == self.__key_profile:
            if compression_method != 0:
                raise InvalidChunkStructureException(
                    'Unsupported compression method: {}, only 0 supported'.format(compression_method))
            return decompress(chunk.data[sep + 2:])

    def set(self, chunk, field, value, ihdr=None, ihdr_data=None):

        # We are doing this here to raise the Exception before checking
        # the chunks structure
        if not field in self.__keys:
            raise KeyError()

        if not self._is_payload_valid(chunk):
            raise InvalidChunkStructureException("chunk is not valid")

        sep = chunk.data.find(0)
        compression_method = chunk.data[sep + 1]

        if field == self.__key_profile_name:
            if type(value) != str:
                raise TypeError("ICC Profile name should be a string, not {}".format(type(value)))
            if len(value) > 79:
                raise ValueError("ICC Profile name should at most 79 characters")
            chunk.data = value.encode('latin-1') + chunk.data[sep:]

        # Only compression method 0 (deflate) is supported by PNG,
        # so setting it to anything else will break the chunk
        elif field == self.__key_compression:
            if type(value) != int:
                raise TypeError("ICC compression method should be an integer")
            chunk.data = chunk.data[:sep + 1] + b'\x00' + chunk.data[sep + 2:]

        # We are not actualy encoding the ICC Profile, just packing it in the PNG iCCP chunk
        elif field == self.__key_profile:
            if type(value) != bytes:
                raise TypeError("ICC Profile type should be bytes")
            if compression_method != 0:
                raise InvalidChunkStructureException(
                    'Unsupported compression method: {}, only 0 supported'.format(compression_method))
            chunk.data = chunk.data[:sep + 2] + compress(value)


implementations = {
    'IHDR': ChunkIHDR(),
    'PLTE': ChunkPLTE(),
    'IDAT': ChunkIDAT(),
    'IEND': ChunkImplementation('IEND', length=0),
    'tEXt': ChunktEXt(),
    'sRGB': ChunksRGB(),
    'tIME': ChunktIME(),
    'gAMA': ChunkgAMA(),
    'zTXt': ChunkzTXt(),
    'cHRM': ChunkcHRM(),
    'pHYs': ChunkpHYs(),
    'iTXt': ChunkiTXt(),
    'bKGD': ChunkbKGD(),
    'sBIT': ChunksBIT(),
    'sPLT': ChunksPLT(),
    'tRNS': ChunktRNS(),
    'iCCP': ChunkiCCP(),
    # https://www.hackthis.co.uk/forum/programming-technology/27373-png-idot-chunk
}

# TODO Use bytearrays
