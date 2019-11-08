FROM python
RUN pip install flask flask-socketio pymongo
ADD . /todo
WORKDIR /todo

