# USAGE
# Start the server:
# 	python app.py
# Submit a request via cURL:
# curl http://localhost:4000/predict -X POST -d 'observation=[]'

import os
import flask
import json

import numpy as np

ACTION_NUM = 3
decision = 0


def polling_select_node(arguments):
    global decision
    if decision % 3 == 0:
        ans = 0
    elif decision % 3 == 1:
        ans = 1
    else:
        ans = 2
    decision += 1
    return ans


# initialize our Flask application
app = flask.Flask(__name__)


# observation = ['node_name', ['image_type']]
@app.route("/predict", methods=["POST"])
def predict():
    if flask.request.method == "POST":
        observation = flask.request.form['observation']
        observation = json.loads(observation)
        result = polling_select_node(arguments=observation)
    return flask.jsonify(result)


# then start the server
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=4002, threaded=True)
