class ReqData(object):
    def __init__(self, edge_name, type, start_time, end_time, if_simple, data=None, execute_standard_time=0, send_system_time=0):
        self.edge_name = edge_name
        self.type = int(type)
        self.start_time = int(start_time)
        self.end_time = int(end_time)
        self.if_simple = if_simple
        self.data = data
        self.execute_standard_time = int(end_time) - int(start_time)
        self.send_system_time = send_system_time

    def __repr__(self):
        return f'ReqData(type={self.type},start_time={self.start_time},end_time={self.end_time},' \
               f'if_simple={self.if_simple},execute_standard_time={self.execute_standard_time},' \
               f'send_system_time={self.send_system_time}) '
