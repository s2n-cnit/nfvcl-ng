import glob
import os
import shutil
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader

from src.nfvcl.utils.util import get_nfvcl_config


def create_tmp_file(filename: str, sub_folder: str = None, file_can_exist: bool = False) -> Path:
    """
    Creates a file in the given sub_folder with the given filename. The main tmp folder is taken from nfvcl config file.
    By default, this function creates a temporary file in '/tmp/sub_folder/filename'.
    Folders are created recursively if not existing.
    Args:
        filename: The file name (e.g. 'file.json')
        sub_folder: The subfolder name (e.g. 'sub_folder' or 'sub_folder/sub_sub_folder/sub_sub_sub_folder')

    Returns:
        The Path to the created file (e.g. PosixPath('/tmp/sub_folder/sub_sub_folder/file.json'))
    """
    nfvcl_config = get_nfvcl_config()
    tmp_base_folder = nfvcl_config.nfvcl.tmp_folder
    return create_file(tmp_base_folder, filename, sub_folder, file_can_exist)


def create_tmp_folder(sub_folder: str = None) -> Path:
    """
    Create a temporary subfolder with the given path in the main tmp folder.
    Args:
        sub_folder: the subfolder which will be created in the main tmp folder from nfvcl config file. Example values are: "test/jojo/subfolder" or "folder"
        will result in something like '/tmp/test/jojo/subfolder' depending on the value in the cfg file (by default '/tmp').

    Returns:
        The Path of the created tmp folder
    """
    nfvcl_config = get_nfvcl_config()
    tmp_folder = nfvcl_config.nfvcl.tmp_folder
    return create_folder(tmp_folder, sub_folder)


def create_accessible_file(filename: str, sub_folder: str = None, file_can_exist: bool = False) -> Path:
    """
    Creates a file in the given, accessible, sub_folder with the given filename. The main accessible(mounted by web server) folder is taken from nfvcl config file.
    By default, this function creates an accessible file in 'mounted_folder/sub_folder/filename'.
    The file is then accessible using 'NFVCL_URL:NFVCL_PORT/files/sub_sub_folder/filename' path.
    Folders are created recursively if not existing.
    Args:
        filename: The file name (e.g. 'file.json')
        sub_folder: The subfolder name (e.g. 'sub_folder' or 'sub_folder/sub_sub_folder/sub_sub_sub_folder')

    Returns:
        The Path to the created file (e.g. PosixPath('mounted_folder/sub_folder/sub_sub_folder/file.json'))
    """
    nfvcl_config = get_nfvcl_config()
    day_2_base_folder = nfvcl_config.nfvcl.mounted_folder
    return create_file(day_2_base_folder, filename, sub_folder,file_can_exist)


def create_accessible_folder(sub_folder: str = None) -> Path:
    """
    Create a temporary subfolder with the given path in the main accessible (mounted by the web server) folder.
    Args:
        sub_folder: the subfolder which will be created in the main accessible folder given from nfvcl config file. Example values are: "test/jojo/subfolder" or "folder"
        will result in something like 'mounted_folder/test/jojo/subfolder' depending on the value in the cfg file (by default 'mounted_folder/').

    Returns:
        The Path of the created accessible folder
    """
    nfvcl_config = get_nfvcl_config()
    day_2_base_folder = nfvcl_config.nfvcl.mounted_folder
    return create_folder(day_2_base_folder, sub_folder)


def create_folder(base_folder_path: str, sub_folder: str = None) -> Path:
    """
    Creates a subfolder in the given base_folder. If parents do not exist, they will be created.
    Args:
        base_folder_path: The base folder (e.g. '/tmp')
        sub_folder:  The sub folder (e.g. 'test/jojo/subfolder')

    Returns:
        The path of the created folder (e.g. PosixPath('/tmp/test/jojo/subfolder'))
    """
    base_folder = Path(base_folder_path)
    if not base_folder.exists():
        base_folder.mkdir(exist_ok=True, parents=True)
    if base_folder.exists() and base_folder.is_dir():
        if sub_folder is not None:
            folder = base_folder / sub_folder
            if not folder.exists():
                folder.mkdir(exist_ok=True, parents=True)
            if not (folder.exists() and folder.is_dir()):
                raise FileExistsError(f"{folder} already exists and is not a directory but a file.")
        else:
            folder = base_folder

        return folder
    else:
        raise FileExistsError(f"The day 2 folder '{base_folder}' exists and is not a directory but a file.")


def create_file(base_folder_path: str, filename: str, sub_folder: str = None, file_can_exist: bool = False) -> Path:
    folder = create_folder(base_folder_path, sub_folder)
    file = folder / filename
    if file.exists() and not file_can_exist:
        raise FileExistsError(f"{file} already exists")
    else:
        file.touch()
        return file


def render_file_from_template_to_file(path: Path, render_dict: dict, prefix_to_name: str = "", extension: str = None) -> Path:
    """
    Render a template file using the render_dict dictionary. Use the keys and their values to give a value at the
    variables present in the template file.
    The result of the rendering is placed in day2_files/filename.extension and the path is returned by this method.

    Args:
        path: the path of the file template

        render_dict: the dictionary containing values to be used in template variables. The name of the variable should
        be the same of the key in this dictionary.

        prefix_to_name: A prefix to be appended to generated file.

        extension: The new extension to be given at the file (e.g '.yaml', '.txt', ...)

    Returns:
        the path of the generated file from the template.
    """
    if not path.exists():
        raise ValueError("The file to be rendered does not exist")
    if not path.is_file():
        raise ValueError("The file to be rendered is not a file but a folder")

    env_path = path.parent
    filename = path.name

    env = Environment(loader=FileSystemLoader(env_path), extensions=['jinja2_ansible_filters.AnsibleCoreFiltersExtension'])

    template = env.get_template(filename)
    data = template.render(confvar=render_dict)

    if extension:
        new_file_path = create_tmp_file(f"{prefix_to_name}{path.stem}{extension}", "rendered_files", True)
    else:
        new_file_path = create_tmp_file(f"{prefix_to_name}{path.name}", "rendered_files", True)

    new_file_path.write_text(data)

    return new_file_path


def render_file_jinja2_to_str(file_to_render: Path, confvar: dict):
    """
    Takes a file and renders it using values in the dictionary
    Args:
        file_to_render: The file to be rendered containing '{{ variable123 }}' references
        confvar: A dictionary containing the variables to be rendered. { 'variable123': 'desiredvalue' }

    Returns:
        The rendered file
    """
    env = Environment(loader=FileSystemLoader(file_to_render.parent))
    template = env.get_template(file_to_render.name)

    return template.render(**confvar)


def render_files_from_template(paths: List[Path], render_dict, files_name_prefix: str = "TEST") -> List[Path]:
    """
    Render multiple files from their templates. For further details looks at render_file_from_template function.
    Then the list of generated files (paths) is returned

    Args:
        paths: the list of file templates

        render_dict: the dictionary containing values to be used in template variables. The name of the variable should
        be the same of the key in this dictionary.

        files_name_prefix: A prefix to be appended to generated files.

    Returns:
        A list path representing generated files.
    """
    to_return: List[Path] = []
    for file_path in paths:
        to_return.append(render_file_from_template_to_file(path=file_path, render_dict=render_dict,
                                                           prefix_to_name=files_name_prefix))
    return to_return


def remove_files_by_pattern(folder: str, name_pattern: str):
    """
    Remove all files in the target folder that match the pattern condition
    Args:
        folder: the folder in witch files are located. ("./day2_files" or "day2_files" or "/tmp/nsd_packages"

        name_pattern: a file name ("DV87AO_vyos_2-3.yaml") or a pattern for multiple files ("DV87AO_*")

    Returns:

    """
    source_path: str = "{}/{}".format(folder, name_pattern)
    path_list = glob.glob(source_path)
    for path in path_list:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
