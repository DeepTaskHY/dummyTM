#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import rospkg
import rospy
import threading
import time
from std_msgs.msg import String


PACKAGE_PATH = rospkg.RosPack().get_path('dummy_tm')


# def kb_interface():

#     publisher = rospy.Publisher('/taskExecution', String, queue_size=10)
#     while True:
#         input_msg = input('scene#:')

#         if input_msg == 'q':
#             break

#         msg = json.load(open(f'{PACKAGE_PATH}/msgs/{input_msg}-k.json'))
#         publisher.publish(json.dumps(msg, ensure_ascii=False))
#         rospy.loginfo(json.dumps(msg, ensure_ascii=False))


if __name__ == '__main__':
    rospy.init_node('service_starter_node')
    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

    print('* 로봇의 비전 인식을 통해 사용자를 이미 인지한 상황 가정')
    print()
    print('[1] : 인식한 사용자를 이미 알고 있는 경우에 대한 시나리오')
    print('[2] : 인식된 사용자가 처음 방문한 사람인 경우에 대한 시나리오')
    scene = input('시작하려는 시나리오 번호 입력 : ')

    # msg = json.load(open(f'{PACKAGE_PATH}/msgs/{input_msg}-k.json'))

    user = "Person00{}".format(scene)
    msg = {
        "header": {
            "source": "planning",
            "target": ["knowledge"],
            "content": "knowledge_query",
            "id": 1,
            "timestamp": time.time()
        },
        "knowledge_query": {
            "timestamp": time.time(),
            "type": "social_context",
            "data": [
                {
                    "target": user
                }
            ]
        }
    }

    publisher.publish(json.dumps(msg, ensure_ascii=False))
    rospy.loginfo(json.dumps(msg, ensure_ascii=False))
