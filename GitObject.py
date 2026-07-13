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

class GitIndexEntry (object):
    def __init__(self, ctime=None, mtime=None, dev=None, ino=None,
                 mode_type=None, mode_perms=None, uid=None, gid=None,
                 fsize=None, sha=None, flag_assume_valid=None,
                 flag_stage=None, name=None) -> None:
      # 文件元数据最后一次更改的时间。 是（秒级时间戳，纳秒级时间戳）的元组
      self.ctime = ctime
      # 文件数据最后一次更改的时间。 是（秒级时间戳，纳秒级时间戳）的元组
      self.mtime = mtime
      # 包含此文件的设备 ID
      self.dev = dev
      # 文件的 inode 编号
      self.ino = ino
      # 对象类型，可以是 b1000（常规），b1010（符号链接），b1110（gitlink）
      self.mode_type = mode_type
      # 对象权限，整数值。
      self.mode_perms = mode_perms
      # 拥有者的用户 ID
      self.uid = uid
      # 拥有者的组 ID
      self.gid = gid
      # 此对象的大小，以字节为单位
      self.fsize = fsize
      # 对象的 SHA
      self.sha = sha
      self.flag_assume_valid = flag_assume_valid
      self.flag_stage = flag_stage
      # 对象名称（这次是完整路径！）
      self.name = name
    
class GitIndex(object):
    version : int = None
    entries : list[GitIndexEntry] = None

    def __init__(self, version: int = 2, entries: list[GitIndexEntry] = None) -> None:
        self.version = version
        self.entries = entries if entries is not None else []