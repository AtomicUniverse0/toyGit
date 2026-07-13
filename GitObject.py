from utils import kvlm_parse, kvlm_serialize, tree_parse, tree_serialize


class GitObject:
    """尝试从 data 初始化一个git对象，如果没有 data，那就调用自己的init"""
    def __init__(self, data: bytes):
        if data is None:
            self.init()
        else:
            self.deserialize(data)

    def serialize(self) -> bytes:
        raise NotImplementedError
    
    def get_type(self) -> bytes:
        raise NotImplementedError

    def deserialize(self, data: bytes):
        raise NotImplementedError

    def init(self) -> None:
        raise NotImplementedError

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
    kvlm : dict = None

    def __init__(self, data: bytes):
        super().__init__(data)

    def serialize(self) -> bytes:
        return kvlm_serialize(self.kvlm)

    def deserialize(self, data: bytes):
        self.kvlm = kvlm_parse(data)
    
    def get_type(self) -> bytes:
        return b"commit"

class GitTreeLeaf(object):
    def __init__(self, mode: str, path: str, sha: str) -> None:
        self.mode = mode
        self.path = path
        self.sha = sha

class GitTree(GitObject):
    items : list[GitTreeLeaf] = None

    def __init__(self, data: bytes):
        super().__init__(data)

    def serialize(self) -> bytes:
        return tree_serialize(self.items)

    def deserialize(self, data: bytes):
        self.items = tree_parse(data)

    def get_type(self) -> bytes:
        return b"tree"

class GitTag(GitCommit):
    def get_type(self) -> bytes:
        return b"tag"