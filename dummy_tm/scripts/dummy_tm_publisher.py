#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import rospkg
import rospy
import threading
import time
from std_msgs.msg import String


PACKAGE_PATH = rospkg.RosPack().get_path('dummy_tm')


def kb_interface():
    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

    while True:
        input_msg = input('scene#:')

        if input_msg == 'q':
            break

        msg = json.load(open(f'{PACKAGE_PATH}/msgs/{input_msg}-k.json'))
        publisher.publish(json.dumps(msg, ensure_ascii=False))
        rospy.loginfo(json.dumps(msg, ensure_ascii=False))


if __name__ == '__main__':
    rospy.init_node('dummy_tm_pub_node')
    t = threading.Thread(target=kb_interface)
    t.start()
    rospy.spin()
