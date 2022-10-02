import itertools
import os
import numpy as np

place_index_dict = {'cloud': {'place_index': 0, 'ip': '192.168.1.35'},
                    'master': {'place_index': 1, 'ip': '192.168.1.30'},
                    'mastera': {'place_index': 2, 'ip': '192.168.1.43'}}

class LatencyMonitor(object):
    """Latency monitoring class

    """

    def __init__(self, this_cluster_index, place_index_dict):
        self.this_cluster_index = this_cluster_index
        self.place_index_dict = place_index_dict
        self.cluster_ips = self.get_index_to_ip()
        self.cluster_indexes = [i for i in range(len(place_index_dict))]

    def get_index_to_ip(self):
        index_to_ip_dict = {}
        for name, item in self.place_index_dict.items():
            place_index = item['place_index']
            ip = item['ip']
            index_to_ip_dict[place_index] = ip
        return index_to_ip_dict

    def measure_rtt(self, cluster_to_ip):
        """Measure the latency (RTT) between two clusters

        Args:
            cluster_to_ip (str): Destination cluster's IP address

        Returns:
            (float): Returns the average RTT
        """
        resp = os.popen(f'ping {cluster_to_ip} -c 2').read()

        rtt_line = next(line for line in resp.split('\n') if 'rtt min/avg/max/mdev' in line)
        min_rtt = rtt_line.split('/')[3]
        avg_rtt = rtt_line.split('/')[4]
        max_rtt = rtt_line.split('/')[5]
        return float(avg_rtt)

    def do_measuring(self):
        """Measure latencies between all clusters

        Args:
            cluster_ips (dict[str, str]): cluster indexes and cluster IP addresses
            cluster_indexes (list[str]): List of cluster names

        Returns:
            (dict[tuple[str, str], float]): Returns the dictionary that gives two cluster name and the RTT between them
        """
        ping_pods_permutations = list(itertools.permutations(self.cluster_indexes, 2))
        rtt_matrix = {(i, j): np.inf for (i, j) in ping_pods_permutations}
        # TODO: Measure delays paralelly
        for i, j in ping_pods_permutations:
            if i == self.this_cluster_index and rtt_matrix[(i, j)] == np.inf:
                print("\tMeasuring {} <-> {}".format(i, j))
                rtt_matrix[(i, j)] = self.measure_rtt(self.cluster_ips[j])
                rtt_matrix[(j, i)] = rtt_matrix[(i, j)]
        return rtt_matrix
