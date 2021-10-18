#!/usr/bin/python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import String
import rospkg

import json, time, threading, re

# PACKAGE_PATH = rospkg.RosPack().get_path('tm')
PACKAGE_PATH = '..'

_scene = 0
_social_context = dict()
_medical_status = dict()


def callback_com(arg):
    global _scene, _social_context, _medical_status
    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

    msg = json.loads(arg.data)
    header = msg['header']
    msg_from = header['source']
    msg_id = header['id']

    if msg_from == "dialog_generation":
        print(msg['dialog_generation']['dialog'])

    if msg_from == "dialog_intent":
        content = msg['human_speech']
        info = content['information']

        if msg_id == 1:
            # 물어본 이름이 맞으면
            
            if info.get('positive'):
                if info['positive'] != "":
                    _scene = 2

            # 물어본 이름이 아니면
            if info.get('negative'):
                if info['negative'] != '':
                    _scene = 3
                    _social_context = dict()

        if msg_id == 2:
            if info.get('medicine'):

                if info['medicine'] != '':
                    response = json.load(open(PACKAGE_PATH + '/msgs/9-k.json'))
                    response['knowledge_query']['data']['target'] = _social_context['name']
                    publisher.publish(json.dumps(response, ensure_ascii=False))
                    return

            if info.get('negative'):
                if info['negative'] != '':
                    _scene = 6

            if info.get('health_check'):
                if info['health_check'] != '':
                    _scene = 10

        # '성함알려주세요'에 대한 대답으로 이름을 줌
        if msg_id == 3:
            if info.get('name'):
                _scene = 4

        # '(신원정보)를 알려주시겠어요?'에 대한 대답
        if msg_id == 5:
            
            if info.get('name'):
                if info['name'] != '':
                    _social_context['name'] = info['name']

            if info.get('gender'):
                if info['gender'] != '':
                    _social_context['gender'] = info['gender']
            
            if info.get('age'):
                if info['age'] != '':
                    _social_context['age'] = info['age']

            if len(list(_social_context.keys())) == 3:
                _scene = 7
            else:
                pass

        if msg_id == 7:
            if info.get('negative'):
                if info['negative'] != '':
                    _scene = 6

            if info.get('positive'):
                if info['positive'] != '':
                    _scene = 8

        if msg_id == 8:
            if info.get('disease'):
                if info['disease'] != '':
                    _scene = 10
                    _social_context['disease'] = info['disease']

        if msg_id == 10:
            if info.get('disease_status'):
                if info['disease_status'] != '':
                    _scene = 11
                    _social_context['disease_status'] = info['disease_status']

        if msg_id == 11:
            if info.get('sleep_time'):
                
                if info['sleep_time'] != '':
                    _scene = 12
                    sleep_time = float(re.findall('\d+', info['sleep_time'])[0])

                    if sleep_time >= 7:
                        _social_context['sleep_status'] = "positive"
                    else:
                        _social_context['sleep_status'] = "negative"

                    response_k = json.load(open(PACKAGE_PATH + '/msgs/knowledge_request.json'.format(_scene)))
                    response_k['knowledge_request']['data'][0]['subject'] = _social_context['name']
                    response_k['knowledge_request']['data'][0]['predicate'][0]['p'] = 'sleepStatus'
                    response_k['knowledge_request']['data'][0]['predicate'][0]['o'] = _social_context['sleep_status']
                    publisher.publish(json.dumps(response_k, ensure_ascii=False))

        if msg_id == 12:
            if info.get('positive'):
                if info['positive'] != '':
                    _scene = 13
            if info.get('negative'):
                if info['negative'] != '':
                    _scene = 14

        if msg_id == 13:
            if info.get('average_drink'):
                if info['average_drink'] != '':
                    average_drink = float(re.findall('\d+', info['average_drink']))
                    _scene = 14
                    _social_context['average_drink'] = average_drink
                    response_k = json.load(open(PACKAGE_PATH + '/msgs/knowledge_request.json'.format(_scene)))
                    response_k['knowledge_request']['data'][0]['subject'] = _social_context['name']
                    response_k['knowledge_request']['data'][0]['predicate'][0]['p'] = 'averageDrink'
                    response_k['knowledge_request']['data'][0]['predicate'][0]['o'] = _social_context['average_drink']
                    publisher.publish(json.dumps(response_k, ensure_ascii=False))

        if msg_id == 14:
            if info.get('positive'):
                if info['positive'] != '':
                    _scene = 15
            if info.get('negative'):
                if info['negative'] != '':
                    _scene = 16                    

        if msg_id == 15:
            if info.get('average_smoke'):
                if info['average_smoke'] != '':
                    average_smoke = float(re.findall('\d+', info['average_smoke']))
            
                    _scene = 16
                    _social_context['average_smoke'] = average_smoke
                    response_k = json.load(open(PACKAGE_PATH + '/msgs/knowledge_request.json'.format(_scene)))
                    response_k['knowledge_request']['data'][0]['subject'] = _social_context['name']
                    response_k['knowledge_request']['data'][0]['predicate'][0]['p'] = 'averageSmoke'
                    response_k['knowledge_request']['data'][0]['predicate'][0]['o'] = _social_context['average_smoke']
                    publisher.publish(json.dumps(response_k, ensure_ascii=False))

        response = json.load(open(PACKAGE_PATH + '/msgs/{}.json'.format(_scene)))
        response['dialog_generation']['social_context'] = _social_context
        response['dialog_generation']['human_speech'] = content['speech']
        publisher.publish(json.dumps(response, ensure_ascii=False))

    if msg_from == "knowledge":
        # KM에 신원정보 존재하는지 확인
        if msg_id == 4:
            # 존재하면
            try:
                _social_context = msg['knowledge_query']['data'][0]['social_context']
                _scene = 1
            # 없으면
            except IndexError:
                _social_context['name'] = msg['knowledge_query']['data'][0]['target']
                _scene = 5
        if msg_id == 9:
            _scene = 9
            _medical_status = msg['knowledge_query']['data'][0]['medical_status']

        response = json.load(open(PACKAGE_PATH + '/msgs/{}.json'.format(_scene)))
        response['dialog_generation']['social_context'] = _social_context
        response['dialog_generation']['medical_status'] = _medical_status
        response['dialog_generation']['human_speech'] = content['speech']
        publisher.publish(json.dumps(response, ensure_ascii=False))

    return


def generate_message(msg_id: int,
                     target: str,
                     content_name: str,
                     content_dict: dict) -> dict:
    msg = {
        "header": {
            "id": msg_id,
            "timestamp": time.time(),
            "source": "planning",
            "target": [target],
            "content": content_name
        }
    }
    msg.update(dialog_generation=content_dict)

    return msg


def kb_interface():
    global _scene
    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

    while True:

        input_msg = input("사람:")

        msg = {
              "header": {
                "source": "planning",
                "target": ["dialog_intent"],
                "content": "human_speech",
                "id": _scene,
                "timestamp": time.time()
              },
              "human_speech": {
                "speech": input_msg
              }
        }

        rospy.loginfo(json.dumps(msg, ensure_ascii=False))
        publisher.publish(json.dumps(msg, ensure_ascii=False))


def callback_exe(arg):
    global _scene, _social_context
    msg = json.loads(arg.data)
    header = msg['header']

    _scene = header['id']
    if _scene == 1:
        _social_context = msg['dialog_generation']['social_context']

    return


if __name__ == '__main__':
    rospy.init_node('tm_node')
    rospy.loginfo('Start TM')

    rospy.Subscriber('/taskCompletion', String, callback_com)
    rospy.Subscriber('/taskExecution', String, callback_exe)

    t = threading.Thread(target=kb_interface)
    t.start()

    rospy.spin()
