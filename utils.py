import os
import zlib
import hashlib
import collections
from GitObject import GitObject, GitCommit, GitTree, GitTag, GitBlob, GitTreeLeaf


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

# 用来将原生的commit对象的字节流解析为一个字典，字典的key是commit对象的属性名，value是对应的属性值
# commit 对象首先有若干key-value对，最后是提交信息
def kvlm_parse(raw: bytes, start: int = 0, dct: dict = None) -> dict:
    if dct is None:
        dct = collections.OrderedDict()

    space = raw.find(b" ", start) 
    nextline = raw.find(b"\n", start)
    assert nextline != start, "Malformed commit object: missing header"

    if space < 0 or nextline < space:
        # 特殊情况，压根找不到key了，这说明剩下的都是消息
        dct[None] = raw[start:]
        return dct

    key = raw[start:space]

    # nextline 不一定是value的结尾，因为一个value可能有多个换行符
    # 如果一个换行符的下一个字符不是空格，那么才是value的结尾
    end = nextline
    while True:
        # raw 是bytes，所以 raw[i] 是个int，所以要用ord获得" "的int值
        if raw[end + 1] != ord(" "):
            break
        end = raw.find(b"\n", end + 1)

    value = raw[space + 1 : end].replace(b"\n ", b"\n")

    if key in dct:
        if type(dct[key]) is list:
            dct[key].append(value)
        else :
            dct[key] = [dct[key], value]
    else:
        dct[key] = value

    return kvlm_parse(raw, end + 1, dct)

def kvlm_serialize(kvlm: dict) -> bytes:
    ret = b""

    for key in kvlm.keys():
        if key is None:
            continue

        value = kvlm[key]
        if type(value) is not list:
            value = [value]

        for v in value:
            ret += key + b" " + v.replace(b"\n", b"\n ") + b"\n"

    if None in kvlm:
        ret += kvlm[None] + b"\n"

    return ret

def log_graphviz(git_repo_path: str, sha: str, seen: set) -> None:
    if sha in seen:
        return
    seen.add(sha)

    commit = read_object(git_repo_path, sha)
    message = commit.kvlm[None].decode("utf8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace("\"", "\\\"")

    if "\n" in message:  # 只保留第一行
        message = message[:message.index("\n")]

    print("  c_{0} [label=\"{1}: {2}\"]".format(sha, sha[0:7], message))
    assert commit.fmt == b'commit'

    if b'parent' not in commit.kvlm.keys():
        # 基本情况：初始提交。
        return

    parents = commit.kvlm[b'parent']

    if type(parents) is list:
        parents = list(parents)

    for p in parents:
        p = p.decode("ascii")
        print("  c_{0} -> c_{1};".format(sha, p))
        log_graphviz(git_repo_path, p, seen)

def tree_leaf_parse(raw: bytes, start: int = 0) -> tuple[GitTreeLeaf, int]:
    # 解析mode
    space_idx = raw.find(b" ", start)
    assert space_idx == 6
    mode = raw[start:space_idx].decode("ascii")

    # 解析path
    null_idx = raw.find(b"\x00", space_idx)
    path = raw[space_idx + 1 : null_idx].decode("utf-8")

    # 解析sha
    sha = raw[null_idx + 1 : null_idx + 21]
    sha_hex = sha.hex()

    leaf = GitTreeLeaf(mode, path, sha_hex)
    return leaf, null_idx + 21

def tree_parse(raw: bytes) -> list[GitTreeLeaf]:
    items = []
    idx = 0
    while idx < len(raw):
        leaf, next_idx = tree_leaf_parse(raw, idx)
        items.append(leaf)
        idx = next_idx
    assert idx == len(raw), "Malformed tree object"

    return items

def tree_serialize(items: list[GitTreeLeaf]) -> bytes:
    # 需要先对items按path排序
    items.sort(key=lambda x: x.path)

    ret = b""
    for item in items:
        ret += item.mode.encode("ascii") + b" " + item.path.encode("utf-8") + b"\x00" + bytes.fromhex(item.sha)
    return ret

def ls_tree(git_repo_path: str, sha: str, recursive: bool) -> None:
    obj = read_object(git_repo_path, sha)
    assert obj.get_type() == b"tree", "对象 {0} 不是一个树对象".format(sha)

    for item in obj.items:
        # 检查一下 item 的 mode 是否合法
        assert item.mode in ["40000", "100644", "100755", "120000"], "对象 {0} 的 mode {1} 不合法".format(sha, item.mode) 

        if recursive and item.mode[:5] == "040000":
            ls_tree(git_repo_path, item.sha, recursive)
        else:
            print("{0} {1} {2}\t{3}".format(item.mode, item.sha, item.path, item.path))

def tree_checkout(git_repo_path: str, commit_sha: str, path: str) -> None:
    commit = read_object(git_repo_path, commit_sha)
    assert commit.get_type() == b"commit", "对象 {0} 不是一个提交对象".format(commit_sha)

    tree_sha = commit.kvlm[b'tree'].decode("ascii")
    tree = read_object(git_repo_path, tree_sha)
    assert tree.get_type() == b"tree", "对象 {0} 不是一个树对象".format(tree_sha)

    for item in tree.items:
        item_path = os.path.join(path, item.path)
        if item.mode[:5] == "040000":
            # 如果是子树，递归调用
            os.makedirs(item_path, exist_ok=True)
            tree_checkout(git_repo_path, item.sha, item_path)
        else:
            # 如果是文件，写入文件
            blob = read_object(git_repo_path, item.sha)
            assert blob.get_type() == b"blob", "对象 {0} 不是一个blob对象".format(item.sha)

            with open(item_path, "wb") as f:
                f.write(blob.serialize())

# 将一个ref解析为sha并返回 
def resolve_ref(git_repo_path: str, ref_path: str) -> str:
    with open(ref_path, "r") as f:
        ref = f.read().strip()

    if ref.startswith("ref:"):
        # 如果是一个符号引用，递归解析
        ref = ref[5:]  # 去掉 "ref: "
        ref_path = git_repo_file(git_repo_path, ref)
        if ref_path is None:
            raise Exception("无法解析引用 {0}".format(ref))
        return resolve_ref(git_repo_path, ref_path)
    else:
        # 否则直接返回sha
        return ref 

# 递归地收集所有的ref
def collect_refs(git_repo_path: str, path: str = None):
    assert git_repo_path is not None

    if path is None:
        path = git_repo_dir(git_repo_path, "refs")

    refs = collections.OrderedDict()
    for name in sorted( os.listdir(path) ):
        ref_path = os.path.join(path, name)
        if os.path.isdir(ref_path):
            refs[name] = collect_refs(git_repo_path, ref_path)
        else:
            refs[name] = resolve_ref(git_repo_path, ref_path)

    return refs