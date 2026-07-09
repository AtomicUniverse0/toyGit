
class GitObject:
    """尝试从 data 初始化一个git对象，如果没有 data，那就调用自己的init"""
    def __init__(self, data: bytes):
        if data is None:
            self.init()
        else:
            self.deserialize(data)

    def serialize(self) -> bytes:
        raise NotImplementedError
    
    def get_type(self) -> str:
        raise NotImplementedError

    def deserialize(self, data: bytes):
        raise NotImplementedError

    def init():
        pass

class GitBlob(GitObject):
    blobData : bytes = None

    def __init__(self, data: bytes):
        super().__init__(data)
        self.blobData = data

    def serialize(self) -> bytes:
        return self.blobData

    def deserialize(self, data: bytes):
        self.blobData = data

    def get_type(self) -> bytes:
        return b"blob"

class GitCommit(GitObject):
    def __init__(self, data: bytes):
        pass

    def serialize(self) -> bytes:
        pass

    def deserialize(self, data: bytes):
        pass
    
    def get_type(self) -> bytes:
        return b"commit"

class GitTree(GitObject):
    def __init__(self, data: bytes):
        pass

    def serialize(self) -> bytes:
        pass

    def deserialize(self, data: bytes):
        pass
    def get_type(self) -> bytes:
        return b"tree"
class GitTag(GitObject):
    def __init__(self, data: bytes):
        pass

    def serialize(self) -> bytes:
        pass

    def deserialize(self, data: bytes):
        pass

    def get_type(self) -> bytes:
        return b"tag"