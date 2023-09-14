import utils.persistency as persistency
from models.config_model import NFVCLConfigModel
from nfvo.osm_nbi_util import get_osm_nbi_utils
from utils.log import create_logger
from datetime import datetime
import yaml
import os.path
import hashlib
from utils.util import get_nfvcl_config

nbiUtil = get_osm_nbi_utils()
nfvcl_config: NFVCLConfigModel = get_nfvcl_config()

logger = create_logger('HelmRepository')
db = persistency.DB()
chart_path = 'helm_charts/'
helm_url_prefix = '/helm_repo/'


def get_timestring() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()+'Z'

class HelmRepository:
    @staticmethod
    def get_entries() -> list:
        return db.find_DB('helm_charts', {})

    def set_entry(self, item: dict):
        # FIXME: check versions and update db item
        for key in ['description', 'name', 'version']:
            if key not in item.keys():
                raise ValueError("Chart Entry is missing of the >{}< key".format(key))

        item['created'] = get_timestring()
        filename = '{}-{}.tgz'.format(item['name'], item['version'])
        if not os.path.isfile(chart_path + 'charts/' + filename):
            print(chart_path + 'charts/' + filename)
            raise ValueError("chart {} not existing".format(filename))
        with open(chart_path + 'charts/' + filename, "rb") as f:
            file_bytes = f.read()
            item['digest'] = hashlib.sha256(file_bytes).hexdigest()

        item['home'] = 'https://helm.sh/helm'
        item['sources'] = ['https://github.com/helm/helm']
        item['urls'] = ['http://{}:{}{}charts/{}'.format(nfvcl_config.nfvcl.ip, nfvcl_config.nfvcl.port, helm_url_prefix, filename)]

        db.insert_DB('helm_charts', item)
        self.create_index()

    def create_index(self):
        global yaml_file
        db_charts = self.get_entries()
        registry_index = {'apiVersion': 'v1', 'entries': {}, 'generated': get_timestring()}
        for c in db_charts:
            if c['name'] not in registry_index['entries']:
                logger.info("found new entry {}".format(c['name']))
                registry_index['entries'][str(c['name'])] = []
            # remove the _id key from the c dict
            c.pop('_id', None)

            # update the URL with the current IP address
            filename = '{}-{}.tgz'.format(c['name'], c['version'])
            c['urls'] = ['http://{}:{}{}charts/{}'.format(nfvcl_config.nfvcl.ip, nfvcl_config.nfvcl.port, helm_url_prefix, filename)]
            # aggregate all the version of the same chart into a same array
            registry_index['entries'][c['name']].append(c)
        try:
            yaml_file = open(chart_path + 'index.yaml', 'w')
        except FileNotFoundError as e:
            logger.error('Helm chart folder not existing, recreating')
            os.mkdir(chart_path)
            yaml_file = open(chart_path + 'index.yaml', 'w')
        except Exception as e:
            logger.error(e.with_traceback(None))
        finally:
            logger.info("dumping registry file")
            yaml.dump(registry_index, yaml_file)


helm_repo = HelmRepository()
helm_repo.create_index()

