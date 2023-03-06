import ipaddress
import random
import pickle
from bson.binary import Binary
import utils.persistency as persistency

class IPdistributor:
    def __init__(self, net_, name: str, pool=None):
        self.name = name
        self.net = ipaddress.ip_network(net_)

        if pool is None:
            self.pool = {
                'ip_start': self.net[1],
                'ip_end': self.net[-2]
            }
        else:
            self.pool = pool
            if 'ip_start' not in pool or 'ip_end' not in pool:
                raise ValueError('IP pool not completely defined')
            if ipaddress.IPv4Address(pool['ip_start']) not in self.net or ipaddress.IPv4Address(pool['ip_end']) not in self.net:
                raise ValueError('IP pool not in the network address range')
            self.pool = {
                'ip_start': ipaddress.IPv4Address(pool['ip_start']),
                'ip_end': ipaddress.IPv4Address(pool['ip_end'])
            }

        self.assigned = []
        self.unassigned = []

        for addr in self.net:
            if self.pool['ip_start'] <= addr <= self.pool['ip_end']:
                self.unassigned.append(ipaddress.IPv4Interface('{}/{}'.format(addr, self.net.netmask)))

        self.db = persistency.DB()
        self.save()

    def save(self):
        self.db.update_DB("ip_address", {"ip_distributor": Binary(pickle.dumps(self, -1))}, {'id': self.name})

    def destroy(self):
        self.db.delete_DB("ip_address", {'id': self.name})

    def dump(self, owner=None):
        if owner is None:
            return self.assigned
        else:
            return [item for item in self.assigned if item['owner'] == owner]

    def get(self, owner, withprefix=False):
        if len(self.unassigned) == 0:
            return False
        ip_ = random.choice(self.unassigned)
        self.unassigned.remove(ip_)
        self.assigned.append({'ip': ip_, 'owner': owner})
        self.save()
        if withprefix:
            return str(ip_.with_prefixlen)
        else:
            return str(ip_.ip)

    def reserve(self, ip_, owner, persistent_dump=True):
        ip = ipaddress.IPv4Interface(ip_)
        if ip in self.unassigned:
            self.unassigned.remove(ip)
            self.assigned.append({'ip': ip, 'owner': owner})
            self.save()
            return True
        else:
            return False

    def release(self, ip_):
        ip = ipaddress.IPv4Interface(ip_)
        for e in self.assigned:
            if ip == e['ip']:
                # self.db.delete_DB(
                #    "ip_addresses", {"net": self.name, "ip": str(ip)})
                self.unassigned.append(ip)
                self.assigned.remove(e)
                print('ip address found')
                self.save()
                return True
        print('ip address found')
        return False

    def release_all(self, owner):

        for e in self.assigned:
            if owner == e['owner']:
                self.unassigned.append(e['ip'])
                self.assigned.remove(e)
        self.save()
        # self.db.delete_DB("ip_addresses", {"net": self.name, "owner": owner})


a = IPdistributor('130.251.17.0/24', "rete", pool={'ip_start': '130.251.17.11', 'ip_end': '130.251.17.16'})
ip = a.get('test', withprefix=False)
print(ip)
a.release(ip)
ip = a.get('test', withprefix=True)
print(a.dump('test'))
print(ip)
a.release(ip)
a.release_all('test')
"""
d = IPdistributor(u'192.0.2.0/24', "rete")
print(d.get('pippo'))
print(d.reserve(u'192.0.2.3', 'paperino'))
print(d.reserve(u'192.0.2.3', 'pippo'))
print(d.reserve(u'192.0.2.4', 'pippo'))
print(d.reserve(u'192.0.2.5', 'pippo'))
print(d.dump('paperino'))
print(d.release_all('paperino'))

print(d.dump('pippo'))
"""
