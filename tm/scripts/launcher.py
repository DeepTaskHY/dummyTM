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
_speech_content = ""

def callback_com(arg):
    global _scene, _social_context, _speech_content
    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

    msg = json.loads(arg.data)
    header = msg['header']
    msg_from = header['source']
    msg_id = header['id']

    if msg_from == "dialog_generation":
        print(msg['dialog_generation']['dialog'])

    if msg_from == "dialog_intent":
        content = msg['dialog_intent']
        _speech_content = content['speech']
        info = content['information']
        
        if msg_id == 0:
            return

        if msg_id == 1:
            
            # 물어본 이름이 맞으면
            if info.get('positive') is not None:
                
                if info['positive'] != "":
                    _scene = 2

            # 물어본 이름이 틀리면
            if info.get('negative') is not None:
                
                if info['negative'] != '':
                    _scene = 3
                    _social_context = dict()
                
            # 처음부터 인식이 안되었을 경우 이름과 나이, 성별을 바로 질문함
            if info.get('person') is not None:
                
                if info['person'] != '':
                    if info['person'].get('name'):
                        if info['person']['name'] != '':
                            name = info['person']['name']
                else:
                    name = _social_context['name'] 
                
                if info.get('age') is not None:
                    age = info['age']

                if int(age) <= 20:
                    ageGroup = "청소년"
                    appellation = '님'
                elif int(age) <= 80:
                    ageGroup = "성인"
                    appellation = '님'
                else:
                    ageGroup = "노인"
                    appellation = '어르신'
                
                if info.get('gender') is not None:
                    gender = info['gender']

                if gender in ['남자', '남성', '남']:
                    gender = '남성'
                else:
                    gender = '여성'
                
                request_km = json.load(open(PACKAGE_PATH + '/msgs/create.json'))
                request_km['knowledge_request']['data'][0]['subject'] = "Person"
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"fullName", "o":name})
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"isAged", "o":ageGroup})
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"gender", "o":gender})
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"hasAppellation", "o":appellation})
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"visitFreq", "o":1})
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"sleepStatus", "o":""})
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"drinkStatus", "o":""})
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"smokeStatus", "o":""})
                # rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(request_km, ensure_ascii=False))
                
                _social_context['name'] = name
                _social_context['age'] = ageGroup
                _social_context['gender'] = gender
                _social_context['appellation'] = appellation
                _social_context['visitFreq'] = 1
                _social_context['sleep_status'] = ""
                _social_context['smoke_status'] = ""
                _social_context['drink_status'] = ""
                
                _scene = 5

        if msg_id == 2:
            if info.get('medicine'):

                if info['medicine'] != '':
                    query_km = json.load(open(PACKAGE_PATH + '/msgs/9-k.json'))
                    query_km['knowledge_query']['data'][0]['target'] = _social_context['name']
                    # rospy.loginfo(json.dumps(query_km, ensure_ascii=False))
                    publisher.publish(json.dumps(query_km, ensure_ascii=False))
                    return

            if info.get('negative'):
                if info['negative'] != '':
                    _scene = 6

            if info.get('health'):
                if info.get('check') and info['check'] != '':
                    _scene = 5

        # '성함알려주세요'에 대한 대답으로 이름을 줌
        if msg_id == 3:
            if info.get('person'):
                _social_context['name'] = info['person']['name']
                _scene = 4
                query_km = json.load(open(PACKAGE_PATH + '/msgs/{}.json'.format(_scene)))
                query_km['knowledge_query']['data'][0]['target'] = _social_context['name']
                # rospy.loginfo(json.dumps(query_km, ensure_ascii=False))
                publisher.publish(json.dumps(query_km, ensure_ascii=False))
                return

        # '아픈 곳이 있으신가요?' / '기존 질병의 상태는 어떠신가요?' 에 대한 대답
        if msg_id == 5:
            if _social_context.get('disease_name'):
                if info.get('negative'):
                    if info['negative'] != '':
                        _social_context['disease_status'] = 'negative'
                elif info.get('positive'):
                    if info['positive'] != '':
                        _social_context['disease_status'] = 'positive'
                else:
                    _social_context['disease_status'] = 'neutral'
                request_km = json.load(open(PACKAGE_PATH + '/msgs/update.json'))
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                request_km['knowledge_request']['data'][0]['predicate'].append({"p":"diseaseStatus", "o":_social_context['disease_status']})
                # rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(request_km, ensure_ascii=False))

                _scene = 8
            else:
                if info.get('negative'):
                    if info['negative'] != '':
                        _scene = 6

                if info.get('positive'):
                    if info['positive'] != '':
                        _scene = 7

        # 어디가 아프신가요? 에 대한 대답
        if msg_id == 7:
            if info.get('disease_name'):
                if info['disease_name'] != '':
                    _scene = 5
                    _social_context['disease_name'] = info['disease_name']
                    request_km = json.load(open(PACKAGE_PATH + '/msgs/create.json'))
                    request_km['knowledge_request']['data'][0]['subject'] = "MedicalRecord"
                    request_km['knowledge_request']['data'][0]['predicate'].append({"p":"relatedDisease", "o":_social_context['disease_name']})
                    request_km['knowledge_request']['data'][0]['predicate'].append({"p":"targetPerson", "o":_social_context['name']})
                    # rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                    publisher.publish(json.dumps(request_km, ensure_ascii=False))

        # 하루 평균 수면 시간이 몇시간입니까 에 대한 대답
        if msg_id == 8:
            if info.get('sleep_average'):
                
                if info['sleep_average'] != '':
                    _scene = 10
                    sleep_time = float(re.findall('\d+', info['sleep_average'])[0])

                    if sleep_time >= 8:
                        _social_context['sleep_status'] = "positive"
                    else:
                        _social_context['sleep_status'] = "negative"

                    response_k = json.load(open(PACKAGE_PATH + '/msgs/update.json'.format(_scene)))
                    response_k['knowledge_request']['data'][0]['subject'] = _social_context['name']
                    pred = dict()
                    pred['p'] = 'sleepStatus'
                    pred['o'] = _social_context['sleep_status']
                    response_k['knowledge_request']['data'][0]['predicate'].append(pred)
                    # rospy.loginfo(json.dumps(response_k, ensure_ascii=False))
                    publisher.publish(json.dumps(response_k, ensure_ascii=False))

        if msg_id == 10:
            if info.get('drink_average'):
                if info['drink_average'] != '':
                    
                    average_drink = float(re.findall('\d+', info['drink_average']))

                    _scene = 11
                    
                    _social_context['drink_status'] = "negative"
                    response_k = json.load(open(PACKAGE_PATH + '/msgs/update.json'.format(_scene)))
                    response_k['knowledge_request']['data'][0]['subject'] = _social_context['name']
                    pred = dict()
                    pred['p'] = 'drinkStatus'
                    pred['o'] = _social_context['drink_status']
                    response_k['knowledge_request']['data'][0]['predicate'].append(pred)
                    # rospy.loginfo(json.dumps(response_k, ensure_ascii=False))
                    publisher.publish(json.dumps(response_k, ensure_ascii=False))
            _scene = 11

        if msg_id == 11:
            if info.get('smoke_average'):
                if info['smoke_average'] != '':
                    average_smoke = float(re.findall('\d+', info['smoke_average']))
                    _scene = 12
                    _social_context['smoke_status'] = 'negative'
                    response_k = json.load(open(PACKAGE_PATH + '/msgs/update.json'.format(_scene)))
                    response_k['knowledge_request']['data'][0]['subject'] = _social_context['name']
                    pred = dict()
                    pred['p'] = 'smokeStatus'
                    pred['o'] = _social_context['smoke_status']
                    response_k['knowledge_request']['data'][0]['predicate'].append(pred)
                    # rospy.loginfo(json.dumps(response_k, ensure_ascii=False))
                    publisher.publish(json.dumps(response_k, ensure_ascii=False))
            _scene = 12
        if msg_id == 13:
            pass

        response = json.load(open(PACKAGE_PATH + '/msgs/{}.json'.format(_scene)))
        response['dialog_generation']['social_context'] = _social_context
        response['dialog_generation']['human_speech'] = _speech_content
        # rospy.loginfo(json.dumps(response, ensure_ascii=False))
        publisher.publish(json.dumps(response, ensure_ascii=False))

    if msg_from == "knowledge":
        # KM에 신원정보 존재하는지 확인
        if msg_id == 1:
            if msg['knowledge_query']['data'][0].get('social_context'):
                _social_context = msg['knowledge_query']['data'][0]['social_context']
            _scene = 1

        if msg_id == 4:
            # 존재하면
            if msg['knowledge_query']['data'][0].get('social_context'):
                _social_context = msg['knowledge_query']['data'][0]['social_context']
            _scene = 1

        if msg_id == 9:

            _scene = 9
            _social_context = msg['knowledge_query']['data'][0]['social_context']


        response = json.load(open(PACKAGE_PATH + '/msgs/{}.json'.format(_scene)))
        response['dialog_generation']['social_context'] = _social_context
        response['dialog_generation']['human_speech'] = _speech_content
        # rospy.loginfo(json.dumps(response, ensure_ascii=False, indent=4))
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
        
        if input_msg == 'q':
            break

        msg = {
              "header": {
                "source": "planning",
                "target": ["dialog_intent"],
                "content": "dialog_intent",
                "id": _scene,
                "timestamp": time.time()
              },
              "dialog_intent": {
                "speech": input_msg
              }
        }

        # rospy.loginfo(json.dumps(msg, ensure_ascii=False))
        publisher.publish(json.dumps(msg, ensure_ascii=False))


def callback_exe(arg):
    global _scene, _social_context
    msg = json.loads(arg.data)
    header = msg['header']

    _scene = header['id']
    
    if _scene == 1:
        if msg.get('dialog_generation'):
            _social_context = msg['dialog_generation']['social_context']
            # print(_social_context)

    return


if __name__ == '__main__':
    rospy.init_node('tm_node')
    rospy.loginfo('Start dummy TM')

    rospy.Subscriber('/taskCompletion', String, callback_com)
    rospy.Subscriber('/taskExecution', String, callback_exe)

    t = threading.Thread(target=kb_interface)
    t.start()

    rospy.spin()
