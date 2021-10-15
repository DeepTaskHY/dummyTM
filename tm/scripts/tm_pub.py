#!/usr/bin/python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import String
import rospkg

import json, time, threading

PACKAGE_PATH = rospkg.RosPack().get_path('tm')

def kb_interface():
    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)
    while True:
        input_msg = input("scene#:")

        msg = json.load(open(PACKAGE_PATH+'/msgs/{}.json'.format(input_msg)))

        rospy.loginfo(json.dump(msg, ensure_ascii=False))
        publisher.publish('/taskExecution', json.dump(msg, ensure_ascii=False))


if __name__ == '__main__':
    rospy.init_node('tm_pub_node')

    t = threading.Thread(target=kb_interface)
    t.start()
    rospy.spin()