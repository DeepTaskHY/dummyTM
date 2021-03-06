#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import re
import rospkg
import rospy
import threading
import time
from std_msgs.msg import String

PACKAGE_PATH = rospkg.RosPack().get_path('dummy_tm')
_start = False
_msg_id = 1
_social_context = dict()
_human_speech = ''
_retry = False
_denial = False
_previous_intent = ''
_end_msg_id = 6
_face_id = None


def time_diff(start_time, end_time):
    time_format = '%Y-%m-%dT%H:%M:%S%z'
    start_time_obj = time.mktime(time.strptime(start_time, time_format))
    end_time_obj = time.mktime(time.strptime(end_time, time_format))

    return end_time_obj - start_time_obj


def time_hour_diff(start_time, end_time):
    return time_diff(start_time, end_time) / 3600


def callback_com(arg):
    global _start, _msg_id, _social_context, _human_speech, _retry, _previous_intent, _end_msg_id, _face_id, _denial
    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

    msg = json.loads(arg.data)
    header = msg['header']
    msg_from = header['source']
    _msg_id = int(header['id'])
    next_msg_id = None

    content_dict = dict()

    if msg_from == 'dialog':
        tts_pub = rospy.Publisher('/action/speech', String, queue_size=10)
        tts_pub.publish(msg['dialog_generation']['dialog'])
        if _msg_id == _end_msg_id or _msg_id == 12:
            _human_speech = ''
            _previous_intent = ''
            _social_context = dict()
            _face_id = None
            time.sleep(20)
            _start = False
        return

    if msg_from == 'knowledge':
        # KM에 신원정보 존재하는지 확인
        if _msg_id == 0:
            if msg.get('knowledge_query'):
                _social_context = msg['knowledge_query']['data'][0]['social_context']

        elif _msg_id == 1 or _msg_id == 4:
            # 존재하면 소셜컨텍스트 채우기
            if msg['knowledge_query']['data'][0].get('social_context'):
                _social_context = msg['knowledge_query']['data'][0]['social_context']
                _face_id = int(_social_context['face_id'])
            next_msg_id = 1
            content_dict['intent'] = 'check_information_user'
            _denial = False
            _retry = False

        elif _msg_id == 9:
            _social_context = msg['knowledge_query']['data'][0]['social_context']
            next_msg_id = 9
            content_dict['intent'] = "transmit_information_medicine"
            _denial = False
            _retry = False
        else:
            return

    if msg_from == 'dialog_intent':
        content = msg['dialog_intent']
        _human_speech = content['speech']
        info = content['information']
        if info.get('speak'): # 물어본 내용에 대한 대답이 "말 안할래", "안 알려줄래" 등의 거부인 경우
            next_msg_id, content_dict['intent'] = fallback_denial()
 
        elif _msg_id == 1:
            # _previous_intent = "check_information_user"
            # 얼굴 인식(ID)이 된 경우 (= 소셜 컨텍스트(이름, 성별, 나이)가 존재하는 경우)
            if _social_context and _social_context.get('name') and _social_context.get('appellation'):
                # "(이름) (호칭) 맞으신가요?"에 대한 대답
                if info.get('positive'):  # 물어본 이름이 맞으면
                    content_dict['intent'] = "check_information_help"
                    _social_context['visitFreq'] += 1
                    request_km = json.load(open(f'{PACKAGE_PATH}/msgs/update.json'))
                    req_time = str(time.time())
                    request_km['header']['timestamp'] = req_time
                    request_km['knowledge_request']['timestamp'] = req_time
                    request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                    request_km['knowledge_request']['data'][0]['predicate'].append({'p': 'visitFreq', 'o': _social_context['visitFreq']})

                    rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                    publisher.publish(json.dumps(request_km, ensure_ascii=False))
                    next_msg_id = 2
                    _denial = False
                    _retry = False
                elif info.get('negative'):  # 물어본 이름이 틀리면
                    _social_context = dict()  # 소셜 컨텍스트 초기화
                    content_dict['intent'] = "check_information_exist_user"
                    next_msg_id = 3
                    _denial = False
                    _retry = False
                else:  # 사용자가 엉뚱한 대답을 하거나 stt 오류로 이상한 대답을 들었을 경우
                    next_msg_id, content_dict['intent'] = fallback_repeat()
            else:  # 얼굴 인식이 안되었을 경우 이름과 나이, 성별을 바로 질문함
                # "처음 뵙겠습니다. 이름과 나이, 성별을 알려주시겠어요?"에 대한 대답
                _social_context['visitFreq'] = 1
                _social_context['sleep_status'] = ''
                _social_context['smoke_status'] = ''
                _social_context['drink_status'] = ''
                _social_context['age'] = None
                _social_context['gender'] = None

                if info.get('negative'): # 물어본 내용에 대한 대답이 "말 안할래", "안 알려줄래" 등의 거부인 경우
                    next_msg_id, content_dict['intent'] = fallback_denial()

                elif info.get('person'):  # 엔티티가 제대로 뽑힌 경우
                    _social_context['name'] = info['person'].get('name')
                    if info.get('gender'):
                        if '남' in info['gender']:
                            _social_context['gender'] = '남성'
                        elif '여' in info['gender']:
                            _social_context['gender'] = '여성'
                        else:
                            pass
                    if info.get('age') is not None and info['age'] is not '':
                        _social_context['age'] = int(info.get('age'))
                    content_dict['intent'] = "check_information_user_age"
                    next_msg_id = 13
                    _denial = False
                    _retry = False

                elif _social_context.get('name') and info.get('age') and not info.get('gender'):
                    _social_context['age'] = int(info.get('age'))
                    content_dict['intent'] = "check_information_user_age"
                    next_msg_id = 13
                    _denial = False
                    _retry = False
                
                elif _social_context.get('name') and info.get('gender') and not info.get('age'):
                    _social_context['gender'] = info['gender']
                    if '남' in _social_context['gender']:
                        _social_context['gender'] = '남성'
                    elif '여' in _social_context['gender']:
                        _social_context['gender'] = '여성'
                    else:
                        pass

                    content_dict['intent'] = "check_information_user_age"
                    next_msg_id = 13
                    _denial = False
                    _retry = False

                elif _social_context.get('name') and info.get('gender') and info.get('age'):
                    _social_context['gender'] = info['gender']
                    if '남' in _social_context['gender']:
                        _social_context['gender'] = '남성'
                    elif '여' in _social_context['gender']:
                        _social_context['gender'] = '여성'
                    else:
                        pass

                    _social_context['age'] = int(info.get('age'))
                    content_dict['intent'] = "check_information_user_age"
                    next_msg_id = 13
                    _denial = False
                    _retry = False

                else:  # 엔티티가 안 뽑힌 경우
                    next_msg_id, content_dict['intent'] = fallback_repeat()

        elif _msg_id == 2:
            print('###################################################################################')
            if info.get('service_desc'):
                print('###################################################################################')
                next_msg_id, content_dict['intent'] = help_repeat()
            elif info.get('medicine'):
                next_msg_id = 9
                query_km = json.load(
                    open(f'{PACKAGE_PATH}/msgs/query_social_context.json'))
                query_km['header']['id'] = next_msg_id
                req_time = time.time()
                query_km['header']['timestamp'] = req_time
                query_km['knowledge_query']['timestamp'] = req_time
                query_km['knowledge_query']['data'][0]['target'] = _social_context['name']

                rospy.loginfo(json.dumps(query_km, ensure_ascii=False))
                publisher.publish(json.dumps(query_km, ensure_ascii=False))
                _denial = False
                _retry = False
                return
            elif info.get('negative'):
                content_dict['intent'] = "saying_good_bye"
                next_msg_id = _end_msg_id

            elif info.get('positive') or info.get('help') or info.get('health'):
                content_dict['intent'] = "check_information_disease"
                next_msg_id = 5
                _denial = False
                _retry = False
            else:
                next_msg_id, content_dict['intent'] = fallback_repeat()

        # '죄송하지만 성함을 알려주세요'에 대한 대답으로 이름을 줌
        elif _msg_id == 3:
            if info.get('negative'):
                next_msg_id, content_dict['intent'] = fallback_denial()
            elif info.get('person'):
                _social_context['name'] = info['person']['name']
                next_msg_id = 4
                query_km = json.load(
                    open(f'{PACKAGE_PATH}/msgs/query_social_context.json'))
                query_km['header']['id'] = next_msg_id
                req_time = time.time()
                query_km['header']['timestamp'] = req_time
                query_km['knowledge_query']['timestamp'] = req_time
                query_km['knowledge_query']['data'][0]['target'] = _social_context['name']
                rospy.loginfo(json.dumps(query_km, ensure_ascii=False))
                publisher.publish(json.dumps(query_km, ensure_ascii=False))
                _denial = False
                _retry = False
                return
            else:
                next_msg_id, content_dict['intent'] = fallback_repeat()

        # '아픈 곳이 있으신가요?' / '기존 질병의 상태는 어떠신가요?' 에 대한 대답
        elif _msg_id == 5:
            if _social_context.get('disease_name'): # '기존 질병의 상태는 어떠신가요?'

                # _social_context['disease_name'] = info['disease_name']
                content_dict['intent'] = "check_information_sleep_2"
                next_msg_id = 8
                if info.get('negative') or info.get('disease_status') == 'negative':    
                    _social_context['disease_status'] = 'negative'
                    _denial = False
                    _retry = False
                elif info.get('disease_status') == 'positive':
                    _social_context['disease_status'] = 'positive'
                    _denial = False
                    _retry = False
                else:
                    _social_context['disease_status'] = 'neutral'
                    next_msg_id, content_dict['intent'] = fallback_repeat()
                
                request_km = json.load(
                    open(f'{PACKAGE_PATH}/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'diseaseStatus', 'o': _social_context['disease_status']})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(request_km, ensure_ascii=False))

                related_d = '통증' if '통증' in _social_context['disease_name'] else _social_context['disease_name']
                request_km = json.load(
                    open(f'{PACKAGE_PATH}/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = 'MedicalRecord'
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'relatedDisease', 'o': related_d})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'targetPerson', 'o': _social_context['name']})

                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'diseaseStatus', 'o': _social_context['disease_status']})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'bloodSugarLevel', 'o': 0})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'cholesterolLevel', 'o': 0})            
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'diastolicBloodPressureLevel', 'o': 0})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'systolicBloodPressureLevel', 'o': 0})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(request_km, ensure_ascii=False))
                # content_dict['intent'] = "check_information_sleep_2"
                # next_msg_id = 8
                
            else: # '아픈 곳이 있으신가요?'
                if info.get('negative'):
                    content_dict['intent'] = "saying_good_bye"
                    next_msg_id = _end_msg_id
                    _denial = False
                    _retry = False
                elif info.get('positive'):
                    content_dict['intent'] = "check_information_disease_name"
                    next_msg_id = 7
                    _denial = False
                    _retry = False
                elif info.get('disease_name'):
                    _social_context['disease_name'] = info['disease_name']
                    
                    related_d = '통증' if '통증' in _social_context['disease_name'] else _social_context['disease_name']

                    request_km = json.load(
                        open(f'{PACKAGE_PATH}/msgs/create.json'))
                    req_time = time.time()
                    request_km['header']['timestamp'] = req_time
                    request_km['knowledge_request']['timestamp'] = req_time
                    request_km['knowledge_request']['data'][0]['subject'] = 'MedicalRecord'
                    request_km['knowledge_request']['data'][0]['predicate'].append(
                        {'p': 'relatedDisease', 'o': related_d})
                    request_km['knowledge_request']['data'][0]['predicate'].append(
                        {'p': 'targetPerson', 'o': _social_context['name']})
                    # request_km['knowledge_request']['data'][0]['predicate'].append(
                    #     {'p': 'diseaseStatus', 'o': _social_context['disease_status']})
                    request_km['knowledge_request']['data'][0]['predicate'].append(
                        {'p': 'bloodSugarLevel', 'o': 0})
                    request_km['knowledge_request']['data'][0]['predicate'].append(
                        {'p': 'cholesterolLevel', 'o': 0})            
                    request_km['knowledge_request']['data'][0]['predicate'].append(
                        {'p': 'diastolicBloodPressureLevel', 'o': 0})
                    request_km['knowledge_request']['data'][0]['predicate'].append(
                        {'p': 'systolicBloodPressureLevel', 'o': 0})

                    rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                    publisher.publish(json.dumps(
                        request_km, ensure_ascii=False))

                    content_dict['intent'] = "check_information_disease"
                    next_msg_id = 5
                    _denial = False
                    _retry = False
                else:
                    next_msg_id, content_dict['intent'] = fallback_repeat()

        # 어디가 아프신가요? 에 대한 대답
        elif _msg_id == 7:
            if info.get('negative'):
                next_msg_id, content_dict['intent'] = fallback_denial()
            elif info.get('disease_name'):
                _social_context['disease_name'] = info['disease_name']
                related_d = '통증' if '통증' in _social_context['disease_name'] else _social_context['disease_name']
                request_km = json.load(
                    open(f'{PACKAGE_PATH}/msgs/create.json'))
                req_time = time.time()
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = 'MedicalRecord'
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'relatedDisease', 'o': related_d})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'targetPerson', 'o': _social_context['name']})

                # request_km['knowledge_request']['data'][0]['predicate'].append(
                #     {'p': 'diseaseStatus', 'o': _social_context['disease_status']})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'bloodSugarLevel', 'o': 0})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'cholesterolLevel', 'o': 0})            
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'diastolicBloodPressureLevel', 'o': 0})
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'systolicBloodPressureLevel', 'o': 0})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(
                    request_km, ensure_ascii=False))

                content_dict['intent'] = "check_information_disease"
                next_msg_id = 5
                _denial = False
                _retry = False
            else:
                next_msg_id, content_dict['intent'] = fallback_repeat()

        # 하루 평균 수면 시간이 몇시간입니까 에 대한 대답
        elif _msg_id == 8:
            content_dict['intent'] = "check_information_drink"
            next_msg_id = 10

            if info.get('negative'):
                _retry = False
                _denial = False
                _social_context['sleep_status'] = 'negative'
                request_km = json.load(
                    open(PACKAGE_PATH + '/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'sleepStatus', 'o': _social_context['sleep_status']})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(
                    request_km, ensure_ascii=False))

            elif info.get('sleep_average'):
                _retry = False
                _denial = False
                sleep_time = time_hour_diff(
                    info.get('sleep_average').get('startDateTime'),
                    info.get('sleep_average').get('endDateTime'))
                if sleep_time >= 8:
                    _social_context['sleep_status'] = 'positive'
                else:
                    _social_context['sleep_status'] = 'negative'
                request_km = json.load(
                    open(PACKAGE_PATH + '/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'sleepStatus', 'o': _social_context['sleep_status']})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(
                    request_km, ensure_ascii=False))

            else:
                next_msg_id, content_dict['intent'] = fallback_repeat()

        elif _msg_id == 10:
            content_dict['intent'] = "check_information_smoke"
            next_msg_id = 11

            if info.get('negative'):
                _retry = False
                _denial = False
                _social_context['drink_status'] = 'positive'
                request_km = json.load(
                    open(PACKAGE_PATH + '/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'drinkStatus', 'o': _social_context['drink_status']})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(
                    request_km, ensure_ascii=False))

            elif info.get('drink_average'):
                _retry = False
                _denial = False
                _social_context['drink_status'] = 'negative'
                request_km = json.load(
                    open(PACKAGE_PATH + '/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'drinkStatus', 'o': _social_context['drink_status']})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(
                    request_km, ensure_ascii=False))

            else:
                next_msg_id, content_dict['intent'] = fallback_repeat()

        elif _msg_id == 11:
            content_dict['intent'] = "transmit_information_advice"
            next_msg_id = 12
            
            if info.get('negative'):
                _retry = False
                _denial = False
                _social_context['smoke_status'] = 'positive'
                request_km = json.load(
                    open(PACKAGE_PATH + '/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']

                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'smokeStatus', 'o': _social_context['smoke_status']})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(
                    request_km, ensure_ascii=False))

            elif info.get('smoke_average') or info.get('smoke'):
                _retry = False
                _denial = False
                _social_context['smoke_status'] = 'negative'
                request_km = json.load(
                    open(PACKAGE_PATH + '/msgs/update.json'))
                req_time = str(time.time())
                request_km['header']['timestamp'] = req_time
                request_km['knowledge_request']['timestamp'] = req_time
                request_km['knowledge_request']['data'][0]['subject'] = _social_context['name']
                request_km['knowledge_request']['data'][0]['predicate'].append(
                    {'p': 'smokeStatus', 'o': _social_context['smoke_status']})
                rospy.loginfo(json.dumps(request_km, ensure_ascii=False))
                publisher.publish(json.dumps(
                    request_km, ensure_ascii=False))

            else:
                next_msg_id, content_dict['intent'] = fallback_repeat()

        elif _msg_id == 13:
            if _social_context.get('age'):  # "나이가 (나이)세가 맞으신가요?" 에 대한 대답
                if info.get('positive'):  # 맞다고 대답한 경우
                    if _social_context['age'] < 20:
                        _social_context['age_group'] = '청소년'
                        _social_context['appellation'] = '님'
                    elif _social_context['age'] <= 80:
                        _social_context['age_group'] = '성인'
                        _social_context['appellation'] = '님'
                    else:
                        _social_context['age_group'] = '노인'
                        _social_context['appellation'] = '어르신'
                    content_dict['intent'] = "check_information_user_gender"
                    next_msg_id = 14
                elif info.get('negative'):  # 나이를 틀렸으면
                    content_dict['intent'] = "check_information_user_age"
                    _social_context['age'] = None
                    next_msg_id = _msg_id
                _denial = False
                _retry = False
            else:
                if info.get('age'):  # "나이를 다시 말씀해주시겠어요?" 에 대한 대답 # 나이를 답한 경우
                    _social_context['age'] = int(info['age'])
                    content_dict['intent'] = "check_information_user_age"
                    next_msg_id = _msg_id
                    _denial = False
                    _retry = False
                else:
                    next_msg_id, content_dict['intent'] = fallback_repeat()

        elif _msg_id == 14:
            if _social_context.get('gender'):
                if info.get('positive'):  # 맞다고 대답한 경우
                    content_dict['intent'] = "check_information_user_name"
                    next_msg_id = 15
                    _retry = False
                elif info.get('negative'):  # 성별을 틀렸으면
                    content_dict['intent'] = "check_information_user_name"
                    if _social_context['gender'] == '남성':
                        _social_context['gender'] = '여성'
                    elif _social_context['gender'] == '여성':
                        _social_context['gender'] = '남성'
                    next_msg_id = 15
                    _retry = False
                else:
                    next_msg_id, content_dict['intent'] = fallback_repeat()
            else:
                if info.get('gender'):
                    _social_context['gender'] = info['gender']
                    content_dict['intent'] = "check_information_user_name"
                    next_msg_id = 15
                    _retry = False
                else:
                    next_msg_id, content_dict['intent'] = fallback_repeat()

        elif _msg_id == 15:
            if _social_context['name']:
                if info.get('positive'):
                    request_km = json.load(
                        open(f'{PACKAGE_PATH}/msgs/create.json'))
                    req_time = str(time.time())
                    request_km['header']['timestamp'] = req_time
                    request_km['header']['id'] = _msg_id
                    req_content = dict()
                    req_content['subject'] = 'Person'
                    req_content['predicate'] = list()

                    req_content['predicate'].append(
                        {'p': 'fullName', 'o': _social_context['name']})
                    req_content['predicate'].append(
                        {'p': 'faceID', 'o': _face_id})
                    req_content['predicate'].append(
                        {'p': 'isAged', 'o': _social_context['age_group']})
                    req_content['predicate'].append(
                        {'p': 'age', 'o': _social_context['age']})
                    req_content['predicate'].append(
                        {'p': 'gender', 'o': _social_context['gender']})
                    req_content['predicate'].append(
                        {'p': 'hasAppellation', 'o': _social_context['appellation']})
                    req_content['predicate'].append(
                        {'p': 'visitFreq', 'o': _social_context['visitFreq']})
                    req_content['predicate'].append(
                        {'p': 'sleepStatus', 'o': _social_context['sleep_status']})
                    req_content['predicate'].append(
                        {'p': 'drinkStatus', 'o': _social_context['drink_status']})
                    req_content['predicate'].append(
                        {'p': 'smokeStatus', 'o': _social_context['smoke_status']})
                    request_km['knowledge_request']['data'][0] = req_content
                    request_km['knowledge_request']['timestamp'] = req_time

                    rospy.loginfo(json.dumps(
                        request_km, ensure_ascii=False))
                    publisher.publish(json.dumps(
                        request_km, ensure_ascii=False))
                    content_dict['intent'] = "check_information_disease"
                    next_msg_id = 5
                    _retry = False

                elif info.get('negative'):
                    if info.get('person'):
                        _social_context['name'] = info['person']['name']
                        content_dict['intent'] = "check_information_user_name"
                        next_msg_id = _msg_id
                        _retry = False
                    else:
                        content_dict['intent'] = "check_information_user_name"
                        _social_context['name'] = None
                        next_msg_id = _msg_id
                        _retry = False
                else:
                    next_msg_id, content_dict['intent'] = fallback_repeat()
            else:
                if info.get('person'):
                    _social_context['name'] = info['person'].get('name')
                    content_dict['intent'] = 'check_information_user_name'
                    next_msg_id = _msg_id
                    _retry = False
                else:
                    next_msg_id, content_dict['intent'] = fallback_repeat()

        else:
            return

    if not content_dict:
        return

    content_dict['previous_intent'] = _previous_intent
    _previous_intent = content_dict['intent']
    content_dict['human_speech'] = _human_speech
    content_dict['social_context'] = _social_context
    response_msg = generate_message(
        next_msg_id, "dialog", "dialog_generation", content_dict)

    rospy.loginfo(json.dumps(response_msg, ensure_ascii=False))
    publisher.publish(json.dumps(response_msg, ensure_ascii=False))

    return


def help_repeat():
    global _msg_id, _end_msg_id
    
    intent = "help_repeat_intent"
    next_id = _msg_id
    
    return next_id, intent


def fallback_repeat():
    global _retry, _msg_id, _end_msg_id
    if not _retry:
        intent = "fallback_repeat_intent"
        next_id = _msg_id
        _retry = True
    else:  # 한번더 같은 질문했는데도 원하는 대답이 아닌 경우 대화 종료
        intent = "fallback_saying_good_bye"
        next_id = _end_msg_id
    return next_id, intent


def fallback_denial():
    global _denial, _msg_id, _end_msg_id
    if not _denial:
        intent = "fallback_denial_intent"
        next_id = _msg_id
        _denial = True
    else:  # 한번더 같은 질문했는데도 원하는 대답이 아닌 경우 대화 종료
        intent = "fallback_saying_good_bye"
        next_id = _end_msg_id
    return next_id, intent


def generate_message(msg_id: int,
                     target: str,
                     content_name: str,
                     content_dict: dict) -> dict:
    msg = {
        'header': {
            'id': msg_id,
            'timestamp': time.time(),
            'source': 'planning',
            'target': [target],
            'content': content_name
        }
    }

    msg.update(dialog_generation=content_dict)

    return msg


def callback_exe(arg):
    global _msg_id, _social_context
    msg = json.loads(arg.data)
    header = msg['header']

    if 'planning' in header['target']:
        _msg_id = header['id']
        if _msg_id == 1:
            if msg.get('dialog_generation'):
                _social_context = msg['dialog_generation']['social_context']

    return


def callback_vision(arg):
    global _face_id, _start

    msg = json.loads(arg.data)
    fid = int(msg['face_recognition']['face_id'])
    if not _face_id:
        _face_id = fid
    elif fid != _face_id:
        _face_id = fid
    else:
        pass

    if not _start:
        publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

        try:
            t_point = msg['face_recognition']['timestamp']
            msg = json.load(
                open(f'{PACKAGE_PATH}/msgs/query_face_recognition.json', 'r'))
            msg['header']['id'] = 1
            req_time = str(time.time())
            msg['header']['timestamp'] = req_time
            msg['knowledge_query']['timestamp'] = req_time
            msg['knowledge_query']['data'][0]['face_id'] = int(fid)
            msg['knowledge_query']['data'][0]['timestamp'] = req_time
            publisher.publish(json.dumps(msg, ensure_ascii=False))
            rospy.loginfo(json.dumps(msg, ensure_ascii=False))
            _start = True
        except ValueError:
            pass
    else:
        time.sleep(0.5)
    return


def callback_speech(arg):
    global _human_speech, _msg_id

    publisher = rospy.Publisher('/taskExecution', String, queue_size=10)

    msg = json.loads(arg.data)
    _human_speech = msg['human_speech']['stt']

    msg = json.load(
        open(f'{PACKAGE_PATH}/msgs/human_speech.json', 'r'))
    msg['header']['id'] = _msg_id
    msg['header']['timestamp'] = time.time()
    msg['human_speech']['speech'] = _human_speech

    publisher.publish(json.dumps(msg, ensure_ascii=False))
    rospy.loginfo(json.dumps(msg, ensure_ascii=False))

    return


if __name__ == '__main__':
    
    rospy.init_node('dummyTM_node')
    rospy.loginfo('Start dummy TM')

    rospy.Subscriber('/taskCompletion', String, callback_com)
    rospy.Subscriber('/taskExecution', String, callback_exe)
    rospy.Subscriber('/recognition/face_id', String, callback_vision)
    rospy.Subscriber('/recognition/speech', String, callback_speech)
    rospy.Publisher('/taskExecution', String, queue_size=10)
    rospy.Publisher('/action/speech', String, queue_size=10)

    rospy.spin()
