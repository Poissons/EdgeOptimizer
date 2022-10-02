import asyncio
import csv
import io
import json
import logging
import os
import pickle
import random
import re
import time
from asyncio import Lock

import aiohttp
import requests
from aiohttp import FormData
from flask import Flask, request

from check_pod1 import check_pod, get_resource_dataframe
from req_data import ReqData

place_index_dict = {'cloudmaster': {'place_index': 0, 'ip': '192.168.1.35'},
                    'master': {'place_index': 1, 'ip': '192.168.1.30'},
                    'mastera': {'place_index': 2, 'ip': '192.168.1.43'}}

PORT = ["2500", "2500", "2500", "2500", "2500", "2500", "2500", "2500", "2500", "2500", "2500", "2500", "2500", "2500",
        "2500", "2500", "2500", "2500", "2500", "2500"]

pod_resource = {1: {'cpu': "3", 'mem': "0.5Gi"}, 2: {'cpu': "3", 'mem': "0.5Gi"}, 3: {'cpu': "3", 'mem': "0.5Gi"},
                4: {'cpu': "3", 'mem': "0.5Gi"},
                5: {'cpu': "3", 'mem': "0.5Gi"}, 6: {'cpu': "3", 'mem': "0.5Gi"}, 7: {'cpu': "3", 'mem': "0.5Gi"},
                8: {'cpu': "3", 'mem': "0.5Gi"},
                9: {'cpu': "3", 'mem': "0.5Gi"}, 10: {'cpu': "3", 'mem': "0.5Gi"}, 11: {'cpu': "3", 'mem': "0.5Gi"},
                12: {'cpu': "3", 'mem': "0.5Gi"},
                13: {'cpu': "3", 'mem': "0.5Gi"}, 14: {'cpu': "3", 'mem': "0.5Gi"}, 15: {'cpu': "3", 'mem': "0.5Gi"},
                16: {'cpu': "3", 'mem': "0.5Gi"},
                17: {'cpu': "3", 'mem': "0.5Gi"}, 18: {'cpu': "3", 'mem': "0.5Gi"}, 19: {'cpu': "3", 'mem': "0.5Gi"},
                20: {'cpu': "3", 'mem': "0.5Gi"}}

CLUSTER_INFORMATION_PORT = 9000
ALG_PORT = ['4001']
ALG_NAME = ['orchestration-score-algorithm-deployment']

epoch_index = 0

state = {'success': 0, 'failure': 0, 'stuck': 0}
state_lock = Lock()

tasks_success_failure_situation_dict = {}
tasks_success_failure_situation_dict_lock = Lock()

tasks_stuck_situation_dict = {}
tasks_stuck_situation_dict_lock = Lock()

current_service_on_each_node_dict = {}
current_service_on_each_node_dict_lock = Lock()

resources_on_each_node_dict = {}
resources_on_each_node_dict_lock = Lock()

cache_index_for_list_clusters_pods_ai_service = 0


def fetch_edge_master_name():
    nodes_list = get_resource_dataframe('node', 2)
    master_name = nodes_list[nodes_list['ROLES'] == 'master']['NAME'].iloc[0]
    return master_name


master_name = fetch_edge_master_name()

app = Flask(__name__)


def transform_to_standard(content):
    if content.endswith("Ki"):
        num = float(content[:-2])
        return 2 ** 10 * num
    elif content.endswith("Mi"):
        num = float(content[:-2])
        return 2 ** 20 * num
    elif content.endswith("Gi"):
        num = float(content[:-2])
        return 2 ** 30 * num
    elif content.endswith("Ti"):
        num = float(content[:-2])
        return 2 ** 40 * num
    elif content.endswith("Pi"):
        num = float(content[:-2])
        return 2 ** 50 * num
    elif content.endswith("Ei"):
        num = float(content[:-2])
        return 2 ** 60 * num
    elif content.endswith("n"):
        num = float(content[:-1])
        return 10 ** (-9) * num
    elif content.endswith("u"):
        num = float(content[:-1])
        return 10 ** (-6) * num
    elif content.endswith("m"):
        num = float(content[:-1])
        return 10 ** (-3) * num
    elif content.endswith("K"):
        num = float(content[:-1])
        return 10 ** 3 * num
    elif content.endswith("M"):
        num = float(content[:-1])
        return 10 ** 6 * num
    elif content.endswith("G"):
        num = float(content[:-1])
        return 10 ** 9 * num
    elif content.endswith("T"):
        num = float(content[:-1])
        return 10 ** 12 * num
    elif content.endswith("P"):
        num = float(content[:-1])
        return 10 ** 15 * num
    elif content.endswith("E"):
        num = float(content[:-1])
        return 10 ** 18 * num
    else:
        return float(content)


def clear_all(this_master_name):
    if this_master_name in tasks_success_failure_situation_dict:
        tasks_success_failure_situation_dict[this_master_name].clear()
    if this_master_name in tasks_stuck_situation_dict:
        tasks_stuck_situation_dict[this_master_name].clear()
    if this_master_name in current_service_on_each_node_dict:
        current_service_on_each_node_dict[this_master_name].clear()
    if this_master_name in resources_on_each_node_dict:
        resources_on_each_node_dict[this_master_name].clear()


async def run_req_from_another_cluster(offload_epoch_index, req, pod_list, from_first_cluster_to_second_cluster,
                                       from_user_to_first_cluster):
    try:
        print('request arrives')
        req_type, req_if_simple, data, req_execute_standard_time = req.type, req.if_simple, req.data, req.execute_standard_time
        current_pod = pod_list[0]
        for i in range(1, len(pod_list)):
            if int(pod_list[i]['busy']) == 0:
                current_pod = pod_list[i]
                break
            else:
                if int(pod_list[i]['busy']) < int(current_pod['busy']):
                    current_pod = pod_list[i]

        busy_num = current_pod['busy']
        os.popen('kubectl label pods ' + current_pod['name'] + ' busy=' + str(int(busy_num) + 1) + ' -n ai-service '
                                                                                                   '--overwrite').read()
        upload_data = FormData()
        if req_if_simple:
            upload_data.add_field('observation', json.dumps(req.data))
            async with aiohttp.ClientSession(f"http://{current_pod['pod_ip']}:{PORT[req_type - 1]}") as session:
                async with session.post('/predict', data=upload_data) as resp:
                    result = await resp.read()
        else:
            request_data = io.BytesIO(req.data)
            upload_data.add_field('image', request_data)
            async with aiohttp.ClientSession(f"http://{current_pod['pod_ip']}:{PORT[req_type - 1]}") as session:
                async with session.post('/predict', data=upload_data) as resp:
                    result = await resp.read()
        print(result)
        flow = {'from': req.edge_name, 'to': current_pod['name'], 'str': result}
        cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
            random.randint(0, 17)].ip
        async with aiohttp.ClientSession(
                f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
            async with session.get(f'/list_cluster_pods/{master_name}/ai-service') as resp:
                this_cluster_pods = await resp.json()
        for key, value in this_cluster_pods.items():
            if value['name'] == current_pod['name']:
                if 'busy' in value['labels']:
                    os.popen(
                        'kubectl label pods ' + current_pod['name'] + ' busy=' + str(
                            int(value['labels']['busy']) - 1) + ' -n ai-service --overwrite').read()
        runtime = time.time() - req.send_system_time + from_user_to_first_cluster + from_first_cluster_to_second_cluster

        runtime = time.time() - req.send_system_time + (
                from_user_to_first_cluster + from_first_cluster_to_second_cluster) * 2

        # logging.info(flow)
        print(flow)

        mission = {'success': 0, 'failure': 0, 'stuck': 0}
        detail_mission = {'name': flow['from'], 'type': req_type, 'success': 0, 'failure': 0}

        if_success = 0

        global state
        if runtime <= req_execute_standard_time:
            state['success'] += 1
            state['stuck'] -= 1
            mission['success'] += 1
            detail_mission['success'] += 1
            if_success = 1
        else:
            state['failure'] += 1
            state['stuck'] -= 1
            mission['failure'] += 1
            detail_mission['failure'] += 1

        with open('./delay.csv', 'a+', newline="") as f0:
            csv_write = csv.writer(f0)
            csv_write.writerow([if_success, runtime, req_execute_standard_time])
            f0.close()

        cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
            random.randint(0, 17)].ip
        async with aiohttp.ClientSession(
                f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
            async with session.get('/list_clusters_pods/ai-service') as resp:
                global list_clusters_pods_ai_service
                try:
                    cluster_pods = await resp.json()
                    global cache_index_for_list_clusters_pods_ai_service
                    if cache_index_for_list_clusters_pods_ai_service % 2 == 0:
                        list_clusters_pods_ai_service = cluster_pods
                        cache_index_for_list_clusters_pods_ai_service += 1
                except:
                    cluster_pods = list_clusters_pods_ai_service

        # param1: pod_situation
        if_have_any_pods_of_this_type = False
        pods_situation = {}
        for cluster_name, pods_items in cluster_pods.items():
            cluster_index = place_index_dict[cluster_name]['place_index']
            pods_situation_for_one_cluster = {'pods_num': 0, 'pods_busy': 1}
            for pod_name in pods_items:
                pod_item = pods_items[pod_name]
                if pod_item['phase'] == 'Running':
                    pod_type = int(re.match(r'^service(.*?)-deployment(.*?)', pod_name).group(1))
                    if pod_type == req_type:
                        if_have_any_pods_of_this_type = True
                        pods_situation_for_one_cluster['pods_num'] += 1
                        if 'busy=0' not in pod_item['labels'] and pods_situation_for_one_cluster['pods_busy'] > 0 \
                                and ('containers' in pod_item):
                            cpu_busy = transform_to_standard(pod_item['containers'][0]['usage']['cpu']) / \
                                       transform_to_standard(pod_resource[pod_type]['cpu'])
                            mem_busy = transform_to_standard(pod_item['containers'][0]['usage']['memory']) / \
                                       transform_to_standard(pod_resource[pod_type]['mem'])
                            new_busy = cpu_busy * 10000 * 0.5 + mem_busy * 10 * 0.5
                            if new_busy < pods_situation_for_one_cluster['pods_busy']:
                                pods_situation_for_one_cluster['pods_busy'] = new_busy
                        else:
                            pods_situation_for_one_cluster['pods_busy'] = 0
            pods_situation[cluster_index] = pods_situation_for_one_cluster

        print(str(state['success']) + " " + str(state['failure']) + " " + str(state['stuck']))
        with open('./collect.csv', 'a+', newline="") as f:
            csv_write = csv.writer(f)
            data_row = [state['success'], state['failure'], state['stuck']]
            csv_write.writerow(data_row)
            f.close()

        async with aiohttp.ClientSession(f"http://localhost:5000") as session:
            async with session.post('/tasks_success_failure_situation',
                                    data=json.dumps(detail_mission)) as resp:
                await resp.read()

        return [offload_epoch_index, pods_situation, runtime, if_success]
    except:
        import traceback
        traceback.print_exc()


@app.route("/master_receive_request_to_process", methods=['POST'])
async def master_receive_request_to_process():
    # logging.debug('cluster start receiving requests from another cluster···')
    print('cluster start receiving requests from another cluster···')
    received_content = pickle.loads(request.data)
    offload_epoch_index = received_content[0]
    first_cluster_send_system_time = received_content[2]
    from_first_cluster_to_second_cluster = time.time() - first_cluster_send_system_time
    from_first_cluster_to_second_cluster = 100 + random.random() * 0.01

    from_user_to_first_cluster = received_content[3]
    received_request = received_content[1]
    req_data = ReqData(received_request[0], received_request[1], received_request[2], received_request[3],
                       received_request[4], received_request[5], received_request[6], received_request[7])
    # logging.debug(
    #     'request needs to be served by service ' + str(req_data.type) + ' is received, offload epoch index is '
    #     + str(offload_epoch_index))
    print('request needs to be served by service ' + str(req_data.type) + ' is received, offload epoch index is '
          + str(offload_epoch_index))
    cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
        random.randint(0, 17)].ip
    async with aiohttp.ClientSession(
            f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
        async with session.get(f'/list_cluster_pods/{master_name}/ai-service') as resp:
            this_cluster_pods = await resp.json()

    pod_dicts = {}
    for i in range(1, 21):
        pod_dicts[i] = []

    for key, value in this_cluster_pods.items():
        if value['phase'] == 'Running':
            pod_type = int(re.match(r'^service(.*?)-deployment(.*?)', value['name']).group(1))
            if 'busy' in value['labels']:
                pod_dict = {'name': value['name'], 'pod_ip': value['pod_ip'], 'busy': value['labels']['busy']}
            else:
                pod_dict = {'name': value['name'], 'pod_ip': value['pod_ip'], 'busy': 0}
            pod_dicts[pod_type].append(pod_dict)

    pod_list = pod_dicts[req_data.type]
    # logging.debug(pod_list)
    result = await run_req_from_another_cluster(offload_epoch_index, req_data, pod_list,
                                                from_first_cluster_to_second_cluster, from_user_to_first_cluster)
    print(json.dumps(result))
    return json.dumps(result)


@app.route("/tasks_success_failure_situation", methods=['POST'])
async def tasks_success_failure_situation():
    # logging.debug('receive execution situation from other clusters...')
    print('receive execution situation from other clusters...')
    mission = json.loads(request.data)
    if len(mission) > 0:
        name = mission['name']
        type = mission['type']
        success = mission['success']
        failure = mission['failure']
        global tasks_success_failure_situation_dict
        temp_dict1 = tasks_success_failure_situation_dict.setdefault(name, {})
        inner_dict = {}
        inner_dict['success'] = 0
        inner_dict['failure'] = 0
        temp_dict2 = temp_dict1.setdefault(type, inner_dict)
        temp_dict2['success'] += success
        temp_dict2['failure'] += failure
    return json.dumps('200')


async def current_services_and_resources_on_this_cluster():
    # logging.debug('collecting current service type on each node starts...')
    # logging.debug('collecting resources on each node starts...')
    print('collecting current service type on each node starts...')
    print('collecting resources on each node starts...')

    # cluster-information
    cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
        random.randint(0, 17)].ip
    async with aiohttp.ClientSession(
            f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
        async with session.get('/list_clusters_pods/ai-service') as resp:
            cluster_pods = await resp.json()

    async with aiohttp.ClientSession(
            f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
        async with session.get('/list_clusters_nodes') as resp:
            cluster_nodes = await resp.json()
    global current_service_on_each_node_dict
    for the_cluster_name, the_value1 in cluster_pods.items():
        if place_index_dict[the_cluster_name]['place_index'] == 0:
            continue
        else:
            temp_dict1 = current_service_on_each_node_dict.setdefault(the_cluster_name, {})
            for pod_full_name, the_value2 in the_value1.items():
                the_phase = the_value2['phase']
                if the_phase == 'Running':
                    the_node_name = the_value2['node_name']
                    the_pod_type = int(re.match(r'^service(.*?)-deployment(.*?)', pod_full_name).group(1))
                    temp_dict2 = temp_dict1.setdefault(the_node_name, {})
                    if the_pod_type in temp_dict2:
                        temp_dict2[the_pod_type] += 1
                    else:
                        temp_dict2[the_pod_type] = 1

    global resources_on_each_node_dict
    for the_cluster_name, the_value1 in cluster_nodes.items():
        if place_index_dict[the_cluster_name]['place_index'] == 0:
            continue
        else:
            temp_dict1 = resources_on_each_node_dict.setdefault(the_cluster_name, {})
            for the_node_name, the_value2 in the_value1.items():
                if 'master' in the_node_name:
                    continue
                temp_dict2 = temp_dict1.setdefault(the_node_name,
                                                   {'cpu': {'percent': 0, 'allocated': 0, 'allocatable': 0},
                                                    'memory': {'percent': 0, 'allocated': 0, 'allocatable': 0}})
                allocatable_cpu = transform_to_standard(the_value2['allocatable']['cpu'])
                allocatable_memory = transform_to_standard(the_value2['allocatable']['memory'])

                allocated_cpu_of_service = 0
                allocated_memory_of_service = 0

                pods_type_on_this_node = current_service_on_each_node_dict[the_cluster_name][the_node_name]
                for each_type, type_num in pods_type_on_this_node.items():
                    allocated_cpu_of_service += transform_to_standard(pod_resource[each_type]['cpu']) * type_num
                    allocated_memory_of_service += transform_to_standard(pod_resource[each_type]['mem']) \
                                                   * type_num

                temp_dict2['cpu']['percent'] = allocated_cpu_of_service / allocatable_cpu * 100
                temp_dict2['cpu']['allocated'] = allocated_cpu_of_service
                temp_dict2['cpu']['allocatable'] = allocatable_cpu
                temp_dict2['memory']['percent'] = allocated_memory_of_service / allocatable_memory * 100
                temp_dict2['memory']['allocated'] = allocated_memory_of_service
                temp_dict2['memory']['allocatable'] = allocatable_memory
    return json.dumps('200')


@app.route("/tasks_stuck_situation", methods=['POST'])
async def tasks_stuck_situation():
    # logging.debug('The process for collecting stuck tasks situation starts...')
    print('The process for collecting stuck tasks situation starts...')
    detail_mission = json.loads(request.data)

    global tasks_stuck_situation_dict
    name = detail_mission['name']
    type = detail_mission['type']
    num = detail_mission['stuck']
    temp_dict1 = tasks_stuck_situation_dict.setdefault(name, {})
    inner_dict = {'stuck': 0}
    temp_dict2 = temp_dict1.setdefault(type, inner_dict)
    temp_dict2['stuck'] += num
    return json.dumps('200')


@app.route("/master_collect_tasks_situation", methods=['POST'])
async def master_collect_tasks_situation():
    mission = json.loads(request.data)
    global state
    state['success'] += mission['success']
    state['failure'] += mission['failure']
    state['stuck'] += mission['stuck']
    print(str(state['success']) + " " + str(state['failure']) + " " + str(state['stuck']))
    with open('./collect.csv', 'a+', newline="") as f:
        csv_write = csv.writer(f)
        data_row = [state['success'], state['failure'], state['stuck']]
        csv_write.writerow(data_row)
        f.close()
    return json.dumps('200')


@app.route("/cloud_master_receive_update", methods=['POST'])
async def cloud_master_receive_update():
    # logging.debug('cloud is ready to give feedback when service needs to be updated on the edge···')
    print('cloud is ready to give feedback when service needs to be updated on the edge···')
    pre = json.loads(request.data)
    this_master_name = pre[0]
    update_interval = pre[1]

    await current_services_and_resources_on_this_cluster()

    print('start using your methods to get result')
    global epoch_index
    local_epoch_index = epoch_index
    epoch_index += 1
    update_result = await placement_chosen(this_master_name, update_interval, 0, local_epoch_index)
    update_result = [local_epoch_index, update_result]
    print(update_result)
    return json.dumps(update_result)


async def placement_chosen(master_name, update_interval, i, epoch_index):
    """
    :param
    tasks_execute_situation_on_each_node_dict
    :param
    current_service_on_each_node_dict
    :param
    stuck_tasks_situation_on_each_node_dict
    :param
    resources_on_each_node_dict
    :param i:
    :return:

    [-MAX_KIND，MAX_KIND]
    [-MAX_KIND，MAX_KIND]
    """
    # logging.debug('choose algorithm' + ALG_NAME[i] + 'to get result')
    print('choose algorithm' + ALG_NAME[i] + 'to get result')
    global tasks_success_failure_situation_dict
    global current_service_on_each_node_dict
    global tasks_stuck_situation_dict
    global resources_on_each_node_dict

    observation = [master_name, update_interval, tasks_success_failure_situation_dict.copy(),
                   current_service_on_each_node_dict.copy(), tasks_stuck_situation_dict.copy(),
                   resources_on_each_node_dict.copy(), epoch_index]

    print('-------------------------------------')
    print(json.dumps(observation))
    upload_data = FormData()
    upload_data.add_field('observation', json.dumps(observation))

    clear_all(master_name)
    alg_pod = check_pod(ALG_NAME[i], True, None, 0, 2, 'algorithm')
    alg_ip = alg_pod[0].ip

    async with aiohttp.ClientSession(f"http://{alg_ip}:{ALG_PORT[i]}", trust_env=True) as session:
        async with session.post('/predict', data=upload_data) as resp:
            print(alg_ip)
            print(ALG_PORT[i])
            result = await resp.json()

    # clear_all(master_name)
    # result = json.loads(result)
    result[1] = int(result[1])
    result[2] = int(result[2])
    return result


def setup_logging(default_path="logging.json", default_level=logging.INFO, env_key="LOG_CFG"):
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, "r") as f:
            config = json.load(f)
            logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


if __name__ == '__main__':
    # setup_logging(default_path='logging.json', default_level=logging.DEBUG)
    app.run(host='0.0.0.0', port=5000)
