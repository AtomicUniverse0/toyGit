from __future__ import annotations
from configparser import ConfigParser
import argparse
import sys
import os

from utils import git_repo_dir, git_repo_file, read_object, hash_object, log_graphviz
from utils import ls_tree, tree_checkout, collect_refs, create_tag, find_object, ls_files
from utils import check_ignore, read_gitignoreobj, read_index, status_on_branch, status_index_diff_head, status_index_diff_worktree

parser = argparse.ArgumentParser(description="Toy Git")
subparser = parser.add_subparsers(title = "Commands", dest= "command")
subparser.required = True

sub_init = subparser.add_parser("init", help="初始化一个新的git仓库")
sub_init.add_argument("path", nargs= "?", default= ".", help = "仓库所在的位置")

sub_cat_file = subparser.add_parser("cat-file", help="显示git对象的内容")
sub_cat_file.add_argument("type", choices=["blob", "commit", "tree", "tag"], help="对象类型")
sub_cat_file.add_argument("object_sha1", help="对象的sha1值")

sub_hash_object = subparser.add_parser("hash-object", help="计算文件的sha1值，并将其写入git对象数据库")
sub_hash_object.add_argument("-w", action="store_true", help="将对象写入git对象数据库")
sub_hash_object.add_argument("-t", choices=["blob", "commit", "tree", "tag"], default="blob", help="对象类型")
sub_hash_object.add_argument("path", help="文件路径")

sub_log = subparser.add_parser("log", help="显示给定提交的历史。")
sub_log.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="开始的提交。")

sub_ls_tree = subparser.add_parser("ls-tree", help="显示给定树对象的内容。")
sub_ls_tree.add_argument("tree", help="树对象，可以是引用，也可以是哈希")
sub_ls_tree.add_argument("-r", action="store_true", help="递归显示子树的内容")

# 这是一个简化版的checkout，只会在一个空目录中写入 commit 对应的树
sub_checkout = subparser.add_parser("checkout", help="检出给定的提交。")
sub_checkout.add_argument("commit", help="要检出的提交的sha1值")
sub_checkout.add_argument("path", help="检出到的目录")

# 简化版的tag命令。 
# toyGit tag 展示所有的标签
# toyGit tag name [object] 创建一个新的简易标签，指向给定的对象，如果没有指定对象，则指向当前的HEAD
# toyGit tag -a name [object] 创建一个新的标签对象，附注内容从标准输入读取
sub_tag = subparser.add_parser("tag", help="创建一个新的标签，或者显示所有的标签。")
sub_tag.add_argument("-a", action="store_true", help="创建一个附注标签")
sub_tag.add_argument("name", nargs="?", help="标签的名字")
sub_tag.add_argument("object", nargs="?", help="标签指向的对象，如果没有指定，则指向当前的HEAD")

sub_rev_parse = subparser.add_parser("rev-parse", help="解析给定的引用，输出对应的sha1值。")
sub_rev_parse.add_argument("--wyag-type", metavar = "type", dest = "type", default = None, choices=["blob", "commit", "tree", "tag"], help="指定引用的类型")
sub_rev_parse.add_argument("name", help="引用的名字")

sub_ls_files = subparser.add_parser("ls-files", help="显示索引中的文件列表。")
sub_ls_files.add_argument("-s", action="store_true", help="显示索引中的文件的详细信息")

sub_check_ignore = subparser.add_parser("check-ignore", help="检查给定的路径是否被忽略。")
sub_check_ignore.add_argument("paths", nargs="+", help="要检查的路径列表")

sub_status = subparser.add_parser("status", help="显示工作区和索引的状态。")

class GitRepository:
    worktree : str = None
    gitdir : str= None
    config : ConfigParser = None

    """若git仓库不存在，则创建"""
    def __init__(self, path: str):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")
        
        if not os.path.isdir(self.worktree):
            raise RuntimeError("Invalid worktree: " + path)
        
        if not os.path.exists(self.gitdir):   # Git仓库不存在，需要新建
            GitRepository._create_new_repo(path)
        
        assert os.path.isdir(self.gitdir), "Error: .git should be a directory"             

        self.config = ConfigParser()
        self.config.read( git_repo_file(self.gitdir, "config") )

        version = int(self.config.get("core", "repositoryformatversion"))
        assert version == 0, "Unsupported repositoryformatversion: " + str(version)
    
    """在path目录下创建一个新的git仓库，调用者需要保证path已经存在"""
    @staticmethod
    def _create_new_repo(path: str) -> None:
        assert os.path.isdir(path)

        git_repo_path = os.path.join(path, ".git")
        assert git_repo_dir(git_repo_path, "branches", mkdir=True)
        assert git_repo_dir(git_repo_path, "objects", mkdir=True)
        assert git_repo_dir(git_repo_path, "refs", "tags", mkdir=True)
        assert git_repo_dir(git_repo_path, "refs", "heads", mkdir=True)

        with open( git_repo_file(git_repo_path, "description", mkdir=True), "w") as f:
            f.write("Unnamed repository; edit this file 'description' to name the repository.\n")
        
        with open( git_repo_file(git_repo_path, "HEAD", mkdir=True), "w") as f:
            f.write("ref: refs/heads/master\n")

        with open( git_repo_file(git_repo_path, "config", mkdir=True), "w") as f:
            config = ConfigParser()
            config.add_section("core")
            config.set("core", "repositoryformatversion", "0")
            config.set("core", "filemode", "false")
            config.set("core", "bare", "false")
            config.write(f)

    @staticmethod
    def find_repo(path=".", required=True) -> GitRepository:
        path = os.path.realpath(path)

        if os.path.isdir(os.path.join(path, ".git")):
            return GitRepository(path)

        # 如果没有返回，递归查找父目录
        parent = os.path.realpath(os.path.join(path, ".."))

        if parent == path:
            # 找到根目录了，结果还没找到
            if required:
                raise Exception("没有 git 目录。")
            else:
                return None

        # 递归情况
        return GitRepository.find_repo(parent, required)

def cmd_init(args) -> None:
    try:
        print("初始化git仓库，路径为: %s" % args.path)
        repo = GitRepository(args.path)
        print(f"Initialized empty Git repository in {repo.gitdir}")
    except RuntimeError as e:
        print(e)

def cmd_cat_file(args) -> None:
    repo = GitRepository.find_repo()
    # 后续会扩展
    assert args.type in ["blob", "commit"]
    blob = read_object(repo.gitdir, find_object(repo.gitdir, args.object_sha1) )        
    print(blob.serialize())

def cmd_hash_object(args) -> None:
    if args.w:
        git_repo_path = GitRepository.find_repo().gitdir
    else:
        git_repo_path = None

    sha = hash_object(args.path, args.t, git_repo_path)
    print(sha)

def cmd_log(args) -> None:
    repo = GitRepository.find_repo()

    print("digraph wyaglog{")
    print("  node[shape=rect]")
    log_graphviz(repo.gitdir, args.commit, set())
    print("}")

def cmd_ls_tree(args) -> None:
    repo = GitRepository.find_repo()
    ls_tree(repo.gitdir, args.sha, args.r)

def cmd_tree_checkout(args) -> None:
    repo = GitRepository.find_repo()
    tree_checkout(repo.gitdir, args.commit, args.path)

def print_refs(refs, prefix="", with_sha = True) -> None:
    for name, value in refs.items():
        if isinstance(value, dict):
            print_refs(value, prefix + name + "/")
        else:
            msg = "{0}{1} {2}".format(prefix, name, value) if with_sha else "{0}{1}".format(prefix, name)
            print(msg)

def cmd_show_ref(args) -> None:
    repo = GitRepository.find_repo()
    refs = collect_refs(repo.gitdir)
    print_refs(refs)

def cmd_tag(args) -> None:
    repo = GitRepository.find_repo()

    if args.name is None:
        # 展示所有的标签
        refs = collect_refs(repo.gitdir, os.path.join(repo.gitdir, "refs", "tags"))
        print_refs(refs, with_sha=False)
    else:
        create_tag(repo.gitdir, args.name, args.object, args.a)

def cmd_rev_parse(args) -> None:
    repo = GitRepository.find_repo()
    sha = find_object(repo.gitdir, args.name, args.type)
    print(sha)

def cmd_ls_files(args) -> None:
    repo = GitRepository.find_repo()
    ls_files(repo.gitdir, args.s)

def cmd_check_ignore(args) -> None:
    repo = GitRepository.find_repo()
    gitIgnore = read_gitignoreobj(repo.gitdir)
    for path in args.paths:
        if check_ignore(gitIgnore, path):
            print(path)

def cmd_status(args) -> None:
    repo = GitRepository.find_repo()

    status_on_branch(repo.gitdir)
    print()

    # 查看当前的 index 于 HEAD 的差异，从而得出被修改的文件列表
    index = read_index(repo.gitdir)
    status_index_diff_head(repo.gitdir, index)
    print()

    status_index_diff_worktree(repo.worktree, repo.gitdir, index)

def main(argv = sys.argv[1:]) -> None:
    args = parser.parse_args(argv)
    match args.command:
        case "init" : 
            cmd_init(args)
        case "cat-file" :
            cmd_cat_file(args)
        case "hash-object":
            cmd_hash_object(args)
        case "log":
            cmd_log(args)
        case "ls-tree":
            cmd_ls_tree(args)
        case "checkout":
            cmd_tree_checkout(args)
        case "show-ref":
            cmd_show_ref(args)
        case "tag":
            cmd_tag(args)
        case "rev-parse":
            cmd_rev_parse(args)
        case "check-ignore":
            cmd_check_ignore(args)
        case "status":
            cmd_status(args)
        case _  : 
            print("无效命令。")