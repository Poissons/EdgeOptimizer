# -*- coding: utf-8 -*-
import re
import subprocess
from dataclasses import dataclass
from io import StringIO
from typing import Callable, List, Optional, Pattern, Union

import numpy as np
import pandas as pd
from pandas.core.series import Series
from typing_extensions import Literal

# 根据edge集群里的名字变化
# edge_node_name = ['edgecluster1-node1', 'edgecluster1-node2']
edge_node_name = ['node1', 'node2', 'node3']


@dataclass
class Pod(object):
    name: str  # service1-deployment1
    fullname: str  # service1-deployment1-598d588bcd-8zttc
    ready: str  # 0/1
    status: str  # ErrImageNeverPull
    restarts: str  # 0
    age: str  # 51s
    ip: str  # 10.244.2.95
    node: str  # node2
    busy: str


cache = {}


# if_busy三个值，正忙0/不忙1/都可2
def get_resource_dataframe(resource: Union[Literal['node'], Literal['pod']], not_busy=2, namespace="default") \
        -> pd.DataFrame:
    if not_busy == 0:
        output = subprocess.getoutput(f"kubectl get {resource} -o wide -l 'busy!=0' -n {namespace} --show-labels")
    elif not_busy == 1:
        output = subprocess.getoutput(f"kubectl get {resource} -o wide -l 'busy=0' -n {namespace} --show-labels")
    else:
        output = subprocess.getoutput(f'kubectl get {resource} -o wide -n {namespace} --show-labels')
    resource_dataframe = pd.read_csv(
        StringIO(output), sep=r'\s{2,}', engine='python')
    cache[resource] = resource_dataframe
    return resource_dataframe


class CheckPodRules(list):
    # pod_name_regex,node_resource_regex
    regex_list = [re.compile(r'^(service\d+-deployment\d*)-[0-9a-f]+-[0-9a-z]+$'),
                  re.compile(r'^(node\d+-resource-deployment)-[0-9a-f]+-[0-9a-z]+$'),
                  re.compile(r'^(.+-offload-deployment)-[0-9a-f]+-[0-9a-z]+$')]

    # running true是必须running，false必须不是running
    def __init__(self, name_starts_with: Optional[str] = None, if_check_regex: bool = True, regex_index: int = 0,
                 running: Optional[bool] = None, rules=[]):
        if running is not None:
            self.append(CheckPodRules.check_running(running))
        if name_starts_with is not None:
            self.append(CheckPodRules.name_starts_with(name_starts_with))
        if if_check_regex is not None:
            self.append(CheckPodRules.rename_by_regex(CheckPodRules.regex_list[regex_index]))
        self += rules

    @staticmethod
    def name_starts_with(prefix: str):
        def rule(pod: Pod, row: Series):
            return pod if pod.fullname.startswith(prefix) else None

        return rule

    @staticmethod
    def rename_by_regex(regex: Pattern[str]):
        def rule(pod: Pod, row: Series):
            matches = re.match(regex, pod.fullname)
            if matches is None:
                return
            pod.name = matches.group(1)
            return pod

        return rule

    @staticmethod
    def check_running(running: bool):
        def rule(pod: Pod, row: Series):
            return pod if (pod.status != 'Running') ^ running else None

        return rule


def check_pod_impl(rules: List[Callable[[Pod, Series], Optional[Pod]]] = [], not_busy=2, namespace="default") -> List[
    Pod]:
    pod_list = []
    for idx, row in get_resource_dataframe('pod', not_busy=not_busy, namespace=namespace).iterrows():
        fullname = str(row['NAME'])
        # 这里要改进
        busy = "0"
        labels_array = (str(row['LABELS'])).split(',')
        for label in labels_array:
            if 'busy' in label:
                busy = label[5:]
        pod = Pod(
            name=fullname,
            fullname=fullname,
            ready=str(row['READY']),
            status=str(row['STATUS']),
            restarts=str(row['RESTARTS']),
            age=str(row['AGE']),
            ip=str(row['IP']),
            node=str(row['NODE']),
            busy=busy
        )
        for rule in rules:
            pod = rule(pod, row)
            if pod is None:
                break
        if pod is not None:
            pod_list.append(pod)
    return pod_list


# 输入：pod关键字
# 输出：属性完善的pod类
# 作用：获取pod当前状态
def check_pod(target, running, if_check_regex, regex_index, not_busy=2, namespace="default"):
    return check_pod_impl(
        CheckPodRules(name_starts_with=target, running=running, if_check_regex=if_check_regex, regex_index=regex_index),
        not_busy, namespace)


def check_pod_for_its_node(deployment_name, service_name, if_check_regex, regex_index, namespace="default"):
    pod_list = check_pod_impl(
        CheckPodRules(name_starts_with=deployment_name, if_check_regex=if_check_regex,
                      regex_index=regex_index), 2, namespace)
    for pod in pod_list:
        if pod.name == deployment_name:
            return pod.node
    raise Exception(f'Pod not found with deployment_name={deployment_name} and service_name={service_name}')


def check_pods_of_the_type_on_this_node(deployment_name, running, node_name, if_check_regex, regex_index,
                                        not_busy=2, namespace="default"):
    pod_on_the_node_list = []
    pod_list = check_pod_impl(
        CheckPodRules(name_starts_with=deployment_name, running=running,
                      if_check_regex=if_check_regex, regex_index=regex_index), not_busy, namespace)
    for pod in pod_list:
        if pod.node == node_name:
            pod_on_the_node_list.append(pod)
    return pod_on_the_node_list


def check_pods_num_for_this_edge_cluster(target, running, if_check_regex, regex_index, not_busy):
    pods_num = np.zeros(20)
    all_pods = check_pod(target, running, if_check_regex, regex_index, not_busy)
    for pod in all_pods:
        pod_type = re.findall(r'\d+\.?\d*', pod.name)[0]
        pods_num[int(pod_type) - 1] += 1
    return pods_num.tolist()
