import os

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

