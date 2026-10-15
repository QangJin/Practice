# -*- coding: utf-8 -*-
# version 4
# developed by zk chen
import random
import sys
import time
import requests
import re
import json

# 让控制台输出统一使用 UTF-8 并实时刷新，避免中文乱码和重定向到文件时看不到进度
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

# 以下的csrftoken和sessionid需要改成自己登录后的cookie中对应的字段！！！！而且脚本需在登录雨课堂状态下使用
# 登录上雨课堂，然后按F12-->选Application-->找到雨课堂的cookies，寻找csrftoken、sessionid、university_id字段，并复制到下面两行即可
csrftoken = "cEdD0CTbSsCNVoSb7CQYOwRGDQxoe7RO"  # 已从你提供的 Cookie 中填入
sessionid = "zaue9n7krucy5dfl12d284vm5togi9vq"  # 已从你提供的 Cookie 中填入
university_id = "2627"  # 已从你提供的 Cookie 中提取（university_id=2627，华工本科生）
url_root = "https://scut.yuketang.cn/"  # 华南理工大学本科生雨课堂域名
learning_rate = 10  # 学习速率：每轮心跳申报前进的秒数。实测 10 可被服务器足额记账（每轮30秒），4 是原始默认值
only_classroom_id = "26776303"  # 只刷这个教室的课（你的形势与政策，跳过选课菜单）；填 "" 则恢复手动选课

# 以下字段不用改，下面的代码也不用改动
user_id = ""

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36',
    'Content-Type': 'application/json',
    'Cookie': 'csrftoken=' + csrftoken + '; sessionid=' + sessionid + '; university_id=' + university_id + '; platform_id=3',
    'x-csrftoken': csrftoken,
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'university-id': university_id,
    'xtbz': 'cloud'
}

# 限流恢复时用到的提交地址，从 __main__ 中提前到这里，避免先使用后定义
submit_url = url_root + "mooc-api/v1/lms/exercise/problem_apply/?term=latest&uv_id=" + university_id + ""

leaf_type = {
    "video": 0,
    "homework": 6,
    "exam": 5,
    "recommend": 3,
    "discussion": 4
}


def one_video_watcher(video_id, video_name, cid, user_id, classroomid, skuid):
    video_id = str(video_id)
    classroomid = str(classroomid)
    url = url_root + "video-log/heartbeat/"
    get_url = url_root + "video-log/get_video_watch_progress/?cid=" + str(
        cid) + "&user_id=" + user_id + "&classroom_id=" + classroomid + "&video_type=video&vtype=rate&video_id=" + str(
        video_id) + "&snapshot=1&term=latest&uv_id=" + university_id + ""
    progress = requests.get(url=get_url, headers=headers)
    if_completed = '0'
    try:
        if_completed = re.search(r'"completed":(.+?),', progress.text).group(1)
    except:
        pass
    if if_completed == '1':
        print(video_name + "已经学习完毕，跳过")
        return 1
    else:
        print(video_name + "，尚未学习，现在开始自动学习")
        time.sleep(2)

    # 默认为0（即还没开始看）
    video_frame = 0
    val = 0
    # 获取实际值（观看时长和完成率）
    try:
        res_rate = json.loads(progress.text)
        tmp_rate = res_rate["data"][video_id]["rate"]
        if tmp_rate is None:
            return 0
        val = tmp_rate
        video_frame = res_rate["data"][video_id]["watch_length"]
    except Exception:
        # 从未看过的视频在进度接口里还没有记录（data 为空），属于正常情况，按 0 进度从头开始刷
        print("还没有观看记录，按 0 进度开始学习")

    t = time.time()
    timstap = int(round(t * 1000))
    heart_data = []
    while float(val) <= 0.95:
        for i in range(3):
            heart_data.append(
                {
                    "i": 5,
                    "et": "loadeddata",
                    "p": "web",
                    "n": "ali-cdn.xuetangx.com",
                    "lob": "cloud4",
                    "cp": video_frame,
                    "fp": 0,
                    "tp": 0,
                    "sp": 2,
                    "ts": str(timstap),
                    "u": int(user_id),
                    "uip": "",
                    "c": cid,
                    "v": int(video_id),
                    "skuid": skuid,
                    "classroomid": classroomid,
                    "cc": video_id,
                    "d": 4976.5,
                    "pg": video_id + "_" + ''.join(random.sample('zyxwvutsrqponmlkjihgfedcba1234567890', 4)),
                    "sq": i + 1,  # 服务器要求 sq >= 1，原版是固定值 2；写成 0 会被判定 Partial data anomaly 而丢弃
                    "t": "video"
                }
            )
            video_frame += learning_rate
        data = {"heart_data": heart_data}
        r = requests.post(url=url, headers=headers, json=data)
        heart_data = []
        # 服务器判定心跳异常时会在响应里返回 anomaly，此时进度会被打回，需从 0 重新开始（移植自原版脚本，本改版此前缺失）
        try:
            error_msg = json.loads(r.text)["message"]
            if "anomaly" in str(error_msg):
                print("收到服务器异常判定(anomaly)，进度被重置，将从 0 重新学习")
                video_frame = 0
                time.sleep(5)
        except Exception:
            pass
        try:
            delay_time = re.search(r'Expected available in(.+?)second.', r.text).group(1).strip()
            print("由于网络阻塞，万恶的雨课堂，要阻塞" + str(delay_time) + "秒")
            time.sleep(float(delay_time) + 0.5)
            print("恢复工作啦～～")
            r = requests.post(url=submit_url, headers=headers, json=data)
        except:
            pass
        try:
            progress = requests.get(url=get_url, headers=headers)
            res_rate = json.loads(progress.text)
            tmp_rate = res_rate["data"][video_id]["rate"]
            if tmp_rate is None:
                return 0
            val = str(tmp_rate)
            print("学习进度为：\t" + str(float(val) * 100) + "%/100%")
            time.sleep(2)
        except Exception:
            # 进度记录尚未生成时忽略，等下一轮心跳后再查
            time.sleep(2)
            pass
    print("视频" + video_id + " " + video_name + "学习完成！")
    return 1


def get_videos_ids(course_name, classroom_id, course_sign):
    get_homework_ids = url_root + "mooc-api/v1/lms/learn/course/chapter?cid=" + str(
        classroom_id) + "&term=latest&uv_id=" + university_id + "&sign=" + course_sign
    homework_ids_response = requests.get(url=get_homework_ids, headers=headers)
    homework_json = json.loads(homework_ids_response.text)
    homework_dic = {}
    try:
        for i in homework_json["data"]["course_chapter"]:
            for j in i["section_leaf_list"]:
                if "leaf_list" in j:
                    for z in j["leaf_list"]:
                        if z['leaf_type'] == leaf_type["video"]:
                            homework_dic[z["id"]] = z["name"]
                else:
                    if j['leaf_type'] == leaf_type["video"]:
                        # homework_ids.append(j["id"])
                        homework_dic[j["id"]] = j["name"]
        print(course_name + "共有" + str(len(homework_dic)) + "个作业喔！")
        return homework_dic
    except:
        print("fail while getting homework_ids!!! please re-run this program!")
        raise Exception("fail while getting homework_ids!!! please re-run this program!")


if __name__ == "__main__":
    your_courses = []

    # 检查必填配置，未填写时给出明确提示，避免跑出难懂的报错
    missing = []
    if not url_root.startswith("http"):
        missing.append("url_root（你学校的雨课堂域名，例如 https://changjiang.yuketang.cn/）")
    if not csrftoken:
        missing.append("csrftoken")
    if not sessionid:
        missing.append("sessionid")
    if not university_id:
        missing.append("university_id")
    if missing:
        print("以下配置还未填写，请先登录雨课堂网页，按 F12 -> Application -> Cookies 复制对应值，再修改 videoHelper.py 顶部的配置：")
        for item in missing:
            print("  - " + item)
        raise SystemExit(1)

    # 首先要获取用户的个人ID，即user_id,该值在查询用户的视频进度时需要使用
    user_id_url = url_root + "edu_admin/check_user_session/"
    id_response = requests.get(url=user_id_url, headers=headers)
    try:
        user_id = re.search(r'"user_id":(.+?)}', id_response.text).group(1).strip()
    except:
        print("也许是网路问题，获取不了user_id,请试着重新运行")
        raise Exception("也许是网路问题，获取不了user_id,请试着重新运行!!! please re-run this program!")

    # 然后要获取教室id
    get_classroom_id = url_root + "mooc-api/v1/lms/user/user-courses/?status=1&page=1&no_page=1&term=latest&uv_id=" + university_id + ""
    classroom_id_response = requests.get(url=get_classroom_id, headers=headers)
    try:
        for ins in json.loads(classroom_id_response.text)["data"]["product_list"]:
            your_courses.append({
                "course_name": ins["course_name"],
                "classroom_id": ins["classroom_id"],
                "course_sign": ins["course_sign"],
                "sku_id": ins["sku_id"],
                "course_id": ins["course_id"]
            })
    except Exception as e:
        print("fail while getting classroom_id!!! please re-run this program!")
        raise Exception("fail while getting classroom_id!!! please re-run this program!")

    # 显示用户提示
    for index, value in enumerate(your_courses):
        print("编号：" + str(index + 1) + " 课名：" + str(value["course_name"]))

    # 配置了 only_classroom_id 时，只刷指定教室的课，跳过手动选课
    if only_classroom_id:
        your_courses = [c for c in your_courses if str(c["classroom_id"]) == str(only_classroom_id)]
        if not your_courses:
            print("没找到 classroom_id=" + str(only_classroom_id) + " 的课程，请检查脚本顶部 only_classroom_id 配置")
            raise SystemExit(1)
        for ins in your_courses:
            homework_dic = get_videos_ids(ins["course_name"], ins["classroom_id"], ins["course_sign"])
            for one_video in homework_dic.items():
                one_video_watcher(one_video[0], one_video[1], ins["course_id"], user_id, ins["classroom_id"],
                                  ins["sku_id"])
        print("搞定啦")
        raise SystemExit(0)

    flag = True
    while(flag):
        number = input("你想刷哪门课呢？请输入编号。输入0表示全部课程都刷一遍\n")
        # 输入不合法则重新输入
        if not (number.isdigit()) or int(number) > len(your_courses):
            print("输入不合法！")
            continue
        elif int(number) == 0:
            flag = False    # 输入合法则不需要循环
            # 0 表示全部刷一遍
            for ins in your_courses:
                homework_dic = get_videos_ids(ins["course_name"], ins["classroom_id"], ins["course_sign"])
                for one_video in homework_dic.items():
                    one_video_watcher(one_video[0], one_video[1], ins["course_id"], user_id, ins["classroom_id"],
                                      ins["sku_id"])
        else:
            flag = False    # 输入合法则不需要循环
            # 指定序号的课程刷一遍
            number = int(number) - 1
            homework_dic = get_videos_ids(your_courses[number]["course_name"], your_courses[number]["classroom_id"],
                                          your_courses[number]["course_sign"])
            for one_video in homework_dic.items():
                one_video_watcher(one_video[0], one_video[1], your_courses[number]["course_id"], user_id,
                                  your_courses[number]["classroom_id"],
                                  your_courses[number]["sku_id"])
        print("搞定啦")
