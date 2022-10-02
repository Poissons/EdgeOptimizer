# USAGE
# Start the server:
# 	python app.py
# Submit a request via cURL:
#  curl http://localhost:3100/predict -X POST -d 'observation=2.0'
import os
import flask
import io
import json
import time
import random

#CPU 
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# initialize our Flask application and the Keras model
app = flask.Flask(__name__)

@app.route("/predict", methods=["POST"])
def predict():
	if flask.request.method == "POST":
		observation = flask.request.form['observation']
		observation = json.loads(observation)
		time.sleep(observation)
		result =  "Time:" + str(observation)
	return flask.jsonify(result)

# if this is the main thread of execution first load the model and
# then start the server
if __name__ == "__main__":
	app.run(host='0.0.0.0',port=5011,threaded=True)
