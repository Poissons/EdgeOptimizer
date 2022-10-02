# USAGE
# Start the server:
# 	python app.py
# Submit a request via cURL:
# curl http://localhost:4000/predict -X POST -d 'observation=[]'

import os
import flask
import json

import numpy as np

ACTION_NUM = 3  # 云+边缘集群


def greedy_select_node(arguments):
    offload_epoch_index = arguments[0]
    request_type = arguments[1]
    pods_situation = arguments[2]['pods_situation']
    trans_time = arguments[2]['trans_time']
    execute_standard_time = arguments[2]['execute_standard_time']

    pods_num = np.zeros(ACTION_NUM, float)
    pods_busy = np.zeros(ACTION_NUM, float)

    for the_type, value in pods_situation.items():
        pods_num[int(the_type)] = value['pods_num']
        pods_busy[int(the_type)] = value['pods_busy']

    pods_num = pods_num / np.sum(pods_num)
    pods_busy = 1 - pods_busy
    cluster_score = pods_num * 0.5 + pods_busy * 0.5

    return np.argmax(cluster_score).item()


# initialize our Flask application
app = flask.Flask(__name__)


# observation = ['node_name', ['image_type']]
@app.route("/predict", methods=["POST"])
def predict():
    if flask.request.method == "POST":
        observation = flask.request.form['observation']
        observation = json.loads(observation)
        result = greedy_select_node(arguments=observation)
    return flask.jsonify(result)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=4000, threaded=True)
