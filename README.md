# Introduction Of *EdgeOptimizer*
In order to give interested readers an intuitive understanding of *EdgeOptimizer*, such as a relative knowledge of the functions of each component, a corresponding introduction is made here according to the location where the modules are placed, with a total of three placement locations, namely cloud, edge, and end. The full code file is divided into three parts, called cloud-system, edge-system, and request-system. 

## Prequisites
The code runs on Python 3 on Linux (Ubuntu). In order to use *EdgeOptimizer*, users must install Python3, Docker, K8s (version 1.18.0) and Metrics Server.

## Getting Started
* place folder cloud-system on the master node of cloud cluster. Then run app_flask.py
* place folder edge-system on the master node of the first edge cluster. Then run node_master_control1.py
  place folder edge-system on the master node of the second edge cluster. Then run node_master_control2.py
* place folder request-system on the first end device. Then run request_sender_platformA.py
  place folder request-system on the second end device. Then run request_sender_platformB.py
