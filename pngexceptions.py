class InvalidChunkStructureException(Exception):
    """Raised when a chunk's internal structure is invalid."""
    def __init__(self, txt):
        super(InvalidChunkStructureException, self).__init__(txt)

class InvalidPngStructureException(Exception):
    """Raised when a png structure is invalid."""
    def __init__(self, txt):
        super(InvalidPngStructureException, self).__init__(txt)

class UnsupportedChunkException(Exception):
    """Raised when trying to understand an unsupported chunk"""
    def __init__(self):
        super(UnsupportedChunkException, self).__init__("This chunk type is not supported.")
