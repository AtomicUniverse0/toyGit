import os
import zlib
import hashlib
import collections
import re
import math
import datetime
import pwd
import grp
from GitObject import GitObject, GitCommit, GitTree, GitTag, GitBlob, GitTreeLeaf, GitIndex, GitIndexEntry


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

def ls_tree(git_repo_path: str, tree: str, recursive: bool) -> None:
    sha = find_object(git_repo_path, tree, type="tree")
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

def create_tag(git_repo_path: str, tag_name: str, object_sha: str, create_tag_object: bool) -> None:
    if object_sha is None:
        # 如果没有指定对象，则指向当前的HEAD
        head_ref_path = git_repo_file(git_repo_path, "HEAD")
        if head_ref_path is None:
            raise Exception("无法解析引用 HEAD")
        object_sha = resolve_ref(git_repo_path, head_ref_path)

    if create_tag_object:
        # 创建一个tag对象
        tag = GitTag(b"")
        tag.kvlm = collections.OrderedDict()
        tag.kvlm[b"object"] = object_sha.encode("ascii")
        tag.kvlm[b"type"] = b"commit"
        tag.kvlm[b"tag"] = tag_name.encode("utf-8")
        tag.kvlm[b"tagger"] = b"ToyGit <toygit@example.com>"
        tag.kvlm[None] = b"create automatic tag by ToyGit"

        # 写入对象数据库
        tag_sha = hash_object(git_repo_path, tag.serialize(), "tag", write=True)

        # 更新refs/tags
        tag_ref_path = git_repo_file(git_repo_path, "refs", "tags", tag_name, mkdir=True)
        with open(tag_ref_path, "w") as f:
            f.write(tag_sha + "\n")
    else:
        tag_ref_path = git_repo_file(git_repo_path, "refs", "tags", tag_name, mkdir=True)
        with open(tag_ref_path, "w") as f:
            f.write(object_sha + "\n")

def resolve_object(git_repo_path: str, name: str)-> list[str]:
    """将名称解析为 repo 中的对象哈希。

    此函数支持：
    - HEAD 字面量
    - 短哈希和长哈希
    - 标签
    - 分支
    - 远程分支
    """

    candidates = list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{4,40}$")

    # 空字符串？终止。
    if not name.strip():
        return None

    # 是Head?
    if name == "HEAD":
        return [ resolve_ref(git_repo_path, git_repo_file(git_repo_path, "HEAD")) ]

    # 如果是十六进制字符串，尝试查找哈希。
    if hashRE.match(name):
        # 这可能是一个哈希，可能是短的或完整的。4 是 Git 认为某个东西是短哈希的最小长度。
        # 这个限制在 man git-rev-parse 中有说明。
        name = name.lower()
        prefix = name[0:2]
        path = git_repo_dir(git_repo_path, "objects", prefix, mkdir=False)
        if path:
            rem = name[2:]
            for f in os.listdir(path):
                if f.startswith(rem):
                    # 注意字符串的 startswith() 本身适用于完整哈希。
                    candidates.append(prefix + f)

    # 尝试查找引用。
    as_tag = resolve_ref(git_repo_path, "refs/tags/" + name)
    if as_tag:  # 找到了标签吗？
        candidates.append(as_tag)

    as_branch = resolve_ref(git_repo_path, "refs/heads/" + name)
    if as_branch:  # 找到了分支吗？
        candidates.append(as_branch)

    return candidates

# name 可能是各种形式的名称，find_object负责将这些 name 转化为对象的 sha1
def find_object(git_repo_path: str, name: str, type: str = None, follow: bool = True) -> str:
    candidates = resolve_object(git_repo_path, name)
    
    if len(candidates) == 0:
        raise Exception("无法解析对象 {0}".format(name))

    if len(candidates) > 1:
        raise Exception("对象 {0} 不唯一，候选对象有: {1}".format(name, candidates))

    sha = candidates[0]

    if type is None:
        return sha

    while True:
        obj = read_object(git_repo_path, sha)

        if obj.get_type() == type.encode("ascii"):
            return sha

        if not follow:
            return None

        if obj.get_type() == b"tag":
            sha = obj.kvlm[b"object"].decode("ascii")
        elif obj.get_type() == b"commit" and type == "tree":
            sha = obj.kvlm[b"tree"].decode("ascii")
        else:
            return None

# 读取并解析一个索引文件
def read_index(git_repo_path: str):
    index_file = git_repo_file(git_repo_path, "index")

    # 新仓库没有索引文件！
    if not os.path.exists(index_file):
        return GitIndex()

    with open(index_file, 'rb') as f:
        raw = f.read()

    header = raw[:12]
    signature = header[:4]
    assert signature == b"DIRC"  # 代表 "DirCache"
    version = int.from_bytes(header[4:8], "big")
    assert version == 2, "wyag 仅支持索引文件版本 2"
    count = int.from_bytes(header[8:12], "big")

    entries = list()

    content = raw[12:]
    idx = 0
    for i in range(0, count):
        # 读取创建时间，作为 UNIX 时间戳（自 1970-01-01 00:00:00 起的秒数）
        ctime_s = int.from_bytes(content[idx: idx+4], "big")
        # 读取创建时间，作为该时间戳后的纳秒数，以获得额外的精度
        ctime_ns = int.from_bytes(content[idx+4: idx+8], "big")
        # 同样处理修改时间：先是从纪元起的秒数
        mtime_s = int.from_bytes(content[idx+8: idx+12], "big")
        # 然后是额外的纳秒数
        mtime_ns = int.from_bytes(content[idx+12: idx+16], "big")
        # 设备 ID
        dev = int.from_bytes(content[idx+16: idx+20], "big")
        # inode
        ino = int.from_bytes(content[idx+20: idx+24], "big")
        # 忽略的字段
        unused = int.from_bytes(content[idx+24: idx+26], "big")
        assert 0 == unused
        mode = int.from_bytes(content[idx+26: idx+28], "big")
        mode_type = mode >> 12
        assert mode_type in [0b1000, 0b1010, 0b1110]
        mode_perms = mode & 0b0000000111111111
        # 用户 ID
        uid = int.from_bytes(content[idx+28: idx+32], "big")
        # 组 ID
        gid = int.from_bytes(content[idx+32: idx+36], "big")
        # 大小
        fsize = int.from_bytes(content[idx+36: idx+40], "big")
        # SHA，对象 ID。我们将其存储为小写的十六进制字符串，以保持一致性
        sha = format(int.from_bytes(content[idx+40: idx+60], "big"), "040x")
        # 我们将忽略的标志
        flags = int.from_bytes(content[idx+60: idx+62], "big")
        # 解析标志
        flag_assume_valid = (flags & 0b1000000000000000) != 0
        flag_extended = (flags & 0b0100000000000000) != 0
        assert not flag_extended
        flag_stage = flags & 0b0011000000000000
        # 名称的长度。这是以 12 位存储的，最大值为 0xFFF，4095。由于名称有时可能超过该长度，git 将 0xFFF 视为表示至少 0xFFF，并寻找最终的 0x00 以找到名称的结束——这会带来小而可能非常罕见的性能损失。
        name_length = flags & 0b0000111111111111

        # 到目前为止我们已经读取了 62 字节。
        idx += 62

        if name_length < 0xFFF:
            assert content[idx + name_length] == 0x00
            raw_name = content[idx:idx+name_length]
            idx += name_length + 1
        else:
            print("注意：名称长度为 0x{:X} 字节。".format(name_length))
            # 这可能没有经过足够的测试。它适用于长度恰好为 0xFFF 字节的路径。任何额外字节可能会在 git、我的 shell 和我的文件系统之间造成问题。
            null_idx = content.find(b'\x00', idx + 0xFFF)
            raw_name = content[idx:null_idx]
            idx = null_idx + 1

        # 将名称解析为 UTF-8
        name = raw_name.decode("utf8")

        # 数据按 8 字节的倍数填充以进行指针对齐，因此我们跳过需要的字节，以便下次读取从正确的位置开始。
        idx = 8 * math.ceil(idx / 8)

        # 然后我们将此条目添加到我们的列表中。
        entries.append(GitIndexEntry(ctime=(ctime_s, ctime_ns),
                                     mtime=(mtime_s, mtime_ns),
                                     dev=dev,
                                     ino=ino,
                                     mode_type=mode_type,
                                     mode_perms=mode_perms,
                                     uid=uid,
                                     gid=gid,
                                     fsize=fsize,
                                     sha=sha,
                                     flag_assume_valid=flag_assume_valid,
                                     flag_stage=flag_stage,
                                     name=name))

    return GitIndex(version=version, entries=entries)

def ls_files(git_repo_path: str, show_details: bool) -> None:
    index = read_index(git_repo_path)

    for entry in index.entries:
        print(entry.name)

        if show_details:
            print("  {}，权限：{:o}".format({ 0b1000: "常规文件", 0b1010: "符号链接",0b1110: "git 链接" }[entry.mode_type], entry.mode_perms))
            print("  对应的 blob: {}".format(entry.sha))
            print("  创建时间：{}.{}, 修改时间：{}.{}".format( datetime.fromtimestamp(entry.ctime[0]), entry.ctime[1], datetime.fromtimestamp(entry.mtime[0]), entry.mtime[1]))
            print("  设备：{}, inode: {}".format(entry.dev, entry.ino))
            print("  用户：{} ({})  组：{} ({})".format( pwd.getpwuid(entry.uid).pw_name, entry.uid, grp.getgrgid(entry.gid).gr_name, entry.gid))
            print("  标志：stage={} assume_valid={}".format( entry.flag_stage, entry.flag_assume_valid))