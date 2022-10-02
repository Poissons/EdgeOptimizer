import json
import flask
from kubernetes import client, config
import requests

config_files = {'cloudmaster': r"./all-config/config-cloud",
                'master': r"./all-config/config-edge1",
                'mastera': r"./all-config/config-edge2"}

app = flask.Flask(__name__)


def list_one_cluster_namespace(api_instance):
    namespace_list = []
    for ns in api_instance.list_namespace().items:
        namespace_list.append(ns.metadata.name)
    return namespace_list


def list_one_cluster_nodes(api_instance):
    api_response = api_instance.list_node()
    data = {}
    for i in api_response.items:
        conditions = {}
        for j in i.status.conditions:
            conditions[j.type] = j.status
        data[i.metadata.name] = {'name': i.metadata.name,
                                 'status': i.status.conditions[-1].type
                                 if i.status.conditions[-1].status == 'True' else 'NotReady',
                                 'allocatable': i.status.allocatable,
                                 'capacity': i.status.capacity,
                                 'conditions': conditions,
                                 'ip': i.status.addresses[0].address,
                                 'kubelet_version': i.status.node_info.kubelet_version,
                                 'os_image': i.status.node_info.os_image,
                                 }
    # data = requests.get('http://localhost:8001/apis/metrics.k8s.io/v1beta1/nodes').json()
    return data


def list_one_cluster_pods(api_instance, namespace):
    ret = api_instance.list_pod_for_all_namespaces(watch=False)
    data = {}
    for i in ret.items:
        if i.metadata.namespace == namespace:
            print(i)
            data[i.metadata.name] = {
                'name': i.metadata.name,
                'namespace': i.metadata.namespace,
                'node_name': i.spec.node_name,
                'host_ip': i.status.host_ip,
                'pod_ip': i.status.pod_ip,
                'labels': i.metadata.labels,
                'phase': i.status.phase
            }
    return data


def list_one_cluster_services(api_instance):
    ret = api_instance.list_service_for_all_namespaces(watch=False)
    data = {}
    for i in ret.items:
        data[i.metadata.name] = {
            'name': i.metadata.name,
            'kind': i.kind,
            'cluster_ip': i.spec.cluster_ip,
            'namespace': i.metadata.namespace,
            'ports': i.spec.ports
        }
    return data


@app.route('/list_cluster_pods/<master_name>/<namespace>', methods=['GET'])
def list_cluster_pods(master_name, namespace):
    data = {}
    config_path = config_files[master_name]
    config.kube_config.load_kube_config(config_file=config_path)
    api_instance = client.CoreV1Api()
    return list_one_cluster_pods(api_instance, namespace)


@app.route('/list_clusters_pods/<namespace>', methods=['GET'])
def list_clusters_pods(namespace):
    data = {}
    for key, value in config_files.items():
        config.kube_config.load_kube_config(config_file=value)
        api_instance = client.CoreV1Api()
        data[key] = list_one_cluster_pods(api_instance, namespace)
        api_client = client.ApiClient()
        ret_metrics = api_client.call_api(
            '/apis/metrics.k8s.io/v1beta1/namespaces/' + namespace + '/pods', 'GET',
            auth_settings=['BearerToken'], response_type='json', _preload_content=False)
        response = ret_metrics[0].data.decode('utf-8')
        response = json.loads(response)
        for item in response['items']:
            data[key][item['metadata']['name']]['containers'] = item['containers']
    return flask.jsonify(data)


@app.route('/list_clusters_services', methods=['GET'])
def list_clusters_services():
    data = {}
    for key, value in config_files.items():
        config.kube_config.load_kube_config(config_file=value)
        api_instance = client.CoreV1Api()
        data[key] = list_one_cluster_services(api_instance)
    return flask.jsonify(data)


@app.route('/list_clusters_nodes', methods=['GET'])
def list_clusters_nodes():
    data = {}
    for key, value in config_files.items():
        config.kube_config.load_kube_config(config_file=value)
        api_instance = client.CoreV1Api()
        data[key] = list_one_cluster_nodes(api_instance)
    return flask.jsonify(data)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=9000)
