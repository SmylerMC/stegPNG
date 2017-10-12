class InvalidChunkStructureException(Exception):

    def __init__(self, txt):
        super(InvalidChunkStructureException, self).__init__(txt)

class UnsupportedChunkException(Exception):

    def __init__(self):
        super(UnsupportedChunkException, self).__init__("This chunk type is not supported.")
