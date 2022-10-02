FROM python:3.6
WORKDIR /home
COPY requirements.txt /home
RUN apt-get update
RUN apt-get install -y tesseract-ocr libtesseract-dev libleptonica-dev
RUN pip install --default-timeout=1000 -r ./requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY app.py /home
EXPOSE 2500
CMD ["python", "app.py"]
