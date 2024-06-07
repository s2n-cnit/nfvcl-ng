import json
from nfvcl.models.openstack.images import ImageList


def get_nfvcl_image_list() -> ImageList:
    """
    Loads the OPENSTACK image list needed by the nfvcl from the json file in config_templates/openstack/images.json
    Returns:
        The list of images with the url where to dowmload them
    """
    file = open("src/nfvcl/config_templates/openstack/images.json")
    dictionary = json.loads(file.read())
    image_list = ImageList.model_validate(dictionary)
    return image_list
