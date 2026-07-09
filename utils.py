import os
import zlib
import hashlib
from GitObject import GitObject, GitCommit, GitTree, GitTag, GitBlob


""" 如果目录存在，则返回目录的地址，否则返回None """
def git_repo_dir(git_repo_path: str, *path, mkdir : bool = False) -> str:

    repo_dir_addr = os.path.join(git_repo_path, *path)
    if os.path.exists(repo_dir_addr) :
        assert os.path.isdir(repo_dir_addr), "Invalid argument: " + repo_dir_addr
        return repo_dir_addr

    if mkdir :
        os.makedirs(repo_dir_addr, exist_ok=True)
        return  repo_dir_addr
    
    return None

""" 如果文件所属的目录存在，则返回文件的地址，否则返回None """
def git_repo_file(git_repo_path: str, *path, mkdir : bool = False) -> str:
    if git_repo_dir(git_repo_path, *path[:-1], mkdir=mkdir) is None :
        return None
    
    # 运行到这里，说明目录一定存在，目录下的文件可能不存在
    repo_file_addr = os.path.join(git_repo_path, *path)
    if os.path.exists(repo_file_addr):
        assert os.path.isfile(repo_file_addr), "Invalid argument: " + repo_file_addr

    return repo_file_addr

def read_object(git_repo_path: str, sha: str) -> GitObject:
    obj_path = git_repo_file(git_repo_path, "objects", sha[0:2], sha[2:])
    if obj_path is None:
        return None

    with open(obj_path, "rb") as f:
        data = zlib.decompress(f.read())

        "判断一下这个对象的类型"
        space_idx = data.find(b" ")
        type = data[0 : space_idx].decode("ascii")

        separate_idx = data.find(b"\x00", space_idx)
        size = int(data[space_idx + 1 : separate_idx].decode("ascii"))
        
        if size != len(data) - separate_idx - 1:
            raise Exception("Malformed object {0}: bad length".format(sha))

        constructor = None

        match type:
            case "commit":
                constructor = GitCommit
            case "tree":
                constructor = GitTree   
            case "tag":
                constructor = GitTag
            case "blob":
                constructor = GitBlob
            case _:
                raise Exception("Unknown type {0} for object {1}".format(type, sha))
        
        return constructor(data[separate_idx + 1 : ])
    
def write_object(obj: GitObject, git_repo_path: str = None) -> str:
    content = obj.serialize()
    data = obj.get_type() + b" " + str(len(content)).encode("ascii") + b"\x00" + content
    sha = hashlib.sha1(data).hexdigest()

    if git_repo_path:
        path = git_repo_file(git_repo_path, "objects", sha[0:2], sha[2:], mkdir=True)

        if os.path.exists(path):
            raise Exception("Object {0} already exists".format(sha))
        else:
            with open(path, "wb") as f:
                f.write(zlib.compress(data))

    return sha

def hash_object(file_path: str, obj_type: str,  git_repo_path: str = None) -> str:
    with open(file_path, "rb") as f:
        data = f.read()

    match obj_type:
        case "blob":
            obj = GitBlob(data)
        case "commit":
            obj = GitCommit(data)
        case "tree":
            obj = GitTree(data)
        case "tag":
            obj = GitTag(data)
        case _:
            raise Exception("Unsupported object type: " + obj_type)

    sha = write_object(obj, git_repo_path)
    return sha