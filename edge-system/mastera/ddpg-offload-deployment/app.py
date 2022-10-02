# USAGE
# Start the server:
# 	python app.py
# Submit a request via cURL:

# curl http://localhost:4002/predict -X POST -d 'observation=[1,0,2,1,{"cpu":[3.0,2194.916,16384.0,4389.83,4.0,1111.916,12384.0,2489.83],"mem":[3165120.0,5077580.0,1321908.0,2165120.0,2077580.0,1121908.0],"up_time":[4388736.59,17551980.02,4388736.59,17551980.02],"pod":[0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3]}]'

import csv
import os
import pickle
import flask
import json
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F

###########################################参数###########################################
import math

LR_A = 0.001  # actor learning rate
LR_C = 0.002  # critic learning rate
GAMMA = 0.9  # reward discount
TAU = 0.01  # soft replacement
MEMORY_CAPACITY = 5000
ARRAY_CAPACITY = 30000
BATCH_SIZE = 200
SERVICE_NUM = 20
TRANS_MAX_TIME = 10.1 + 100.1
WEIGHTS_LIST = [5, 3]

# Change according to the actual situation
ACTION_NUM = 3 # cloud and edge 0/1
# CPU_PARAM_LEN = 4
# MEM_PARAM_LEN = 3
# UPTIME_PARAM_LEN = 2
POD_PARAM_LEN = 20
# TIME_LEN = 3

# There are two nodes here. The parameters are tentative, which can be modified
s_dim = SERVICE_NUM + ACTION_NUM * 3 + 1
a_dim = 1


###########################################DDPG Framework##########################################
class ANet(nn.Module):
    def __init__(self, s_dim, a_dim):
        super(ANet, self).__init__()
        self.fc1 = nn.Linear(s_dim, 30)
        self.fc1.weight.data.normal_(0, 0.1)
        self.out = nn.Linear(30, a_dim)
        self.out.weight.data.normal_(0, 0.1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.sigmoid(self.out(x))
        return x*3


class CNet(nn.Module):
    def __init__(self, s_dim, a_dim):
        super(CNet, self).__init__()
        self.fcs = nn.Linear(s_dim, 30)
        self.fcs.weight.data.normal_(0, 0.1)
        self.fca = nn.Linear(a_dim, 30)
        self.fca.weight.data.normal_(0, 0.1)
        self.out = nn.Linear(30, 1)
        self.out.weight.data.normal_(0, 0.1)

    def forward(self, s, a):
        x = self.fcs(s)
        y = self.fca(a)
        actions = self.out(F.relu(x + y))
        return actions


class DDPG(object):
    def __init__(self, a_dim, s_dim):
        self.a_dim, self.s_dim = a_dim, s_dim

        self.ep_r = 0
        self.var=3
        self.memory = np.zeros((MEMORY_CAPACITY, s_dim * 2 + a_dim + 1), dtype=np.float32)
        self.array = np.zeros((ARRAY_CAPACITY, s_dim * 2 + a_dim + 1), dtype=np.float32)
        self.memory_counter = 0


        self.Actor_eval = ANet(s_dim, a_dim)
        self.Actor_target = ANet(s_dim, a_dim)
        self.Critic_eval = CNet(s_dim, a_dim)
        self.Critic_target = CNet(s_dim, a_dim)

        self.actor_optimizer = torch.optim.Adam(self.Actor_eval.parameters(), lr=LR_A)
        self.critic_optimizer = torch.optim.Adam(self.Critic_eval.parameters(), lr=LR_C)

        self.loss_td = nn.MSELoss()

    def choose_action(self, s):
        s = torch.unsqueeze(torch.FloatTensor(s), 0)
        return self.Actor_eval(s)[0].detach()  # ae(s)

    def learn(self):
        for x in self.Actor_target.state_dict().keys():
            eval('self.Actor_target.' + x + '.data.mul_((1-TAU))')
            eval('self.Actor_target.' + x + '.data.add_(TAU*self.Actor_eval.' + x + '.data)')
        for x in self.Critic_target.state_dict().keys():
            eval('self.Critic_target.' + x + '.data.mul_((1-TAU))')
            eval('self.Critic_target.' + x + '.data.add_(TAU*self.Critic_eval.' + x + '.data)')

        # sample a mini-batch
        indices = np.random.choice(MEMORY_CAPACITY, size=BATCH_SIZE)
        bt = self.memory[indices, :]
        bs = torch.FloatTensor(bt[:, :self.s_dim])
        ba = torch.FloatTensor(bt[:, self.s_dim:self.s_dim + self.a_dim])
        br = torch.FloatTensor(bt[:, -self.s_dim - 1:-self.s_dim])
        bs_ = torch.FloatTensor(bt[:, -self.s_dim:])

        a = self.Actor_eval(bs)
        q = self.Critic_eval(bs, a)

        loss_a = -torch.mean(q)

        self.actor_optimizer.zero_grad()
        loss_a.backward()
        self.actor_optimizer.step()

        a_ = self.Actor_target(bs_)
        q_ = self.Critic_target(bs_, a_)
        q_target = br + GAMMA * q_

        q_v = self.Critic_eval(bs, ba)

        td_error = self.loss_td(q_target, q_v)

        self.critic_optimizer.zero_grad()
        td_error.backward()
        self.critic_optimizer.step()

        return loss_a, td_error

    def store_array(self, s, a, index):
        transition = np.hstack((s, a, -1, s))
        self.array[index, :] = transition

    def remember(self, state, action, reward, next_state):
        if not hasattr(self, 'memory_counter'):
            self.memory_counter = 0
        transition = np.hstack((state, action, reward, next_state))
        index = self.memory_counter % MEMORY_CAPACITY
        self.memory[index, :] = transition
        self.memory_counter += 1


    def transfer_memory(self, array_index):
        if not hasattr(self, 'memory_counter'):
            self.memory_counter = 0
        memory_index = self.memory_counter % MEMORY_CAPACITY
        self.memory[memory_index, :] = self.array[array_index, :]
        with open('/home/memory.csv', 'a+', newline="") as f:
            csv_write = csv.writer(f)
            csv_write.writerow(self.memory[memory_index, :])
            f.close()
        self.memory_counter += 1


def calc_reward(if_success, total_time, standard_time):
    reward = 0
    if if_success != 0:
        reward += (1 - (total_time - standard_time) / standard_time) * 20
    else:
        reward = -20
    return reward


def calc_utility(weights_list, if_success, total_time, standard_time):
    record1 = weights_list[0] * if_success
    record2 = weights_list[1] * math.exp(-(total_time - standard_time) / 30000)
    utility_record_list = [record1, record2]
    utility_this_epoch = sum(utility_record_list)
    return utility_this_epoch


def ddpg_select_node(arguments):
    offload_epoch_index = arguments[0]
    request_type = arguments[1]
    pods_situation = arguments[2]['pods_situation']
    trans_time = arguments[2]['trans_time']
    execute_standard_time = arguments[2]['execute_standard_time']

    type_position = np.zeros(SERVICE_NUM, float)
    pods_num = np.zeros(ACTION_NUM, float)
    pods_busy = np.zeros(ACTION_NUM, float)
    trans_time_std = np.zeros(ACTION_NUM, float)
    execute_standard_time_std = np.zeros(1, float)

    type_position[int(request_type) - 1] = 1

    for the_type, value in pods_situation.items():
        pods_num[int(the_type)] = value['pods_num']
        pods_busy[int(the_type)] = value['pods_busy']

    for index, value in trans_time.items():
        trans_time_std[int(index)] = value

    execute_standard_time_std[0] = execute_standard_time

    pods_num = pods_num / np.sum(pods_num)
    pods_busy = 1 - pods_busy
    trans_time_std = trans_time_std / (TRANS_MAX_TIME * 2)
    execute_standard_time_std = execute_standard_time_std / (TRANS_MAX_TIME * 2)

    s = np.concatenate((type_position, pods_num, pods_busy, trans_time_std, execute_standard_time_std))

    not_proper = True
    a = 0

    while not_proper:
        a = ddpg.choose_action(s)
        print(a)
        a = round(np.clip(np.random.normal(a, ddpg.var), 0, 2)[0])

        if pods_num[a] == 0:
            r = calc_utility(WEIGHTS_LIST, 0, TRANS_MAX_TIME, 0)
            s_ = s
            ddpg.remember(s, a, r, s_)
        else:
            not_proper = False

    ddpg.store_array(s, a, offload_epoch_index)

    return a


def store_feedback(arguments):
    offload_epoch_index = arguments[0]
    request_type = arguments[1]
    pods_situation = arguments[2]['pods_situation']
    trans_time = arguments[2]['trans_time']
    execute_standard_time = arguments[2]['execute_standard_time']
    execute_time = arguments[3]
    if_success = arguments[4]

    loss_a, td_error = 0, 0

    r = calc_utility(WEIGHTS_LIST, if_success, execute_time, execute_standard_time)

    type_position = np.zeros(SERVICE_NUM, float)
    pods_num = np.zeros(ACTION_NUM, float)
    pods_busy = np.zeros(ACTION_NUM, float)
    trans_time_std = np.zeros(ACTION_NUM, float)
    execute_standard_time_std = np.zeros(1, float)

    type_position[int(request_type) - 1] = 1

    for the_type, value in pods_situation.items():
        pods_num[int(the_type)] = value['pods_num']
        pods_busy[int(the_type)] = value['pods_busy']

    for index, value in trans_time.items():
        trans_time_std[int(index)] = value

    execute_standard_time_std[0] = execute_standard_time

    pods_num = pods_num / np.sum(pods_num)
    pods_busy = 1 - pods_busy
    trans_time_std = trans_time_std / (TRANS_MAX_TIME * 2)
    execute_standard_time_std = execute_standard_time_std / (TRANS_MAX_TIME * 2)

    s_ = np.concatenate((type_position, pods_num, pods_busy, trans_time_std, execute_standard_time_std))

    ddpg.array[offload_epoch_index][s_dim + 1] = r
    ddpg.array[offload_epoch_index][s_dim + a_dim + 1:] = s_
    ddpg.transfer_memory(offload_epoch_index)

    # if there are enough transitions, perform learning
    if ddpg.memory_counter >= BATCH_SIZE:
        ddpg.var *= 0.9995  # decay the exploration controller factor
        loss_a, td_error = ddpg.learn()

    if offload_epoch_index >= BATCH_SIZE:
        with open('/home/loss_hist.csv', 'a+', newline="") as f1:
            csv_write = csv.writer(f1)
            csv_write.writerow([offload_epoch_index, loss_a.item(), td_error.item()])
            f1.close()

    # record the reward
    if offload_epoch_index > 0:
        with open('/home/reward_hist.csv', 'a+', newline="") as f2:
            csv_write = csv.writer(f2)
            csv_write.writerow([offload_epoch_index, r])  # 记得要改
            f2.close()



# CPU
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# initialize our Flask application
app = flask.Flask(__name__)


@app.route("/predict", methods=["POST"])
def predict():
    if flask.request.method == "POST":
        observation = flask.request.form['observation']
        observation = json.loads(observation)
        result = ddpg_select_node(observation)
    return flask.jsonify(result)


@app.route("/feedback", methods=["POST"])
def feedback():
    if flask.request.method == "POST":
        observation = flask.request.form['observation']
        observation = json.loads(observation)
        store_feedback(observation)
        return flask.jsonify(["feedback"])


# then start the server
if __name__ == "__main__":
    ddpg = DDPG(a_dim, s_dim)
    app.run(host='0.0.0.0', port=4003, threaded=False)
