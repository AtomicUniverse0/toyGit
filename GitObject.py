
class GitObject:
    """尝试从 data 初始化一个git对象，如果没有 data，那就调用自己的init"""
    def __init__(self, data: bytes):
        if data is None:
            self.init()
        else:
            self.deserialize(data)

    def serialize(self) -> bytes:
        raise NotImplementedError

    def deserialize(self, data: bytes):
        raise NotImplementedError

    def init():
        pass