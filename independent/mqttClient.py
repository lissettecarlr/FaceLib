
import threading
from loguru import logger
import time
import  json
import paho.mqtt.client as mqtt
from dotenv import find_dotenv, load_dotenv
import os
import mqttClient
import requests
import sys
import random
import faceApi
# 使用先创建.env配置文件

class mqttClientFace(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.flag =False
        self.closeFlag = True
        self.taskStatus = ""
        self.netChangeCb = None
        #当前连接状态
        self.connectStatus = False
        load_dotenv(find_dotenv('.env'))
        self.mqttServerName = os.environ.get("MQTT_SERVER_NAME")
        self.mqttServerPassword = os.environ.get("MQTT_SERVER_PASSWORD")
        self.mqttServerIp = os.environ.get("MQTT_SERVER_HOST")
        self.mqttServerPort = int(os.environ.get("MQTT_SERVER_PORT"))
        self.mqttId = os.environ.get("MQTT_ID")
        #图片的下周地址
        self.downloadImgPath = os.path.dirname(os.path.realpath(sys.argv[0])) + '\\faceData'
        self.init()

    def init(self):
        face = mqttClient.mqttClientFace()
        self.client = mqtt.Client(client_id=self.mqttId,clean_session=False)
        
        self.client.on_connect = self.connectCb
        self.client.on_message = self.messageCb
        self.client.on_disconnect = self.disconnectCb
        self.client.on_publish = self.publishCb
        self.client.on_subscribe = self.subscribeCb
        # self.client.on_unsubscribe = self.on_unsubscribe

        #如果MQTT有账号密码
        if(self.mqttServerName != ""):
            self.client.username_pw_set(self.mqttServerName, self.mqttServerPassword)
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)

        logger.info("网络通讯线程初始化结束")

        #初始化识别器
        self.api = faceApi.faceApi()

    def connect(self):
        try:
            self.client.connect(self.mqttServerIp, self.mqttServerPort, 60)  # 60为keepalive的时间间隔
        except:
            #会自动重连
            logger.warning("mqtt连接失败")

    def run(self):
        while 1:
            if(self.flag):
                self.connect()
                self.client.loop_forever()
            if(self.closeFlag == False):
                return True
            time.sleep(10)

    def go(self):
        if(self.flag == False):
            self.flag = True
            logger.info("网络通讯线程启动")

    def suspend(self):
        time.sleep(1)
        self.client.disconnect()
        self.flag = False
        logger.info("网络通讯线程暂停")

    def close(self):
        time.sleep(1)
        self.client.disconnect()
        self.flag = False
        self.closeFlag = False
        logger.info("网络通讯线程退出")

    def getStatus(self):
        temp = self.taskStatus
        self.taskStatus = ""
        return temp

    def getNetStatus(self):
        return self.connectStatus

         
    # 连接回调
    def connectCb(self,client, userdata, flags, rc):
        if(rc == 0):
            logger.info("MQTT连接建立")
            self.connectStatus = True
            if(self.netChangeCb):
                self.netChangeCb(self.connectStatus)
            self.client.subscribe([("faceRecognition/"+self.mqttId+"/addFace", 0), ("faceRecognition/"+self.mqttId+"/updateFaceLib", 0),("faceRecognition/"+self.mqttId+"/rec", 0)])
        else:
            # 1协议版本不正确  2客户端标识符无效 3服务器不可用 4用户名或密码错误 5未授权
            logger.info("MQTT连接被拒绝 {}".format(rc))
            
        #print("Connected with result code: " + str(rc))

    #连接断开回调 rc参数表示断开状态
    def disconnectCb(self,client, userdata, rc):
        logger.info("MQTT连接断开")
        self.connectStatus = False
        if(self.netChangeCb):
            self.netChangeCb(self.connectStatus)
        #print("Disconnected with result code "+str(rc))

    def messageCb(self,client, userdata, message):
        if(message.topic.find("addFace") != -1):
            logger.debug("任务：添加一张人脸图")
            try:
                resp = json.loads(message.payload.decode('utf-8'))
            except:
                logger.warning("格式错误")
                self.publishNormalAck(msgId,"json error")
                return False
            try:
                img = resp["img"]
                name = resp["name"]
                msgId = resp["msgId"]
            except:
                logger.warning("字段错误")
                self.publishNormalAck(msgId,"msg error")
                return False
            #首先下载图片，然后将图片加入的预备区    
            if(self.download(img,self.downloadImgPath,name) == False):
                self.publishNormalAck(msgId,"download error")
            
            #然后将图片按照对应名称放
            self.api.input_new_face(name,self.downloadImgPath+"\\"+name)
            self.publishNormalAck(msgId,"succeed")

        elif(message.topic.find("updateFaceLib") != -1):
            logger.info("任务：更新识别库")
            try:
                resp = json.loads(message.payload.decode('utf-8'))
            except:
                self.publishNormalAck(msgId,"json error")
                logger.warning("格式错误")
                return False
            try:
                msgId = resp["msgId"]
            except:
                logger.warning("字段错误")
                self.publishNormalAck(msgId,"msg error")
                return False
            self.api.update_facebank()
            self.publishNormalAck(msgId,"succeed")

        elif(message.topic.find("rct") != -1):
            logger.info("任务：识别")
            try:
                resp = json.loads(message.payload.decode('utf-8'))
            except:
                self.publishNormalAck(msgId,"json error")
                logger.warning("格式错误")
                return False
            try:
                img = resp["img"]
                msgId = resp["msgId"]
            except:
                self.publishNormalAck(msgId,"msg error")
                logger.warning("字段错误")
                return False      

            inferImgPath = os.path.dirname(os.path.realpath(sys.argv[0])) + '\\out'
            if(self.download(img,inferImgPath,msgId) == False):
                self.publishNormalAck(msgId,"download error")
                return False
            
            res = self.api.infer(inferImgPath + "\\" + msgId , inferImgPath + "\\" + msgId + "-infer")
            if(res == None):
                self.publishNormalAck(msgId,"infer error")
            else:
                #上传图片
                imgBed = ""
                with open(inferImgPath + "\\" + msgId , inferImgPath + "\\" + msgId + "-infer", "rb")as f_abs:# 以2进制方式打开图片
                    body = {'camera_code': (None, "识别"),'image_face': (msgId, f_abs, 'image/jpeg')}
                    response = requests.post(url=imgBed, files=body).json
                    resImg = json.loads(response.text).get('data').get('url')
                self.publishRecognitionAck(msgId,resImg,res)

        else:
            logger.warning("warning","Received message '" + str(message.payload) + "' on topic '"
            + message.topic + "' with QoS " + str(message.qos))
            self.publishNormalAck(msgId,"topic error")
 
    #消息发送成功后的回调
    #对于Qos级别为1和2的消息，这意味着已经完成了与代理的握手。
    #对于Qos级别为0的消息，这只意味着消息离开了客户端。
    #mid变量与从相应的publish()返回的mid变量匹配
    def publishCb(self,client, userdata, mid):
        pass
        #print("mid: "+str(mid))

    # 识别结果应答 
    def publishRecognitionAck(self,msgId,url,res):
        aItem = {}
        aItem["msgId"] = msgId
        aItem["url"] = url
        aItem["res"] = res
        ackJson = json.dumps(aItem, ensure_ascii=False)
        if(self.connectStatus == True):
            self.client.publish("faceRecognition/"+self.mqttId+"/recAck",ackJson)
            return True
        return False


    #通用应答
    def publishNormalAck(self,msgId,result):
        if(self.connectStatus == True):
            self.client.publish("faceRecognition/"+self.mqttId+"/ack", json.dumps({"msgId":msgId,"result":result}))
            return True
        return False


    def setCallback(self,netChange=None):
        self.netChangeCb = netChange


    #订阅主题后的回调
    #mid变量匹配从相应的subscri be()返回的mid变量
    def subscribeCb(self,client, userdata, mid, granted_qos):
        logger.debug("Subscribed: {} , {}".format(str(mid),str(granted_qos)))
        


    def download(self, downloadURL,downloadPath, name):
        """ 进行下载请求 """
        try:
            headers = {'content-type': "application/octet-stream",}
            response = requests.post(downloadURL,headers = headers,timeout=10)
            with open(downloadPath + name , "wb") as code:
                code.write(response.content)
                code.close()
                logger.info("下载完成{}".format(name))
                return True
        except:
            logger.warning("下载请求失败")
            return False
        
import keyboard

def publishRecognitionAck(msgId,url,res):
    aItem = {}
    aItem["msgId"] = msgId
    aItem["url"] = url
    aItem["res"] = res
    ackJson = json.dumps(aItem, ensure_ascii=False)
    print(ackJson)

def main():
    face = mqttClientFace()
    face.start()
    face.go()
    try:
        while(1):
            if keyboard.is_pressed('q'): 
                face.close()
                break
            time.sleep(5)
    except:
        face.close()


if __name__ == "__main__":
        main()
