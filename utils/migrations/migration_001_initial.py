from pymongo.database import Database


def upgrade(db: Database):
    blue_inst_v2_collection = db.get_collection("blue-inst-v2")
    blueprint_instances = blue_inst_v2_collection.find()
    for blueprint_instance in blueprint_instances:
        for resource in blueprint_instance["registered_resources"].values():
            if resource["type"] == "blueprints_ng.resources.VmResource":
                for key, net_res in resource["value"]["network_interfaces"].items():
                    if isinstance(net_res, dict):
                        print(f"Update blueprint instance: {blueprint_instance['id']}")
                        resource["value"]["network_interfaces"][key] = [net_res]

        blue_inst_v2_collection.replace_one({"_id": blueprint_instance["_id"]}, blueprint_instance)

def downgrade(db: Database):
    blue_inst_v2_collection = db.get_collection("blue-inst-v2")
    blueprint_instances = blue_inst_v2_collection.find()
    for blueprint_instance in blueprint_instances:
        for resource in blueprint_instance["registered_resources"].values():
            if resource["type"] == "blueprints_ng.resources.VmResource":
                for key, net_res in resource["value"]["network_interfaces"].items():
                    if isinstance(net_res, list):
                        print(f"Update blueprint instance: {blueprint_instance['id']}")
                        resource["value"]["network_interfaces"][key] = net_res[0]

        blue_inst_v2_collection.replace_one({"_id": blueprint_instance["_id"]}, blueprint_instance)

