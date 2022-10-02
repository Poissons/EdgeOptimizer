# USAGE
# Start the server:
# 	python app.py
# Submit a request via cURL:

# curl http://localhost:4001/predict -X POST -d 'observation='[tasks_execute_situation_on_each_node_dict,
# current_service_on_each_node_dict, stuck_tasks_situation_on_each_node_dict,
# resources_on_each_node_dict, epoch_index]'

import flask
import json
import numpy as np
import sys


SERVICE_NUM = 20

resource_limits = {
    1: {'cpu': '3', 'memory': '0.5Gi'},
    2: {'cpu': '3', 'memory': '0.5Gi'},
    3: {'cpu': '3', 'memory': '0.5Gi'},
    4: {'cpu': '3', 'memory': '0.5Gi'},
    5: {'cpu': '3', 'memory': '0.5Gi'},
    6: {'cpu': '3', 'memory': '0.5Gi'},
    7: {'cpu': '3', 'memory': '0.5Gi'},
    8: {'cpu': '3', 'memory': '0.5Gi'},
    9: {'cpu': '3', 'memory': '0.5Gi'},
    10: {'cpu': '3', 'memory': '0.5Gi'},
    11: {'cpu': '3', 'memory': '0.5Gi'},
    12: {'cpu': '3', 'memory': '0.5Gi'},
    13: {'cpu': '3', 'memory': '0.5Gi'},
    14: {'cpu': '3', 'memory': '0.5Gi'},
    15: {'cpu': '3', 'memory': '0.5Gi'},
    16: {'cpu': '3', 'memory': '0.5Gi'},
    17: {'cpu': '3', 'memory': '0.5Gi'},
    18: {'cpu': '3', 'memory': '0.5Gi'},
    19: {'cpu': '3', 'memory': '0.5Gi'},
    20: {'cpu': '3', 'memory': '0.5Gi'}
}


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


def find_sub_max(arr):
    decrease_stack = []
    increase_stack = []
    for i in range(0, len(arr)):
        item = arr[i]
        if len(decrease_stack) == 0:
            decrease_stack.append(i)
        else:
            top = decrease_stack[len(decrease_stack) - 1]
            while arr[top] < item:
                increase_stack.append(decrease_stack.pop())
                if len(decrease_stack) == 0:
                    break
                top = decrease_stack[len(decrease_stack) - 1]
            decrease_stack.append(i)
            while len(increase_stack):
                decrease_stack.append(increase_stack.pop())
    return decrease_stack


def score_algorithm_placement(master_name, update_interval, tasks_execute_situation_on_each_node_dict,
                               current_service_on_each_node_dict,
                               stuck_tasks_situation_on_each_node_dict, resources_on_each_node_dict, epoch_index):
    total_task_sum = 0

    result = []
    failure_box = np.zeros(SERVICE_NUM, float)
    stuck_box = np.zeros(SERVICE_NUM, float)

    # choose first param
    first_dict = tasks_execute_situation_on_each_node_dict[master_name]
    print(first_dict)
    for the_type in first_dict:
        value = first_dict[the_type]
        failure_percent = value['failure'] / (value['success'] + value['failure'])

        total_task_sum += value['success'] + value['failure']
        failure_box[int(the_type) - 1] = failure_percent
    first_param = None

    second_dict = stuck_tasks_situation_on_each_node_dict[master_name]
    print(second_dict)
    for the_type in second_dict:
        stuck_percent = second_dict[the_type]['stuck'] / update_interval
        stuck_box[int(the_type) - 1] = 1 if stuck_percent > 1 else stuck_percent

    # Select the types to be added, and give a probability for each type
    # 1.Pick the one with the highest failure rate
    # 2.If there are no successful/failed tasks at all during this period, then choose whichever type which is more likely to be stucked
    # failure rate*0.7 + stuck rate*0.3

    scored_box = failure_box * 0.7 + stuck_box * 0.3
    decrease_stack = find_sub_max(scored_box)

    third_dict = resources_on_each_node_dict[master_name]
    print(third_dict)
    # If you want to delete, choose one of the existing services: type which has the lowest score in the scored_box
    fourth_dict = current_service_on_each_node_dict[master_name]
    print(fourth_dict)

    for i in range(0, int(SERVICE_NUM * 0.5)):
        new_service = decrease_stack[i]+1

    add_action = 1
    delete_action = -1
    chose_add_node = None
    # First select the type to be added, select the one with the largest score in the scored_box,
    # and pick only from the first 1/2*(len) in the scored_box.

    add_chose_count = 0

    # First check if there is no need to delete any type of service
    while add_chose_count < SERVICE_NUM * 0.5:
        chose_type = decrease_stack[add_chose_count]+1
        chose_resource = resource_limits[chose_type]
        chose_cpu = transform_to_standard(chose_resource['cpu'])
        chose_memory = transform_to_standard(chose_resource['memory'])

        for the_node in third_dict:
            the_resources = third_dict[the_node]

            the_cpu = the_resources['cpu']
            the_cpu_percent = the_cpu['percent']
            the_cpu_allocated = the_cpu['allocated']
            the_cpu_allocatable = the_cpu['allocatable']

            the_memory = the_resources['memory']
            the_memory_percent = the_memory['percent']
            the_memory_allocated = the_memory['allocated']
            the_memory_allocatable = the_memory['allocatable']

            if (chose_cpu + the_cpu_allocated <= the_cpu_allocatable * 0.8) and (
                    chose_memory + the_memory_allocated <= the_memory_allocatable * 0.8):
                add_action = chose_type
                chose_add_node = the_node
                delete_action = 0
                return [chose_add_node, add_action, delete_action]
        add_chose_count += 1

    service_node_dict = {1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: [], 8: [], 9: [], 10: [], 11: [], 12: [], 13: [],
                         14: [], 15: [], 16: [], 17: [], 18: [], 19: [], 20: []}
    for node_name in fourth_dict:
        type_dict = fourth_dict[node_name]
        for the_type in type_dict:
            service_node_dict[int(the_type)].append(node_name)

    # If you have to delete one, you can only select the existing services at this time
    for i in range(0, int(SERVICE_NUM * 0.5)):
        new_service = decrease_stack[i]+1
        new_service_cpu = resource_limits[int(new_service)]['cpu']
        new_service_memory = resource_limits[int(new_service)]['memory']
        for j in range(SERVICE_NUM - 1, i, -1):
            old_service = decrease_stack[j]+1
            if len(service_node_dict[old_service]) == 0:
                continue
            old_service_cpu = resource_limits[int(old_service)]['cpu']
            old_service_memory = resource_limits[int(old_service)]['memory']

            if new_service_cpu <= old_service_cpu and new_service_memory <= old_service_memory:
                add_action = new_service
                chose_add_node = service_node_dict[old_service][0]
                delete_action = old_service
                return [chose_add_node, add_action, delete_action]

    return [chose_add_node, 0, 0]


# initialize our Flask application
app = flask.Flask(__name__)


@app.route("/predict", methods=["POST"])
def predict():
    if flask.request.method == "POST":
        observation = flask.request.form['observation']
        observation = json.loads(observation)
        result = score_algorithm_placement(observation[0], observation[1], observation[2], observation[3],
                                            observation[4], observation[5], observation[6])
    return flask.jsonify(result)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=4001)
