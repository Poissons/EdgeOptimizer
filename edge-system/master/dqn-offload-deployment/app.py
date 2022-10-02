import csv
import os
import pickle
import flask
import numpy as np
import math
import random
from keras.models import Sequential
from keras.layers import Dense
from keras.optimizers import Adam
from keras import initializers
import tensorflow
import json

# some constants
ACTION_NUM = 3
SERVICE_NUM = 20
S_DIM = SERVICE_NUM + ACTION_NUM * 3 + 1
A_DIM = 1
REPLACE_TARGET_PERIOD = 250
ARRAY_SIZE = 40000
TRANS_MAX_TIME = 10.1 + 100.1
WEIGHTS_LIST = [5, 3]
DISCOUNT_FACTOR = 0.9
REPLAY_MEMORY_CAPACITY_M = 5000
MINI_BATCH_SIZE_M = 200


class DQNAgent:
    def __init__(self, state_size, action_size, replay_memory_size, array_size, mini_batch_size, replace_target_period,
                 gamma, epsilon=1.0, epsilon_min=0.01, epsilon_decrement=0.001, learning_rate=0.005):
        self.state_size = state_size
        self.action_size = action_size
        self.replay_memory_size = replay_memory_size
        self.mini_batch_size = mini_batch_size
        self.memory = np.zeros((self.replay_memory_size, state_size * 2 + 2))
        self.memory_counter = 0
        self.array_size = array_size
        self.array = np.zeros((self.array_size, state_size * 2 + 2))
        self.gamma = gamma  # discount rate
        self.epsilon = epsilon  # exploration rate
        self.epsilon_min = epsilon_min
        self.learning_rate = learning_rate
        self.epsilon_decrement = epsilon_decrement
        self.model = self._build_model()
        self.target_model = self._build_model()
        self.update_target_model()
        self.loss_hist = []
        self.loss_epoch_hist = []
        self.learning_step = 0
        self.replace_target_period = replace_target_period

    def _build_model(self):
        # Neural Net for Deep-Q learning Model
        model = Sequential()
        model.add(
            Dense(200, input_dim=self.state_size, activation='tanh',
                  kernel_initializer=initializers.RandomNormal(mean=0.0, stddev=0.03)))
        model.add(Dense(self.action_size, activation='linear'))
        model.compile(loss='mean_squared_error',
                      optimizer=Adam(lr=self.learning_rate))
        return model

    def update_target_model(self):
        # copy weights from model to target_model
        self.target_model.set_weights(self.model.get_weights())

    def remember(self, state, action, reward, next_state):
        if not hasattr(self, 'memory_counter'):
            self.memory_counter = 0
        transition = np.hstack((state, action, reward, next_state))
        index = self.memory_counter % self.replay_memory_size
        self.memory[index, :] = transition
        self.memory_counter += 1

    def store_array(self, s, a, index):
        transition = np.hstack((s, a, -1, s))
        self.array[index, :] = transition

    def transfer_memory(self, array_index):
        if not hasattr(self, 'memory_counter'):
            self.memory_counter = 0
        memory_index = self.memory_counter % self.replay_memory_size
        self.memory[memory_index, :] = self.array[array_index, :]
        with open('/home/memory.csv', 'a+', newline="") as f:
            csv_write = csv.writer(f)
            csv_write.writerow(self.memory[memory_index, :])
            f.close()
        self.memory_counter += 1

    def act(self, state):
        if np.random.rand() <= self.epsilon:
            # random action, exploration
            return random.randrange(self.action_size)
        act_values = self.model.predict(np.reshape(state, [1, self.state_size]))
        return (np.argmax(act_values[0])).item()  # returns action

    def replay(self):
        if self.memory_counter > self.replay_memory_size:
            sample_index = np.random.choice(self.replay_memory_size, size=self.mini_batch_size)
        else:
            sample_index = np.random.choice(self.memory_counter, size=self.mini_batch_size)
        batch_memory = self.memory[sample_index, :]

        # obtain the samples
        state_array = batch_memory[:, :self.state_size]
        with graph.as_default():
            target_array = self.model.predict(state_array)
            next_target_array = self.target_model.predict(batch_memory[:, -self.state_size:])
            # obtain the target q values for the comparison with eval q values
            for idx_mini_batch in range(self.mini_batch_size):
                target_array[idx_mini_batch, batch_memory[idx_mini_batch, self.state_size].astype(int)] = \
                    batch_memory[idx_mini_batch, self.state_size + 1] + \
                    self.gamma * np.amax(next_target_array[idx_mini_batch])

            # mini-batch
            cur_history = self.model.fit(state_array, target_array, epochs=1,
                                         batch_size=self.mini_batch_size, verbose=0)
            self.epsilon = self.epsilon - self.epsilon_decrement \
                if self.epsilon > self.epsilon_min else self.epsilon_min

            # record the learning step already been done
            self.learning_step = self.learning_step + 1
            # replace target network periodically
            if self.learning_step % self.replace_target_period == 0:
                self.update_target_model()

            return cur_history.history["loss"][0]

    def load(self, name):
        self.model.load_weights(name)

    def save(self, name):
        self.model.save_weights(name)

# calculate utility
# WEIGHTS_LIST = [5, 3]
def calc_utility(weights_list, if_success, total_time, standard_time):
    record1 = weights_list[0] * if_success
    record2 = weights_list[1] * math.exp(-(total_time - standard_time) / 30000)
    utility_record_list = [record1, record2]
    utility_this_epoch = sum(utility_record_list)
    return utility_this_epoch


def dqn_select_node(arguments):
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

    s = np.array(np.concatenate((type_position, pods_num, pods_busy, trans_time_std, execute_standard_time_std)))

    not_proper = True
    a = 0

    while not_proper:
        a = agent.act(s)
        if pods_num[a] == 0:
            r = calc_utility(WEIGHTS_LIST, 0, TRANS_MAX_TIME, 0)
            s_ = s
            agent.remember(s, a, r, s_)
        else:
            not_proper = False

    agent.store_array(s, a, offload_epoch_index)

    return a


def store_feedback(arguments):
    offload_epoch_index = arguments[0]
    request_type = arguments[1]
    pods_situation = arguments[2]['pods_situation']
    trans_time = arguments[2]['trans_time']
    execute_standard_time = arguments[2]['execute_standard_time']
    execute_time = arguments[3]
    if_success = arguments[4]

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

    s_ = np.array(np.concatenate((type_position, pods_num, pods_busy, trans_time_std, execute_standard_time_std)))

    agent.array[offload_epoch_index][S_DIM + 1] = r
    agent.array[offload_epoch_index][S_DIM + A_DIM + 1:] = s_
    agent.transfer_memory(offload_epoch_index)

    # if there are enough transitions, perform learning
    if agent.memory_counter >= MINI_BATCH_SIZE_M:
        cur_loss = agent.replay()
        agent.loss_hist.append(cur_loss)

        with open('/home/loss_hist.csv', 'a+', newline="") as f1:
            csv_write = csv.writer(f1)
            csv_write.writerow([offload_epoch_index, cur_loss])
            f1.close()

    # record the reward after convergence
    with open('/home/reward_hist.csv', 'a+', newline="") as f2:
        csv_write = csv.writer(f2)
        csv_write.writerow([offload_epoch_index, r])  # 记得要改
        f2.close()


# initialize our Flask application
app = flask.Flask(__name__)


@app.route("/predict", methods=["POST"])
def predict():
    if flask.request.method == "POST":
        observation = flask.request.form['observation']
        observation = json.loads(observation)
        result = dqn_select_node(observation)
    return flask.jsonify(result)


@app.route("/feedback", methods=["POST"])
def feedback():
    if flask.request.method == "POST":
        observation = flask.request.form['observation']
        observation = json.loads(observation)
        store_feedback(observation)
        return flask.jsonify(["feedback"])


# if this is the main thread of execution first load the model and
# then start the server
if __name__ == "__main__":
    graph = tensorflow.get_default_graph()
    agent = DQNAgent(S_DIM, ACTION_NUM,
                     REPLAY_MEMORY_CAPACITY_M,
                     ARRAY_SIZE,
                     MINI_BATCH_SIZE_M,
                     REPLACE_TARGET_PERIOD,
                     DISCOUNT_FACTOR
                     )
    app.run(host='0.0.0.0', port=4001, threaded=False)
