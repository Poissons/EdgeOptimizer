import os

import yaml
from kubernetes import client, watch, config
import time
from ruamel import yaml

config_files = {'cloudmaster': r"./all-config/config-cloud",
                'master': r"./all-config/config-edge1",
                'mastera': r"./all-config/config-edge2"}


def bind_name(v1, pod, node, namespace="default"):
    target = client.V1ObjectReference(api_version='v1', kind='Node', name=node)
    meta = client.V1ObjectMeta()
    meta.name = pod
    body = client.V1Binding(target=target, metadata=meta)
    try:
        print("INFO Pod: %s placed on: %s\n" % (pod, node))
        print(pod, ' choose node ', node)
        api_response = v1.create_namespaced_pod_binding(
            name=pod, namespace=namespace, body=body)
        print(api_response)
        return api_response
    except Exception as e:
        print("Warning when calling CoreV1Api->create_namespaced_pod_binding: %s\n" % e)


# 输入：pod配置信息
# 输出：无
# 作用：部署pod
def deploy_with_node(cluster_name, yaml_path, node, namespace, name):
    config.load_kube_config(config_files[cluster_name])
    try:
        with open(yaml_path, encoding="utf-8") as f:
            content = yaml.load(f, Loader=yaml.RoundTripLoader)
            content['metadata']['name'] = name
            content['spec']['template']['spec']['nodeName'] = node
            k8s_apps_v1 = client.AppsV1Api()
            resp = k8s_apps_v1.create_namespaced_deployment(
                body=content, namespace=namespace)
        print("Deployment created. status='%s'" % resp.metadata.name)
    except Exception as e:
        print("Error, when creating deployment!!!", e)
        pass
    return 0


def deploy(cluster_name, yaml_path, namespace, name):
    # 使用
    config.load_kube_config(config_files[cluster_name])
    try:
        with open(yaml_path, encoding="utf-8") as f:
            content = yaml.load(f, Loader=yaml.RoundTripLoader)
            content['metadata']['name'] = name
            k8s_apps_v1 = client.AppsV1Api()
            resp = k8s_apps_v1.create_namespaced_deployment(
                body=content, namespace=namespace)
            print("Deployment created. status='%s'" % resp.metadata.name)
    except Exception as e:
        print("Error, when creating deploy!!!", e)
        pass


def delete(cluster_name, namespace, deployment_name):
    config.load_kube_config(config_files[cluster_name])
    # k8s_apps_v1 = client.AppsV1Api()
    # resp = k8s_apps_v1.delete_namespaced_deployment(name=deployment_name, namespace=namespace)

    resp = os.popen(f'kubectl delete deploy {deployment_name} -n {namespace}').read()
    print("delete deploy " + deployment_name)
    print(resp)
    return time.time()
