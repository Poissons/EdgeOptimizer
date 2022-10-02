import asyncio
import json
import pickle
import time

import pandas as pd
import aiohttp
from sys import float_info
from req_data import ReqData

request_sender_platform_para_path = './request_sender_platform_paraA.json'
with open(request_sender_platform_para_path) as file_obj:
    request_sender_platform_para = json.load(file_obj)

request_path = request_sender_platform_para["request_path"]

# IP of edge_master
EDGE_MASTER_IP = request_sender_platform_para["EDGE_MASTER_IP"]
EDGE_MASTER_RECEIVE_REQUEST_PORT = request_sender_platform_para["EDGE_MASTER_RECEIVE_REQUEST_PORT"]

loop = asyncio.get_event_loop()

def create_req(dataset_path):
    req_data_list = []
    for idx, row in pd.read_csv(dataset_path).iterrows():
        req_type = row['type']
        start_time = row['start_time']
        end_time = row['end_time']
        if_simple = (row['if_simple'] == 'TRUE')
        data = row['data']
        if not if_simple:
            data = open(data, 'rb').read()
        req_data_list.append(ReqData(req_type, start_time, end_time, if_simple, data))
    return req_data_list


async def send_request(req_data, session):
    req_data.send_system_time = time.time()
    print(req_data)
    request = [req_data.type, req_data.start_time, req_data.end_time, req_data.if_simple, req_data.data,
               req_data.execute_standard_time, req_data.send_system_time]
    async with session.post(f'/edge_master_receive_request_from_user', data=pickle.dumps(request)) as resp:
        await resp.read()


async def main_coroutine():
    print('center start')
    req_data_list = create_req(request_path)

    time_offset = loop.time() - req_data_list[0].start_time

    now_index = 0

    req_data_len = len(req_data_list)
    async with aiohttp.ClientSession(f'http://{EDGE_MASTER_IP}:{EDGE_MASTER_RECEIVE_REQUEST_PORT}') as session:
        while now_index < req_data_len:
            time_now = loop.time() - time_offset
            time_to_wait = req_data_list[now_index].start_time - time_now
            if time_to_wait > float_info.epsilon:
                print('waiting for next batch')
                await asyncio.sleep(time_to_wait)
                time_now = loop.time() - time_offset

            print('time now:', time_now)

            last_index = now_index
            max_time = time_now + float_info.epsilon
            while now_index < req_data_len:
                req_data = req_data_list[now_index]
                if req_data.start_time > max_time:
                    break
                now_index += 1

            batch_to_send = req_data_list[last_index:now_index]
            print('sending:', batch_to_send)
            await asyncio.gather(*map(lambda req_data: send_request(req_data, session), batch_to_send))
            print(f'progress: {now_index}/{req_data_len}')


if __name__ == '__main__':
    while True:
        loop.run_until_complete(main_coroutine())
