import asyncio
import csv
import io
import logging.config
import re
import aiohttp
from aiohttp import FormData
import json
import os
import pickle
import random
import time
from collections import defaultdict
from flask import Flask, request

from req_data import ReqData
from deploy1 import deploy_with_node, delete
from check_pod1 import (check_pod, get_resource_dataframe)
from LatencyMonitor import LatencyMonitor

# node_master_control_simulate_para_path = './node_master_control_simulate_para.json'
# with open(node_master_control_simulate_para_path) as file_obj:
#     node_master_platform_para = json.load(file_obj)

"""
定义ip和端口
"""
cluster_names = ['cloudmaster', 'master', 'mastera']
place_index_dict = {'cloudmaster': {'place_index': 0, 'ip': '192.168.1.35'},
                    'master': {'place_index': 1, 'ip': '192.168.1.85'},
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
NODES_RESOURCE_PORT = 7000

# 服务种类
SERVICE_TYPE_NUM = 20
# update设定何时更新
UPDATE = 500000

offload_algorithm_name = ["greedy-offload-deployment", "dqn-offload-deployment", "polling-offload-deployment",
                          "ddpg-offload-deployment"]
offload_algorithm_port = [4000, 4001, 4002, 4003]

if_use_nodes_resource = False
# 没什么用，就记录一下本地是第几个
local_task_count = 0
update_index = 0
offload_epoch_index = 0
pod_name_index = [3 for i in range(SERVICE_TYPE_NUM)]
# 这里增加offload算法，0为random_node，1为强化学习
offload_algorithm_index = 1

cache_index_for_list_master_cluster_pods = 0
list_master_cluster_pods = {}
cache_index_for_list_clusters_pods_ai_service = 0
list_clusters_pods_ai_service = {}

app = Flask(__name__)


def fetch_edge_master_name():
    nodes_list = get_resource_dataframe('node', 2)
    master_name = nodes_list[nodes_list['ROLES'] == 'master']['NAME'].iloc[0]
    return master_name


master_name = fetch_edge_master_name()


def get_index_to_ip(place_index_dict):
    index_to_ip_dict = {}
    for name, item in place_index_dict.items():
        place_index = item['place_index']
        ip = item['ip']
        index_to_ip_dict[place_index] = ip
    return index_to_ip_dict


index_to_ip = get_index_to_ip(place_index_dict)


def transform_to_standard(content):
    if content.endswith("Ki"):
        num = float(content[:-2])
        return_content = 2 ** 10 * num
    elif content.endswith("Mi"):
        num = float(content[:-2])
        return_content = 2 ** 20 * num
    elif content.endswith("Gi"):
        num = float(content[:-2])
        return_content = 2 ** 30 * num
    elif content.endswith("Ti"):
        num = float(content[:-2])
        return_content = 2 ** 40 * num
    elif content.endswith("Pi"):
        num = float(content[:-2])
        return_content = 2 ** 50 * num
    elif content.endswith("Ei"):
        num = float(content[:-2])
        return_content = 2 ** 60 * num
    elif content.endswith("n"):
        num = float(content[:-1])
        return_content = 10 ** (-9) * num
    elif content.endswith("u"):
        num = float(content[:-1])
        return_content = 10 ** (-6) * num
    elif content.endswith("m"):
        num = float(content[:-1])
        return_content = 10 ** (-3) * num
    elif content.endswith("K"):
        num = float(content[:-1])
        return_content = 10 ** 3 * num
    elif content.endswith("M"):
        num = float(content[:-1])
        return_content = 10 ** 6 * num
    elif content.endswith("G"):
        num = float(content[:-1])
        return_content = 10 ** 9 * num
    elif content.endswith("T"):
        num = float(content[:-1])
        return_content = 10 ** 12 * num
    elif content.endswith("P"):
        num = float(content[:-1])
        return_content = 10 ** 15 * num
    elif content.endswith("E"):
        num = float(content[:-1])
        return_content = 10 ** 18 * num
    else:
        return_content = float(content)
    return return_content


def update_delete(epoch_index: int, delete_action: int, chose_node_name: str, namespace: str):
    not_running_pod_list = check_pod('service' + str(delete_action) + '-deployment', False, True, 0, 2, "ai-service")
    if len(not_running_pod_list) > 0:
        pod = not_running_pod_list.pop()
        while pod.node != chose_node_name and len(not_running_pod_list) > 0:
            pod = not_running_pod_list.pop()
        if pod.node == chose_node_name:
            deploy_name = pod.name
            delete(master_name, namespace, deploy_name)
            return

    running_idle_pod_list = check_pod('service' + str(delete_action) + '-deployment', True, True, 0, 1, "ai-service")
    if len(running_idle_pod_list) > 0:
        pod = running_idle_pod_list.pop()
        while pod.node != chose_node_name and len(running_idle_pod_list) > 0:
            pod = running_idle_pod_list.pop()
        if pod.node == chose_node_name:
            deploy_name = pod.name
            delete(master_name, namespace, deploy_name)
            return

    # 这里是不是要改成最不busy的？？？
    running_busy_pod_list = check_pod('service' + str(delete_action) + '-deployment', True, True, 0, 0, "ai-service")
    if len(running_busy_pod_list) > 0:
        pod = running_busy_pod_list.pop()
        while pod.node != chose_node_name and len(running_busy_pod_list) > 0:
            pod = running_busy_pod_list.pop()
        if pod.node == chose_node_name:
            deploy_name = pod.name
            delete(master_name, namespace, deploy_name)

    return


# 如果算法又说要增加这种类型的pod，可以优先将标记为即将删除的pod的标签改为正在运行，这样就不用真的加减pod了
def update_add(add_action: int, chose_node_name: str, namespace: str):
    time.sleep(55)
    global pod_name_index
    new_name = f'service{add_action}-deployment{pod_name_index[add_action - 1]}'
    pod_name_index[add_action - 1] += 1
    deploy_with_node(master_name, f'./service/service{add_action}/service.yaml', chose_node_name,
                     namespace, new_name)


# 取队列里的request本地执行
# 输入：可用pod列表， 选中pod的序号， 请求
# 输出：请求处理结果
# 作用：处理请求
# multiprocessing.sharedctypes._Value类型标注
# 为了pylance提供的静态类型检查
#
async def local_run(req: ReqData, local_offload_epoch_returned_by_func: int, pod_list: list,
                    receive_start_time, from_user_to_first_cluster):
    try:
        req_type, req_if_simple, data, req_execute_standard_time = req.type, req.if_simple, req.data, req.execute_standard_time

        # 选择pod
        current_pod = pod_list[0]
        for i in range(1, len(pod_list)):
            if pod_list[i]['busy'] == 0:
                current_pod = pod_list[i]
                break
            else:
                if pod_list[i]['busy'] < current_pod['busy']:
                    current_pod = pod_list[i]

        # if current_pod is None:
        #     # 怎么定义？？？？
        #     # pod不够
        #     flow = {'from': master_name, 'to': '', 'str': 'no pod'}
        #     mission = {'success': 0, 'failure': 1, 'stuck': -1}
        #     detail_mission = {'name': flow['from'],
        #                       'type': req_type, 'success': 0, 'failure': 1}
        #
        #     # 如何衡量stuck？？？
        #     stuck_mission = {'name': master_name, 'type': req_type}
        #     async with aiohttp.ClientSession(f"http://{place_index_dict['cloud']['ip']}:5000") as session:
        #         async with session.post('/tasks_stuck_situation', data=json.dumps(stuck_mission)) as resp:
        #             await resp.read()

        busy_num = current_pod['busy']
        # 这里需要锁吗？需要换成异步的吗？
        # 这里是否需要添加namespace参数
        os.popen('kubectl label pods ' + current_pod['name'] + ' -n ai-service busy=' + str(int(busy_num) + 1)
                 + ' --overwrite').read()

        upload_data = FormData()
        if req_if_simple:
            upload_data.add_field('observation', json.dumps(req.data))
            async with aiohttp.ClientSession(f"http://{current_pod['pod_ip']}:{PORT[req_type - 1]}") as session:
                async with session.post('/predict', data=upload_data) as resp:
                    result = await resp.read()
        else:
            # 例子
            request_data = io.BytesIO(req.data)
            # 自定义
            upload_data.add_field('image', request_data)
            async with aiohttp.ClientSession(f"http://{current_pod['pod_ip']}:{PORT[req_type - 1]}") as session:
                async with session.post('/predict', data=upload_data) as resp:
                    result = await resp.read()
        flow = {'from': master_name, 'to': current_pod['name'], 'str': result}

        # 这里又查了一遍，是否就不需要lock了？
        cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
            random.randint(0, 14)].ip

        try:
            async with aiohttp.ClientSession(
                    f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
                async with session.get(f'/list_cluster_pods/{master_name}/ai-service') as resp:
                    this_cluster_pods = await resp.json()
        except:
            global list_master_cluster_pods
            this_cluster_pods = list_master_cluster_pods

        for key, value in this_cluster_pods.items():
            if value['name'] == current_pod['name']:
                if 'busy' in value['labels']:
                    os.popen('kubectl label pods ' + current_pod['name'] + ' -n ai-service busy=' + str(
                        int(value['labels']['busy']) - 1) + ' --overwrite').read()

        ###########################需要要改时间??????
        runtime = time.time() - receive_start_time + from_user_to_first_cluster * 2

        logging.info(f'task #{local_task_count}, type {req_type} ends:')
        logging.info(flow)

        mission = {'success': 0, 'failure': 0, 'stuck': -1}
        stuck_mission = {'name': flow['from'], 'type': req_type, 'stuck': -1}
        detail_mission = {'name': flow['from'], 'type': req_type, 'success': 0, 'failure': 0}

        if_success = 0
        if runtime <= req_execute_standard_time:
            mission['success'] += 1
            detail_mission['success'] += 1
            if_success = 1
        else:
            mission['failure'] += 1
            detail_mission['failure'] += 1

        with open('./delay.csv', 'a+', newline="") as f0:
            csv_write = csv.writer(f0)
            csv_write.writerow([if_success, runtime, req_execute_standard_time])
            f0.close()

        # 强化学习，为offload返回情况
        global offload_algorithm_index
        if offload_algorithm_index == 1 or offload_algorithm_index == 3:
            # 收集集群信息cluster-information
            cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
                random.randint(0, 14)].ip
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

            # 实际系统有时延区别，直接用这个
            this_cluster_index = place_index_dict[master_name]['place_index']
            latency_monitor = LatencyMonitor(this_cluster_index, place_index_dict)
            latency_matrix = latency_monitor.do_measuring()

            # 和其他边缘集群之间的传播时间
            trans_latency_matrix = {0: 0, 1: 0, 2: 0}
            for key in trans_latency_matrix:
                if key == this_cluster_index:
                    trans_latency_matrix[key] = 0
                else:
                    trans_latency_matrix[key] = latency_matrix[(this_cluster_index, key)]

            # 因为是模拟
            trans_latency_matrix = {0: 100 + random.random() * 0.01, 1: 0, 2: 20 + random.random() * 0.01}

            # 自定义算法参数即可
            # offload_param = {
            #                 'pods_situation':{0:{'pods_num':,'pods_busy':},1:{'pods_num':,'pods_busy':}...},
            #                 'trans_time': {0:trans_to_0,1:trans_to_1,2:trans_to_2···},
            #                 'execute_standard_time':request_execute_standard_time
            # }

            # param1: pod_situation
            if_have_any_pods_of_this_type = False
            pods_situation = {}
            for cluster_name, pods_items in cluster_pods.items():
                cluster_index = place_index_dict[cluster_name]['place_index']
                pods_situation_for_one_cluster = {'pods_num': 0, 'pods_busy': 1}
                for pod_name in pods_items:
                    pod_item = pods_items[pod_name]
                    # print('-----------------------')
                    # print(pod_item)
                    if pod_item['phase'] == 'Running':
                        pod_type = int(re.match(r'^service(.*?)-deployment(.*?)', pod_name).group(1))
                        if pod_type == req_type:
                            # 一定会有，因为云上有
                            if_have_any_pods_of_this_type = True
                            pods_situation_for_one_cluster['pods_num'] += 1
                            if 'busy=0' not in pod_item['labels'] and pods_situation_for_one_cluster['pods_busy'] > 0 \
                                    and ('containers' in pod_item):
                                # 注意这里container个数只有1个
                                # print(pod_item)
                                cpu_busy = transform_to_standard(pod_item['containers'][0]['usage']['cpu']) / \
                                           transform_to_standard(pod_resource[pod_type]['cpu'])
                                mem_busy = transform_to_standard(pod_item['containers'][0]['usage']['memory']) / \
                                           transform_to_standard(pod_resource[pod_type]['mem'])
                                # 参数可调整
                                new_busy = cpu_busy * 10000 * 0.5 + mem_busy * 10 * 0.5
                                if new_busy < pods_situation_for_one_cluster['pods_busy']:
                                    pods_situation_for_one_cluster['pods_busy'] = new_busy
                            else:
                                pods_situation_for_one_cluster['pods_busy'] = 0
                pods_situation[cluster_index] = pods_situation_for_one_cluster

            # param2: trans_time
            trans_time = {}
            for i, the_time in trans_latency_matrix.items():
                trans_time[i] = (from_user_to_first_cluster + the_time) * 2

            offload_param = {'pods_situation': pods_situation, 'trans_time': trans_time,
                             'execute_standard_time': req_execute_standard_time}

            offload_algorithm_pod = \
                check_pod(offload_algorithm_name[offload_algorithm_index], True, True, 2, 2, 'algorithm')[0]

            arguments = [local_offload_epoch_returned_by_func, req_type, offload_param, runtime, if_success]

            upload_data = FormData()
            upload_data.add_field('observation', json.dumps(arguments))
            print(json.dumps(arguments))
            async with aiohttp.ClientSession(
                    f'http://{offload_algorithm_pod.ip}:{offload_algorithm_port[offload_algorithm_index]}') as session:
                async with session.post('/feedback', data=upload_data) as resp:
                    result = await resp.json()

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/master_collect_tasks_situation', data=json.dumps(mission)) as resp:
                json.loads(await resp.text())

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/tasks_success_failure_situation',
                                    data=json.dumps(detail_mission)) as resp:
                json.loads(await resp.text())

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/tasks_stuck_situation',
                                    data=json.dumps(stuck_mission)) as resp:
                json.loads(await resp.text())

        global update_index
        update_index += 1
        # 这里怎么样能让下面这行不跳过呢，会不会造成跳过不update？？？
        print('请求序列是： ' + str(local_offload_epoch_returned_by_func))
        print('update_index是： ' + str(update_index))
        if update_index % UPDATE == 0:
            print('进入更新！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！')
            await update_control()
        return flow
    except:
        import traceback
        traceback.print_exc()


# 输入：无
# 输出：运行时间
# 作用：重新编排服务

# def update_pod():

# # 发送已经有的服务
# async with aiohttp.ClientSession(f"http://{place_index_dict['cloud']['ip']}:5000") as session:
#     async with session.post('/current_services_on_this_cluster',
#                             data=json.dumps([master_name, pod_info, 0])) as resp:
#         await resp.read()


# # 发送node上的资源
# async with aiohttp.ClientSession(f"http://{place_index_dict['cloud']['ip']}:5000") as session:
#     async with session.post('/resources_on_this_cluster', data=json.dumps(current_resource_of_nodes)) as resp:
#         await resp.read()

# 在云上直接弄已有服务和node上资源
# return start


# 编排服务
async def update_control():
    print('更新！！！！！！！！！！！！！')
    logging.debug('···start update process')

    start = time.time()

    async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
        async with session.post('/cloud_master_receive_update', data=json.dumps([master_name, UPDATE])) as resp:
            update_result = await resp.text()

    update_result = json.loads(update_result)
    print(update_result)
    this_epoch_index = update_result[0]
    chose_node_name = update_result[1][0]
    add_action = update_result[1][1]
    delete_action = update_result[1][2]

    # cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[0].ip
    # async with aiohttp.ClientSession(
    #         f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
    #     async with session.get(f'/list_cluster_pods/{master_name}/ai-service') as resp:
    #         this_cluster_pods = await resp.json()

    if add_action > 0:
        # 尽量减去不busy的
        update_delete(this_epoch_index, delete_action, chose_node_name, 'ai-service')
        update_add(add_action, chose_node_name, 'ai-service')
    else:
        print('no action')
    end = time.time()
    runtime = end - start
    print('Updating pods consumes time:', runtime, '\n')


async def offload_service(algorithm_type, req_data, from_user_to_edge):
    request_type = req_data.type
    request_execute_standard_time = req_data.execute_standard_time

    # 收集集群信息cluster-information
    cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
        random.randint(0, 14)].ip
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

    # async with aiohttp.ClientSession(
    #         f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
    #     async with session.get('/list_clusters_nodes') as resp:
    #         cluster_nodes_return = await resp.json()
    #         cluster_nodes = {}
    #         for name in cluster_nodes_return:
    #             cluster_nodes[place_index_dict[name]['place_index']] = cluster_nodes_return[name]

    # 实际系统有时延区别，直接用这个
    this_cluster_index = place_index_dict[master_name]['place_index']
    latency_monitor = LatencyMonitor(this_cluster_index, place_index_dict)
    latency_matrix = latency_monitor.do_measuring()

    # 和其他边缘集群之间的传播时间
    trans_latency_matrix = {0: 0, 1: 0, 2: 0}
    for key in trans_latency_matrix:
        if key == this_cluster_index:
            trans_latency_matrix[key] = 0
        else:
            trans_latency_matrix[key] = latency_matrix[(this_cluster_index, key)]

    # 因为是模拟
    trans_latency_matrix = {0: 100 + random.random() * 0.01, 1: 0, 2: 20 + random.random() * 0.01}

    # 自定义算法参数即可
    # offload_param = {
    #                 'pods_situation':{0:{'pods_num':,'pods_busy':},1:{'pods_num':,'pods_busy':}...},
    #                 'trans_time': {0:trans_to_0,1:trans_to_1,2:trans_to_2···},
    #                 'execute_standard_time':request_execute_standard_time
    # }

    # param1: pod_situation
    # pods_situation = {}
    # for cluster_name, pods_items in cluster_pods.items():
    #     cluster_index = place_index_dict[cluster_name]['place_index']
    #     pods_situation_for_one_cluster = {'pods_num': [0 for _ in range(SERVICE_TYPE_NUM)],
    #                                       'pods_busy': [1 for _ in range(SERVICE_TYPE_NUM)]}
    #     for pod_name in pods_items:
    #         pod_item = pods_items[pod_name]
    #         if pod_item['phase'] == 'Running':
    #             pod_type = int(re.match(r'^service(.*?)-deployment-(.*?)', pod_name).group(1))
    #             pods_situation_for_one_cluster['pods_num'][pod_type] += 1
    #
    #             if 'busy=0' not in pod_item['labels'] and pods_situation_for_one_cluster['pods_busy'][pod_type] > 0:
    #                 cpu_busy = transform_to_standard(pod_item['containers']['usage']['cpu']) / \
    #                            transform_to_standard(pod_resource[pod_type]['cpu'])
    #                 mem_busy = transform_to_standard(pod_item['containers']['usage']['memory']) / \
    #                            transform_to_standard(pod_resource[pod_type]['mem'])
    #                 # 参数可调整
    #                 new_busy = cpu_busy * 0.5 + mem_busy * 0.5
    #                 if new_busy < pods_situation_for_one_cluster['pods_busy'][pod_type]:
    #                     pods_situation_for_one_cluster['pods_busy'][pod_type] = new_busy
    #             else:
    #                 pods_situation_for_one_cluster['pods_busy'][pod_type] = 0
    #     pods_situation[cluster_index] = pods_situation_for_one_cluster

    # param1: pod_situation
    if_have_any_pods_of_this_type = False
    pods_situation = {}
    for cluster_name, pods_items in cluster_pods.items():
        cluster_index = place_index_dict[cluster_name]['place_index']
        pods_situation_for_one_cluster = {'pods_num': 0, 'pods_busy': 1}
        for pod_name in pods_items:
            pod_item = pods_items[pod_name]
            # print('-----------------------')
            # print(pod_item)
            if pod_item['phase'] == 'Running':
                pod_type = int(re.match(r'^service(.*?)-deployment(.*?)', pod_name).group(1))
                if pod_type == request_type:
                    # 一定会有，因为云上有
                    if_have_any_pods_of_this_type = True
                    pods_situation_for_one_cluster['pods_num'] += 1
                    if 'busy=0' not in pod_item['labels'] and pods_situation_for_one_cluster['pods_busy'] > 0 \
                            and ('containers' in pod_item):
                        # 注意这里container个数只有1个
                        # print(pod_item)
                        cpu_busy = transform_to_standard(pod_item['containers'][0]['usage']['cpu']) / \
                                   transform_to_standard(pod_resource[pod_type]['cpu'])
                        mem_busy = transform_to_standard(pod_item['containers'][0]['usage']['memory']) / \
                                   transform_to_standard(pod_resource[pod_type]['mem'])
                        # 参数可调整
                        new_busy = cpu_busy * 10000 * 0.5 + mem_busy * 10 * 0.5
                        if new_busy < pods_situation_for_one_cluster['pods_busy']:
                            pods_situation_for_one_cluster['pods_busy'] = new_busy
                    else:
                        pods_situation_for_one_cluster['pods_busy'] = 0
        pods_situation[cluster_index] = pods_situation_for_one_cluster

    # param2: trans_time
    trans_time = {}
    for i, the_time in trans_latency_matrix.items():
        trans_time[i] = (from_user_to_edge + the_time) * 2

    offload_param = {'pods_situation': pods_situation, 'trans_time': trans_time,
                     'execute_standard_time': request_execute_standard_time}

    offload_algorithm_pod = \
        check_pod(offload_algorithm_name[algorithm_type], True, True, 2, 2, 'algorithm')[0]

    global offload_epoch_index
    this_offload_epoch_index = offload_epoch_index
    offload_epoch_index += 1

    arguments = [this_offload_epoch_index, request_type, offload_param]
    print(json.dumps(arguments))
    upload_data = FormData()
    upload_data.add_field('observation', json.dumps(arguments))

    async with aiohttp.ClientSession(
            f'http://{offload_algorithm_pod.ip}:{offload_algorithm_port[algorithm_type]}') as session:
        async with session.post('/predict', data=upload_data) as resp:
            result = await resp.json()
    return result, arguments[0]


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


def transform_pickle_to_normal(data):
    try:
        req_info = pickle.loads(data)
        # logging.info(req_info)
        return req_info
    except:
        logging.info('The format is wrong, please check!')


# async def write_data_into_file(file_request_type, file_format,file_data):
#     try:
#         async with aiofiles.open('./type_data/' + str(file_request_type) + file_format, 'wb') as f:
#             await f.write(file_data)
#             return
#     except:
#         logging.info('A problem occurred when write data into file!')

async def run_req_from_another_cluster(offload_epoch_index, req, pod_list, from_first_cluster_to_second_cluster,
                                       from_user_to_first_cluster):
    try:
        req_type, req_if_simple, data, req_execute_standard_time = req.type, req.if_simple, req.data, req.execute_standard_time
        # 选择pod
        current_pod = pod_list[0]
        for i in range(1, len(pod_list)):
            if pod_list[i]['busy'] == 0:
                current_pod = pod_list[i]
                break
            else:
                if pod_list[i]['busy'] < current_pod['busy']:
                    current_pod = pod_list[i]

        # 是否要加锁
        busy_num = current_pod['busy']
        os.popen('kubectl label pods ' + current_pod['name'] + ' busy=' + str(int(busy_num) + 1)).read()

        upload_data = FormData()
        if req_if_simple:
            upload_data.add_field('observation', json.dumps(req.data))
            async with aiohttp.ClientSession(f"http://{current_pod['pod_ip']}:{PORT[req_type - 1]}") as session:
                async with session.post('/predict', data=upload_data) as resp:
                    result = await resp.read()
        else:
            # 例子
            request_data = io.BytesIO(req.data)
            # 自定义
            upload_data.add_field('image', request_data)
            async with aiohttp.ClientSession(f"http://{current_pod['pod_ip']}:{PORT[req_type - 1]}") as session:
                async with session.post('/predict', data=upload_data) as resp:
                    result = await resp.read()

        flow = {'from': req.edge_name, 'to': current_pod['name'], 'str': result}

        cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
            random.randint(0, 14)].ip
        async with aiohttp.ClientSession(
                f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
            async with session.get(f'/list_cluster_pods/{master_name}/ai-service') as resp:
                try:
                    this_cluster_pods = await resp.json()
                except:
                    global list_master_cluster_pods
                    this_cluster_pods = list_master_cluster_pods

        for key, value in this_cluster_pods.items():
            if value['name'] == current_pod['name']:
                if 'busy' in value['labels']:
                    os.popen('kubectl label pods ' + current_pod['name'] + ' busy=' + str(
                        int(value['labels']['busy']) - 1)).read()

        ###########################需要要改时间??????
        runtime = time.time() - req.send_system_time + from_user_to_first_cluster + from_first_cluster_to_second_cluster

        # 因为是模拟
        runtime = time.time() - req.send_system_time + (from_user_to_first_cluster +
                                                        from_first_cluster_to_second_cluster) * 2

        logging.info(flow)

        mission = {'success': 0, 'failure': 0, 'stuck': -1}
        stuck_mission = {'name': flow['from'], 'type': req_type, 'stuck': -1}
        detail_mission = {'name': flow['from'], 'type': req_type, 'success': 0, 'failure': 0}

        if_success = 0
        if runtime <= req_execute_standard_time:
            mission['success'] += 1
            detail_mission['success'] += 1
            if_success = 1
        else:
            mission['failure'] += 1
            detail_mission['failure'] += 1

        with open('./delay.csv', 'a+', newline="") as f0:
            csv_write = csv.writer(f0)
            csv_write.writerow([if_success, runtime, req_execute_standard_time])
            f0.close()

        cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
            random.randint(0, 14)].ip
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
                # print('-----------------------')
                # print(pod_item)
                if pod_item['phase'] == 'Running':
                    pod_type = int(re.match(r'^service(.*?)-deployment(.*?)', pod_name).group(1))
                    if pod_type == req_type:
                        # 一定会有，因为云上有
                        if_have_any_pods_of_this_type = True
                        pods_situation_for_one_cluster['pods_num'] += 1
                        if 'busy=0' not in pod_item['labels'] and pods_situation_for_one_cluster['pods_busy'] > 0 and \
                                ('containers' in pod_item):
                            # 注意这里container个数只有1个
                            # print(pod_item)
                            cpu_busy = transform_to_standard(pod_item['containers'][0]['usage']['cpu']) / \
                                       transform_to_standard(pod_resource[pod_type]['cpu'])
                            mem_busy = transform_to_standard(pod_item['containers'][0]['usage']['memory']) / \
                                       transform_to_standard(pod_resource[pod_type]['mem'])
                            # 参数可调整
                            new_busy = cpu_busy * 10000 * 0.5 + mem_busy * 10 * 0.5
                            if new_busy < pods_situation_for_one_cluster['pods_busy']:
                                pods_situation_for_one_cluster['pods_busy'] = new_busy
                        else:
                            pods_situation_for_one_cluster['pods_busy'] = 0
            pods_situation[cluster_index] = pods_situation_for_one_cluster

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/master_collect_tasks_situation', data=json.dumps(mission)) as resp:
                json.loads(await resp.text())

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/tasks_success_failure_situation',
                                    data=json.dumps(detail_mission)) as resp:
                json.loads(await resp.text())

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/tasks_stuck_situation',
                                    data=json.dumps(stuck_mission)) as resp:
                json.loads(await resp.text())

        return [offload_epoch_index, pods_situation, runtime, if_success]
    except:
        import traceback
        traceback.print_exc()


@app.route("/edge_master_receive_request_from_user", methods=['POST'])
async def edge_master_receive_request_from_user():
    print('!!!!!!!!!!!!!!!!!!!')
    logging.info('waiting to receive requests···')
    try:
        receive_request = transform_pickle_to_normal(request.data)
        logging.info('edge receive request from user successfully')
    except:
        logging.info('A problem occurred when edge receive request from user!')

    try:
        req_data = ReqData(master_name, receive_request[0], receive_request[1], receive_request[2], receive_request[3],
                           receive_request[4], receive_request[5], receive_request[6])
        print(req_data)
        # logging.info(req_data)

        mission = {'success': 0, 'failure': 0, 'stuck': 1}
        stuck_mission = {'name': master_name, 'type': req_data.type, 'stuck': 1}

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/master_collect_tasks_situation', data=json.dumps(mission)) as resp:
                json.loads(await resp.text())

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/tasks_stuck_situation', data=json.dumps(stuck_mission)):
                json.loads(await resp.text())

    except:
        logging.info('A problem occurred when transfer requests into the right data format!')

    request_type = req_data.type

    # 如果系统时延是真实的
    # 画图用
    receive_start_time = time.time()
    from_user_to_first_cluster = receive_start_time - req_data.send_system_time

    # 因为是模拟
    from_user_to_first_cluster = 10 + random.random() * 0.01

    # 1.加入一个双链表+二叉树，等待实现
    # collections.OrderedDict

    # 收集信息
    global offload_algorithm_index
    place_index, offload_epoch_returned_by_func = await offload_service(offload_algorithm_index, req_data,
                                                                        from_user_to_first_cluster)

    # 画图用
    place_end_time = time.time()
    place_time = place_end_time - receive_start_time
    with open('./place_time.csv', 'a+', newline="") as f0:
        csv_write = csv.writer(f0)
        csv_write.writerow([offload_epoch_returned_by_func, place_index, place_time])
        f0.close()

    print('发送到：' + str(place_index))
    # 如果是本地就local执行，不是的话发送给别的地方
    if place_index == place_index_dict[master_name]['place_index']:
        cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
            random.randint(0, 14)].ip
        async with aiohttp.ClientSession(
                f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
            async with session.get(f'/list_cluster_pods/{master_name}/ai-service') as resp:
                global list_master_cluster_pods
                try:
                    global cache_index_for_list_master_cluster_pods
                    this_cluster_pods = await resp.json()
                    if cache_index_for_list_master_cluster_pods % 2 == 0:
                        list_master_cluster_pods = this_cluster_pods
                except:
                    this_cluster_pods = list_master_cluster_pods

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

        pod_list = pod_dicts[request_type]
        logging.debug(pod_list)

        if len(pod_list) == 0:
            # 这里node上根本没有这个类型pod
            mission = {'success': 0, 'failure': 1, 'stuck': -1}
            stuck_mission = {'name': master_name, 'type': request_type, 'stuck': -1}
            detail_mission = {'name': master_name, 'type': request_type, 'success': 0, 'failure': 1}

            with open('./delay.csv', 'a+', newline="") as f0:
                csv_write = csv.writer(f0)
                csv_write.writerow([0, req_data.execute_standard_time])
                f0.close()

            # 这里要计算成功数量，应该发给谁比较好？
            async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
                async with session.post('/master_collect_tasks_situation', data=json.dumps(mission)) as resp:
                    json.loads(await resp.text())

            async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
                async with session.post('/tasks_success_failure_situation', data=json.dumps(detail_mission)):
                    json.loads(await resp.text())

            async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
                async with session.post('/tasks_stuck_situation', data=json.dumps(stuck_mission)):
                    json.loads(await resp.text())
        else:
            # 如何定义busy？？？
            # pods_with_label_list = check_pod('service' + str(request_type)+ '-deployment', True, True, 0, 1)
            # if len(pods_with_label_list) > 0:
            #     selected_pod = pods_with_label_list[
            #         random.randint(0, len(pods_with_label_list) - 1)]
            #     # 需要锁吗
            #     # 怎么办？？？这个是命令行
            #     os.popen('kubectl label pods ' + selected_pod.fullname + ' busy=true').read()

            # 多协程可以吗？
            flow = await local_run(req_data, offload_epoch_returned_by_func, pod_list, receive_start_time,
                                   from_user_to_first_cluster)
            global local_task_count
            local_task_count += 1
    else:
        logging.info('request is offload to another cluster')

        first_cluster_send_system_time = time.time()
        receive_request = [master_name, receive_request[0], receive_request[1], receive_request[2], receive_request[3],
                           receive_request[4], receive_request[5], receive_request[6]]
        req = [offload_epoch_returned_by_func, receive_request, first_cluster_send_system_time,
               from_user_to_first_cluster]

        async with aiohttp.ClientSession(f"http://{index_to_ip[place_index]}:5000") as session:
            async with session.post('/master_receive_request_to_process', data=pickle.dumps(req)) as resp:
                process_result = json.loads(await resp.text())

        print(process_result)
        this_offload_epoch_index = process_result[0]
        pods_situation = process_result[1]
        runtime = process_result[2]
        if_success = process_result[3]

        # 添加智能算法反馈
        if offload_algorithm_index == 1 or offload_algorithm_index == 3:

            # 实际系统有时延区别，直接用这个
            this_cluster_index = place_index_dict[master_name]['place_index']
            latency_monitor = LatencyMonitor(this_cluster_index, place_index_dict)
            latency_matrix = latency_monitor.do_measuring()

            # 和其他边缘集群之间的传播时间
            trans_latency_matrix = {0: 0, 1: 0, 2: 0}
            for key in trans_latency_matrix:
                if key == this_cluster_index:
                    trans_latency_matrix[key] = 0
                else:
                    trans_latency_matrix[key] = latency_matrix[(this_cluster_index, key)]

            # 因为是模拟
            trans_latency_matrix = {0: 100 + random.random() * 0.01, 1: 0, 2: 20 + random.random() * 0.01}

            # 自定义算法参数即可
            # offload_param = {
            #                 'pods_situation':{0:{'pods_num':,'pods_busy':},1:{'pods_num':,'pods_busy':}...},
            #                 'trans_time': {0:trans_to_0,1:trans_to_1,2:trans_to_2···},
            #                 'execute_standard_time':request_execute_standard_time
            # }

            # param2: trans_time
            trans_time = {}
            for i, the_time in trans_latency_matrix.items():
                trans_time[i] = (from_user_to_first_cluster + the_time) * 2

            offload_param = {'pods_situation': pods_situation, 'trans_time': trans_time,
                             'execute_standard_time': receive_request[6]}

            # 收集集群信息cluster-information
            offload_algorithm_pod = \
                check_pod(offload_algorithm_name[offload_algorithm_index], True, True, 2, 2, 'algorithm')[0]

            arguments = [this_offload_epoch_index, request_type, offload_param, runtime, if_success]

            upload_data = FormData()
            upload_data.add_field('observation', json.dumps(arguments))
            print(json.dumps(arguments))
            async with aiohttp.ClientSession(
                    f'http://{offload_algorithm_pod.ip}:{offload_algorithm_port[offload_algorithm_index]}') as session:
                async with session.post('/feedback', data=upload_data) as resp:
                    result = await resp.json()

        global update_index
        update_index += 1
        logging.debug('receive the result from other cluster')

        print('请求序列是： ' + str(offload_epoch_returned_by_func))
        print('update_index是： ' + str(update_index))
        if update_index % UPDATE == 0:
            print('进入更新！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！')
            await update_control()
    return json.dumps("200")


@app.route("/master_receive_request_to_process", methods=['POST'])
async def master_receive_request_to_process():
    logging.debug('cluster start receiving requests from another cluster···')
    received_content = pickle.loads(request.data)
    offload_epoch_index = received_content[0]
    first_cluster_send_system_time = received_content[2]
    from_first_cluster_to_second_cluster = time.time() - first_cluster_send_system_time
    # 因为是模拟
    from_first_cluster_to_second_cluster = 20 + random.random() * 5

    from_user_to_first_cluster = received_content[3]
    received_request = received_content[1]
    req_data = ReqData(received_request[0], received_request[1], received_request[2], received_request[3],
                       received_request[4], received_request[5], received_request[6], received_request[7])
    logging.debug(
        'request needs to be served by service ' + str(req_data.type) + ' is received, offload epoch index is '
        + str(offload_epoch_index))

    cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
        random.randint(0, 14)].ip
    async with aiohttp.ClientSession(
            f'http://{cluster_information_pod_ip}:{CLUSTER_INFORMATION_PORT}') as session:
        async with session.get(f'/list_cluster_pods/{master_name}/ai-service') as resp:
            global list_master_cluster_pods
            try:
                this_cluster_pods = await resp.json()
                global cache_index_for_list_master_cluster_pods
                if cache_index_for_list_master_cluster_pods % 2 == 0:
                    list_master_cluster_pods = this_cluster_pods
                    cache_index_for_list_master_cluster_pods += 1
            except:
                this_cluster_pods = list_master_cluster_pods

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
    logging.debug(pod_list)

    if len(pod_list) == 0:
        # 这里node上根本没有这个类型pod
        mission = {'success': 0, 'failure': 1, 'stuck': -1}
        stuck_mission = {'name': req_data.edge_name, 'type': req_data.type, 'stuck': -1}
        detail_mission = {'name': req_data.edge_name, 'type': req_data.type, 'success': 0, 'failure': 1}

        with open('./delay.csv', 'a+', newline="") as f0:
            csv_write = csv.writer(f0)
            csv_write.writerow([0, req_data.execute_standard_time])
            f0.close()

        # 这里要计算成功数量，应该发给谁比较好？
        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/master_collect_tasks_situation', data=json.dumps(mission)) as resp:
                json.loads(await resp.text())

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/tasks_success_failure_situation', data=json.dumps(detail_mission)):
                json.loads(await resp.text())

        async with aiohttp.ClientSession(f"http://{place_index_dict['cloudmaster']['ip']}:5000") as session:
            async with session.post('/tasks_stuck_situation', data=json.dumps(stuck_mission)):
                json.loads(await resp.text())

        cluster_information_pod_ip = check_pod('cluster-information-deployment', True, None, 0, 2, "information")[
            random.randint(0, 9)].ip
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

        pods_situation = {}
        for cluster_name, pods_items in cluster_pods.items():
            cluster_index = place_index_dict[cluster_name]['place_index']
            pods_situation_for_one_cluster = {'pods_num': 0, 'pods_busy': 1}
            for pod_name in pods_items:
                pod_item = pods_items[pod_name]
                # print('-----------------------')
                # print(pod_item)
                if pod_item['phase'] == 'Running':
                    pod_type = int(re.match(r'^service(.*?)-deployment(.*?)', pod_name).group(1))
                    if pod_type == req_data.type:
                        # 一定会有，因为云上有
                        if_have_any_pods_of_this_type = True
                        pods_situation_for_one_cluster['pods_num'] += 1
                        if 'busy=0' not in pod_item['labels'] and pods_situation_for_one_cluster['pods_busy'] > 0 \
                                and ('containers' in pod_item):
                            # 注意这里container个数只有1个
                            # print(pod_item)
                            cpu_busy = transform_to_standard(pod_item['containers'][0]['usage']['cpu']) / \
                                       transform_to_standard(pod_resource[pod_type]['cpu'])
                            mem_busy = transform_to_standard(pod_item['containers'][0]['usage']['memory']) / \
                                       transform_to_standard(pod_resource[pod_type]['mem'])
                            # 参数可调整
                            new_busy = cpu_busy * 10000 * 0.5 + mem_busy * 10 * 0.5
                            if new_busy < pods_situation_for_one_cluster['pods_busy']:
                                pods_situation_for_one_cluster['pods_busy'] = new_busy
                        else:
                            pods_situation_for_one_cluster['pods_busy'] = 0
            pods_situation[cluster_index] = pods_situation_for_one_cluster

        runtime = time.time() - req_data.send_system_time + from_user_to_first_cluster + from_first_cluster_to_second_cluster

        # 因为是模拟
        runtime = time.time() - req_data.send_system_time + (from_user_to_first_cluster +
                                                             from_first_cluster_to_second_cluster) * 2

        result = [offload_epoch_index, pods_situation, runtime, 0]
    else:
        result = await run_req_from_another_cluster(offload_epoch_index, req_data, pod_list,
                                                    from_first_cluster_to_second_cluster, from_user_to_first_cluster)
    print(result)
    return json.dumps(result)


if __name__ == "__main__":
    setup_logging(default_path='logging.json', default_level=logging.DEBUG)
    logging.info('edge master start···')
    app.run(host='0.0.0.0', port=5000)
