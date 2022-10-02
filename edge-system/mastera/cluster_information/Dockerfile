FROM python:3.6
WORKDIR /home
COPY requirements.txt /home
RUN apt-get update
RUN pip install --default-timeout=1000 -r ./requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY get_cluster_information.py /home
COPY all-config /home/all-config
EXPOSE 9000
CMD ["python", "get_cluster_information.py"]
