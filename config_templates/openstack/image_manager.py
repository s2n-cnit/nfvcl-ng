import json
from models.openstack.images import ImageList

def get_nfvcl_image_list() -> ImageList:
    file = open("config_templates/openstack/images.json")
    dictionary = json.loads(file.read())
    image_list = ImageList.model_validate(dictionary)
    return image_list
