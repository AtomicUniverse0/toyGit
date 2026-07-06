from configparser import ConfigParser
import argparse
import sys
import os

from utils import git_repo_dir, git_repo_file


parser = argparse.ArgumentParser(description="Toy Git")
subparser = parser.add_subparsers(title = "Commands", dest= "command")
subparser.required = True

sub_init = subparser.add_parser("init", help="初始化一个新的git仓库")
sub_init.add_argument("path", nargs= "?", default= ".", help = "仓库所在的位置")


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


def cmd_init(args) -> None:
    try:
        print("初始化git仓库，路径为: %s" % args.path)
        repo = GitRepository(args.path)
        print(f"Initialized empty Git repository in {repo.gitdir}")
    except RuntimeError as e:
        print(e)

def main(argv = sys.argv[1:]) -> None:
    args = parser.parse_args(argv)
    match args.command:
        case "init" : 
            cmd_init(args)
        case _  : 
            print("无效命令。")

